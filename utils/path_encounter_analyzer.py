"""
Read-only path evidence for location-transition validation.

The transition system used to combine graph metadata with fresh reads of each
area file.  That allowed the route and the evidence shown to the validator to
come from different world states.  This module now takes one immutable snapshot
of the active module and derives every route segment from that snapshot.

This reader intentionally does not use ``LocationGraph``.  Its legacy repair
logic may write connectivity changes while loading data, which is inappropriate
for a validation read.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import deque
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from utils.enhanced_logger import debug, warning


_AREA_FILE_RE = re.compile(r"^[A-Za-z]+\d+\.json$")
_LOCATION_ID_RE = re.compile(r"^[A-Za-z]+\d+$")
_COMPOSITE_CONNECTION_RE = re.compile(r"^([A-Za-z]+\d+)-([A-Za-z]+\d+)$")
_BACKUP_SUFFIXES = ("_BU.json", "_backup.json")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_json_object(path: Path) -> Dict[str, Any]:
    """Read JSON without locks, recovery, repairs, backups, or writes."""
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("area JSON root must be an object")
    return value


def _area_files(module_dir: Path) -> List[Path]:
    """Discover canonical area files with ``areas/`` taking precedence."""
    selected: Dict[str, Path] = {}
    areas_dir = module_dir / "areas"
    if areas_dir.is_dir():
        for path in sorted(areas_dir.iterdir(), key=lambda item: item.name):
            if (
                path.is_file()
                and _AREA_FILE_RE.match(path.name)
                and not path.name.endswith(_BACKUP_SUFFIXES)
            ):
                selected[path.name] = path

    if module_dir.is_dir():
        for path in sorted(module_dir.iterdir(), key=lambda item: item.name):
            if (
                path.is_file()
                and _AREA_FILE_RE.match(path.name)
                and not path.name.endswith(_BACKUP_SUFFIXES)
                and path.name not in selected
            ):
                selected[path.name] = path
    return [selected[name] for name in sorted(selected)]


def _id_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, str) and entry]


def _unique_mapping(items: Iterable[tuple]) -> Dict[str, str]:
    """Return only keys that map unambiguously to one value."""
    values: Dict[str, set] = {}
    for key, value in items:
        if isinstance(key, str) and key:
            values.setdefault(key, set()).add(value)
    return {
        key: next(iter(matches)) for key, matches in values.items() if len(matches) == 1
    }


def _monster_names(monsters: Iterable[Any]) -> List[str]:
    return [
        monster.get("name", "Unknown")
        for monster in monsters
        if isinstance(monster, dict)
    ]


def derive_location_exploration_state(location: Dict[str, Any]) -> Dict[str, Any]:
    """Derive visit state without mutating legacy location data.

    New modules carry the machine-owned ``explorationState.status`` field.
    Older modules fall back to the two historical runtime artifacts: a
    departure adventure summary or a gameplay encounter record. Template
    encounter records without ``encounterId`` do not establish a visit.
    """
    encounters = location.get("encounters", [])
    if not isinstance(encounters, list):
        encounters = []
    has_gameplay_encounter = any(
        isinstance(entry, dict) and "encounterId" in entry
        for entry in encounters
    )
    summary = location.get("adventureSummary", "")
    has_adventure_summary = isinstance(summary, str) and bool(summary.strip())

    explicit = location.get("explorationState")
    if explicit is not None:
        if (
            not isinstance(explicit, dict)
            or set(explicit) != {"status"}
            or explicit.get("status") not in {"unvisited", "visited"}
        ):
            return {
                "valid": False,
                "status": "unknown",
                "visited": False,
                "evidence": ["invalid_exploration_state"],
            }
        status = explicit["status"]
        return {
            "valid": True,
            "status": status,
            "visited": status == "visited",
            "evidence": ["exploration_state"],
        }

    evidence = []
    if has_adventure_summary:
        evidence.append("adventure_summary")
    if has_gameplay_encounter:
        evidence.append("gameplay_encounter")
    return {
        "valid": True,
        "status": "visited" if evidence else "unvisited",
        "visited": bool(evidence),
        "evidence": evidence or ["legacy_no_visit_evidence"],
    }


def _issue(code: str, message: str, **details: Any) -> Dict[str, Any]:
    return {"code": code, "message": message, **details}


def build_active_module_snapshot(
    module_name: str,
    modules_root: Union[str, Path] = "modules",
) -> Dict[str, Any]:
    """Build a canonical, read-only snapshot of one active module.

    The returned dictionaries are detached from the parsed JSON documents.
    Duplicate IDs and dangling connections are retained as validation issues;
    they are never silently repaired or resolved by load order.
    """
    normalized_module = str(module_name or "").replace(" ", "_")
    module_dir = Path(modules_root) / normalized_module
    nodes: Dict[str, Dict[str, Any]] = {}
    areas: Dict[str, Dict[str, Any]] = {}
    edges: Dict[str, List[str]] = {}
    issues: List[Dict[str, Any]] = []
    invalid_location_ids: set[str] = set()
    duplicate_area_ids: set[str] = set()
    canonical_sources: List[Dict[str, Any]] = []

    files = _area_files(module_dir)
    if not files:
        issues.append(
            _issue(
                "no_area_files",
                f"No area files found for active module {normalized_module!r}",
                module=normalized_module,
            )
        )

    for path in files:
        relative_source = path.relative_to(Path(modules_root)).as_posix()
        try:
            area = _read_json_object(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            try:
                source_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                source_digest = "unreadable"
            canonical_sources.append(
                {"source_file": relative_source, "invalid_content_hash": source_digest}
            )
            issues.append(
                _issue(
                    "invalid_area_file",
                    f"Could not read area file {relative_source}: {exc}",
                    source_file=relative_source,
                )
            )
            continue

        # Include every discovered source in snapshot identity, including
        # duplicate definitions rejected below. This lets a durable checkpoint
        # notice any atlas change after restart.
        canonical_sources.append(
            {"source_file": relative_source, "area": copy.deepcopy(area)}
        )

        area_id = area.get("areaId")
        if not isinstance(area_id, str) or not area_id:
            issues.append(
                _issue(
                    "missing_area_id",
                    f"Area file {relative_source} has no valid areaId",
                    source_file=relative_source,
                )
            )
            continue
        if area_id in areas:
            # The first-loaded definition silently wins node registration, so
            # the blemish taints that winner's OWN nodes as invalid (below)
            # instead of failing the whole module or trusting load order.
            duplicate_area_ids.add(area_id)
            issues.append(
                _issue(
                    "duplicate_area_id",
                    f"Area ID {area_id} is defined more than once",
                    area_id=area_id,
                    source_file=relative_source,
                )
            )
            continue

        area_name = area.get("areaName", "Unknown")
        areas[area_id] = {
            "area_id": area_id,
            "area_name": area_name,
            "source_file": relative_source,
        }
        locations = area.get("locations", [])
        if not isinstance(locations, list):
            issues.append(
                _issue(
                    "invalid_locations",
                    f"Area {area_id} locations must be an array",
                    area_id=area_id,
                    source_file=relative_source,
                )
            )
            continue

        for location in locations:
            if not isinstance(location, dict):
                issues.append(
                    _issue(
                        "invalid_location",
                        f"Area {area_id} contains a non-object location",
                        area_id=area_id,
                        source_file=relative_source,
                    )
                )
                continue
            location_id = location.get("locationId")
            if not isinstance(location_id, str) or not _LOCATION_ID_RE.fullmatch(
                location_id
            ):
                issues.append(
                    _issue(
                        "invalid_location_id",
                        f"Area {area_id} has invalid location ID {location_id!r}",
                        area_id=area_id,
                        location_id=location_id,
                        source_file=relative_source,
                    )
                )
                if isinstance(location_id, str) and location_id:
                    invalid_location_ids.add(location_id)
                continue
            if location_id in nodes:
                invalid_location_ids.add(location_id)
                issues.append(
                    _issue(
                        "duplicate_location_id",
                        f"Location ID {location_id} is defined more than once",
                        location_id=location_id,
                        area_id=area_id,
                        source_file=relative_source,
                    )
                )
                continue

            monsters = location.get("monsters", [])
            encounters = location.get("encounters", [])
            if not isinstance(monsters, list):
                monsters = []
                invalid_location_ids.add(location_id)
                issues.append(
                    _issue(
                        "invalid_monsters",
                        f"Location {location_id} monsters must be an array",
                        location_id=location_id,
                    )
                )
            if not isinstance(encounters, list):
                encounters = []
                invalid_location_ids.add(location_id)
                issues.append(
                    _issue(
                        "invalid_encounters",
                        f"Location {location_id} encounters must be an array",
                        location_id=location_id,
                    )
                )

            internal_connections = _id_list(location.get("connectivity"))
            area_connectivity_names = _id_list(location.get("areaConnectivity"))
            area_connectivity_ids = _id_list(location.get("areaConnectivityId"))
            gameplay_encounters = [
                copy.deepcopy(entry)
                for entry in encounters
                if isinstance(entry, dict) and "encounterId" in entry
            ]
            adventure_summary = location.get("adventureSummary", "")
            if not isinstance(adventure_summary, str):
                adventure_summary = str(adventure_summary or "")
            exploration = derive_location_exploration_state(location)
            if exploration["valid"] is not True:
                invalid_location_ids.add(location_id)
                issues.append(
                    _issue(
                        "invalid_exploration_state",
                        f"Location {location_id} has invalid explorationState",
                        location_id=location_id,
                        source_file=relative_source,
                    )
                )

            evidence = {
                "adventure_summary": adventure_summary,
                "encounters": copy.deepcopy(encounters),
                "gameplay_encounters": gameplay_encounters,
                "monsters": copy.deepcopy(monsters),
            }
            nodes[location_id] = {
                "location_id": location_id,
                "location_name": location.get("name", "Unknown"),
                "area_id": area_id,
                "area_name": area_name,
                "source_file": relative_source,
                "connections": list(dict.fromkeys(internal_connections)),
                "internal_connections": list(dict.fromkeys(internal_connections)),
                # These two generated-schema arrays are positional pairs. Keep
                # duplicates and ordering intact until the pair validator has
                # consumed them; deduplicating either side can shift indexes.
                "area_connectivity_names": list(area_connectivity_names),
                "area_connectivity_ids": list(area_connectivity_ids),
                "location_data": copy.deepcopy(location),
                "monsters": copy.deepcopy(monsters),
                "encounters": copy.deepcopy(encounters),
                "adventure_summary": adventure_summary,
                "exploration_status": exploration["status"],
                "visited": exploration["visited"],
                "visit_evidence": list(exploration["evidence"]),
                "has_monsters": bool(monsters),
                "has_encounter_entries": bool(gameplay_encounters),
                "monster_count": len(monsters),
                "monster_names": _monster_names(monsters),
                "evidence_hash": _canonical_hash(evidence),
            }
            edges[location_id] = list(dict.fromkeys(internal_connections))

    # A duplicated area ID means the registered (first-loaded) nodes for that
    # area cannot be trusted as the module's intent. Taint those winner nodes
    # so routes through them fail scoped, not the entire module.
    if duplicate_area_ids:
        for location_id, node in nodes.items():
            if node["area_id"] in duplicate_area_ids:
                invalid_location_ids.add(location_id)

    location_name_to_id = _unique_mapping(
        (node.get("location_name"), location_id) for location_id, node in nodes.items()
    )
    area_name_to_id = _unique_mapping(
        (area.get("area_name"), area_id) for area_id, area in areas.items()
    )

    def target_area_endpoint(source_id: str, target_area_id: str) -> Optional[str]:
        """Resolve a schema area edge through its unique reciprocal endpoint."""
        source = nodes[source_id]
        source_area_id = source["area_id"]
        source_area_name = source["area_name"]
        source_name = source["location_name"]
        matches = []
        for candidate_id, candidate in nodes.items():
            if candidate["area_id"] != target_area_id:
                continue
            reciprocal_ids = candidate["area_connectivity_ids"]
            reciprocal_names = candidate["area_connectivity_names"]
            if (
                source_id in reciprocal_ids
                or source_area_id in reciprocal_ids
                or source_name in reciprocal_names
                or source_area_name in reciprocal_names
            ):
                matches.append(candidate_id)
        return matches[0] if len(matches) == 1 else None

    # Resolve external connectivity only after every area/location is loaded.
    # Supported contracts:
    # - legacy direct location IDs in areaConnectivityId
    # - legacy unique location names in areaConnectivity
    # - schema area IDs/names paired through a unique reciprocal endpoint
    # - generated parallel pairs: areaConnectivity[N] names the area containing
    #   the exact gateway location in areaConnectivityId[N]
    # - generated composite IDs: "AREA-LOC" in areaConnectivityId, resolved
    #   iff LOC exists in AREA (area cross-checked)
    for source_id, node in nodes.items():
        external_targets: List[str] = []
        unresolved: List[str] = []
        consumed_name_indexes: set[int] = set()
        area_names = node["area_connectivity_names"]
        for index, reference in enumerate(node["area_connectivity_ids"]):
            if reference in nodes:
                target = nodes[reference]
                paired_name = area_names[index] if index < len(area_names) else None
                if paired_name is not None:
                    consumed_name_indexes.add(index)
                    # Generated modules use this parallel value variously as
                    # an area name, a gateway label, or a source-side route
                    # label. The unique direct location ID is authoritative;
                    # the text is consumed as metadata rather than resolved as
                    # a second independent edge.
                    external_targets.append(reference)
                else:
                    external_targets.append(reference)
            elif reference in areas:
                endpoint = target_area_endpoint(source_id, reference)
                if endpoint:
                    external_targets.append(endpoint)
                else:
                    unresolved.append(reference)
            else:
                # Generated composite reference: "AREA-LOC" names the exact
                # gateway location LOC inside area AREA. Bare location IDs
                # never contain hyphens, so the form is unambiguous. It
                # resolves iff LOC exists AND actually lives in AREA; any
                # mismatch stays unresolved rather than masking a dangle.
                composite = _COMPOSITE_CONNECTION_RE.fullmatch(reference)
                if (
                    composite
                    and composite.group(2) in nodes
                    and nodes[composite.group(2)]["area_id"] == composite.group(1)
                ):
                    if index < len(area_names):
                        # The paired name is metadata for this same edge, not
                        # a second independent connection to resolve.
                        consumed_name_indexes.add(index)
                    external_targets.append(composite.group(2))
                else:
                    unresolved.append(reference)
        for index, reference in enumerate(area_names):
            if index in consumed_name_indexes:
                continue
            if reference in location_name_to_id:
                external_targets.append(location_name_to_id[reference])
            elif reference in area_name_to_id:
                endpoint = target_area_endpoint(source_id, area_name_to_id[reference])
                if endpoint:
                    external_targets.append(endpoint)
                else:
                    unresolved.append(reference)
            else:
                unresolved.append(reference)

        for target_id in dict.fromkeys(external_targets):
            if target_id not in edges[source_id]:
                edges[source_id].append(target_id)
            if source_id not in edges[target_id]:
                edges[target_id].append(source_id)
        node["connections"] = list(edges[source_id])
        for reference in dict.fromkeys(unresolved):
            invalid_location_ids.add(source_id)
            issues.append(
                _issue(
                    "unresolved_area_connection",
                    f"Location {source_id} has unresolved area connection {reference}",
                    location_id=source_id,
                    connection=reference,
                )
            )
    for source_id, destinations in edges.items():
        for destination_id in destinations:
            if destination_id not in nodes:
                invalid_location_ids.add(source_id)
                issues.append(
                    _issue(
                        "dangling_connection",
                        f"Location {source_id} connects to missing location {destination_id}",
                        location_id=source_id,
                        destination_id=destination_id,
                    )
                )

    canonical_content = {
        "module": normalized_module,
        "sources": canonical_sources,
        "validation_errors": issues,
    }
    snapshot_hash = _canonical_hash(canonical_content)
    topology_identity = _canonical_hash(
        {
            "module": normalized_module,
            "areas": sorted(areas),
            "nodes": [
                {
                    "location_id": location_id,
                    "area_id": nodes[location_id]["area_id"],
                    "connections": sorted(edges.get(location_id, [])),
                }
                for location_id in sorted(nodes)
            ],
            "invalid_location_ids": sorted(invalid_location_ids),
            "validation_errors": [
                {
                    key: issue[key]
                    for key in sorted(issue)
                    if key not in {"message", "source_file"}
                }
                for issue in issues
            ],
        }
    )
    return {
        "module_name": normalized_module,
        "areas": areas,
        "nodes": nodes,
        "edges": edges,
        "validation_errors": issues,
        "invalid_location_ids": sorted(invalid_location_ids),
        "is_valid": not issues,
        "snapshot_hash": snapshot_hash,
        "topology_identity": topology_identity,
    }


def find_path_in_snapshot(
    snapshot: Dict[str, Any],
    origin_id: str,
    destination_id: str,
) -> Dict[str, Any]:
    """Find a shortest path using only the supplied immutable snapshot.

    The result is JSON-serializable and carries the snapshot identity, making
    it suitable for a durable transition checkpoint. Invalid or ambiguous
    nodes are never traversed.

    Rejection is route-scoped: unrelated atlas blemishes elsewhere in the
    module never fail a route that touches zero invalid nodes. A route that
    REQUIRES an invalid node fails with a reason naming that specific node.
    """
    nodes = snapshot.get("nodes", {})
    invalid_ids = set(snapshot.get("invalid_location_ids", []))
    edges = snapshot.get("edges", {})
    result = {
        "success": False,
        "path": [],
        "reason": "",
        "snapshot_hash": snapshot.get("snapshot_hash", ""),
        "snapshot_identity": snapshot.get("snapshot_hash", ""),
    }
    if origin_id not in nodes:
        result["reason"] = (
            f"Origin {origin_id} is absent from the active-module snapshot"
        )
        return result
    if destination_id not in nodes:
        result["reason"] = (
            f"Destination {destination_id} is absent from the active-module snapshot"
        )
        return result
    if origin_id in invalid_ids:
        result["reason"] = (
            f"Origin {origin_id} has invalid or ambiguous atlas data"
        )
        return result
    if destination_id in invalid_ids:
        result["reason"] = (
            f"Destination {destination_id} has invalid or ambiguous atlas data"
        )
        return result
    if origin_id == destination_id:
        result.update(success=True, path=[origin_id])
        return result

    def _bfs(skip_invalid: bool) -> Optional[List[str]]:
        queue = deque([(origin_id, [origin_id])])
        visited = {origin_id}
        while queue:
            location_id, path = queue.popleft()
            for neighbor_id in edges.get(location_id, []):
                if (
                    neighbor_id in visited
                    or (skip_invalid and neighbor_id in invalid_ids)
                    or neighbor_id not in nodes
                ):
                    continue
                candidate = path + [neighbor_id]
                if neighbor_id == destination_id:
                    return candidate
                visited.add(neighbor_id)
                queue.append((neighbor_id, candidate))
        return None

    valid_path = _bfs(skip_invalid=True)
    if valid_path:
        result.update(success=True, path=valid_path)
        return result

    # Honest, scoped failure: if a route exists only through invalid nodes,
    # name the specific node that blocks it instead of a generic refusal.
    tainted_path = _bfs(skip_invalid=False)
    if tainted_path:
        blocking_id = next(
            (step for step in tainted_path if step in invalid_ids), None
        )
        if blocking_id:
            result["reason"] = (
                f"Every route from {origin_id} to {destination_id} requires "
                f"location {blocking_id}, which has invalid or ambiguous "
                "atlas data"
            )
            return result

    result["reason"] = f"No valid route from {origin_id} to {destination_id}"
    return result


def analyze_path_for_encounters(
    path: List[str],
    location_graph,
    module_name: str,
    *,
    snapshot: Optional[Dict[str, Any]] = None,
    modules_root: Union[str, Path] = "modules",
) -> Dict[str, Any]:
    """Analyze a route using one active-module snapshot.

    ``location_graph`` remains in the signature for compatibility, but route
    evidence is intentionally not read from it.  Callers may pass a prebuilt
    snapshot to guarantee that path planning and repeated analysis share the
    exact same evidence version.
    """
    del location_graph
    debug(
        f"Analyzing path for encounters: {' -> '.join(path)}", category="path_analysis"
    )
    snapshot = snapshot or build_active_module_snapshot(module_name, modules_root)
    nodes = snapshot.get("nodes", {})
    invalid_ids = set(snapshot.get("invalid_location_ids", []))

    result: Dict[str, Any] = {
        "has_unexplored": False,
        "first_unexplored_with_encounters": None,
        "first_blocking_location": None,
        "path_segments": [],
        "safe_to_auto_travel": True,
        "requires_stop": False,
        "stop_reason": "",
        "snapshot_hash": snapshot.get("snapshot_hash", ""),
        "snapshot_identity": snapshot.get("snapshot_hash", ""),
        "snapshot_valid": snapshot.get("is_valid", False),
        "snapshot_validation_errors": copy.deepcopy(
            snapshot.get("validation_errors", [])
        ),
    }

    last_index = len(path) - 1
    for index, location_id in enumerate(path):
        position = (
            "origin"
            if index == 0
            else "destination" if index == last_index else "intermediate"
        )
        node = nodes.get(location_id)
        if not node:
            warning(
                f"Location {location_id} not found in active-module snapshot",
                category="path_analysis",
            )
            segment = {
                "location_id": location_id,
                "location_name": "Unknown",
                "area_id": None,
                "area_name": "Unknown",
                "position": position,
                "status": "unknown",
                "has_monsters": False,
                "has_encounter_entries": False,
                "monster_count": 0,
                "monster_names": [],
                "encounters": [],
                "gameplay_encounters": [],
                "adventure_summary": "",
                "evidence_hash": "",
                "classification": "invalid",
                "blocks_travel": True,
                "requires_context_review": False,
                "reason": "Location is absent from the active-module snapshot",
            }
        else:
            visited = bool(node["visited"])
            has_monsters = bool(node["has_monsters"])
            classification = "passable"
            reason = ""
            requires_review = False

            if location_id in invalid_ids:
                classification = "invalid"
                reason = "Location data or connectivity is invalid"
            elif position == "origin":
                reason = "Origin is not evaluated as a travel blocker"
            elif position == "destination":
                reason = "Requested destination may be entered; it is not an intermediate blocker"
            elif not visited and has_monsters:
                classification = "blocked"
                reason = "Unexplored intermediate location has recorded monsters"
                result["has_unexplored"] = True
            elif visited and has_monsters:
                classification = "review_required"
                requires_review = True
                reason = "Visited intermediate location still has recorded monsters"
            elif visited:
                reason = "Visited intermediate location has no recorded monsters"
            else:
                reason = "Unexplored intermediate location has no recorded monsters"

            gameplay_encounters = [
                copy.deepcopy(entry)
                for entry in node["encounters"]
                if isinstance(entry, dict) and "encounterId" in entry
            ]
            segment = {
                "location_id": location_id,
                "location_name": node["location_name"],
                "area_id": node["area_id"],
                "area_name": node["area_name"],
                "position": position,
                "status": "visited" if visited else "unexplored",
                "has_monsters": has_monsters,
                "has_encounter_entries": node["has_encounter_entries"],
                "visit_evidence": list(node["visit_evidence"]),
                "exploration_status": node["exploration_status"],
                "monster_count": node["monster_count"],
                "monster_names": list(node["monster_names"]),
                "encounters": copy.deepcopy(node["encounters"]),
                "gameplay_encounters": gameplay_encounters,
                "adventure_summary": node["adventure_summary"],
                "evidence_hash": node["evidence_hash"],
                "classification": classification,
                "blocks_travel": classification in {"blocked", "invalid"},
                "requires_context_review": requires_review,
                "reason": reason,
            }

        result["path_segments"].append(segment)
        if not result["first_blocking_location"] and segment["classification"] in {
            "blocked",
            "review_required",
            "invalid",
        }:
            result["first_blocking_location"] = location_id
            result["safe_to_auto_travel"] = False
            result["requires_stop"] = True
            result["stop_reason"] = (
                f"Travel requires resolution at {location_id} "
                f"({segment['location_name']}): {segment['reason']}"
            )
            if (
                segment["classification"] == "blocked"
                and segment["status"] == "unexplored"
            ):
                result["first_unexplored_with_encounters"] = location_id

    result["route_hash"] = _canonical_hash(
        {
            "module": snapshot.get("module_name", module_name),
            "path": path,
            "segments": [
                {
                    "location_id": segment["location_id"],
                    "position": segment["position"],
                    "classification": segment["classification"],
                    "evidence_hash": segment["evidence_hash"],
                }
                for segment in result["path_segments"]
            ],
        }
    )
    # The route evidence identity is stable across JSON serialization and can
    # be compared after a disconnect/restart before committing movement.
    result["evidence_identity"] = result["route_hash"]
    return result


def get_encounter_summary_for_location(
    location_id: str, area_id: str, module_name: str
) -> str:
    snapshot = build_active_module_snapshot(module_name)
    node = snapshot["nodes"].get(location_id)
    if not node or node.get("area_id") != area_id:
        return f"Location {location_id} not found in area {area_id}"
    if not node["monsters"] and not node["encounters"]:
        return f"No encounters at {node['location_name']}"
    parts = [f"At {node['location_name']}:"]
    if node["monster_names"]:
        parts.append(f"  Monsters: {', '.join(node['monster_names'])}")
    if node["encounters"]:
        parts.append(
            f"  Encounters: {len([entry for entry in node['encounters'] if entry])} defined"
        )
    return "\n".join(parts)


def build_path_context_for_ai(path_analysis: Dict[str, Any]) -> str:
    """Format all independent route facts; never hide monsters when visited."""
    if not path_analysis.get("path_segments"):
        return "ERROR: No path data available"
    lines = ["TRAVEL PATH ANALYSIS:", "=" * 60]
    for index, segment in enumerate(path_analysis["path_segments"], 1):
        marker = segment.get("classification", "invalid").upper().replace("_", " ")
        lines.append(
            f"{index}. {segment['location_id']}: {segment['location_name']} "
            f"({segment['area_name']}) [{segment.get('position', 'intermediate').upper()}] "
            f"[{marker}]"
        )
        lines.append(f"   Exploration: {segment.get('status', 'unknown').upper()}")
        lines.append(
            f"   Monsters recorded: {'YES' if segment.get('has_monsters') else 'NO'}"
        )
        if segment.get("monster_names"):
            lines.append(f"   Monster records: {', '.join(segment['monster_names'])}")
        lines.append(
            f"   Gameplay encounter records: {len(segment.get('gameplay_encounters', []))}"
        )
        if segment.get("adventure_summary"):
            lines.append(f"   Adventure summary: {segment['adventure_summary']}")
        if segment.get("reason"):
            lines.append(f"   Classification reason: {segment['reason']}")
    lines.append("=" * 60)
    if path_analysis.get("requires_stop"):
        lines.append(f"\nREQUIRES RESOLUTION: {path_analysis['stop_reason']}")
    else:
        lines.append("\nPath is clear for travel")
    lines.append(f"Snapshot: {path_analysis.get('snapshot_hash', 'unavailable')}")
    lines.append(f"Route evidence: {path_analysis.get('route_hash', 'unavailable')}")
    return "\n".join(lines)
