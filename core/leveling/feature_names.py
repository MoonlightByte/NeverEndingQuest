# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""T125: the SRD feature a legacy classFeatures entry is (keyword validation V4).

Use pools, level-up and subclass inference match a classFeatures entry by its
SRD identity (``tables._feature_key``): the typed ``srd_name`` when the entry
has one, else its whole name. No name is cut. A sheet written before the SRD
names ("Channel Divinity (2/rest)", "Preserve Life (Channel Divinity Option)")
then misses a table lookup. When one misses (``naming_needed``), T125 is asked
ONCE about every entry whose whole name is not an SRD feature of the class:
it names the SRD feature from the closed list, or none. Code checks the answer
and writes it on the entries (``srd_name``: the name, or null for none), so the
sheet is not asked again (owner Q-V3 a)."""
import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.ai import api_client
from core.leveling import tables
from utils.capture.live_provider_call import LiveProviderSuperseded
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.enhanced_logger import info, warning

register_callsite("T125", "core/leveling/feature_names.py", 152)

_MAX_ATTEMPTS = 2

_SYSTEM = """You match a character's class features to the official feature names of the 5th edition System Reference Document 5.2.1.

Some class features on this sheet were written with older or decorated names, such as a use count, an option or a subclass in parentheses. For every feature row you are shown, name the SRD feature of the character's class it is, using exactly one name from the SRD FEATURE NAMES list, or null when it is none of them (an older rule, a trait of another class, or a note that is not a class feature).

Rules:
- A decorated name is the feature it decorates: "Channel Divinity (2/rest)" is "Channel Divinity".
- An option of a feature that has its own SRD name is that name: "Preserve Life (Channel Divinity Option)" is "Preserve Life".
- Each SRD name may be given to at most one row, and never to a row when the sheet already has a feature with exactly that name.
- When unsure, answer null.

