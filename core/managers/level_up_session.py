# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Level-up as tables + engine + one conversation (L1).

The SRD tables (core/leveling/tables.py) settle everything that is not a choice;
the engine (core/nql/leveling.py) applies the growth; ONE model callsite, T121,
talks to the player about the choices the level actually opens and nothing else.
Code validates every choice against the tables and the spell repository, so
there is no model validator and no specialist round. A player who says "you
decide" gets fitting defaults in one turn; a player who steers gets one turn
per exchange. Companions run the same agent once with no questions.

Public surface is the one main.py drives: start(), handle_input(text),
is_complete, success, summary, conversation, commit_guard.
"""
import copy
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from core.ai import api_client
from core.leveling import tables
from core.managers.level_up_manager import LevelUpTurn, _level_up_commit_guard
from core.nql import leveling as nql_leveling
from utils.capture.live_provider_call import get_live_turn_scope
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import debug, error, info
from utils.file_operations import safe_read_json
from utils.module_path_manager import ModulePathManager

register_callsite("T121", "core/managers/level_up_session.py", 0)

_PROMPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "prompts", "leveling", "level_up_agent.txt")
_MAX_CORRECTIONS_PER_TURN = 2


def _spell_index() -> Dict[str, Dict[str, Any]]:
    path = os.path.join(os.path.dirname(_PROMPT), "..", "..", "data", "spell_repository.json")
    data = safe_read_json(os.path.normpath(path)) or {}
    out: Dict[str, Dict[str, Any]] = {}
    for key, entry in data.items():
        if key == "_metadata" or not isinstance(entry, dict) or not entry.get("name"):
            continue
        out[str(entry["name"]).strip().lower()] = entry
        for alias in entry.get("aliases") or []:
            out[str(alias).strip().lower()] = entry
    return out


class LevelUpSession:
    def __init__(self, character_name, current_level, new_level, *, accepted_history=None, player_input=None):
        self.character_name = character_name
        self.current_level = current_level
        self.requested_level = new_level
        self.conversation: List[Dict[str, str]] = []
        self.is_complete = False
        self.success = False
        self.summary = ""
        self._entry_input = player_input
        self._accepted_history = accepted_history or []
        self._scope = None
        self._sheet: Optional[Dict[str, Any]] = None
        self._path: Optional[str] = None
        self._settled: Optional[tables.Settled] = None
        self._choices: Dict[str, Any] = {}
        self._features_text: Dict[str, str] = {}
        self._spells = _spell_index()
        self._last_turn: Optional[LevelUpTurn] = None
        self.is_player = False

    # ---- surface -------------------------------------------------------------
    def commit_guard(self):
        return _level_up_commit_guard(self._scope)

    def start(self) -> LevelUpTurn:
        self._scope = get_live_turn_scope()
        module_name = str((safe_read_json("party_tracker.json") or {}).get("module", "")).replace(" ", "_")
        from updates.update_character_info import normalize_character_name

        self._path = ModulePathManager(module_name).get_character_path(normalize_character_name(self.character_name))
        self._sheet = safe_read_json(self._path)
        if not self._sheet:
            return self._terminal("not_applied", f"Your level-up has not been applied: no sheet for {self.character_name}.")
        self.is_player = self._sheet.get("character_type") == "player"
        check = tables.eligibility(self._sheet, self.requested_level)
        if not check.ok:
            return self._terminal("not_applied", f"Your level-up has not been applied: {check.reason}.")
        self._settled = tables.settle(self._sheet, check.new_level)
        opening = self._entry_input if isinstance(self._entry_input, str) and self._entry_input.strip() else None
        if opening:
            self.conversation.append({"role": "user", "content": opening})
        return self._turn()

    def handle_input(self, user_input) -> LevelUpTurn:
        self.conversation.append({"role": "user", "content": str(user_input)})
        return self._turn()

    # ---- one agent turn ---------------------------------------------------------
    def _turn(self) -> LevelUpTurn:
        corrections: List[str] = []
        for _ in range(_MAX_CORRECTIONS_PER_TURN + 1):
            with self.commit_guard():
                pass
            answer = self._ask_agent(corrections)
            if answer is None:
                return self._interview("I could not reach the level-up rules just now. Say 'retry' to try again.")
            problems = self._take_choices(answer.get("choices") or {})
            for name, text in (answer.get("features") or {}).items():
                if isinstance(text, str) and text.strip():
                    self._features_text[str(name)] = text.strip()
            narration = str(answer.get("narration") or "").strip()
            if problems:
                corrections = problems
                continue
            if answer.get("done") is True and self._all_settled():
                return self._commit(narration)
            missing = [c["id"] for c in self._settled.choice_points if c["id"] not in self._choices]
            if answer.get("done") is True and missing:
                corrections = [f"not done: these choices are still open: {', '.join(missing)}"]
                continue
            return self._interview(narration or "What would you like to do?")
        return self._interview("I could not settle your choices from that; tell me plainly what you pick, "
                               "or say 'you decide' and I will choose for you.")

    def _ask_agent(self, corrections: List[str]) -> Optional[Dict[str, Any]]:
        from model_config import MODEL_PROVIDER, resolve_callsite_config

        with open(_PROMPT, "r", encoding="utf-8") as handle:
            system = handle.read()
        messages = [{"role": "system", "content": system},
                    {"role": "system", "content": "LEVEL-UP PACKET\n" + json.dumps(self._packet(), ensure_ascii=True)}]
        messages.extend(self.conversation[-12:])
        if corrections:
            messages.append({"role": "system", "content": "The rules refused part of your last answer: "
                             + "; ".join(corrections) + ". Answer again with valid choices."})
        cfg = resolve_callsite_config("T121", MODEL_PROVIDER, 0)
        try:
            response = capture_and_fanout(
                "T121", api_client.create_completion, _live_selected="required", _detached_scope=self._scope,
                _request_provider=MODEL_PROVIDER, messages=messages, model=cfg["model"], temperature=0.7,
                response_format={"type": "json_object"},
                **{k: v for k, v in cfg.items() if k != "model"})
            raw = response.choices[0].message.content
        except Exception as exc:  # transport already reissued; a completed failure ends this turn
            error(f"LEVEL-UP: agent call failed: {exc}", category="level_up")
            return None
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            debug(f"LEVEL-UP: agent answer was not JSON: {str(raw)[:200]}", category="level_up")
            return {"narration": "", "choices": {}, "done": False}
        self.conversation.append({"role": "assistant", "content": json.dumps({"narration": parsed.get("narration", ""), "actions": []})})
        return parsed if isinstance(parsed, dict) else {}

    # ---- packet ------------------------------------------------------------------
    def _packet(self) -> Dict[str, Any]:
        s, sheet = self._settled, self._sheet
        casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else {}
        points = []
        for point in s.choice_points:
            p = {k: v for k, v in point.items() if k != "source"}
            if point.get("source"):
                p["options"] = self._spell_options(point)
            if point["id"] in self._choices:
                p["settled"] = self._choices[point["id"]]
            points.append(p)
        return {
            "mode": "player" if self.is_player else "companion",
            "character": {
                "name": sheet.get("name"), "class": sheet.get("class"), "subclass": sheet.get("subclass"),
                "race": sheet.get("race"), "level": s.new_level - 1, "new_level": s.new_level,
                "abilities": sheet.get("abilities"), "feats": sheet.get("feats"),
                "features": [f.get("name") for f in sheet.get("classFeatures") or [] if isinstance(f, dict)],
                "cantrips": (casting.get("spells") or {}).get("cantrips"),
                "prepared_spells": casting.get("preparedSpells"),
                "known_spells": {k: v for k, v in (casting.get("spells") or {}).items() if k != "cantrips"},
            },
            "settled_by_the_rules": {
                "proficiency_bonus": s.proficiency_bonus, "hit_die": f"d{s.hit_die}", "fixed_hp_gain": s.hp_gain_fixed,
                "new_features": s.features, "spell_slots_max": {k: v for k, v in s.slot_targets.items() if v},
                "pools": {k: v[0] for k, v in s.pools.items()}, "cantrips_known": s.spell_counts["cantrips"],
                "prepared_spells": s.spell_counts["prepared"],
            },
            "choice_points": points,
        }

    def _spell_options(self, point: Dict[str, Any]) -> List[str]:
        cls = self._settled.cls
        if point["kind"] == "cantrips":
            level_ok = lambda lvl: lvl == 0
        else:
            top = max([int(k[5:]) for k, v in self._settled.slot_targets.items() if v] or [0])
            level_ok = lambda lvl: 1 <= lvl <= top
        seen = set()
        out = []
        for entry in self._spells.values():
            name = entry.get("name")
            if name in seen or not level_ok(int(entry.get("level", -1))):
                continue
            if cls.capitalize() not in (entry.get("classes") or []):
                continue
            seen.add(name)
            out.append(f"{name} ({entry.get('level')})")
        return sorted(out)

    # ---- validation ----------------------------------------------------------------
    def _take_choices(self, choices: Dict[str, Any]) -> List[str]:
        problems: List[str] = []
        by_id = {c["id"]: c for c in self._settled.choice_points}
        for cid, value in choices.items():
            point = by_id.get(cid)
            if point is None:
                problems.append(f"{cid!r} is not a choice this level opens")
                continue
            ok, why = self._check_choice(point, value)
            if ok:
                self._choices[cid] = value
            else:
                problems.append(f"{cid}: {why}")
        return problems

    def _check_choice(self, point: Dict[str, Any], value: Any) -> Tuple[bool, str]:
        kind = point["kind"]
        cls = self._settled.cls
        if kind == "hit_points":
            if not isinstance(value, dict) or value.get("method") not in ("fixed", "roll"):
                return False, "hit_points must be {method: fixed} or {method: roll, roll: N}"
            if value["method"] == "roll":
                try:
                    tables.hp_gain(self._sheet, cls, "roll", value.get("roll"))
                except ValueError as exc:
                    return False, str(exc)
            return True, ""
        if kind == "asi_or_feat":
            if isinstance(value, dict) and isinstance(value.get("asi"), dict):
                _, why = tables.apply_asi(dict(self._sheet.get("abilities") or {}), value["asi"])
                return (False, why) if why else (True, "")
            if isinstance(value, dict) and isinstance(value.get("feat"), str) and value["feat"].strip():
                return True, ""
            return False, "ability_score_improvement must be {asi: {ability: +n}} or {feat: name}"
        if kind in ("subclass", "epic_boon"):
            if not isinstance(value, str) or not value.strip():
                return False, f"{kind} must be a name"
            if point.get("options") and value not in point["options"]:
                return False, f"{value!r} is not one of {point['options']}"
            return True, ""
        if kind in ("cantrips", "prepared_spells"):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False, f"{kind} must be a list of spell names"
            names = [v.strip() for v in value]
            if len(set(n.lower() for n in names)) != len(names):
                return False, "a spell is listed twice"
            if len(names) > int(point["count"]):
                return False, f"at most {point['count']} spells"
            top = max([int(k[5:]) for k, v in self._settled.slot_targets.items() if v] or [0])
            for name in names:
                entry = self._spells.get(name.lower())
                if entry is None:
                    return False, f"{name!r} is not an SRD spell"
                if cls.capitalize() not in (entry.get("classes") or []):
                    return False, f"{name!r} is not a {cls} spell"
                lvl = int(entry.get("level", -1))
                if kind == "cantrips" and lvl != 0:
                    return False, f"{name!r} is not a cantrip"
                if kind == "prepared_spells" and not 1 <= lvl <= top:
                    return False, f"{name!r} is level {lvl}; you can prepare up to level {top}"
            return True, ""
        return False, f"unknown choice kind {kind!r}"

    def _all_settled(self) -> bool:
        return all(c["id"] in self._choices for c in self._settled.choice_points)

    # ---- commit ------------------------------------------------------------------
    def _commit(self, narration: str) -> LevelUpTurn:
        from updates.update_character_info import (
            _get_character_update_lock, commit_character_sheet, prepare_character_delta, repair_character_data)
        from utils.path_transaction_lock import path_transaction_lock

        s, sheet = self._settled, self._sheet
        cls = s.cls
        # 1. numbers from the tables
        hp_choice = self._choices.get("hit_points") or {"method": "fixed"}
        gain, how = tables.hp_gain(sheet, cls, hp_choice.get("method", "fixed"), hp_choice.get("roll"))
        abilities = dict(sheet.get("abilities") or {})
        asi = self._choices.get("ability_score_improvement")
        feats = list(sheet.get("feats") or [])
        if isinstance(asi, dict) and isinstance(asi.get("asi"), dict):
            abilities, _ = tables.apply_asi(abilities, asi["asi"])
        elif isinstance(asi, dict) and asi.get("feat"):
            feats.append({"name": asi["feat"], "description": self._features_text.get(asi["feat"], ""),
                          "source": f"{sheet.get('class')} level {s.new_level}"})
        changes: Dict[str, Any] = {"level": s.new_level, "abilities": abilities,
                                   "exp_required_for_next_level": s.exp_required_for_next_level}
        changes.update(tables.derived_numbers(sheet, s.new_level, abilities))
        if feats != (sheet.get("feats") or []):
            changes["feats"] = feats
        if self._choices.get("subclass"):
            changes["subclass"] = self._choices["subclass"]
        # 2. features: new ones with the agent's text, pools resized from the table
        existing = {f.get("name"): f for f in sheet.get("classFeatures") or [] if isinstance(f, dict)}
        # A pool's feature may carry a suffix on the sheet ("Channel Divinity (2/rest)"):
        # match on the name before any parenthesis, case-insensitively.
        def stored_name(name):
            key = str(name).split("(")[0].strip().lower()
            for stored in existing:
                if str(stored).split("(")[0].strip().lower() == key:
                    return stored
            return None
        feature_updates: List[Dict[str, Any]] = []
        for name in s.features:
            if stored_name(name) or name in ("Ability Score Improvement", "Subclass feature"):
                continue
            entry = {"name": name, "description": self._features_text.get(name, f"{name} (gained at level {s.new_level})."),
                     "source": f"{sheet.get('class')} level {s.new_level}"}
            if name in s.pools:
                entry["usage"] = {"current": s.pools[name][0], "max": s.pools[name][0], "refreshOn": s.pools[name][1]}
            feature_updates.append(entry)
        for name, (size, refresh) in s.pools.items():
            feature = existing.get(stored_name(name))
            if feature is None:
                continue
            name = feature.get("name")
            usage = feature.get("usage") if isinstance(feature.get("usage"), dict) else {"current": size, "refreshOn": refresh}
            if usage.get("max") != size:
                grown = size - (usage.get("max") if type(usage.get("max")) is int else 0)
                feature_updates.append({"name": name, "usage": {"current": min(size, (usage.get("current") or 0) + max(0, grown)),
                                                                 "max": size, "refreshOn": usage.get("refreshOn", refresh)}})
        if feature_updates:
            changes["classFeatures"] = feature_updates
        # 3. spells
        casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else None
        if casting:
            spell_changes: Dict[str, Any] = {}
            if "spellSaveDC" in changes:
                spell_changes["spellSaveDC"] = changes.pop("spellSaveDC")
                spell_changes["spellAttackBonus"] = changes.pop("spellAttackBonus")
            if isinstance(self._choices.get("prepared_spells"), list):
                spell_changes["preparedSpells"] = list(self._choices["prepared_spells"])
            if isinstance(self._choices.get("cantrips"), list):
                spells = copy.deepcopy(casting.get("spells") or {})
                known = list(spells.get("cantrips") or [])
                for name in self._choices["cantrips"]:
                    if name not in known:
                        known.append(name)
                spells["cantrips"] = known
                spell_changes["spells"] = spells
            if spell_changes:
                changes["spellcasting"] = spell_changes
        else:
            changes.pop("spellSaveDC", None)
            changes.pop("spellAttackBonus", None)
        # 4. prepare (typed totals, level-up path), then engine growth, then commit atomically
        from updates.update_character_info import load_schema  # noqa: WPS433
        schema = load_schema()
        role = "player" if self.is_player else "npc"
        with self.commit_guard():
            pass
        _, prepared, checks = prepare_character_delta(repair_character_data(copy.deepcopy(sheet)), changes, role,
                                                      schema, self.character_name)
        if not checks.get("schema_valid"):
            return self._interview(f"Your level-up has not been applied: {checks.get('error_message')}. Say 'retry'.")
        growth = nql_leveling.grow(prepared, gain, s.slot_targets)
        if not growth.ok:
            return self._interview(f"Your level-up has not been applied: {growth.reason}. Say 'retry'.")
        after = growth.sheet
        with _get_character_update_lock(os.path.basename(self._path)[:-5]), \
                path_transaction_lock(self._path, suffix=".effects.lock", timeout_seconds=30.0) as lease:
            if lease is None:
                return self._interview("Your sheet is busy; say 'retry' in a moment.")
            from updates.update_character_info import create_character_backup
            create_character_backup(self._path)
            commit_character_sheet(self._path, after, commit_guard=self.commit_guard, expected_before=sheet)
        info(f"LEVEL-UP: {self.character_name} -> level {s.new_level} ({how}); engine ops {growth.operations}",
             category="level_up")
        summary = self._summary(after, how)
        text = (narration + " " if narration else "") + summary
        return self._terminal("complete", text)

    def _summary(self, after: Dict[str, Any], how: str) -> str:
        s = self._settled
        bits = [f"{self.character_name} is now level {s.new_level}.",
                f"Hit points {after['hitPoints']}/{after['maxHitPoints']} ({how}).",
                f"Proficiency bonus +{s.proficiency_bonus}."]
        slots = {k: v for k, v in s.slot_targets.items() if v}
        if slots:
            bits.append("Spell slots " + ", ".join(f"{k[5:]}: {v}" for k, v in slots.items()) + ".")
        new = [f for f in s.features if f not in ("Ability Score Improvement", "Subclass feature")]
        if new:
            bits.append("Gained: " + ", ".join(new) + ".")
        for cid, value in self._choices.items():
            if cid != "hit_points":
                bits.append(f"{cid.replace('_', ' ')}: {json.dumps(value, ensure_ascii=True)}.")
        return " ".join(bits)

    # ---- turns ---------------------------------------------------------------------
    def _interview(self, narration: str) -> LevelUpTurn:
        self._last_turn = LevelUpTurn("interview", narration)
        return self._last_turn

    def _terminal(self, kind: str, narration: str) -> LevelUpTurn:
        self.is_complete = True
        self.success = kind == "complete"
        self.summary = f"Level Up: {narration}" if self.success else narration
        self._last_turn = LevelUpTurn(kind, narration)
        return self._last_turn
