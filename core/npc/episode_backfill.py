"""W4: episodic BACKFILL for existing games (callsite T113).

When a running game upgrades to the episodic-memory feature it has NO episodes, but
its journey is recoverable from prose the game already kept:

  * journal.json (the STRONG source) -- {module, entries:[{date,time,location,summary}]}.
    Dialogue-level prose with TEXTURE (tender/bond/gift/confession). Its `location` is
    free text that alternates "Name" vs "Name (RO01)"; we normalize it.
  * campaign_summaries/* (COARSE, module-level) -- one saga summary per module.

Both funnel through ONE model call (T113) that, given the prose plus a CLOSED module
roster, SELECTS which known companions are present (agentic presence) -- then CODE
reconciles: a name not in the roster is dropped, facts are kept only for reconciled
companions. This is the same model-parses / code-reconciles discipline as live capture;
the only difference from T108 is that presence is SELECTED here, not given.

Provenance: derived_from="backfill" (already reserved in the ledger schema -> no schema
change). Coordinates are `backfill-journal-<loc>-<seq>` / `backfill-summary-<module>`,
all `backfill-` prefixed so they are lexically disjoint from live prefixes
(close-/roll-/combat-) and a re-run is an idempotent no-op. Everything is fail-open and
always on at the call site (the upgrade orchestrator, W5).
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import time
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

import model_config
from core.ai import api_client
from core.npc.episode_capture import _commit_and_overlay, resolve_present_companions
from core.npc.episode_store import EpisodeStore, VALID_SALIENT_KINDS
from core.npc.relationship_store import RelationshipStore, record_store_health
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.encoding_utils import safe_json_load

_LOGGER = logging.getLogger(__name__)

TASK_ID = "T113"
PROMPT_VERSION = "npc-backfill-extract/v1"
register_callsite(TASK_ID, "core/npc/episode_backfill.py", 60)


class BackfillCompletedInvalid(RuntimeError):
    """One T113 entry completed without a usable typed result."""

# Response shape: like T108 but the model also SELECTS present companions.
BACKFILL_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["present", "headline", "canonicalSummary", "intensity", "entityTags", "salientFacts"],
    "properties": {
        "present": {"type": "array", "items": {"type": "string"}},
        "headline": {"type": "string"},
        "canonicalSummary": {"type": "string"},
        "intensity": {"type": "number"},
        "entityTags": {"type": "array", "items": {"type": "string"}},
        "salientFacts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["npc", "kind", "oneLine"],
                "properties": {
                    "npc": {"type": "string"},
                    "kind": {"type": "string"},
                    "oneLine": {"type": "string"},
                    "objectLabel": {"type": "string"},
                },
            },
        },
    },
}

_SYSTEM = """You reconstruct a CANONICAL episode from a PAST journal/summary passage, and the PER-COMPANION beats it contains. You are given a CLOSED roster of the campaign's known companions; ONLY those names may appear.

Produce:
- present: which roster companions are PHYSICALLY PRESENT and acting in this passage (a subset of the roster; [] if none). A companion merely mentioned/absent is NOT present.
- headline: a short label for what happened.
- canonicalSummary: the shared, factual account, third person. Only what the passage supports; do not embellish or invent.
- intensity: 0..1 emotional weight (near-death/betrayal high; idle travel low).
- entityTags: short lowercase recall anchors (e.g. "wizard", "wishing well").
- salientFacts: the specific, personal, character-defining beats a plot summary drops -- a gift, joke, fear shown, tender act, vow, near-death. Each: {npc, kind, oneLine, objectLabel?}.

STRICT RULES:
- Use ONLY what is explicitly in the passage. Never invent a companion, trait, motive, or number.
- present and every salientFact.npc MUST be an EXACT name from the roster. Never output a name not on the roster.
- Attribute each fact to the present companion who DID it. No fact for an absent/mentioned companion.
- kind is one of: {kinds}.
- oneLine is concrete and keeps attribution intact.