Return only this JSON object, with one entry for every row you are shown:
{"features": [{"row": 3, "srd_name": "Channel Divinity"}, {"row": 5, "srd_name": null}]}"""


@dataclass
class NamingResult:
    sheet: Dict[str, Any]
    notes: List[str] = field(default_factory=list)
    error: Optional[str] = None


class NamingAnswerError(ValueError):
    """A T125 answer that breaks the contract; the message is shown on the retry."""


def naming_needed(sheet: Dict[str, Any]) -> List[int]:
    """The classFeatures indexes to ask T125 about, or [].

    Asked only when a table lookup misses: a use pool of the sheet's class and
    level has no feature on the sheet, or the sheet is at or past its subclass
    level with no subclass recorded or inferred. Then every entry that has no
    ``srd_name`` and whose whole name is not an SRD feature of the class."""
    cls = tables.class_key(sheet)
    level = sheet.get("level")
    if cls is None or type(level) is not int or not 1 <= level <= 20:
        return []
    unsettled = tables.unnamed_features(sheet)
    if not unsettled:
        return []
    features = sheet.get("classFeatures")
    pool_missing = any(tables.pool_feature(features, name) is None
                       for name in tables.use_pools_at(cls, level, sheet.get("abilities")))
    subclass_level = tables.tables()["classes"][cls].get("subclass_level")
    subclass_missing = (type(subclass_level) is int and level >= subclass_level
                        and tables.infer_subclass(sheet, cls) is None)
    return unsettled if pool_missing or subclass_missing else []


def build_prompt(sheet: Dict[str, Any], rows: List[int]) -> str:
    cls = tables.class_key(sheet)
    features = sheet.get("classFeatures") or []
    lines = [f"CHARACTER: {sheet.get('name', 'Unknown')}, {sheet.get('class')} level {sheet.get('level')}",
             f"SUBCLASS RECORDED: {sheet.get('subclass') or 'none'}", "",
             "SRD FEATURE NAMES: " + json.dumps(tables.srd_feature_names(cls), ensure_ascii=True), "",
             "FEATURES ALREADY NAMED (not to be given again): " + json.dumps(
                 [f.get("name") for i, f in enumerate(features) if isinstance(f, dict) and i not in rows],
                 ensure_ascii=True), "",
             "FEATURE ROWS TO NAME:"]
    for row in rows:
        entry = features[row]
        lines += ["", f"Row {row}:", f"- Name: {entry.get('name')}",
                  f"- Description: {entry.get('description') or 'none'}"]
    lines += ["", "Answer every row."]
    return "\n".join(lines)


def check_answer(raw: Any, sheet: Dict[str, Any], rows: List[int]) -> Dict[int, Optional[str]]:
    """{row: SRD name or None} from a T125 answer, or NamingAnswerError."""
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else None
    except ValueError as exc:
        raise NamingAnswerError(f"T125: invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict) or set(parsed) != {"features"} or not isinstance(parsed["features"], list):
        raise NamingAnswerError('T125: the answer must be one object {"features": [...]}')
    closed = {tables._feature_key(name): name for name in tables.srd_feature_names(tables.class_key(sheet))}
    features = sheet.get("classFeatures") or []
    held = {tables._feature_key(f) for i, f in enumerate(features) if isinstance(f, dict) and i not in rows}
    named: Dict[int, Optional[str]] = {}
    for index, answer in enumerate(parsed["features"]):
        path = f"T125: features[{index}]"
        if not isinstance(answer, dict) or set(answer) != {"row", "srd_name"}:
            raise NamingAnswerError(f"{path} must be an object with exactly row and srd_name")
        row = answer["row"]
        if type(row) is not int or row not in rows:
            raise NamingAnswerError(f"{path}.row must be one of the rows shown: {rows}")
        if row in named:
            raise NamingAnswerError(f"{path} answers row {row} a second time")
        value = answer["srd_name"]
        if value is None:
            named[row] = None
            continue
        name = closed.get(tables._feature_key(value)) if isinstance(value, str) else None
        if name is None:
            raise NamingAnswerError(f"{path}.srd_name must be null or one of the SRD feature names listed")
        if tables._feature_key(name) in held:
            raise NamingAnswerError(f"{path}: the sheet already has {name!r}; answer null for row {row}")
        if name in named.values():
            raise NamingAnswerError(f"{path}: {name!r} is given to two rows; give it to one row only")
        named[row] = name
    missing = sorted(set(rows).difference(named))
    if missing:
        raise NamingAnswerError(f"T125: rows {missing} were not answered")
    return named


def name_features(sheet: Dict[str, Any], *, scope: Any = None, status: Any = None,
                  live_selected: Any = None) -> NamingResult:
    """Ask T125 once when ``naming_needed``; return a copy of the sheet with
    ``srd_name`` written on every asked entry. On failure the sheet is returned
    unchanged with ``error`` set; the next validation asks again."""
    rows = naming_needed(sheet)
    if not rows:
        return NamingResult(sheet)
    from model_config import MODEL_PROVIDER, resolve_callsite_config

    character = sheet.get("name", "Unknown")
    messages = [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": build_prompt(sheet, rows)}]
    problem = "no answer"
    for attempt in range(_MAX_ATTEMPTS):
        raw = None
        try:
            cfg = resolve_callsite_config("T125", MODEL_PROVIDER, attempt)
            response = capture_and_fanout(
                "T125", api_client.create_completion, _live_selected=live_selected, _detached_scope=scope,
                _detached_status=status, _request_provider=MODEL_PROVIDER, messages=messages, model=cfg["model"],
                temperature=0.1, response_format={"type": "json_object"},
                **{k: v for k, v in cfg.items() if k != "model"})
            raw = response.choices[0].message.content
            named = check_answer(raw, sheet, rows)
        except LiveProviderSuperseded:
            raise
        except NamingAnswerError as exc:
            problem = str(exc)
            messages = messages[:2] + [
                {"role": "assistant", "content": raw if isinstance(raw, str) else ""},
                {"role": "user", "content": "Your last answer failed this contract: " + problem
                 + ". Return the complete JSON object again, with that defect corrected."}]
            continue
        except Exception as exc:
            problem = f"T125 call failed: {exc}"
            continue
        out = copy.deepcopy(sheet)
        notes = []
        for row, name in sorted(named.items()):
            entry = out["classFeatures"][row]
            entry["srd_name"] = name
            notes.append(f"{entry.get('name')!r} is SRD feature {name!r}" if name else
                         f"{entry.get('name')!r} is no SRD {sheet.get('class')} feature")
        for note in notes:
            info(f"[Feature Names] {character}: {note} (T125)", category="character_validation")
        return NamingResult(out, notes)
    warning(f"[Feature Names] {character}: legacy feature names not named: {problem}",
            category="character_validation")
    return NamingResult(sheet, error=problem)
