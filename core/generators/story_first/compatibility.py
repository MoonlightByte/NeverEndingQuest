# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Deterministic projections for the story-first legacy compatibility tail."""

from __future__ import annotations

import os
from pathlib import Path
import re
import secrets
from typing import Any, Dict, Iterable, Mapping, Sequence

from .contracts import freeze_value, mutable_copy


def derive_entry_projection(
    outline: Mapping[str, Any],
    areas: Sequence[Mapping[str, Any]],
    beat_locations: Mapping[str, str],
) -> Mapping[str, str]:
    """Return the accepted first-beat anchor, failing closed on ambiguity."""
    beats = outline.get("beats")
    if not isinstance(beats, (list, tuple)) or not beats:
        raise ValueError("accepted outline has no entry beat")
    entry_beat = beats[0]
    if not isinstance(entry_beat, Mapping):
        raise ValueError("accepted entry beat is invalid")
    if list(entry_beat.get("prerequisites", ())) != []:
        raise ValueError("accepted entry beat has prerequisites")
    entry_beat_id = entry_beat.get("id")
    entry_location_id = beat_locations.get(entry_beat_id)
    if not isinstance(entry_location_id, str) or not entry_location_id:
        raise ValueError("accepted entry beat has no location anchor")

    matches = []
    for area in areas:
        locations = area.get("locations")
        if not isinstance(locations, (list, tuple)):
            raise ValueError("accepted area has invalid locations")
        if any(
            isinstance(location, Mapping)
            and location.get("locationId") == entry_location_id
            for location in locations
        ):
            matches.append(area.get("areaId"))
    if len(matches) != 1 or not isinstance(matches[0], str) or not matches[0]:
        raise ValueError("accepted entry location is missing or ambiguous")
    return freeze_value(
        {
            "entryBeatId": entry_beat_id,
            "entryLocationId": entry_location_id,
            "entryAreaId": matches[0],
        }
    )


def project_overview(outline: Mapping[str, Any], seed: Any) -> Mapping[str, Any]:
    """Project accepted outline facts into the non-persistent legacy view."""
    opposition = mutable_copy(outline["opposition"])
    story_promise = outline["storyPromise"]
    return freeze_value(
        {
            "moduleName": outline["moduleTitle"],
            "moduleDescription": outline["conceptSummary"],
            "storyPromise": story_promise,
            "objective": story_promise,
            "opposition": opposition,
            "mainPlot": {
                "mainObjective": story_promise,
                "antagonist": opposition["name"],
            },
            "areaSynopsis": [
                {
                    "roleId": area["roleId"],
                    "name": area["name"],
                    "storyPurpose": area["storyPurpose"],
                    "environment": area["environment"],
                    "dangerBand": area["dangerBand"],
                }
                for area in outline["areas"]
            ],
            "moduleControls": mutable_copy(seed.module_controls),
        }
    )


