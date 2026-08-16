# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Pure semantic gates that supplement frozen production JSON Schemas."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Tuple

import jsonschema

from .compilers import (
    GraphEmbeddingError,
    compile_grid_embedding,
    compile_side_thread_projection,
)
from .execution import SemanticCorrectionError


def require_ascii(value: Any, label: str) -> None:
    try:
        json.dumps(value, ensure_ascii=False).encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} contains non-ASCII text") from exc


_POSITIVE_MOVEMENT = re.compile(
    r"(?i)(?:\b(?:fly|flying|hover|swim|swimming|burrow|burrowing|climb|climbing)"
    r"(?:\s+speed)?(?:\s+of)?\s*([0-9]+)\s*(?:ft\.?|feet|foot)\b|"
    r"\b([0-9]+)\s*(?:ft\.?|feet|foot)\s*"
    r"(?:fly|flying|hover|swim|swimming|burrow|burrowing|climb|climbing)\b)"
)


def semantic_creature_viability_checks(creature: Mapping[str, Any]) -> Dict[str, Any]:
    """Enforce a loose minimum: the creature can move and take one action."""
    issues = []
    speed = creature.get("speed")
    ability_text = " ".join(
        value
        for ability in creature.get("specialAbilities", [])
        if isinstance(ability, Mapping)
        for key in ("name", "description")
        for value in (ability.get(key),)
        if isinstance(value, str)
    )
    movement_match = _POSITIVE_MOVEMENT.search(ability_text)
    alternate_speed = max(
        (
            int(value)
            for match in _POSITIVE_MOVEMENT.finditer(ability_text)
            for value in match.groups()
            if value is not None
        ),
        default=0,
    )
    if not isinstance(speed, (int, float)) or isinstance(speed, bool) or speed < 0:
        issues.append(
            {
                "invariant": "creature_speed",
                "offending": json.dumps({"speed": speed}, ensure_ascii=True),
                "expectation": "speed must be a non-negative number",
            }
        )
    elif speed == 0 and not movement_match:
        issues.append(
            {
                "invariant": "creature_mobility",
                "offending": json.dumps(
                    {"speed": speed, "positiveAlternateSpeed": False},
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                "expectation": (
                    "use speed above zero or explicitly state a positive fly, hover, "
                    "swim, burrow, or climb distance in specialAbilities text"
                ),
            }
        )
    actions = creature.get("actions", [])
    usable_names = [
        action.get("name", "").strip()
        for action in actions
        if isinstance(action, Mapping) and isinstance(action.get("name"), str)
    ]
    if not usable_names or not any(usable_names):
        issues.append(
            {
                "invariant": "usable_action",
                "offending": json.dumps(
                    {"actionCount": len(actions), "namedActionCount": 0},
                    ensure_ascii=True,
                    sort_keys=True,
                ),
                "expectation": "provide at least one action with a non-empty name",
            }
        )
    if issues:
        raise SemanticCorrectionError(issues)
    return {
        "baseSpeed": speed,
        "alternateMovementSpeed": alternate_speed,
        "usableActionCount": sum(bool(name) for name in usable_names),
    }


def non_ascii_issues(value: Any, label: str) -> List[Dict[str, str]]:
    """Return bounded, path-specific Unicode issues without echoing authored prose."""
    issues = []

    def visit(item: Any, path: str) -> None:
        if len(issues) >= 24:
            return
        if isinstance(item, dict):
            for key, child in item.items():
                visit(child, f"{path}.{key}")
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]")
        elif isinstance(item, str):
            code_points = sorted(
                {f"U+{ord(char):04X}" for char in item if ord(char) > 127}
            )
            if code_points:
                issues.append(
                    {
                        "invariant": "ascii_only",
                        "offending": json.dumps(
                            {"path": path, "codePoints": code_points},
                            ensure_ascii=True,
                            sort_keys=True,
                        ),
                        "expectation": (
                            f"{label} contains non-ASCII text; use standard ASCII "
                            "characters only"
                        ),
                    }
                )

    visit(value, "$")
    return issues


def unique_values(items: Iterable[Dict[str, Any]], key: str, label: str) -> List[str]:
    values = [str(item.get(key, "")) for item in items]
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}: {values}")
    return values


def unexpected_blocklist_terms(
    authored: Dict[str, Any], seed: Dict[str, Any], blocklist: Iterable[str]
) -> List[str]:
    authored_text = json.dumps(authored, ensure_ascii=True).casefold()
    immutable_seed = json.dumps(seed, ensure_ascii=True).casefold()
    unexpected = set()
    for word in blocklist:
        pattern = rf"\b{re.escape(word.casefold())}(?:s|'s)?\b"
        authored_count = len(re.findall(pattern, authored_text))
        seed_count = len(re.findall(pattern, immutable_seed))
        if authored_count > seed_count:
            unexpected.add(word)
    return sorted(unexpected)


def _outline_identity_fields(outline: Dict[str, Any]) -> Dict[str, Any]:
    """Return only authored identity fields governed by the gold-prior list."""
    return {
        "moduleTitle": outline.get("moduleTitle", ""),
        "oppositionName": outline.get("opposition", {}).get("name", ""),
        "areaNames": [item.get("name", "") for item in outline.get("areas", [])],
        "beatTitles": [item.get("title", "") for item in outline.get("beats", [])],
        "sideThreadTitles": [
            item.get("title", "") for item in outline.get("sideThreads", [])
        ],
        "creatureNames": [
            item.get("name", "") for item in outline.get("creatureBriefs", [])
        ],
    }


_AREA_MASS_BEAT_PATTERNS = (
    r"\b(?:city|district|region|settlement|town|village)[ -]?wide\b",
    r"\b(?:army|armies|battlefield|mass battle|mass combat|siege lines?|war ?host)\b",
    r"\b(?:evacuate|evacuation of) (?:the )?(?:city|district|settlement|town|village)\b",
)
_CONFINED_BEAT_PATTERNS = (
    r"\bprivate (?:conversation|interview|meeting|ritual)\b",
    r"\b(?:one|single) (?:captive|patient|prisoner|witness)\b",
)
_SITE_BEAT_PATTERNS = (
    r"\b(?:building|bridge|camp|courtyard|gate|hall|house|temple|tower)[ -]wide\b",
    r"\b(?:defend|evacuate|search) (?:the )?(?:building|bridge|camp|gate|hall|temple|tower)\b",
)
_CONFINED_LOCATION_PATTERNS = (
    r"\b(?:alcoves?|cells?|closets?|cupboards?|pantries|privies)\b",
    r"\b(?:cramped|narrow|tiny) (?:cells?|chambers?|rooms?)\b",
    r"\b(?:interior|one-room|private) shacks?\b",
)
_AREA_MASS_LOCATION_PATTERNS = (
    r"\b(?:battlefield|city streets?|district streets?|siege lines?)\b",
    r"\b(?:city|district|settlement|town|village) (?:center|centre|streets?)\b",
)
_SITE_LOCATION_PATTERNS = (
    r"\b(?:market|muster|parade|public|town|village) (?:field|ground|plaza|square)\b",
    r"\b(?:courtyard|marketplace|open field|public plaza)\b",
)
_SUBMERGED_ROLE_PATTERNS = (
    r"\b(?:ambush|ambushes|attack|attacks|hunt|hunts|hunting|live|lives|move|moves|"
    r"operate|operates|pursue|pursues|remain|remains)\b[^.]{0,100}"
    r"\b(?:fully )?(?:submerged|underwater)\b",
    r"\b(?:fully )?(?:submerged|underwater)\b[^.]{0,100}"
    r"\b(?:ambush|ambushes|attack|attacks|hunt|hunts|hunting|move|moves|"
    r"operate|operates|pursue|pursues)\b",
)
_VIBRATION_ROLE_PATTERNS = (
    r"\b(?:detect|detects|find|finds|hunt|hunts|locate|locates|sense|senses|track|"
    r"tracks)\b[^.]{0,100}\b(?:tremorsense|vibrations?)\b",
    r"\b(?:tremorsense|vibrations?)\b[^.]{0,100}\b(?:detect|detects|find|finds|"
    r"hunt|hunts|locate|locates|sense|senses|track|tracks)\b",
)


