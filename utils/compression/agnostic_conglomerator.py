#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""
Agnostic Conversation Conglomerator (dialogue-only)

- Collapses older *non-combat* user/assistant turns in the active area into one TEMP pair.
- Preserves *all* combat/location markers and assistant messages that start combat.
- Keeps the last N turns verbatim (default 5).
- CLI: analyze | conglomerate | drop-temp | test

Input/Output JSON format: list[ { "role": "user"|"assistant", "content": "..." }, ... ]
Assistant messages may contain JSON in content (e.g., { "narration": "...", "actions": [...] }).
"""

import json
import re
import argparse
from typing import List, Dict, Any, Tuple, Optional
from copy import deepcopy
from collections import Counter

# -----------------------------
# Configuration (edit as needed)
# -----------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    # Markers that define the start of the active history (we compress after the last one)
    "transition_markers": [
        r"Location transition:",  # Exact match for location transitions
        r"Module transition:",    # Module transitions
        r"^\[SCENE:.*?\]\s*$",    # Scene markers
    ],

    # Messages that must be preserved verbatim (never absorbed)
    "preserve_exact": [
        r"(?i)Combat Summary:",
        r"(?i)\[COMBAT CONCLUDED[^\]]*?\]",  # handles [COMBAT CONCLUDED] and [COMBAT CONCLUDED - HISTORICAL RECORD]
        r"^Current Location:\s*\{",
    ],

    # Assistant action names that *start* or *commit* combat (preserve those messages)
    "assistant_combat_actions": [
        "createEncounter", "startCombat", "initiateEncounter"
    ],

    # Consider these arrays as potential action collections in assistant JSON
    "candidate_action_keys": [
        "actions", "moves", "steps", "systemActions", "effects"
    ],

    # Clean noisy prefixes out of user messages (optional)
    "user_prefix_strip": [
        r"(?is)\bDungeon Master Note:\s*",
        r"(?is)\bPlayer:\s*",
    ],

    # Additional user "meta/debug" patterns to skip counting as turns
    "meta_user_prefixes": [
        r"(?is)^Error Note:\s*",
        r"(?is)^Your previous response failed validation.*",
        r"(?is)^Validation (error|failed|note).*",
        r"(?is)^\[SYSTEM:.*\]",
    ],

    # Trivial system pairs to remove entirely (e.g., crash/recovery noise)
    "system_pairs": [
        (r"^\[SYSTEM:\s*Combat was interrupted.*\]\s*$",
         r"^\[SYSTEM:\s*Combat recovery initiated.*\]\s*$"),
    ],

    # Guardrails and thresholds
    "keep_recent_turns": 5,     # keep the last N turns verbatim
    "min_messages": 12,         # only conglomerate if the active slice is at least this many messages
    "min_chars": 4000,          # and this many characters
    "min_noncombat_turns": 2,   # require at least this many *non-combat* user turns to build TEMP

    # Parameters compression (for actionsDigest)
    "interesting_param_patterns": [
        r"name$", r"id$", r"target$", r"location",
        r"\bxp\b", r"\bhp\b", r"heal", r"damage",
        r"spell", r"slot", r"level", r"quantity", r"item",
        r"timeEstimate", r"encounter", r"combatant"
    ],
    "params_budget_bytes": 800,
    "max_str_len": 256,
    "max_depth": 3,
    "lossless_params_fallback": True,
}

# -----------------------------
# Compiled config for fast use
# -----------------------------
def _compile_patterns(patterns: List[str]) -> List[re.Pattern]:
    return [re.compile(p) for p in patterns]

class CompiledConfig:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.transition_markers = _compile_patterns(cfg["transition_markers"])
        self.preserve_exact = _compile_patterns(cfg["preserve_exact"])
        self.user_prefix_strip = _compile_patterns(cfg["user_prefix_strip"])
        self.meta_user_prefixes = [re.compile(p) for p in cfg["meta_user_prefixes"]]
        self.system_pairs = [(re.compile(a), re.compile(b)) for a, b in cfg["system_pairs"]]
        self.candidate_action_keys = cfg["candidate_action_keys"]
        self.assistant_combat_actions = {a.lower() for a in cfg["assistant_combat_actions"]}
        self.interesting_param_patterns = [re.compile(p, re.I) for p in cfg["interesting_param_patterns"]]

        self.keep_recent_turns = cfg["keep_recent_turns"]
        self.min_messages = cfg["min_messages"]
        self.min_chars = cfg["min_chars"]
        self.min_noncombat_turns = cfg["min_noncombat_turns"]
        self.params_budget_bytes = cfg["params_budget_bytes"]
        self.max_str_len = cfg["max_str_len"]
        self.max_depth = cfg["max_depth"]
        self.lossless_params_fallback = cfg["lossless_params_fallback"]

# -----------------------------
# Small utilities
# -----------------------------
def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def chars_to_tokens_estimate(chars: int) -> int:
    return max(1, chars // 4)

def message_chars(messages: List[Dict[str, Any]]) -> int:
    return sum(len(m.get("content", "")) for m in messages)

def find_last_index_where(patterns: List[re.Pattern], messages: List[Dict[str, Any]]) -> int:
    for i in range(len(messages) - 1, -1, -1):
        c = messages[i].get("content", "")
        if any(p.search(c) for p in patterns):
            return i
    return -1

def strip_user_prefixes(text: str, CC: CompiledConfig) -> str:
    out = text
    for p in CC.user_prefix_strip:
        out = p.sub("", out)
    return out.strip()

# -----------------------------
# Classification helpers
# -----------------------------
def is_meta_user_turn(text: str, CC: CompiledConfig) -> bool:
    t = text.strip()
    return any(p.search(t) for p in CC.meta_user_prefixes)

def parse_assistant_json_safe(content: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(content)
    except Exception:
        return None

def is_assistant_combat_message(msg: Dict[str, Any], CC: CompiledConfig) -> bool:
    if msg.get("role") != "assistant":
        return False
    payload = parse_assistant_json_safe(msg.get("content", ""))
    if not isinstance(payload, dict):
        return False
    # examine candidate action arrays
    for key in CC.candidate_action_keys:
        arr = payload.get(key)
        if isinstance(arr, list):
            for act in arr:
                if isinstance(act, dict):
                    a_type = (act.get("action") or act.get("type") or "").lower()
                    if a_type in CC.assistant_combat_actions:
                        return True
    return False

def is_preserved_message(msg: Dict[str, Any], CC: CompiledConfig) -> bool:
    content = msg.get("content", "")
    # 1) explicit markers (combat summaries, current location blocks)
    if any(p.search(content) for p in CC.preserve_exact):
        return True
    # 2) assistant messages that start/commit combat
    if is_assistant_combat_message(msg, CC):
        return True
    return False

def sweep_trivial_system_pairs(messages: List[Dict[str, Any]], CC: CompiledConfig) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    i = 0
    while i < len(messages):
        if i + 1 < len(messages):
            m1, m2 = messages[i], messages[i+1]
            if m1.get("role") == "user" and m2.get("role") == "assistant":
                c1 = (m1.get("content", "") or "").strip()
                c2 = (m2.get("content", "") or "").strip()
                for a_pat, b_pat in CC.system_pairs:
                    if a_pat.match(c1) and b_pat.match(c2):
                        i += 2
                        break
                else:
                    out.append(messages[i])
                    i += 1
                    continue
                continue
        out.append(messages[i])
        i += 1
    return out

def find_active_history_start(messages: List[Dict[str, Any]], CC: CompiledConfig) -> int:
    idx = find_last_index_where(CC.transition_markers, messages)
    if idx != -1:
        return idx + 1
    idx = find_last_index_where([re.compile(r"^Current Location:\s*\{")], messages)
    if idx != -1:
        return idx + 1
    return 0

# -----------------------------
# Param compression
# -----------------------------
def _clip_string(s: str, limit: int) -> str:
    return s if len(s) <= limit else s[:limit - 1] + "..."

def _json_size(obj: Any) -> int:
    try:
        return len(json.dumps(obj, ensure_ascii=False))
    except Exception:
        return 0

def _compress_value(v: Any, CC: CompiledConfig, depth: int) -> Any:
    if depth > CC.max_depth:
        return None
    if isinstance(v, str):
        return _clip_string(v, CC.max_str_len)
    if isinstance(v, (int, float, bool)) or v is None:
        return v
    if isinstance(v, list):
        out = []
        for item in v:
            out.append(_compress_value(item, CC, depth + 1))
            if _json_size(out) > CC.params_budget_bytes:
                break
        return out
    if isinstance(v, dict):
        out = {}
        for k, val in v.items():
            out[k] = _compress_value(val, CC, depth + 1)
            if _json_size(out) > CC.params_budget_bytes:
                break
        return out
    return str(v)

def _keep_interesting_keys(params: Dict[str, Any], CC: CompiledConfig) -> Dict[str, Any]:
    keep: Dict[str, Any] = {}
    for k, v in params.items():
        if any(p.search(k) for p in CC.interesting_param_patterns):
            keep[k] = v
    return keep

def compress_params(params: Any, CC: CompiledConfig) -> Any:
    if not isinstance(params, dict):
        return _compress_value(params, CC, 0)
    preferred = _keep_interesting_keys(params, CC)
    if preferred:
        compact = _compress_value(preferred, CC, 0)
        if _json_size(compact) <= CC.params_budget_bytes:
            return compact
    compact = _compress_value(params, CC, 0)
    if compact and (compact != {} or not CC.lossless_params_fallback):
        return compact
    return params if CC.lossless_params_fallback else {}

# -----------------------------
# Conglomeration logic
# -----------------------------
def should_conglomerate(active_block: List[Dict[str, Any]], CC: CompiledConfig) -> bool:
    if not active_block:
        return False
    if len(active_block) < CC.min_messages:
        return False
    if message_chars(active_block) < CC.min_chars:
        return False
    # keep recent turns: 2 messages per turn
    turns = len(active_block) // 2
    if turns <= CC.keep_recent_turns:
        return False
    return True

def conglomerate_active_history(messages: List[Dict[str, Any]], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    CC = CompiledConfig(cfg)
    if not messages:
        return messages

    # 1) sweep trivial system pairs (e.g., crash/recovery)
    messages = sweep_trivial_system_pairs(messages, CC)

    # 2) slice the active area (after the last transition)
    start = find_active_history_start(messages, CC)
    cutoff = max(start, len(messages) - (CC.keep_recent_turns * 2))
    active = messages[start:cutoff]
    if not should_conglomerate(active, CC):
        return messages

    # 3) build TEMP content from *non-preserved* pairs only
    user_turns: List[str] = []
    outcomes: List[Dict[str, Any]] = []
    actions_digest: List[Dict[str, Any]] = []

    i = 0
    while i < len(active):
        msg = active[i]

        # Never absorb preserved messages (combat summaries, location blocks, assistant combat starters)
        if is_preserved_message(msg, CC):
            i += 1
            continue

        if msg.get("role") == "user":
            raw = strip_user_prefixes(msg.get("content", ""), CC)
            if is_meta_user_turn(raw, CC):
                i += 1
                continue

            if raw:
                user_turns.append(raw)

            # Pair with next assistant if present and not preserved
            if i + 1 < len(active) and active[i + 1].get("role") == "assistant":
                nxt = active[i + 1]
                if not is_preserved_message(nxt, CC):
                    payload = parse_assistant_json_safe(nxt.get("content", ""))
                    if isinstance(payload, dict):
                        nar = payload.get("narration")
                        if isinstance(nar, str) and nar.strip():
                            outcomes.append({"turn": len(user_turns), "text": nar})
                        # Extract schema-agnostic actions
                        for key in CC.candidate_action_keys:
                            arr = payload.get(key)
                            if isinstance(arr, list):
                                for act in arr:
                                    if isinstance(act, dict):
                                        a_type = act.get("action") or act.get("type") or "action"
                                        params = act.get("parameters") or act.get("params") or {}
                                        actions_digest.append({
                                            "action": a_type,
                                            "parameters": compress_params(params, CC)
                                        })
                    else:
                        # Plain-text assistant content — keep as outcome
                        txt = nxt.get("content", "").strip()
                        if txt:
                            outcomes.append({"turn": len(user_turns), "text": txt})
                    i += 1  # consumed the assistant
        i += 1

    # Require minimum number of *non-combat* turns
    if len(user_turns) < CC.min_noncombat_turns:
        return messages

    # 4) Build TEMP pair
    temp_user = {
        "role": "user",
        "content":
            "=== TEMP_CONGLOMERATE_START ===\n"
            f"Summary of {len(user_turns)} non-combat player actions in this location:\n\n"
            + "\n\n".join(f"[Turn {k+1}]: {t}" for k, t in enumerate(user_turns))
            + "\n=== TEMP_CONGLOMERATE_END ==="
    }

    temp_asst_payload = {
        "narration": f"Condensed non-combat outcomes for {len(outcomes)} turns.",
        "outcomes": outcomes,
        "actionsDigest": actions_digest,
        "_metadata": {
            "type": "conglomerated_history",
            "turns_compressed": len(user_turns),
            "actions_preserved": len(actions_digest)
        }
    }
    temp_assistant = {
        "role": "assistant",
        "content": json.dumps(temp_asst_payload, ensure_ascii=False, indent=2)
    }

    # 5) Rebuild the active slice *in order*:
    #    - keep preserved messages where they were
    #    - insert the TEMP pair once at the first non-preserved position
    #    - skip the summarized (non-preserved) messages
    rebuilt: List[Dict[str, Any]] = []
    inserted = False
    i = 0
    while i < len(active):
        msg = active[i]
        if is_preserved_message(msg, CC):
            rebuilt.append(msg)  # keep in place
        else:
            if not inserted:
                rebuilt.extend([temp_user, temp_assistant])
                inserted = True
            # skip this non-preserved msg (and its paired assistant if applicable)
            if (msg.get("role") == "user" and
                i + 1 < len(active) and
                active[i + 1].get("role") == "assistant" and
                not is_preserved_message(active[i + 1], CC)):
                i += 1  # skip the assistant, too
        i += 1

    if not inserted:
        # Edge: nothing to replace — do nothing.
        return messages

    # 6) Return with the active slice replaced
    return messages[:start] + rebuilt + messages[cutoff:]


# -----------------------------
# TEMP pair removal
# -----------------------------
def drop_temp_conglomerates(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    skip_next_assistant = False
    for m in messages:
        if m.get("role") == "user" and "=== TEMP_CONGLOMERATE_START ===" in m.get("content", ""):
            skip_next_assistant = True
            continue
        if skip_next_assistant and m.get("role") == "assistant":
            skip_next_assistant = False
            continue
        out.append(m)
    return out

# -----------------------------
# Analysis helpers (for reports)
# -----------------------------
def count_marker_hits(messages: List[Dict[str, Any]], patterns: List[re.Pattern]) -> int:
    n = 0
    for m in messages:
        c = m.get("content", "")
        if any(p.search(c) for p in patterns):
            n += 1
    return n

def scan_actions(messages: List[Dict[str, Any]], CC: CompiledConfig) -> List[str]:
    types: List[str] = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        payload = parse_assistant_json_safe(m.get("content", ""))
        if not isinstance(payload, dict):
            continue
        for key in CC.candidate_action_keys:
            arr = payload.get(key)
            if isinstance(arr, list):
                for act in arr:
                    if isinstance(act, dict):
                        a_type = act.get("action") or act.get("type") or "action"
                        types.append(a_type)
    return types

def scan_temp_pair(messages: List[Dict[str, Any]]) -> Tuple[int, int]:
    user_temp = sum(1 for m in messages if m.get("role") == "user" and "=== TEMP_CONGLOMERATE_START ===" in m.get("content", ""))
    asst_temp = sum(1 for m in messages if m.get("role") == "assistant" and "conglomerated_history" in (m.get("content", "") or ""))
    return user_temp, asst_temp

def analyze_conversation(messages: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    CC = CompiledConfig(cfg)
    total_chars = message_chars(messages)
    token_est = chars_to_tokens_estimate(total_chars)
    markers = {
        "transitions": count_marker_hits(messages, CC.transition_markers),
        "preserve_exact": count_marker_hits(messages, CC.preserve_exact),
    }
    action_types = scan_actions(messages, CC)
    hist = dict(Counter(action_types))
    temp_user_count, temp_asst_count = scan_temp_pair(messages)
    return {
        "messages": len(messages),
        "chars": total_chars,
        "token_estimate": token_est,
        "markers": markers,
        "action_histogram": hist,
        "temp_pairs": {"user": temp_user_count, "assistant": temp_asst_count},
    }

# -----------------------------
# CLI
# -----------------------------
def cli_main():
    parser = argparse.ArgumentParser(description="Agnostic dialogue-only conglomerator (no combat absorption)")
    sub = parser.add_subparsers(dest="cmd")

    p_conglom = sub.add_parser("conglomerate", help="Create a dialogue-only TEMP pair in the active area")
    p_conglom.add_argument("--in", dest="in_path", required=True)
    p_conglom.add_argument("--out", dest="out_path", required=True)

    p_drop = sub.add_parser("drop-temp", help="Remove any TEMP conglomerate pairs")
    p_drop.add_argument("--in", dest="in_path", required=True)
    p_drop.add_argument("--out", dest="out_path", required=True)

    p_an = sub.add_parser("analyze", help="Print stats for a conversation JSON")
    p_an.add_argument("--in", dest="in_path", required=True)
    p_an.add_argument("--report", dest="report_path", required=False)

    p_test = sub.add_parser("test", help="Before/after test (writes output + report)")
    p_test.add_argument("--in", dest="in_path", required=True)
    p_test.add_argument("--out", dest="out_path", required=True)
    p_test.add_argument("--report", dest="report_path", required=True)

    args = parser.parse_args()
    cfg = deepcopy(DEFAULT_CONFIG)

    if args.cmd == "conglomerate":
        data = load_json(args.in_path)
        out = conglomerate_active_history(data, cfg)
        save_json(args.out_path, out)
        print(f"[OK] Wrote conglomerated conversation -> {args.out_path}")

    elif args.cmd == "drop-temp":
        data = load_json(args.in_path)
        out = drop_temp_conglomerates(data)
        save_json(args.out_path, out)
        print(f"[OK] Dropped TEMP conglomerates -> {args.out_path}")

    elif args.cmd == "analyze":
        data = load_json(args.in_path)
        report = analyze_conversation(data, cfg)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        if args.report_path:
            save_json(args.report_path, report)
            print(f"[OK] Wrote analysis report -> {args.report_path}")

    elif args.cmd == "test":
        original = load_json(args.in_path)
        before = analyze_conversation(original, cfg)
        conglomerated = conglomerate_active_history(original, cfg)
        after = analyze_conversation(conglomerated, cfg)

        invariants = {
            "preserve_exact_equal": before["markers"]["preserve_exact"] == after["markers"]["preserve_exact"],
            "temp_pair_count": after["temp_pairs"],
        }
        report = {
            "before": before,
            "after": after,
            "invariants": invariants,
            "savings": {
                "messages": before["messages"] - after["messages"],
                "chars": before["chars"] - after["chars"],
                "token_estimate": before["token_estimate"] - after["token_estimate"],
            },
        }
        save_json(args.out_path, conglomerated)
        save_json(args.report_path, report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"[OK] Wrote conglomerated -> {args.out_path}")
        print(f"[OK] Wrote test report -> {args.report_path}")

    else:
        parser.print_help()

if __name__ == "__main__":
    cli_main()