def build_story_first_summary(
    *,
    outline: Mapping[str, Any],
    plot: Mapping[str, Any],
    areas: Sequence[Mapping[str, Any]],
    monsters: Sequence[Mapping[str, Any]],
    entry: Mapping[str, str],
) -> str:
    """Compile one deterministic ASCII Markdown summary from accepted data."""
    areas_by_id = {area["areaId"]: area for area in areas}
    locations_by_id = {
        location["locationId"]: (area["areaId"], location)
        for area in areas
        for location in area["locations"]
    }
    entry_area = areas_by_id.get(entry["entryAreaId"])
    entry_pair = locations_by_id.get(entry["entryLocationId"])
    if (
        entry_area is None
        or entry_pair is None
        or entry_pair[0] != entry["entryAreaId"]
    ):
        raise ValueError("story-first summary entry projection is invalid")

    lines = [
        f"# {outline['moduleTitle']} - Module Summary",
        "",
        "## Overview",
        str(outline["conceptSummary"]),
        "",
        f"**Story Promise**: {outline['storyPromise']}",
        f"**Opposition**: {outline['opposition']['name']} - "
        f"{outline['opposition']['nature']}",
        f"**Opposition Goal**: {outline['opposition']['goal']}",
        f"**Opposition Method**: {outline['opposition']['method']}",
        f"**Why Now**: {outline['opposition']['whyNow']}",
        "",
        "## Main Objective",
        str(plot["mainObjective"]),
        "",
        "## Getting Started",
        f"- **Entry Beat**: {entry['entryBeatId']}",
        f"- **Starting Area**: {entry_area['areaName']} " f"({entry['entryAreaId']})",
        f"- **Starting Location**: {entry_pair[1]['name']} "
        f"({entry['entryLocationId']})",
        "",
        "## Ordered Plot Beats",
    ]
    if len(outline["beats"]) != len(plot["plotPoints"]):
        raise ValueError("story-first summary beat/plot cardinality drifted")
    for index, (beat, point) in enumerate(zip(outline["beats"], plot["plotPoints"]), 1):
        bound = locations_by_id.get(point["location"])
        if bound is None:
            raise ValueError("story-first summary plot location is unknown")
        lines.append(
            f"{index}. {beat['title']} [{beat['id']} / {point['id']}] - "
            f"{bound[1]['name']} ({point['location']})"
        )
        lines.append(f"   {point['description']}")

    lines.extend(["", "## Areas"])
    for area in areas:
        lines.extend(
            [
                f"### {area['areaName']} ({area['areaId']})",
                f"- **Description**: {area['areaDescription']}",
                f"- **Danger Level**: {area['dangerLevel']}",
                f"- **Recommended Level**: {area['recommendedLevel']}",
                f"- **Locations**: {len(area['locations'])}",
            ]
        )

    lines.extend(["", "## Side Threads"])
    if outline["sideThreads"]:
        for thread in outline["sideThreads"]:
            lines.append(
                f"- {thread['title']} [{thread['id']}]: {thread['hook']} "
                f"Payoff: {thread['mainStoryPayoff']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Creature Provenance"])
    if monsters:
        for monster in monsters:
            lines.append(f"- {monster['name']}: AI-authored")
    else:
        lines.append("- No compiled creatures")

    lines.extend(
        [
            "",
            "## Module Structure",
            f"- **Total Areas**: {len(areas)}",
            f"- **Total Locations**: {len(locations_by_id)}",
            f"- **Total Plot Points**: {len(plot['plotPoints'])}",
            f"- **Total Monsters**: {len(monsters)}",
            "",
        ]
    )
    summary = "\n".join(lines)
    summary.encode("ascii")
    return summary