def _semantic_text(value: Any) -> str:
    parts: List[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return " ".join(parts).casefold()


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def classify_beat_scene_scale(beat: Dict[str, Any]) -> str:
    """Classify only explicit scene-scale language; ambiguity is unclassified."""
    text = _semantic_text(
        [
            beat.get("title", ""),
            beat.get("purpose", ""),
            beat.get("playerApproaches", []),
            beat.get("consequences", []),
        ]
    )
    if _matches_any(text, _AREA_MASS_BEAT_PATTERNS):
        return "area_mass"
    if _matches_any(text, _CONFINED_BEAT_PATTERNS):
        return "confined"
    if _matches_any(text, _SITE_BEAT_PATTERNS):
        return "site"
    return "unclassified"


def classify_location_scene_scale(
    role: Dict[str, Any], area: Dict[str, Any], outline_area: Dict[str, Any]
) -> str:
    """Classify a location role without treating danger or broad area as capacity."""
    role_text = _semantic_text(
        [role.get("name", ""), role.get("type", ""), role.get("storyPurpose", "")]
    )
    confined = _matches_any(role_text, _CONFINED_LOCATION_PATTERNS)
    large = _matches_any(role_text, _AREA_MASS_LOCATION_PATTERNS)
    site = _matches_any(role_text, _SITE_LOCATION_PATTERNS)
    if sum((confined, large, site)) > 1:
        return "unclassified"
    if confined:
        return "confined"
    if large:
        return "area_mass"
    if site:
        return "site"

    # Broad area context is evidence only when the role itself declares that it
    # is public/open/complex. It never upgrades a named cell or shack.
    if re.search(r"\b(?:complex|open|public)\b", role_text):
        context = _semantic_text(
            [
                area.get("areaType", ""),
                outline_area.get("environment", ""),
            ]
        )
        if re.search(r"\b(?:city|district|settlement|town|village)\b", context):
            return "site"
    return "unclassified"


def classify_unrepresentable_creature_role(brief: Mapping[str, Any]) -> List[str]:
    """Name only explicit role dependencies absent from the frozen monster shape."""
    text = _semantic_text([brief.get("concept", ""), brief.get("storyRole", "")])
    requirements = []
    if _matches_any(text, _SUBMERGED_ROLE_PATTERNS):
        requirements.append("submerged_movement")
    if _matches_any(text, _VIBRATION_ROLE_PATTERNS):
        requirements.append("unsupported_special_sense")
    return requirements


def looks_plural_creature_reference(name: str) -> bool:
    """Catch ordinary plural keys without pretending to be a full inflector."""
    words = re.findall(r"[A-Za-z]+", name)
    if not words:
        return False
    word = words[-1].casefold()
    if word in {"species", "series", "gas", "glass", "moss", "grass", "chaos"}:
        return False
    if word.endswith(("ss", "us", "is")):
        return False
    return word.endswith(
        ("ies", "ves", "ches", "shes", "xes", "zes", "ses")
    ) or word.endswith("s")


def semantic_outline_checks(
    outline: Dict[str, Any],
    seed: Dict[str, Any],
    blocklist: Iterable[str],
) -> Dict[str, Any]:
    """Check the model-authored graph and trusted seed constraints."""
    require_ascii(outline, "outline")
    truth_ids = unique_values(outline["truthLog"], "id", "truth IDs")
    area_ids = set(unique_values(outline["areas"], "roleId", "area role IDs"))
    beat_ids = set(unique_values(outline["beats"], "id", "beat IDs"))
    unique_values(outline["sideThreads"], "id", "side-thread IDs")
    if len(area_ids) != seed["moduleControls"]["numAreas"]:
        raise ValueError("outline area count differs from module controls")
    if not any(beat["isCrescendo"] for beat in outline["beats"]):
        raise ValueError("outline declares no crescendo")
    if outline["beats"][0]["prerequisites"]:
        raise ValueError("outline entry beat must have no prerequisites")
    reachable = {beat["id"] for beat in outline["beats"] if not beat["prerequisites"]}
    for beat in outline["beats"]:
        if beat["areaRoleId"] not in area_ids:
            raise ValueError(f"{beat['id']} references an unknown area")
        unknown = set(beat["prerequisites"]) - beat_ids
        if unknown or beat["id"] in beat["prerequisites"]:
            raise ValueError(f"{beat['id']} has invalid prerequisites")
    changed = True
    while changed:
        changed = False
        for beat in outline["beats"]:
            if beat["id"] not in reachable and set(beat["prerequisites"]).issubset(
                reachable
            ):
                reachable.add(beat["id"])
                changed = True
    if reachable != beat_ids:
        raise ValueError(f"unreachable/cyclic beats: {sorted(beat_ids - reachable)}")
    successors = {beat_id: set() for beat_id in beat_ids}
    for beat in outline["beats"]:
        for prerequisite in beat["prerequisites"]:
            successors[prerequisite].add(beat["id"])
    final_beat_id = outline["beats"][-1]["id"]
    progression_issues = []
    for beat in outline["beats"]:
        beat_successors = successors[beat["id"]]
        if beat["optionalTerminal"]:
            if beat_successors:
                progression_issues.append(
                    {
                        "invariant": "optional_terminal_has_successor",
                        "offending": json.dumps(
                            {
                                "beatId": beat["id"],
                                "successors": sorted(beat_successors),
                            },
                            ensure_ascii=True,
                            sort_keys=True,
                        ),
                        "expectation": (
                            "optional-terminal beats must not unlock a later beat"
                        ),
                    }
                )
        elif beat["id"] != final_beat_id and not beat_successors:
            progression_issues.append(
                {
                    "invariant": "non_final_successor",
                    "offending": json.dumps(
                        {"beatId": beat["id"]},
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                    "expectation": (
                        "every non-final beat needs a successor or explicit "
                        "optionalTerminal"
                    ),
                }
            )
    if progression_issues:
        raise SemanticCorrectionError(progression_issues)
    unknown_thread_anchors = [
        thread["anchorBeatId"]
        for thread in outline["sideThreads"]
        if thread["anchorBeatId"] not in beat_ids
    ]
    if unknown_thread_anchors:
        raise ValueError(
            f"side threads reference unknown anchor beats: {unknown_thread_anchors}"
        )
    blocked = unexpected_blocklist_terms(
        _outline_identity_fields(outline), seed, blocklist
    )
    if blocked:
        raise ValueError(f"outline introduced blocklisted priors: {blocked}")
    plural = [
        brief["name"]
        for brief in outline["creatureBriefs"]
        if looks_plural_creature_reference(brief["name"])
    ]
    if plural:
        raise ValueError(f"creature reference names must be singular: {plural}")
    creature_names: Dict[str, str] = {}
    role_issues = []
    for index, brief in enumerate(outline["creatureBriefs"]):
        name = brief["name"].strip()
        name_key = name.casefold()
        if name_key in creature_names:
            raise ValueError(
                f"duplicate creature brief names: {creature_names[name_key]!r}, {name!r}"
            )
        creature_names[name_key] = name
        requirements = classify_unrepresentable_creature_role(brief)
        if requirements:
            role_issues.append(
                {
                    "invariant": "unsupported_creature_role",
                    "offending": json.dumps(
                        {"creatureIndex": index, "requirements": requirements},
                        ensure_ascii=True,
                        sort_keys=True,
                    ),
                    "expectation": (
                        "preserve the story purpose but remove dependence on movement or "
                        "senses the frozen monster format cannot represent"
                    ),
                }
            )
    if role_issues:
        raise SemanticCorrectionError(role_issues)
    return {
        "truthCount": len(truth_ids),
        "areaCount": len(area_ids),
        "beatCount": len(beat_ids),
        "reachableBeatCount": len(reachable),
        "crescendoCount": sum(bool(item["isCrescendo"]) for item in outline["beats"]),
        "sideThreadCount": len(outline["sideThreads"]),
        "creatureBriefCount": len(outline["creatureBriefs"]),
        "creatureRoleCompatibilityCheckedCount": len(outline["creatureBriefs"]),
        "unsupportedCreatureRoleCount": 0,
    }


def semantic_area_binding_checks(
    binding: Dict[str, Any], seed: Dict[str, Any], outline: Dict[str, Any]
) -> Dict[str, Any]:
    """Check reciprocal/reachable location and area graphs plus beat coverage."""
    issues = []

    def add(invariant: str, offending: Any, expectation: str) -> None:
        issues.append(
            {
                "invariant": invariant,
                "offending": json.dumps(offending, ensure_ascii=True, sort_keys=True),
                "expectation": expectation,
            }
        )

    try:
        require_ascii(binding, "area binding")
    except ValueError:
        add("ascii_only", "non-ASCII text", "use standard ASCII text only")

    expected_areas = {area["roleId"] for area in outline["areas"]}
    outline_areas = {area["roleId"]: area for area in outline["areas"]}
    outline_beats = {beat["id"]: beat for beat in outline["beats"]}
    area_values = [area["areaRoleId"] for area in binding["areas"]]
    actual_areas = set(area_values)
    if len(area_values) != len(actual_areas):
        add(
            "unique_area_roles",
            area_values,
            "each accepted area role ID must appear exactly once",
        )
    if actual_areas != expected_areas:
        add(
            "accepted_area_roles",
            {"actual": sorted(actual_areas), "expected": sorted(expected_areas)},
            "area roles differ from accepted outline; use the exact accepted IDs",
        )
    expected_beats = {beat["id"] for beat in outline["beats"]}
    assigned = set()
    roles_by_area: Dict[str, set] = {}
    role_values_by_area: Dict[str, Dict[str, Dict[str, Any]]] = {}
    edge_count = 0
    grid_embedded_area_count = 0
    for area in binding["areas"]:
        area_id = area["areaRoleId"]
        outline_area = outline_areas.get(area_id)
        if (
            outline_area is not None
            and area["dangerLevel"] != outline_area["dangerBand"]
        ):
            add(
                "accepted_danger_band",
                {
                    "areaRoleId": area_id,
                    "actual": area["dangerLevel"],
                    "expected": outline_area["dangerBand"],
                },
                "dangerLevel must exactly preserve the accepted outline dangerBand",
            )
        roles = area["locationRoles"]
        if len(roles) != seed["moduleControls"]["locationsPerArea"]:
            add(
                "location_count",
                {"areaRoleId": area_id, "actual": len(roles)},
                "use exactly the module-controls locationsPerArea count",
            )
        role_keys = [role["roleKey"] for role in roles]
        keys = set(role_keys)
        if len(role_keys) != len(keys):
            add(
                "unique_location_roles",
                {"areaRoleId": area_id, "roleKeys": role_keys},
                "each roleKey must be unique within its area",
            )
        roles_by_area[area_id] = keys
        role_values_by_area[area_id] = {role["roleKey"]: role for role in roles}
        adjacency = {role["roleKey"]: set(role["connections"]) for role in roles}
        for key, targets in adjacency.items():
            if key in targets or not targets.issubset(keys):
                add(
                    "valid_local_connections",
                    {
                        "areaRoleId": area_id,
                        "roleKey": key,
                        "connections": sorted(targets),
                    },
                    "connections must reference other roleKeys in the same area",
                )
            for target in targets:
                if target in adjacency and key not in adjacency[target]:
                    add(
                        "reciprocal_local_connections",
                        {"areaRoleId": area_id, "edge": f"{key}->{target}"},
                        "every local connection must appear in both directions",
                    )
        reached = {roles[0]["roleKey"]}
        frontier = list(reached)
        while frontier:
            key = frontier.pop()
            for target in (adjacency.get(key, set()) & keys) - reached:
                reached.add(target)
                frontier.append(target)
        if reached != keys:
            add(
                "reachable_local_graph",
                {"areaRoleId": area_id, "unreachable": sorted(keys - reached)},
                "every location role in the area must be reachable",
            )
        try:
            compile_grid_embedding(adjacency)
            grid_embedded_area_count += 1
        except GraphEmbeddingError as exc:
            named_edges = [f"{source}-{target}" for source, target in exc.edges[:12]]
            expectation = (
                "simplify the reciprocal local graph so deterministic grid search "
                "completes within its fixed state budget"
                if exc.reason == "search_budget_exhausted"
                else "use reciprocal local connections that the completed search can "
                "embed on an orthogonal grid without false passages"
            )
            add(
                "grid_embeddable_local_graph",
                {
                    "areaRoleId": area_id,
                    "reason": exc.reason,
                    "edges": named_edges,
                },
                expectation,
            )
        edge_count += sum(map(len, adjacency.values())) // 2
        for role in roles:
            beat_ids = set(role["beatIds"])
            unknown = beat_ids - expected_beats
            if unknown:
                add(
                    "known_role_beats",
                    {"roleKey": role["roleKey"], "unknown": sorted(unknown)},
                    "role beatIds must come from the accepted outline",
                )
            assigned.update(beat_ids)
    if assigned != expected_beats:
        add(
            "beat_assignment_coverage",
            {
                "missing": sorted(expected_beats - assigned),
                "unknown": sorted(assigned - expected_beats),
            },
            "unbound beats must be assigned; bind every accepted beat at least once",
        )
    anchors = [anchor["beatId"] for anchor in binding["beatAnchors"]]
    if len(anchors) != len(set(anchors)):
        add(
            "unique_beat_anchors",
            anchors,
            "each accepted beat must have exactly one canonical anchor",
        )
    if set(anchors) != expected_beats:
        add(
            "beat_anchor_coverage",
            {
                "missing": sorted(expected_beats - set(anchors)),
                "unknown": sorted(set(anchors) - expected_beats),
            },
            "beat anchors differ from accepted beats; anchor every accepted beat once",
        )
    area_mass_count = 0
    confined_anchor_count = 0
    scale_checked_count = 0
    for anchor in binding["beatAnchors"]:
        area_id = anchor["areaRoleId"]
        role_key = anchor["roleKey"]
        if area_id not in roles_by_area or role_key not in roles_by_area[area_id]:
            add(
                "known_anchor_role",
                anchor,
                "every beat anchor must reference a declared role in its accepted area",
            )
            continue
        role = role_values_by_area[area_id][role_key]
        if anchor["beatId"] not in role["beatIds"]:
            add(
                "anchor_role_claim",
                anchor,
                "the anchor role's beatIds must include the anchored beat",
            )
        beat = outline_beats.get(anchor["beatId"])
        outline_area = outline_areas.get(area_id)
        if beat is None or outline_area is None:
            continue
        beat_scale = classify_beat_scene_scale(beat)
        location_scale = classify_location_scene_scale(
            role,
            next(item for item in binding["areas"] if item["areaRoleId"] == area_id),
            outline_area,
        )
        if beat_scale != "unclassified" or location_scale != "unclassified":
            scale_checked_count += 1
        if beat_scale == "area_mass":
            area_mass_count += 1
        if location_scale == "confined":
            confined_anchor_count += 1
        if beat_scale == "area_mass" and location_scale == "confined":
            add(
                "beat_location_scale",
                {
                    "beatId": anchor["beatId"],
                    "areaRoleId": area_id,
                    "roleKey": role_key,
                    "beatScale": beat_scale,
                    "locationScale": location_scale,
                },
                "area-scale beats require a physically usable public, open, or complex anchor",
            )
    adjacency = {area: set() for area in actual_areas}
    physical: set[Tuple[Tuple[str, str], Tuple[str, str]]] = set()
    area_pairs = set()
    for link in binding["crossAreaLinks"]:
        source, target = link["fromAreaRoleId"], link["toAreaRoleId"]
        if (
            source == target
            or source not in roles_by_area
            or target not in roles_by_area
        ):
            add(
                "valid_cross_area_link",
                {
                    "fromAreaRoleId": source,
                    "fromRoleKey": link["fromRoleKey"],
                    "toAreaRoleId": target,
                    "toRoleKey": link["toRoleKey"],
                },
                "a cross-area link must join two different accepted areas",
            )
            continue
        if (
            link["fromRoleKey"] not in roles_by_area[source]
            or link["toRoleKey"] not in roles_by_area[target]
        ):
            add(
                "known_cross_area_roles",
                {
                    "fromAreaRoleId": source,
                    "fromRoleKey": link["fromRoleKey"],
                    "toAreaRoleId": target,
                    "toRoleKey": link["toRoleKey"],
                },
                "cross-area endpoints must reference declared roleKeys",
            )
            continue
        endpoints = tuple(
            sorted(((source, link["fromRoleKey"]), (target, link["toRoleKey"])))
        )
        pair = tuple(sorted((source, target)))
        if endpoints in physical or pair in area_pairs:
            add(
                "single_cross_area_passage",
                {"areaPair": list(pair), "endpoints": list(endpoints)},
                "declare one undirected passage per connected area pair, not reciprocal entries",
            )
            continue
        physical.add(endpoints)
        area_pairs.add(pair)
        adjacency[source].add(target)
        adjacency[target].add(source)
    reached = {next(iter(actual_areas))} if actual_areas else set()
    frontier = list(reached)
    while frontier:
        for target in adjacency[frontier.pop()] - reached:
            reached.add(target)
            frontier.append(target)
    if reached != actual_areas:
        add(
            "connected_area_graph",
            {"unreachable": sorted(actual_areas - reached)},
            "the undirected cross-area passage graph must connect every area",
        )
    if issues:
        raise SemanticCorrectionError(issues)
    return {
        "areaCount": len(actual_areas),
        "locationCount": sum(len(a["locationRoles"]) for a in binding["areas"]),
        "edgeCount": edge_count,
        "gridEmbeddedAreaCount": grid_embedded_area_count,
        "crossAreaLinkCount": len(physical),
        "assignedBeatCount": len(assigned),
        "areaMassBeatCount": area_mass_count,
        "confinedAnchorCount": confined_anchor_count,
        "sceneScaleCheckedCount": scale_checked_count,
    }


def validate_compiled_world(
    areas: List[Dict[str, Any]],
    maps: List[Dict[str, Any]],
    beat_locations: Dict[str, str],
    map_schema: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate deterministic binding outputs and every publishable map.

    Area locations are trusted stubs at this boundary, not publishable location files;
    the frozen location schema is applied after T026 fills their required content.
    """
    if len(areas) != len(maps):
        raise ValueError("compiled area/map cardinality differs")
    location_ids = []
    expected_beats = set(beat_locations)
    actual_beats = set()
    for area, area_map in zip(areas, maps):
        jsonschema.validate(area_map, map_schema)
        locations = area["locations"]
        if len(locations) != area_map["totalRooms"]:
            raise ValueError("compiled map room count differs from area")
        by_id = {location["locationId"]: location for location in locations}
        if len(by_id) != len(locations):
            raise ValueError("compiled location IDs are not unique")
        rooms = {room["id"]: room for room in area_map["rooms"]}
        if set(rooms) != set(by_id):
            raise ValueError("compiled map IDs differ from area location IDs")
        layout_positions = {}
        layout = area_map["layout"]
        if (
            not layout
            or not layout[0]
            or any(len(row) != len(layout[0]) for row in layout)
        ):
            raise ValueError("compiled map layout must be a non-empty rectangle")
        for y, row in enumerate(layout, 1):
            for x, cell in enumerate(row, 1):
                if cell == "   ":
                    continue
                if cell in layout_positions:
                    raise ValueError("compiled map layout repeats a room")
                layout_positions[cell] = (x, y)
        if set(layout_positions) != set(rooms):
            raise ValueError("compiled map layout rooms differ from room records")
        for room_id, room in rooms.items():
            match = re.fullmatch(r"X([0-9]+)Y([0-9]+)", room["coordinates"])
            if (
                match is None
                or tuple(map(int, match.groups())) != layout_positions[room_id]
            ):
                raise ValueError("compiled map coordinate differs from layout")
        room_ids = sorted(rooms)
        for index, source in enumerate(room_ids):
            for target in room_ids[index + 1 :]:
                left = layout_positions[source]
                right = layout_positions[target]
                adjacent = abs(left[0] - right[0]) + abs(left[1] - right[1]) == 1
                connected = target in rooms[source]["connections"]
                if adjacent != connected:
                    raise ValueError(
                        "compiled map layout differs from connectivity graph"
                    )
        for location_id, location in by_id.items():
            if set(location["connectivity"]) != set(rooms[location_id]["connections"]):
                raise ValueError("compiled map connectivity differs from area")
            if not set(location["connectivity"]).issubset(by_id):
                raise ValueError("compiled area has an unknown local connection")
            actual_beats.update(location["beatIds"])
        location_ids.extend(by_id)
    known_locations = set(location_ids)
    if len(known_locations) != len(location_ids):
        raise ValueError("compiled location IDs collide across areas")
    if actual_beats != expected_beats:
        raise ValueError("compiled beat assignments differ from anchors")
    if not set(beat_locations.values()).issubset(known_locations):
        raise ValueError("compiled beat anchor uses an unknown location")
    for area in areas:
        for location in area["locations"]:
            destinations = location["areaConnectivityId"]
            if not set(destinations).issubset(known_locations):
                raise ValueError("compiled cross-area destination is unknown")
    return {
        "compiledAreaCount": len(areas),
        "compiledMapCount": len(maps),
        "compiledLocationCount": len(location_ids),
        "compiledBeatAnchorCount": len(beat_locations),
        "frozenMapSchemaValidatedCount": len(maps),
        "graphTrueMapCount": len(maps),
    }


TRUSTED_LOCATION_FIELDS = (
    "locationId",
    "name",
    "type",
    "coordinates",
    "connectivity",
    "areaConnectivity",
    "areaConnectivityId",
    "dangerLevel",
)

_PUBLIC_RUNTIME_REFERENCE = re.compile(r"\b(?:PP|SQ|B|S)[0-9]{3}\b")
_KEY_LITERAL_CONVENTION = re.compile(
    r"(?i)^(?:key|passphrase|answer|cycle tag|ritual phrase):\s*(\S(?:.*\S)?)$"
)
_GENERIC_KEY_LITERAL = re.compile(
    r"(?i)\b(?:active|appropriate|correct|corresponding|current|matching|proper|"
    r"required|right|tbd|unknown)\b"
)
_PUBLIC_LOCATION_CONTENT_FIELDS = (
    "name",
    "description",
    "dmInstructions",
    "accessibility",
    "npcs",
    "monsters",
    "plotHooks",
    "lootTable",
    "traps",
    "features",
    "dcChecks",
)


def _public_text(value: Any) -> str:
    parts: List[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            parts.append(item)

    visit(value)
    return " ".join(parts)


def _contains_exact_literal(text: str, literal: str) -> bool:
    normalized_text = " ".join(text.casefold().split())
    normalized_literal = " ".join(literal.casefold().split())
    return bool(
        normalized_literal
        and re.search(rf"(?<!\w){re.escape(normalized_literal)}(?!\w)", normalized_text)
    )


def validate_public_candidate_references_and_keys(
    areas: Iterable[Mapping[str, Any]],
    plot: Mapping[str, Any],
    entry_location_id: str,
) -> Dict[str, Any]:
    """Block objective reference failures and report prose concerns as advisories.

    The frozen door shape has no destination or edge ID. Key reachability therefore
    cannot prove which edge a door blocks or that agentic narration cannot resolve it.
    Door-literal findings and leaked private authoring IDs are consequently advisory.
    A PPxxx/SQxxx reference to no published object remains an objective blocker.
    """
    area_values = list(areas)
    locations = {
        location["locationId"]: location
        for area in area_values
        for location in area["locations"]
    }
    points = list(plot.get("plotPoints", ()))
    known_plot_ids = {
        point.get("id")
        for point in points
        if isinstance(point, Mapping) and isinstance(point.get("id"), str)
    }
    known_quest_ids = {
        quest.get("id")
        for point in points
        if isinstance(point, Mapping)
        for quest in point.get("sideQuests", ())
        if isinstance(quest, Mapping) and isinstance(quest.get("id"), str)
    }
    known_public_ids = known_plot_ids | known_quest_ids
    blocking_issues: List[Dict[str, str]] = []
    advisories: List[Dict[str, str]] = []

    def add(target, invariant: str, offending: Any, expectation: str) -> None:
        if len(target) >= 24:
            return
        target.append(
            {
                "invariant": invariant,
                "offending": json.dumps(offending, ensure_ascii=True, sort_keys=True),
                "expectation": expectation,
            }
        )

    def scan_references(item: Any, path: str) -> None:
        if len(blocking_issues) >= 24:
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                scan_references(child, f"{path}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                scan_references(child, f"{path}[{index}]")
        elif isinstance(item, str):
            for reference in _PUBLIC_RUNTIME_REFERENCE.findall(item):
                if reference[:2] not in {"PP", "SQ"}:
                    add(
                        advisories,
                        "private_internal_reference",
                        {"path": path, "reference": reference},
                        (
                            "prefer public story language over private Bxxx/Sxxx authoring "
                            "IDs; this is advisory unless agentic play proves a failure"
                        ),
                    )
                elif reference not in known_public_ids:
                    add(
                        blocking_issues,
                        "undefined_public_reference",
                        {"path": path, "reference": reference},
                        "PPxxx/SQxxx references must resolve to a published plot object",
                    )

    scan_references(area_values, "$.areas")
    scan_references(plot, "$.plot")

    graph = {location_id: set() for location_id in locations}
    for location_id, location in locations.items():
        destinations = [
            *location.get("connectivity", ()),
            *location.get("areaConnectivityId", ()),
        ]
        for destination in destinations:
            if destination in graph:
                graph[location_id].add(destination)
                graph[destination].add(location_id)
    distances: Dict[str, int] = {}
    if entry_location_id in graph:
        distances[entry_location_id] = 0
        frontier = [entry_location_id]
        while frontier:
            source = frontier.pop(0)
            for destination in sorted(graph[source]):
                if destination not in distances:
                    distances[destination] = distances[source] + 1
                    frontier.append(destination)

    searchable_text = {
        location_id: _public_text(
            {
                key: location[key]
                for key in _PUBLIC_LOCATION_CONTENT_FIELDS
                if key in location
            }
        )
        for location_id, location in locations.items()
    }
    validated_literals = 0
    unreachable_literals = 0
    for location_id, location in locations.items():
        for door_index, door in enumerate(location.get("doors", ())):
            if not isinstance(door, Mapping) or not door.get("locked"):
                continue
            keyname = door.get("keyname", "")
            if not isinstance(keyname, str) or not keyname.strip():
                continue
            path = f"$.areas.locations[{location_id}].doors[{door_index}].keyname"
            match = _KEY_LITERAL_CONVENTION.fullmatch(keyname.strip())
            if match is None or _GENERIC_KEY_LITERAL.search(
                match.group(1) if match else keyname
            ):
                add(
                    advisories,
                    "riddle_answer_exists",
                    {"locationId": location_id, "path": path},
                    (
                        "use Key:, Passphrase:, Answer:, Cycle tag:, or Ritual "
                        "phrase: followed by one concrete literal, never a generic "
                        "correct/matching/current/active placeholder"
                    ),
                )
                continue
            literal = match.group(1).strip()
            matching_locations = {
                candidate_id
                for candidate_id, text in searchable_text.items()
                if _contains_exact_literal(text, literal)
            }
            if not matching_locations:
                add(
                    advisories,
                    "riddle_answer_exists",
                    {"locationId": location_id, "path": path},
                    "the exact declared literal must appear in public location content",
                )
                continue
            door_distance = distances.get(location_id)
            available = {
                candidate_id
                for candidate_id in matching_locations
                if door_distance is not None
                and candidate_id in distances
                and distances[candidate_id] <= door_distance
            }
            if not available:
                unreachable_literals += 1
                add(
                    advisories,
                    "key_reachability",
                    {
                        "doorLocationId": location_id,
                        "literalLocationIds": sorted(matching_locations),
                    },
                    (
                        "the exact literal must be available in the same location "
                        "or a reachable location no farther from the module entry"
                    ),
                )
                continue
            validated_literals += 1

    if blocking_issues:
        raise SemanticCorrectionError(blocking_issues)
    return {
        "knownPublicReferenceCount": len(known_public_ids),
        "invalidInternalReferenceCount": 0,
        "validatedLockedDoorLiteralCount": validated_literals,
        "unreachableKeyLiteralCount": unreachable_literals,
        "privateInternalReferenceAdvisoryCount": sum(
            item["invariant"] == "private_internal_reference" for item in advisories
        ),
        "lockedDoorAdvisoryCount": sum(
            item["invariant"] in {"riddle_answer_exists", "key_reachability"}
            for item in advisories
        ),
        "advisories": advisories,
    }


def validate_story_first_location_result(
    generated: Dict[str, Any],
    area: Dict[str, Any],
    outline: Dict[str, Any],
    seed: Dict[str, Any],
    blocklist: Iterable[str],
) -> Dict[str, Any]:
    """Enforce story-first invariants around an unchanged accepted T026 batch."""
    expected, actual = area["locations"], generated["locations"]
    if len(actual) != len(expected):
        raise ValueError("T026 changed location count")
    for stub, location in zip(expected, actual):
        for field in TRUSTED_LOCATION_FIELDS:
            if location.get(field) != stub.get(field):
                raise ValueError(
                    f"T026 changed trusted field {stub['locationId']}.{field}"
                )
        if location.get("adventureSummary") != "" or location.get("encounters") != []:
            raise ValueError(f"{stub['locationId']} contains false new-game history")
        if location.get("explorationState") != {"status": "unvisited"}:
            raise ValueError(f"{stub['locationId']} is not initially unvisited")
    require_ascii(generated, "T026 output")
    seed_text = json.dumps(seed, ensure_ascii=True).casefold()
    for location in actual:
        for entity in [*location.get("npcs", []), *location.get("monsters", [])]:
            name = str(entity.get("name", ""))
            for blocked in blocklist:
                pattern = rf"\b{re.escape(str(blocked).casefold())}(?:s|'s)?\b"
                if re.search(pattern, name.casefold()) and not re.search(
                    pattern, seed_text
                ):
                    raise ValueError(
                        f"T026 introduced blocklisted entity in {location['locationId']}"
                    )
    party = {
        str(name).strip().casefold()
        for name in seed.get("campaignContext", {}).get("partyNames", [])
    }
    if any(
        npc.get("name", "").strip().casefold() in party
        for location in actual
        for npc in location.get("npcs", [])
    ):
        raise ValueError("T026 placed a party member in an NPC roster")
    briefs = {brief["name"].strip().casefold() for brief in outline["creatureBriefs"]}
    monsters = [
        monster for location in actual for monster in location.get("monsters", [])
    ]
    if any(
        monster.get("name", "").strip().casefold() not in briefs for monster in monsters
    ):
        raise ValueError("T026 introduced an unbriefed creature")
    if any(looks_plural_creature_reference(monster["name"]) for monster in monsters):
        raise ValueError("T026 used a plural creature reference")
    if any(
        monster["quantity"]["min"] > monster["quantity"]["max"] for monster in monsters
    ):
        raise ValueError("T026 returned inverted creature quantity")
    return {
        "locationCount": len(actual),
        "npcCount": sum(len(item.get("npcs", [])) for item in actual),
        "monsterReferenceCount": len(monsters),
        "trustedFieldDriftCount": 0,
    }


def validate_side_thread_location_projection(
    areas: Iterable[Mapping[str, Any]],
    plot: Mapping[str, Any],
    outline: Mapping[str, Any],
    beat_locations: Mapping[str, str],
    thread_to_quest: Mapping[str, str],
) -> Dict[str, Any]:
    """Prove every compiled side thread exists once in its canonical host."""
    locations = {
        location["locationId"]: location
        for area in areas
        for location in area["locations"]
    }
    quests = {
        quest["id"]: quest
        for point in plot["plotPoints"]
        for quest in point.get("sideQuests", [])
    }
    for thread in outline["sideThreads"]:
        quest_id = thread_to_quest[thread["id"]]
        projection = compile_side_thread_projection(thread, quest_id)
        host_id = beat_locations[thread["anchorBeatId"]]
        quest = quests.get(quest_id)
        if quest is None:
            raise ValueError("compiled side thread is missing from plot")
        if (
            quest["title"] != projection["title"]
            or quest["description"] != projection["description"]
            or quest["involvedLocations"] != [host_id]
        ):
            raise ValueError("compiled side-thread plot projection drifted")
        placements = [
            location_id
            for location_id, location in locations.items()
            if projection["plotHook"] in location["plotHooks"]
        ]
        if placements != [host_id]:
            raise ValueError("canonical side-thread hook is not unique at its host")
    return {
        "canonicalSideThreadHookCount": len(outline["sideThreads"]),
        "sideThreadHostMismatchCount": 0,
    }


def duplicate_npc_placements(
    generated_areas: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    placements: Dict[str, List[str]] = {}
    display_names: Dict[str, str] = {}
    for area in generated_areas:
        for location in area["locations"]:
            for npc in location.get("npcs", []):
                name = npc.get("name", "").strip()
                if not name:
                    continue
                key = name.casefold()
                display_names.setdefault(key, name)
                placements.setdefault(key, []).append(location["locationId"])
    return {
        display_names[key]: location_ids
        for key, location_ids in placements.items()
        if len(location_ids) > 1
    }


def social_monster_overlaps(
    generated_areas: List[Dict[str, Any]],
) -> Dict[str, List[str]]:
    overlaps: Dict[str, List[str]] = {}
    for area in generated_areas:
        for location in area["locations"]:
            npcs = {
                npc["name"].strip().casefold(): npc["name"].strip()
                for npc in location.get("npcs", [])
            }
            monsters = {
                monster["name"].strip().casefold(): monster["name"].strip()
                for monster in location.get("monsters", [])
            }
            for key in sorted(set(npcs) & set(monsters)):
                overlaps.setdefault(location["locationId"], []).append(npcs[key])
    return overlaps


def semantic_plot_checks(
    plot: Dict[str, Any],
    outline: Dict[str, Any],
    areas: List[Dict[str, Any]],
    beat_locations: Dict[str, str],
    beat_to_plot: Dict[str, str],
    thread_to_quest: Dict[str, str],
) -> Dict[str, Any]:
    """Validate trusted plot IDs, graph, locations, quests, and clean state."""
    issues = non_ascii_issues(plot, "plot")

    def add(invariant: str, offending: Any, expectation: str) -> None:
        issues.append(
            {
                "invariant": invariant,
                "offending": json.dumps(offending, ensure_ascii=True, sort_keys=True),
                "expectation": expectation,
            }
        )

    if issues and "plotPoints" not in plot:
        raise SemanticCorrectionError(issues)
    points = plot["plotPoints"]
    point_id_values = [point["id"] for point in points]
    point_ids = set(point_id_values)
    if len(point_id_values) != len(point_ids):
        add(
            "unique_plot_ids",
            point_id_values,
            "each trusted plot-point ID must appear exactly once",
        )
    expected_points = set(beat_to_plot.values())
    if point_ids != expected_points:
        add(
            "trusted_plot_ids",
            {
                "missing": sorted(expected_points - point_ids),
                "unknown": sorted(point_ids - expected_points),
            },
            "plot IDs differ from trusted mapping; use every supplied ID exactly once",
        )
    point_by_id = {point["id"]: point for point in points}
    plot_to_beat = {plot_id: beat_id for beat_id, plot_id in beat_to_plot.items()}
    valid_locations = {
        location["locationId"] for area in areas for location in area["locations"]
    }
    expected_forward = {plot_id: set() for plot_id in expected_points}
    for beat in outline["beats"]:
        current = beat_to_plot[beat["id"]]
        for prerequisite in beat["prerequisites"]:
            expected_forward[beat_to_plot[prerequisite]].add(current)
    optional_terminal_ids = []
    final_beat_id = outline["beats"][-1]["id"]
    for beat in outline["beats"]:
        point_id = beat_to_plot[beat["id"]]
        successors = expected_forward[point_id]
        if beat["optionalTerminal"]:
            optional_terminal_ids.append(point_id)
            if successors:
                add(
                    "optional_terminal_has_successor",
                    {
                        "plotPointId": point_id,
                        "successors": sorted(successors),
                    },
                    "optional-terminal beats must not unlock a later plot point",
                )
        elif beat["id"] != final_beat_id and not successors:
            add(
                "non_final_successor",
                {"plotPointId": point_id, "beatId": beat["id"]},
                "every non-final beat needs a successor or explicit optionalTerminal",
            )
    for point_id, point in point_by_id.items():
        beat_id = plot_to_beat.get(point_id)
        if beat_id is None:
            continue
        expected_location = beat_locations[beat_id]
        if point["location"] != expected_location:
            add(
                "trusted_plot_location",
                {
                    "plotPointId": point_id,
                    "actual": point["location"],
                    "expected": expected_location,
                },
                "each plot point must keep its supplied canonical location",
            )
        if point["location"] not in valid_locations:
            add(
                "known_plot_location",
                {"plotPointId": point_id, "location": point["location"]},
                "plot locations must be declared compiled location IDs",
            )
        if point["status"] != "not started" or point["plotImpact"] != "":
            add(
                "clean_plot_state",
                {
                    "plotPointId": point_id,
                    "status": point["status"],
                    "plotImpactEmpty": point["plotImpact"] == "",
                },
                "new plot points require status 'not started' and empty plotImpact",
            )
        if set(point["nextPoints"]) != expected_forward[point_id]:
            add(
                "trusted_plot_edges",
                {
                    "plotPointId": point_id,
                    "actual": sorted(set(point["nextPoints"])),
                    "expected": sorted(expected_forward[point_id]),
                },
                "nextPoints must exactly match the supplied prerequisite graph",
            )
    roots = {
        beat_to_plot[beat["id"]]
        for beat in outline["beats"]
        if not beat["prerequisites"]
    }
    reached = set(roots)
    frontier = list(roots)
    while frontier:
        point_id = frontier.pop()
        if point_id not in point_by_id:
            continue
        for target in point_by_id[point_id]["nextPoints"]:
            if target not in point_by_id:
                continue
            if target not in reached:
                reached.add(target)
                frontier.append(target)
    if reached != expected_points:
        add(
            "reachable_plot_graph",
            {"unreachable": sorted(expected_points - reached)},
            "runtime plot graph must make every trusted plot point reachable",
        )
    quest_ids = []
    threads_by_quest = {
        thread_to_quest[thread["id"]]: thread for thread in outline["sideThreads"]
    }
    for point in points:
        for quest in point.get("sideQuests", []):
            quest_ids.append(quest["id"])
            thread = threads_by_quest.get(quest["id"])
            if thread is not None:
                projection = compile_side_thread_projection(thread, quest["id"])
                expected_host = beat_locations[thread["anchorBeatId"]]
                if (
                    quest["title"] != projection["title"]
                    or quest["description"] != projection["description"]
                    or quest["involvedLocations"] != [expected_host]
                ):
                    add(
                        "compiled_side_quest_projection",
                        {"sideQuestId": quest["id"]},
                        "side-quest prose and host must match the accepted thread projection",
                    )
            if quest["status"] != "not started" or quest["plotImpact"] != "":
                add(
                    "clean_side_quest_state",
                    {
                        "sideQuestId": quest["id"],
                        "status": quest["status"],
                        "plotImpactEmpty": quest["plotImpact"] == "",
                    },
                    "new side quests require status 'not started' and empty plotImpact",
                )
            if not set(quest["involvedLocations"]).issubset(valid_locations):
                add(
                    "known_side_quest_locations",
                    {
                        "sideQuestId": quest["id"],
                        "unknown": sorted(
                            set(quest["involvedLocations"]) - valid_locations
                        ),
                    },
                    "side-quest locations must be declared compiled location IDs",
                )
    if len(quest_ids) != len(set(quest_ids)):
        add(
            "unique_side_quest_ids",
            quest_ids,
            "each supplied side-quest ID must appear exactly once",
        )
    if set(quest_ids) != set(thread_to_quest.values()):
        expected_quests = set(thread_to_quest.values())
        add(
            "accepted_side_quests",
            {
                "missing": sorted(expected_quests - set(quest_ids)),
                "unknown": sorted(set(quest_ids) - expected_quests),
            },
            "side quests differ from accepted threads; use every supplied ID exactly once",
        )
    if issues:
        raise SemanticCorrectionError(issues)
    return {
        "plotPointCount": len(points),
        "sideQuestCount": len(quest_ids),
        "rootCount": len(roots),
        "reachablePlotPointCount": len(reached),
        "crescendoPlotPointIds": [
            beat_to_plot[beat["id"]] for beat in outline["beats"] if beat["isCrescendo"]
        ],
        "optionalTerminalPlotPointIds": optional_terminal_ids,
    }


# ---------------------------------------------------------------------------
# Cross-area route agreement (Item B) -- REPORT-ONLY.
#
# Confirms the physical cross-area connections written into the area files agree
# with the story route the unified plot (T028) implies, using the code-owned
# gateway-endpoint contract from module_builder._create_bidirectional_connection
# (source area's LAST location <-> destination area's FIRST location, reciprocal).
#
# This function NEVER raises and NEVER mutates -- it returns a list of
# human-readable finding strings for logging. Escalation to fail-loud is deferred
# until it runs clean on real linear/hub/branch/revisit/dial-down builds. Bare
# area reachability is intentionally NOT used: cross-area edges are bidirectional,
# so a wrong-direction link would look "reachable" either way.
# ---------------------------------------------------------------------------

def _route_area_of(loc_id, loc_to_area):
    return loc_to_area.get(loc_id)


def validate_plot_route_agreement(areas_by_id, plot):
    """Report-only check that physical cross-area links match the plot route.

    areas_by_id: {area_id: area_dict}  (each with 'areaName' and 'locations')
    plot:        unified module plot dict (plotPoints[].location = area IDs)
    Returns: List[str] findings ([] means agreement). Never raises.
    """
    findings = []
    try:
        if not isinstance(areas_by_id, dict) or not isinstance(plot, dict):
            return ["route: invalid inputs (areas_by_id/plot not dicts)"]
        valid_areas = set(areas_by_id)
        points = plot.get("plotPoints") or []

        # location -> area, and per-area first/last gateway locations
        loc_to_area = {}
        first_loc = {}
        last_loc = {}
        area_name = {}
        for aid, area in areas_by_id.items():
            area_name[aid] = area.get("areaName")
            locs = area.get("locations") or []
            for L in locs:
                lid = L.get("locationId")
                if lid:
                    loc_to_area[lid] = aid
            ids = [L.get("locationId") for L in locs if L.get("locationId")]
            if ids:
                first_loc[aid] = ids[0]
                last_loc[aid] = ids[-1]

        # ---- expected edges from the SHARED nextPoints-aware extractor -----
        # (159-C) Same source of truth as the classic finalizer, so detector and
        # finalizer agree by construction. nextPoints is authoritative; adjacency
        # is a fallback only for a zero-usable-edge plot -- NOT a union with the
        # nextPoints graph (a union invents sibling edges in a branched plot).
        from core.generators.plot_route import extract_plot_route
        route = extract_plot_route(areas_by_id, plot)
        directed = list(route["edges"])
        plot_areas = set(route["plot_areas"])

        # ---- healing + coverage -------------------------------------------
        # A plot-REFERENCED area left unreachable by partial nextPoints coverage is
        # HEALED (the finalizer adds the plot-order connection); report it as info,
        # not a defect -- a module is always produced and fully connected.
        if route.get("healed_edges"):
            findings.append(
                "route/healed: added %d plot-order connection(s) %s so every "
                "plot-referenced area is reachable (nextPoints left a gap)"
                % (len(route["healed_edges"]), route["healed_edges"])
            )
        # Generated-but-not-plot-referenced coverage is the separate plot-free
        # question (report-only pending the structural designation).
        uncovered = sorted(valid_areas - plot_areas)
        if uncovered:
            findings.append(
                "route/coverage: area(s) %s are generated but never referenced by the plot "
                "(possible missing plot coverage or an intentional plot-free area)" % uncovered
            )
        if len(valid_areas) >= 2 and len(plot_areas) < 2:
            findings.append(
                "route/fallback: multi-area module (%d areas) but the plot references < 2 areas -- "
                "cross-area linking would fall back to alphabetical order (unverified route)"
                % len(valid_areas)
            )

        # undirected physical cross-area link set: {frozenset(area_a, area_b): {(src_loc, dst_loc)}}
        def _cross_links():
            out = {}
            for aid, area in areas_by_id.items():
                for L in (area.get("locations") or []):
                    lid = L.get("locationId")
                    for tgt in (L.get("areaConnectivityId") or []):
                        ta = loc_to_area.get(tgt)
                        if ta and ta != aid:
                            out.setdefault(frozenset((aid, ta)), set()).add((lid, tgt))
            return out

        phys = _cross_links()

        # ---- B1: every plot-connected area PAIR realized at a code-owned gateway,
        # reciprocal. Collapse to UNDIRECTED pairs because the cross-area door is
        # bidirectional and finalize writes ONE link per pair (a plot that goes
        # A->B and later B->A shares the same physical door). Accept EITHER
        # code-owned orientation: last(A)<->first(B) OR last(B)<->first(A).
        expected_pairs = []
        seen_undirected = set()
        for a, b in directed:
            u = frozenset((a, b))
            if u not in seen_undirected:
                seen_undirected.add(u)
                expected_pairs.append((a, b))

        def _reciprocal_gateway(gateway, links):
            src, dst = gateway
            return src is not None and dst is not None and (src, dst) in links and (dst, src) in links

        for a, b in expected_pairs:
            pair = frozenset((a, b))
            if pair not in phys:
                findings.append(
                    "route/missing: plot connects %s<->%s but no physical cross-area link exists"
                    % (a, b)
                )
                continue
            links = phys[pair]
            gateway_ab = (last_loc.get(a), first_loc.get(b))
            gateway_ba = (last_loc.get(b), first_loc.get(a))
            if not (_reciprocal_gateway(gateway_ab, links) or _reciprocal_gateway(gateway_ba, links)):
                findings.append(
                    "route/gateway: plot connects %s<->%s; expected a reciprocal code-owned gateway "
                    "(last<->first: %s or %s) but physical links are %s"
                    % (a, b, gateway_ab, gateway_ba, sorted(links))
                )

        # ---- B3: parallel-array integrity + reciprocity ------------------
        for aid, area in areas_by_id.items():
            for L in (area.get("locations") or []):
                lid = L.get("locationId")
                names = L.get("areaConnectivity") or []
                ids = L.get("areaConnectivityId") or []
                if len(names) != len(ids):
                    findings.append(
                        "route/parallel: %s:%s areaConnectivity(len %d) != areaConnectivityId(len %d)"
                        % (aid, lid, len(names), len(ids))
                    )
                if len(set(ids)) != len(ids):
                    findings.append("route/parallel: %s:%s has duplicate areaConnectivityId targets %s"
                                    % (aid, lid, ids))
                for i, tgt in enumerate(ids):
                    ta = loc_to_area.get(tgt)
                    if ta is None:
                        findings.append("route/parallel: %s:%s target %s resolves to no known location"
                                        % (aid, lid, tgt))
                        continue
                    if ta == aid:
                        findings.append("route/parallel: %s:%s links to its own area (%s)"
                                        % (aid, lid, tgt))
                    if i < len(names) and names[i] != area_name.get(ta):
                        findings.append(
                            "route/parallel: %s:%s name[%d]=%r != target area %s name %r"
                            % (aid, lid, i, names[i], ta, area_name.get(ta))
                        )
                    # reciprocal: target location carries this location's id + this area's name
                    tgt_area = areas_by_id.get(ta) or {}
                    tgt_loc = next((x for x in (tgt_area.get("locations") or [])
                                    if x.get("locationId") == tgt), None)
                    if tgt_loc is not None:
                        back_ids = tgt_loc.get("areaConnectivityId") or []
                        back_names = tgt_loc.get("areaConnectivity") or []
                        if lid not in back_ids:
                            findings.append(
                                "route/reciprocity: %s:%s -> %s but %s does not link back to %s"
                                % (aid, lid, tgt, tgt, lid)
                            )
                        else:
                            j = back_ids.index(lid)
                            if j < len(back_names) and back_names[j] != area_name.get(aid):
                                findings.append(
                                    "route/reciprocity: %s back-link name[%d]=%r != source area %s name %r"
                                    % (tgt, j, back_names[j], aid, area_name.get(aid))
                                )
    except Exception as exc:  # report-only must never break a build
        findings.append("route: detector error (non-fatal): %s" % exc)
    return findings


# ---------------------------------------------------------------------------
# NPC cross-area role/attitude coherence (Item E) -- REPORT-ONLY ADVISORY.
#
# Surfaces same-name NPCs that appear across multiple locations/areas and any
# EXACT attitude differences among their appearances. Never raises, never
# mutates. Role/faction lives only in free-text prose (location NPC entries are
# {name, description, attitude} with NO role field), so role coherence CANNOT be
# decided deterministically -- same attitudes can hide conflicting roles and
# different attitudes can be intentional. This reports coverage/advisory facts
# only; the semantic reconciliation decision (same mobile person / projection /
# intentional change / accidental duplicate) is owned by the agentic pass, not
# by code. Groups by exact casefold name (after T088 name reconciliation).
# ---------------------------------------------------------------------------

def npc_cross_area_coherence_findings(areas_by_id):
    """Report-only advisory: cross-area same-name NPC appearances + attitude
    divergences. areas_by_id: {area_id: area_dict}. Returns List[str]."""
    findings = []
    try:
        if not isinstance(areas_by_id, dict):
            return []
        appearances = {}
        for aid, area in areas_by_id.items():
            for location in (area.get("locations") or []):
                lid = location.get("locationId")
                for npc in (location.get("npcs") or []):
                    name = (npc.get("name") or "").strip()
                    if not name:
                        continue
                    appearances.setdefault(name.casefold(), []).append({
                        "area": aid,
                        "location": lid,
                        "attitude": (npc.get("attitude") or "").strip(),
                        "name": name,
                    })
        for key in sorted(appearances):
            apps = appearances[key]
            if len(apps) < 2:
                continue
            areas_spanned = {a["area"] for a in apps}
            if len(areas_spanned) < 2:
                continue  # same-area duplicates are a separate (placement) concern
            attitudes = {a["attitude"] for a in apps if a["attitude"]}
            display = apps[0]["name"]
            where = ", ".join(
                "%s:%s(%s)" % (a["area"], a["location"], a["attitude"] or "no-attitude")
                for a in apps
            )
            if len(attitudes) > 1:
                findings.append(
                    "npc/role-coherence: '%s' appears in %d areas with DIVERGENT attitudes %s -- %s "
                    "(advisory: mobile person / projection / intentional change / accidental duplicate; "
                    "agentic reconciliation decides -- role is prose, not code-decidable)"
                    % (display, len(areas_spanned), sorted(attitudes), where)
                )
            else:
                findings.append(
                    "npc/role-coherence: '%s' recurs across %d areas (%s) with a consistent attitude "
                    "(advisory: confirm same person or intended recurring figure)"
                    % (display, len(areas_spanned), where)
                )
    except Exception as exc:  # advisory must never break a build
        findings.append("npc/role-coherence: advisory error (non-fatal): %s" % exc)
    return findings