Roster: {roster}. Player: {player}.
Return ONLY JSON matching the requested shape."""


# ---- pure helpers ---------------------------------------------------------

_JOURNAL_ID_RE = re.compile(r"\(([A-Za-z]+\d+)\)\s*$")


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def normalize_journal_location(
    location: Any, name_to_id: Mapping[str, str]
) -> Dict[str, str]:
    """Resolve a free-text journal location -> {id, name}. Prefer an embedded id
    ("Name (RO01)" -> RO01). Else map the cleaned name via name_to_id; if the name is
    unknown or AMBIGUOUS (not in the map), fall back to module-level (id="") rather
    than silently guessing a location."""
    text = str(location or "").strip()
    match = _JOURNAL_ID_RE.search(text)
    if match:
        loc_id = match.group(1)
        name = text[: match.start()].strip()
        return {"id": loc_id, "name": name or text}
    loc_id = name_to_id.get(_norm(text), "")
    return {"id": loc_id, "name": text}


def build_location_name_map(area_dicts: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    """{normalized location name: locationId} across the module's area files. A name
    that maps to MORE THAN ONE id is ambiguous and is DROPPED (callers then fall back
    to module-level) so backfill never mis-attributes to the wrong room."""
    seen: Dict[str, set] = {}
    for area in area_dicts:
        for loc in (area.get("locations") or []) if isinstance(area, Mapping) else []:
            if not isinstance(loc, Mapping):
                continue
            name = _norm(loc.get("name"))
            loc_id = str(loc.get("locationId") or "").strip()
            if name and loc_id:
                seen.setdefault(name, set()).add(loc_id)
    return {name: next(iter(ids)) for name, ids in seen.items() if len(ids) == 1}


def build_companion_roster(character_dicts: Sequence[Mapping[str, Any]]) -> List[str]:
    """Distinct NPC display names (the CLOSED roster). Players and blank names dropped;
    deduped preserving first-seen order."""
    names: List[str] = []
    seen = set()
    for sheet in character_dicts:
        if not isinstance(sheet, Mapping):
            continue
        if str(sheet.get("character_type") or sheet.get("type") or "").lower() == "player":
            continue
        name = str(sheet.get("name") or "").strip()
        if name and _norm(name) not in seen:
            seen.add(_norm(name))
            names.append(name)
    return names


def _reconcile_facts(raw_facts, name_to_id: Mapping[str, str]) -> List[Dict[str, Any]]:
    """Keep only facts whose npc is a PRESENT roster companion (name -> id); drop the
    rest. Mirrors T108's code-reconciliation."""
    name_to_id_ci = {_norm(n): i for n, i in name_to_id.items()}
    facts: List[Dict[str, Any]] = []
    for raw in raw_facts or []:
        if not isinstance(raw, Mapping):
            continue
        npc = (raw.get("npc") or "").strip()
        kind = raw.get("kind")
        one_line = (raw.get("oneLine") or "").strip()
        actor_id = name_to_id.get(npc) or name_to_id_ci.get(_norm(npc))
        if actor_id is None or kind not in VALID_SALIENT_KINDS or not one_line:
            continue
        fact: Dict[str, Any] = {
            "kind": kind,
            "subject": {"label": npc, "id": actor_id},
            "oneLine": one_line,
        }
        obj = (raw.get("objectLabel") or "").strip()
        if obj:
            fact["object"] = {"label": obj}
        facts.append(fact)
    return facts


def _completion_kwargs(provider: str, config: Mapping[str, Any]) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {k: v for k, v in config.items() if k != "model"}
    if provider == "gemini":
        kwargs["response_schema"] = model_config.convert_to_gemini_schema(BACKFILL_RESPONSE_SCHEMA)
        kwargs["response_format"] = None
    elif provider == "lmstudio":
        kwargs["response_format"] = None
    else:
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


# ---- extraction (T113) ----------------------------------------------------