def atomic_write_ascii(path: Path, text: str) -> None:
    """Durably replace one ASCII text artifact."""
    payload = text.encode("ascii")
    path = Path(path)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def expected_context_projection(
    *,
    module_name: str,
    module_id: str,
    areas: Sequence[Mapping[str, Any]],
    plot: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Build the accepted-file relationships T088 must preserve."""
    plot_by_area: Dict[str, list[str]] = {area["areaId"]: [] for area in areas}
    location_to_area = {
        location["locationId"]: area["areaId"]
        for area in areas
        for location in area["locations"]
    }
    for point in plot["plotPoints"]:
        try:
            plot_by_area[location_to_area[point["location"]]].append(point["id"])
        except KeyError as exc:
            raise ValueError("accepted plot references an unknown location") from exc

    expected_areas = {}
    expected_locations = {}
    appearances: Dict[str, list[Dict[str, str]]] = {}
    for area in areas:
        area_id = area["areaId"]
        area_npcs = []
        for location in area["locations"]:
            location_id = location["locationId"]
            location_npcs = []
            for npc in location.get("npcs", []):
                name = npc["name"]
                if name not in location_npcs:
                    location_npcs.append(name)
                if name not in area_npcs:
                    area_npcs.append(name)
                appearance = {"area": area_id, "location": location_id}
                appearances.setdefault(name, [])
                if appearance not in appearances[name]:
                    appearances[name].append(appearance)
            expected_locations[location_id] = {
                "name": location["name"],
                "area": area_id,
                "npcs": location_npcs,
                "connections": list(location.get("connectivity", []))
                + list(location.get("areaConnectivityId", [])),
            }
        expected_areas[area_id] = {
            "name": area["areaName"],
            "type": area.get("areaType", ""),
            "locations": [location["locationId"] for location in area["locations"]],
            "npcs": area_npcs,
            "plot_points": plot_by_area[area_id],
        }
    return freeze_value(
        {
            "module_name": module_name,
            "module_id": module_id,
            "areas": expected_areas,
            "locations": expected_locations,
            "npc_appearances": appearances,
            "plot_scopes": {
                point["id"]: location_to_area[point["location"]]
                for point in plot["plotPoints"]
            },
        }
    )


def _identity_labels(npc: Mapping[str, Any]) -> set[str]:
    labels = {npc.get("name")}
    labels.update(npc.get("aliases", ()))
    return {label for label in labels if isinstance(label, str) and label}


def _stable_unique(values: Iterable[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def validate_reconciled_context(
    expected: Mapping[str, Any], actual: Mapping[str, Any]
) -> None:
    """Field-compare T088 output against accepted-file relationships."""
    if actual.get("module_name") != expected["module_name"]:
        raise ValueError("reconciled context module name drifted")
    if actual.get("module_id") != expected["module_id"]:
        raise ValueError("reconciled context module id drifted")
    if actual.get("validation_issues") != []:
        raise ValueError("reconciled context has validation issues")

    actual_areas = actual.get("areas")
    actual_locations = actual.get("locations")
    actual_npcs = actual.get("npcs")
    if not all(
        isinstance(value, Mapping)
        for value in (actual_areas, actual_locations, actual_npcs)
    ):
        raise ValueError("reconciled context mappings are invalid")
    if set(actual_areas) != set(expected["areas"]):
        raise ValueError("reconciled context area identities drifted")
    if set(actual_locations) != set(expected["locations"]):
        raise ValueError("reconciled context location identities drifted")
    if actual.get("plot_scopes") != mutable_copy(expected["plot_scopes"]):
        raise ValueError("reconciled context plot scopes drifted")

    source_names = set(expected["npc_appearances"])
    labels_by_key = {key: _identity_labels(npc) for key, npc in actual_npcs.items()}
    source_to_key = {}
    for source_name in source_names:
        matches = [
            key for key, labels in labels_by_key.items() if source_name in labels
        ]
        if len(matches) != 1:
            raise ValueError("reconciled context NPC identity is missing or ambiguous")
        source_to_key[source_name] = matches[0]
    if any(not (labels & source_names) for labels in labels_by_key.values()):
        raise ValueError("reconciled context introduced an NPC identity")

    expected_by_key: Dict[str, list[Dict[str, str]]] = {}
    for source_name, appearances in expected["npc_appearances"].items():
        key = source_to_key[source_name]
        expected_by_key.setdefault(key, [])
        for appearance in appearances:
            value = mutable_copy(appearance)
            if value not in expected_by_key[key]:
                expected_by_key[key].append(value)
    if set(expected_by_key) != set(actual_npcs):
        raise ValueError("reconciled context NPC identities drifted")
    for key, expected_appearances in expected_by_key.items():
        npc = actual_npcs[key]
        if npc.get("appears_in") != expected_appearances:
            raise ValueError("reconciled context NPC appearances drifted")
        canonical = npc.get("name")
        allowed_canonical_names = {
            re.sub(r"\s*\([^)]*\)\s*", "", source_name).strip()
            for source_name, source_key in source_to_key.items()
            if source_key == key
        }
        if canonical not in allowed_canonical_names:
            raise ValueError("reconciled context NPC canonical identity drifted")

    def canonical_names(source_values: Iterable[str]) -> list[str]:
        return _stable_unique(
            actual_npcs[source_to_key[value]]["name"] for value in source_values
        )

    for area_id, expected_area in expected["areas"].items():
        actual_area = actual_areas[area_id]
        for field in ("name", "type", "locations", "plot_points"):
            if actual_area.get(field) != mutable_copy(expected_area[field]):
                raise ValueError(f"reconciled context area {field} drifted")
        if actual_area.get("npcs") != canonical_names(expected_area["npcs"]):
            raise ValueError("reconciled context area NPC membership drifted")

    for location_id, expected_location in expected["locations"].items():
        actual_location = actual_locations[location_id]
        for field in ("name", "area", "connections"):
            if actual_location.get(field) != mutable_copy(expected_location[field]):
                raise ValueError(f"reconciled context location {field} drifted")
        if actual_location.get("npcs") != canonical_names(expected_location["npcs"]):
            raise ValueError("reconciled context location NPC membership drifted")

    valid_npc_names = {
        npc["name"] for npc in actual_npcs.values() if isinstance(npc.get("name"), str)
    }
    for reference in actual.get("references", {}):
        if reference.startswith("npc:") and reference[4:] not in valid_npc_names:
            raise ValueError("reconciled context has an unknown NPC reference")


def context_npc_name(context: Any, source_name: str) -> str:
    """Return the canonical name registered for one exact source appearance."""
    for npc in context.npcs.values():
        if source_name in _identity_labels(npc):
            return npc["name"]
    raise ValueError("story-first NPC registration lost an accepted identity")


__all__ = [
    "atomic_write_ascii",
    "build_story_first_summary",
    "context_npc_name",
    "derive_entry_projection",
    "expected_context_projection",
    "project_overview",
    "validate_reconciled_context",
]
