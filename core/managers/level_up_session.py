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
from utils.capture.live_provider_call import LiveProviderCompletedError, get_live_turn_scope
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import debug, error, info, warning
from utils.provider_errors import account_refusal_message, classify_provider_error
from utils.file_operations import safe_read_json
from utils.module_path_manager import ModulePathManager

register_callsite("T121", "core/managers/level_up_session.py", 0)

_PROMPT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "prompts", "leveling", "level_up_agent.txt")
_MAX_CORRECTIONS_PER_TURN = 2
_MAX_AGENT_FAILURES = 3


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


def _species_changes(sheet: Dict[str, Any], changes: Dict[str, Any],
                     grants: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    """The sheet changes for gained species grants (#1292). A spell joins its level's list (and the
    prepared list when the sheet keeps one); a racialTraits entry records its ability and its free
    cast. A trait joins racialTraits with its text. The per-spell ability and the use count are text:
    no char_schema field holds them (NEQ-SCHEMA-01). A sheet with no spellcasting block gets no spell."""
    out: Dict[str, Any] = {}
    names: List[str] = []
    traits = list(sheet.get("racialTraits") or [])
    known = {t.get("name") for t in traits if isinstance(t, dict)}
    stored = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else None
    casting = copy.deepcopy(changes.get("spellcasting") or {})
    lists = copy.deepcopy(casting.get("spells") or (stored or {}).get("spells") or {})
    prepared = casting.get("preparedSpells", (stored or {}).get("preparedSpells"))
    for grant in grants:
        if grant["kind"] == "spell":
            if stored is None:
                warning(f"LEVEL-UP: species spell {grant['name']} not added: the sheet has no spellcasting block",
                        category="level_up")
                continue
            slot = "level%d" % grant["level"]
            if grant["name"] not in (lists.get(slot) or []):
                lists[slot] = list(lists.get(slot) or []) + [grant["name"]]
            if isinstance(prepared, list) and grant["name"] not in prepared:
                prepared = list(prepared) + [grant["name"]]
            entry = {"name": "%s (%s)" % (grant["name"], grant["source"]),
                     "description": ("Always prepared. Cast it once without a spell slot and regain that use when "
                                     "you finish a Long Rest; it can also be cast with spell slots of its level. "
                                     "Spellcasting ability: %s." % (grant.get("ability") or "not recorded")),
                     "source": grant["source"]}
        else:
            entry = {"name": grant["name"], "description": grant.get("text") or "", "source": grant["source"]}
        if entry["name"] not in known:
            traits.append(entry)
            known.add(entry["name"])
            names.append(entry["name"])
    if names:
        out["racialTraits"] = traits
    if stored is not None and lists != (stored.get("spells") or {}):
        casting["spells"] = lists
        if isinstance(prepared, list):
            casting["preparedSpells"] = prepared
        out["spellcasting"] = casting
    return out, names


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
        self._loaded: Optional[Dict[str, Any]] = None  # the sheet as read; the commit expects it on disk
        self._path: Optional[str] = None
        self._settled: Optional[tables.Settled] = None
        self._choices: Dict[str, Any] = {}
        self._features_text: Dict[str, str] = {}
        self._spells = _spell_index()
        self._last_turn: Optional[LevelUpTurn] = None
        self.is_player = False
        self._failures = 0
        self._refusal_text = None  # #442: an account refusal's line ends the session
        self._committed = False

    # ---- surface -------------------------------------------------------------
    def commit_guard(self):
        return _level_up_commit_guard(self._scope)

    def start(self) -> LevelUpTurn:
        return self._guarded(self._start)

    def handle_input(self, user_input) -> LevelUpTurn:
        return self._guarded(lambda: self._handle_input(user_input))

    def _guarded(self, step) -> LevelUpTurn:
        """One level-up step. An unexpected error ends this level-up as a narrated
        line instead of ending the game loop (#539); supersession and a read-only
        save stop go through as before (#654)."""
        from core.combat.invocation import InvocationSupersededError
        from utils.capture.live_provider_call import LiveProviderSuperseded
        from utils.transient_filesystem import ReadOnlySaveStop
        try:
            return step()
        except (LiveProviderSuperseded, InvocationSupersededError, ReadOnlySaveStop):
            raise
        except Exception as exc:
            error(f"LEVEL-UP: {self.character_name} step failed: {exc}", exception=exc, category="level_up")
            if self._committed:
                return self._terminal("complete", f"{self.character_name} is now level "
                                      f"{self._settled.new_level}; the summary could not be built.")
            return self._terminal("not_applied", "Your level-up has not been applied: the rules could not "
                                  f"read part of {self.character_name}'s sheet. Nothing changed; the game "
                                  "goes on, and the level-up can be asked for again.")

    def _start(self) -> LevelUpTurn:
        self._scope = get_live_turn_scope()
        module_name = str((safe_read_json("party_tracker.json") or {}).get("module", "")).replace(" ", "_")
        from updates.update_character_info import normalize_character_name

        self._path = ModulePathManager(module_name).get_character_path(normalize_character_name(self.character_name))
        self._sheet = safe_read_json(self._path)
        if not self._sheet:
            return self._terminal("not_applied", f"Your level-up has not been applied: no sheet for {self.character_name}.")
        # The sheet as loaded is what the commit expects on disk. A legacy feature
        # name the SRD tables miss is named once by T125 (typed srd_name) before
        # the level is settled; the names ride in this level-up's commit (V4).
        self._loaded = self._sheet
        from core.leveling import feature_names
        named = feature_names.name_features(self._sheet, scope=self._scope,
                                            live_selected="advisory" if self._scope is not None else None)
        if named.error:
            return self._terminal("not_applied", "Your level-up has not been applied: the rules could not read "
                                  f"{self.character_name}'s older feature names. Nothing changed; ask to level up "
                                  "again later.")
        self._sheet = named.sheet
        self.is_player = self._sheet.get("character_type") == "player"
        check = tables.eligibility(self._sheet, self.requested_level)
        if not check.ok:
            return self._terminal("not_applied", f"Your level-up has not been applied: {check.reason}.")
        self._settled = tables.settle(self._sheet, check.new_level)
        opening = self._entry_input if isinstance(self._entry_input, str) and self._entry_input.strip() else None
        if opening:
            self.conversation.append({"role": "user", "content": opening})
        return self._turn()

    def _handle_input(self, user_input) -> LevelUpTurn:
        self.conversation.append({"role": "user", "content": str(user_input)})
        return self._turn()

    # ---- one agent turn ---------------------------------------------------------
    def _turn(self) -> LevelUpTurn:
        corrections: List[str] = []
        for _ in range(_MAX_CORRECTIONS_PER_TURN + 1):
            with self.commit_guard():
                pass
            answer = self._ask_agent(corrections)
            if answer is None and self._refusal_text:
                # #442: retrying cannot help an account refusal.
                return self._terminal("not_applied", self._refusal_text)
            if answer is None:
                self._failures += 1
                if self._failures >= _MAX_AGENT_FAILURES:
                    return self._terminal("not_applied", "Your level-up has not been applied: the level-up guide could "
                                          "not be reached. Nothing changed; ask to level up again later.")
                return self._interview("I could not reach the level-up rules just now. Say 'retry' to try again.")
            self._failures = 0
            if answer.get("abort") is True:
                return self._terminal("not_applied", (str(answer.get("narration") or "").strip() or
                                      "Understood, we will leave the level-up for later.") +
                                      " Your level-up has not been applied; nothing on your sheet changed.")
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
            if isinstance(exc, LiveProviderCompletedError):
                refusal = classify_provider_error(exc)
                self._refusal_text = account_refusal_message(refusal["category"], refusal["provider"], "turn")
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
                "name": sheet.get("name"), "class": sheet.get("class"), "subclass": s.subclass,
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
                "pools": {k: v.max for k, v in s.pools.items()}, "cantrips_known": s.spell_counts["cantrips"],
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
        if kind in ("asi_or_feat", "epic_boon", "subclass", "fighting_style", "expertise", "skill", "other_named"):
            from core.leveling import choices as srd_choices

            return srd_choices.check_pick(point, value, self._sheet, cls, self._settled.new_level)
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
        abilities = dict(sheet.get("abilities") or {})
        feats = list(sheet.get("feats") or [])
        extra_features: List[Dict[str, Any]] = []
        skill_times: Dict[str, int] = {}
        by_id = {c["id"]: c for c in s.choice_points}
        for cid, value in self._choices.items():
            point = by_id.get(cid) or {}
            kind = point.get("kind")
            if kind in ("asi_or_feat", "epic_boon"):
                from core.leveling import choices as srd_choices
                name = value.get("feat") if isinstance(value, dict) else value
                increases = value.get("asi") if isinstance(value, dict) else None
                rule = srd_choices.feat_rule(name) if name else None
                if isinstance(increases, dict) and not name:
                    abilities, _ = tables.apply_asi(abilities, increases)
                elif rule is not None:
                    # #424: the increase the feat declares (Grappler, an Epic Boon, an ASI named as a feat)
                    abilities, _ = srd_choices.apply_feat_increase(abilities, rule, increases, name)
                if name and name != "Ability Score Improvement":
                    feats.append({"name": name, "description": self._features_text.get(name, ""),
                                  "source": f"{sheet.get('class')} level {s.new_level}"})
                    # #891: a feat with its own use (Magic Initiate) starts full.
                    from core.nql.resources import add_feat_usage as _add_feat_usage
                    _add_feat_usage({"feats": feats[-1:]})
            elif kind == "fighting_style":
                for name in (value if isinstance(value, list) else [value]):
                    extra_features.append({"name": f"Fighting Style: {name}",
                                           "description": self._features_text.get(name, self._features_text.get(f"Fighting Style: {name}", "")),
                                           "source": f"{sheet.get('class')} level {s.new_level}"})
            elif kind == "expertise":
                for name in (value if isinstance(value, list) else [value]):
                    skill_times[str(name).lower().replace(" ", "_")] = 2
            elif kind == "skill":
                for name in (value if isinstance(value, list) else [value]):
                    skill_times.setdefault(str(name).lower().replace(" ", "_"), 1)
            elif kind == "other_named":
                picks = value if isinstance(value, list) else [value]
                label = str(point.get("feature") or point.get("name"))
                extra_features.append({"name": f"{label}: {', '.join(picks)}" if picks else label,
                                       "description": self._features_text.get(label, "") or f"Chosen: {', '.join(picks)}.",
                                       "source": f"{sheet.get('class')} level {s.new_level}"})
        # #1045: this level's gain uses the Constitution after this level's increase,
        # and a higher modifier adds the difference for every earlier level.
        gain, how = tables.hp_gain(dict(sheet, abilities=abilities), cls, hp_choice.get("method", "fixed"),
                                   hp_choice.get("roll"))
        earlier = tables.con_increase_hp(sheet.get("abilities"), abilities, s.new_level - 1)
        if earlier:
            gain += earlier
            how += f" + {earlier} Constitution increase (levels 1-{s.new_level - 1})"
        changes: Dict[str, Any] = {"level": s.new_level, "abilities": abilities,
                                   "exp_required_for_next_level": s.exp_required_for_next_level}
        # Facts only: level, scores, and which skills carry proficiency or
        # expertise. The engine derives the totals when the growth is applied
        # (core/nql/leveling -> core/nql/stats).
        if skill_times:
            from core.nql import stats as nql_stats
            skills = sheet.get("skills")
            listed = isinstance(skills, list)
            # A list names the proficient skills and is written back whole (the
            # merge replaces it), so it keeps every stored name (#769).
            skills = list(skills) if listed else dict(skills) if isinstance(skills, dict) else {}
            expertise = list(sheet.get(nql_stats.EXPERTISE_FIELD) or [])
            for key, times in skill_times.items():
                stored = next((k for k in skills if nql_stats.skill_id(k) == nql_stats.skill_id(key)), None)
                if stored is None:
                    if listed:
                        skills.append(nql_stats._display(nql_stats.skill_id(key) or key))
                    else:
                        skills[key] = 0  # a new proficiency; the engine writes the bonus
                if times == 2:
                    display = nql_stats._display(nql_stats.skill_id(key) or key)
                    if display not in expertise:
                        expertise.append(display)
            if not listed or skills != sheet.get("skills"):
                changes["skills"] = skills
            if expertise != list(sheet.get(nql_stats.EXPERTISE_FIELD) or []):
                changes[nql_stats.EXPERTISE_FIELD] = expertise
        if feats != (sheet.get("feats") or []):
            changes["feats"] = feats
        chosen_subclass = self._choices.get("subclass") or s.subclass
        if chosen_subclass and chosen_subclass != sheet.get("subclass"):
            changes["subclass"] = chosen_subclass
        if self._choices.get("subclass"):
            # the chosen subclass's features at this level join the gained list
            s.features = tables.features_for(cls, chosen_subclass, s.new_level)
        # #858: the typed per-level hit point bonuses (species trait, subclass feature)
        # from the SRD hp_bonuses table, after the hit die minimum.
        from core.leveling.creation_picks import creation_picks
        picks = creation_picks(self._path)
        for bonus_name, amount in tables.hp_bonuses_gained(sheet, cls, chosen_subclass, s.new_level, picks):
            gain += amount
            how += f" + {amount} {bonus_name}"
        # 2. features: new ones with the agent's text, pools resized from the table.
        # A pool's maximum can follow an ability (Bardic Inspiration: Charisma), so
        # the pools are read with the scores after this level's increase; the rest
        # that refreshes a pool is the table row in effect at the new level (#704).
        pools = tables.use_pools_at(cls, s.new_level, abilities)
        existing = {f.get("name"): f for f in sheet.get("classFeatures") or [] if isinstance(f, dict)}
        # A stored feature is matched by its SRD identity: the typed srd_name T125
        # gave a decorated legacy name ("Channel Divinity (2/rest)"), else its
        # whole name (keyword validation V4).
        def stored_name(name):
            key = tables._feature_key(name)
            for stored, feature in existing.items():
                if tables._feature_key(feature) == key:
                    return stored
            return None
        feature_updates: List[Dict[str, Any]] = []
        for name in s.features:
            if stored_name(name) or name in ("Ability Score Improvement", "Subclass feature"):
                continue
            entry = {"name": name, "description": self._features_text.get(name, f"{name} (gained at level {s.new_level})."),
                     "source": f"{sheet.get('class')} level {s.new_level}"}
            pool = next((p for key, p in pools.items() if tables.pool_key(key) == tables.pool_key(name)), None)
            if pool is not None:
                entry["usage"] = pool.usage()
            feature_updates.append(entry)
        for name, pool in pools.items():
            feature = existing.get(stored_name(name))
            if feature is None:
                continue
            name = feature.get("name")
            usage = feature.get("usage") if isinstance(feature.get("usage"), dict) else {}
            stored_max = usage.get("max") if type(usage.get("max")) is int else 0
            current = usage.get("current") if type(usage.get("current")) is int else stored_max
            # Uses grow by what the maximum grew; refreshOn and shortRestRegain are
            # rewritten from the new level's row even when the maximum is unchanged.
            updated = pool.usage(min(pool.max, current + max(0, pool.max - stored_max)))
            if updated != usage:
                feature_updates.append({"name": name, "usage": updated})
        feature_updates.extend(extra_features)
        if feature_updates:
            changes["classFeatures"] = feature_updates
        # 3. spells
        casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else None
        if casting:
            spell_changes: Dict[str, Any] = {}
            # Pact slots move as one set to the new level's slot level (#704,
            # H4-Q4 a); the growth below then finds the table's count in place.
            pact = copy.deepcopy(casting.get("spellSlots")) if isinstance(casting.get("spellSlots"), dict) else None
            if pact is not None and tables.move_pact_slots(pact, cls, s.new_level):
                spell_changes["spellSlots"] = pact
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
        # 3b. species grants at this character level (#1292): typed from the creation archive, else a gap
        species_grants, species_gap = tables.species_grants_gained(sheet, picks, s.new_level)
        species_names: List[str] = []
        if species_gap:
            info(f"LEVEL-UP: {self.character_name}: not typed: species grants at level {s.new_level} "
                 f"({species_gap['where']})", category="level_up")
        if species_grants:
            species_changes, species_names = _species_changes(sheet, changes, species_grants)
            changes.update(species_changes)
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
        # #760: a saved old-shape Fighting Style is recorded as "Fighting Style: <name>" at this
        # player-visible step, and AC is re-projected so the style's effect lands in this commit.
        from core.leveling import fighting_style
        style_record: Dict[str, Any] = {}
        style_notes = fighting_style.canonicalize(after, style_record,
                                                  source="core.managers.level_up_session._commit")
        style_moved = bool((style_record.get("fighting_style") or {}).get("moved_from"))
        if style_moved:
            from core.nql import armor_class as _armor_class
            projection = _armor_class.project(after)
            if projection.applied:
                after = projection.sheet
            else:
                warning(f"LEVEL-UP: {self.character_name} armor class not re-projected ({projection.reason})",
                        category="level_up")
        for note in style_notes:
            info(f"LEVEL-UP: {self.character_name}: {note}", category="level_up")
        # Item C: the engine's attack rows follow the new level (proficiency, the Martial Arts die). One
        # engine call, outside the locks; the rows ride in the same commit, and the level-up commits either way.
        from core.nql import armor_class, startup_rows
        refreshed = startup_rows.refresh_rows(after, armor_class.PROJECTION_LOCATION)
        if not refreshed.get("refreshed"):
            warning(f"LEVEL-UP: {self.character_name} attack rows not refreshed ({refreshed.get('reason')})",
                    category="level_up")
        with _get_character_update_lock(os.path.basename(self._path)[:-5]), \
                path_transaction_lock(self._path, suffix=".effects.lock", timeout_seconds=30.0) as lease:
            if lease is None:
                return self._interview("Your sheet is busy; say 'retry' in a moment.")
            from updates.update_character_info import create_character_backup
            create_character_backup(self._path)
            commit_character_sheet(self._path, after, commit_guard=self.commit_guard, expected_before=self._loaded if self._loaded is not None else sheet)
            self._committed = True
        info(f"LEVEL-UP: {self.character_name} -> level {s.new_level} ({how}); engine ops {growth.operations}",
             category="level_up")
        summary = self._summary(after, how)
        if species_names:
            summary += " Species: %s." % ", ".join(species_names)
        elif species_gap:
            summary += " Species grants for this level are not typed for this character (no creation record)."
        if style_moved:
            summary += " " + style_notes[-1]
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