def extract_backfill_episode(
    scene_text: str,
    roster_names: Sequence[str],
    resolve_ids: Callable[[Sequence[str]], Mapping[str, str]],
    *,
    player_name: str = "",
    provider: Optional[str] = None,
    completion_fn: Callable[..., Any] = api_client.create_completion,
    capture_fn: Callable[..., Any] = None,
    advisory_scope: Any = None,
    advisory_status: Optional[Callable[[str], None]] = None,
) -> Optional[Dict[str, Any]]:
    """One T113 call over prose + a CLOSED roster. Returns commit-ready kwargs (minus
    coordinates) or None. `resolve_ids(names)->{name:id}` maps present roster names to
    identity UUIDs (reconcile-by-code). Fail-open."""
    if not scene_text.strip() or not roster_names:
        return None
    prov = provider or model_config.get_provider()
    config = model_config.resolve_callsite_config(TASK_ID, prov)
    roster_ci = {_norm(n) for n in roster_names}
    system = (
        _SYSTEM.replace("{kinds}", ", ".join(sorted(VALID_SALIENT_KINDS)))
        .replace("{roster}", ", ".join(roster_names))
        .replace("{player}", player_name or "the player")
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": "Passage:\n\n%s" % scene_text},
    ]
    capture = capture_fn or (lambda task_id, fn, **kw: fn(**kw))
    try:
        response = capture(
            TASK_ID,
            completion_fn,
            _request_provider=prov,
            _live_selected="advisory" if advisory_scope is not None else None,
            _detached_scope=advisory_scope,
            _detached_status=advisory_status,
            model=config["model"],
            messages=messages,
            **_completion_kwargs(prov, config),
        )
        payload = json.loads(response.choices[0].message.content or "{}")
    except Exception as error:
        from utils.capture.live_provider_call import LiveProviderSuperseded

        if isinstance(error, LiveProviderSuperseded):
            raise
        _LOGGER.debug("backfill extraction failed: %r", error)
        raise BackfillCompletedInvalid(type(error).__name__) from error
    if not isinstance(payload, Mapping):
        raise BackfillCompletedInvalid("payload_not_mapping")

    # Closed-roster guard IN CODE: keep only present names that are actually on the
    # roster (the model must not invent a companion).
    present_names = [
        str(n).strip() for n in (payload.get("present") or [])
        if str(n).strip() and _norm(n) in roster_ci
    ]
    if not present_names:
        return None
    name_to_id = dict(resolve_ids(present_names) or {})
    if not name_to_id:
        return None
    facts = _reconcile_facts(payload.get("salientFacts", []), name_to_id)
    return {
        "headline": (payload.get("headline") or "").strip(),
        "canonical_summary": (payload.get("canonicalSummary") or "").strip(),
        "salient_facts": facts,
        "entity_tags": [str(t).strip() for t in (payload.get("entityTags") or []) if str(t).strip()],
        "witness_ids": list(name_to_id.values()),
        "intensity": payload.get("intensity", 0.0),
        "prompt_version": PROMPT_VERSION,
    }


# ---- module data loaders --------------------------------------------------

def _safe_load_dict(path: str) -> Optional[Dict[str, Any]]:
    """Load one JSON dict, tolerating corrupt/empty/temp files in real dirs (a bad
    character or area file must never break roster/name-map building)."""
    try:
        data = safe_json_load(path)
    except Exception:  # noqa: BLE001 - corrupt file -> skip, never abort backfill
        return None
    return data if isinstance(data, dict) else None


def load_module_area_dicts(module_dir: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(module_dir, "areas", "*.json"))):
        data = _safe_load_dict(path)
        if data is not None:
            out.append(data)
    return out


def load_character_dicts(characters_dir: str = "characters") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(glob.glob(os.path.join(characters_dir, "*.json"))):
        base = os.path.basename(path)
        if ".backup" in base or "_temp" in base or base.endswith((".bak", ".tmp")):
            continue
        data = _safe_load_dict(path)
        if data is not None:
            out.append(data)
    return out


# ---- orchestration --------------------------------------------------------

def _make_resolver(party_tracker_data, path_manager, rel_store, json_loader):
    def resolve_ids(names):
        present = resolve_present_companions(
            names, party_tracker_data,
            path_manager=path_manager, rel_store=rel_store, json_loader=json_loader,
        )
        return {p["name"]: p["id"] for p in present if p.get("id")}
    return resolve_ids


def _commit_backfill(
    store, rel, result, *, module, location_id, location_name,
    boundary_turn_id, player_name, party_tracker_data, path_manager, json_loader,
) -> Optional[str]:
    if not result or not result.get("witness_ids"):
        return None
    return _commit_and_overlay(
        store, rel, result,
        module=module,
        location_id=location_id,
        location_name=location_name,
        world={},  # backfill: no live world clock; gameDay stays None (chronological
                   # order is preserved by commit order, journal being time-ordered).
        boundary_turn_id=boundary_turn_id,
        derived_from="backfill",
        player_name=player_name,
        party_tracker_data=party_tracker_data,
        path_manager=path_manager,
        json_loader=json_loader,
    )


def backfill_from_journal(
    journal: Mapping[str, Any],
    party_tracker_data: Mapping[str, Any],
    *,
    path_manager: Any,
    roster_names: Sequence[str],
    name_to_id_map: Mapping[str, str],
    episode_store: EpisodeStore,
    rel_store: RelationshipStore,
    player_name: str = "",
    provider: Optional[str] = None,
    json_loader: Callable[[str], Any] = safe_json_load,
    progress_cb: Optional[Callable[..., None]] = None,
    start_index: int = 0,
    advisory_scope: Any = None,
) -> Dict[str, Any]:
    """Backfill episodes from journal entries. Idempotent (stable coordinates), fail-
    open per entry. Returns {committed, processed, next_index, total}."""
    entries = journal.get("entries") if isinstance(journal, Mapping) else None
    entries = entries if isinstance(entries, list) else []
    total = len(entries)
    module = str(party_tracker_data.get("module") or "")
    resolve_ids = _make_resolver(party_tracker_data, path_manager, rel_store, json_loader)
    committed = 0
    processed = 0
    failure = None
    index = max(0, start_index)
    while index < total:
        entry = entries[index]
        index += 1
        processed += 1
        if progress_cb:
            try:
                progress_cb(index, total)
            except Exception:
                pass
        if not isinstance(entry, Mapping):
            continue
        summary = str(entry.get("summary") or "").strip()
        if not summary:
            continue
        loc = normalize_journal_location(entry.get("location"), name_to_id_map)
        entry_started = time.monotonic()

        def entry_status(_message):
            if progress_cb:
                progress_cb(index, total, time.monotonic() - entry_started)

        try:
            result = extract_backfill_episode(
                summary, roster_names, resolve_ids,
                player_name=player_name, provider=provider,
                capture_fn=capture_and_fanout, advisory_scope=advisory_scope,
                advisory_status=entry_status,
            )
            eid = _commit_backfill(
                episode_store, rel_store, result,
                module=module, location_id=loc["id"], location_name=loc["name"],
                boundary_turn_id="backfill-journal-%s-%d" % (loc["id"] or "mod", index - 1),
                player_name=player_name, party_tracker_data=party_tracker_data,
                path_manager=path_manager, json_loader=json_loader,
            )
            if eid:
                committed += 1
        except BackfillCompletedInvalid as error:
            index -= 1
            failure = {
                "kind": "completed_invalid",
                "entryIndex": index,
                "errorClass": type(error).__name__,
            }
            _LOGGER.warning(
                "journal backfill entry %d remains pending: %s",
                index,
                type(error).__name__,
            )
            break
        except Exception as error:  # noqa: BLE001 - fail-open per entry
            from utils.capture.live_provider_call import LiveProviderSuperseded

            if isinstance(error, LiveProviderSuperseded):
                raise
            _LOGGER.debug("journal backfill entry %d failed: %r", index - 1, error)
    return {
        "committed": committed,
        "processed": processed,
        "next_index": index,
        "total": total,
        "failure": failure,
    }


def backfill_from_summaries(
    summaries: Sequence[Mapping[str, Any]],
    party_tracker_data: Mapping[str, Any],
    *,
    path_manager: Any,
    roster_names: Sequence[str],
    episode_store: EpisodeStore,
    rel_store: RelationshipStore,
    player_name: str = "",
    provider: Optional[str] = None,
    json_loader: Callable[[str], Any] = safe_json_load,
    progress_cb: Optional[Callable[..., None]] = None,
    advisory_scope: Any = None,
) -> Dict[str, Any]:
    """Backfill one COARSE module-level episode per campaign summary. Location is
    module-level (id=""); grain is derived as 'module' from the backfill-summary
    coordinate, so these never outrank specific fight/location episodes in retrieval."""
    total = len(summaries)
    resolve_ids = _make_resolver(party_tracker_data, path_manager, rel_store, json_loader)
    committed = 0
    for i, summary_doc in enumerate(summaries):
        if progress_cb:
            try:
                progress_cb(i + 1, total)
            except Exception:
                pass
        if not isinstance(summary_doc, Mapping):
            continue
        prose = str(summary_doc.get("summary") or "").strip()
        module_name = str(summary_doc.get("moduleName") or party_tracker_data.get("module") or "")
        if not prose or not module_name:
            continue
        entry_started = time.monotonic()

        def entry_status(_message):
            if progress_cb:
                progress_cb(i + 1, total, time.monotonic() - entry_started)

        try:
            result = extract_backfill_episode(
                prose, roster_names, resolve_ids,
                player_name=player_name, provider=provider,
                capture_fn=capture_and_fanout, advisory_scope=advisory_scope,
                advisory_status=entry_status,
            )
            eid = _commit_backfill(
                episode_store, rel_store, result,
                module=module_name, location_id="",
                location_name="%s (module chronicle)" % module_name,
                boundary_turn_id="backfill-summary-%s" % module_name.replace(" ", "_"),
                player_name=player_name, party_tracker_data=party_tracker_data,
                path_manager=path_manager, json_loader=json_loader,
            )
            if eid:
                committed += 1
        except BackfillCompletedInvalid:
            raise
        except Exception as error:  # noqa: BLE001 - fail-open per summary
            from utils.capture.live_provider_call import LiveProviderSuperseded

            if isinstance(error, LiveProviderSuperseded):
                raise
            _LOGGER.debug("summary backfill %d failed: %r", i, error)
    return {"committed": committed, "total": total}
