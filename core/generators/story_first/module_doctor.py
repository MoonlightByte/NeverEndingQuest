# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Objective-only, transactional repair for accepted story-first modules.

The doctor deliberately does not interpret prose or modify monster profiles.
Descriptive abilities, private authoring IDs, and lock-answer concerns are advisory
until an agentic playthrough demonstrates a real failure. The only currently
implemented repair is an exact unresolved public PPxxx/SQxxx reference in an
allowlisted location text field; other objective defects return to their owning stage.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import jsonschema

from .contracts import StageEvidence, freeze_value, mutable_copy
from .execution import NonRetryableStageError, SemanticCorrectionError
from .validators import (
    require_ascii,
    validate_public_candidate_references_and_keys,
)


_LOCATION_TEXT_PATH = re.compile(
    r"^\$\.areas\[(?P<area>[0-9]+)\]\.locations\[(?P<location>[0-9]+)\]\."
    r"(?P<field>.+)$"
)
_LIST_FIELD = re.compile(r"^(?P<field>plotHooks)\[(?P<index>[0-9]+)\]$")
_OBJECTIVE_DEFECT_KINDS = frozenset({"undefined_public_reference"})


class ModuleDoctorScopeError(NonRetryableStageError):
    """A requested repair is interpretive or belongs to another authoring stage."""


@dataclass(frozen=True)
class ModuleDoctorResult:
    areas: Tuple[Mapping[str, Any], ...]
    plot: Mapping[str, Any]
    monsters: Tuple[Mapping[str, Any], ...]
    evidence: StageEvidence
    metrics: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "areas", freeze_value(self.areas))
        object.__setattr__(self, "plot", freeze_value(self.plot))
        object.__setattr__(self, "monsters", freeze_value(self.monsters))
        object.__setattr__(self, "metrics", freeze_value(self.metrics))


def _get_text_field(location: Mapping[str, Any], field_path: str) -> str:
    if field_path in {"description", "dmInstructions"}:
        value = location[field_path]
    else:
        match = _LIST_FIELD.fullmatch(field_path)
        if match is None:
            raise ModuleDoctorScopeError("reference field is outside the allowlist")
        try:
            value = location[match.group("field")][int(match.group("index"))]
        except (KeyError, IndexError, TypeError):
            raise ModuleDoctorScopeError("reference field is missing") from None
    if not isinstance(value, str):
        raise ModuleDoctorScopeError("reference field is not text")
    return value


def _set_text_field(location: Dict[str, Any], field_path: str, value: str) -> None:
    if field_path in {"description", "dmInstructions"}:
        location[field_path] = value
        return
    match = _LIST_FIELD.fullmatch(field_path)
    if match is None:
        raise ModuleDoctorScopeError("reference field is outside the allowlist")
    location[match.group("field")][int(match.group("index"))] = value


def _scrub_unresolved_public_reference(text: str, reference: str) -> str:
    if reference.startswith("PP"):
        replacement = "the relevant plot point"
    elif reference.startswith("SQ"):
        replacement = "the related side quest"
    else:
        raise ModuleDoctorScopeError("only unresolved public IDs are repairable")
    result = re.sub(rf"\b{re.escape(reference)}\b", replacement, text)
    if result == text or re.search(rf"\b{re.escape(reference)}\b", result):
        raise ModuleDoctorScopeError("public reference could not be scrubbed exactly")
    return result


def collect_candidate_integrity_defects(
    areas: Sequence[Mapping[str, Any]],
    plot: Mapping[str, Any],
    entry_location_id: str,
) -> Tuple[Dict[str, Any], ...]:
    """Return only objective unresolved-public-reference repair targets.

    The validator returns private-ID and lock/key findings as advisories, so they
    never enter this repair list. Unknown public references in plot prose are left
    to the plot-owning stage rather than granting this doctor a broad plot rewrite.
    """
    try:
        validate_public_candidate_references_and_keys(
            mutable_copy(areas), mutable_copy(plot), entry_location_id
        )
        return ()
    except SemanticCorrectionError as exc:
        issues = exc.issues

    defects = []
    seen = set()
    for issue in issues:
        if issue["invariant"] != "undefined_public_reference":
            raise ModuleDoctorScopeError(
                f"candidate issue is outside objective doctor scope: "
                f"{issue['invariant']}"
            )
        offending = json.loads(issue["offending"])
        match = _LOCATION_TEXT_PATH.fullmatch(offending["path"])
        if match is None:
            raise ModuleDoctorScopeError(
                "unresolved plot reference belongs to the plot-owning stage"
            )
        area_index = int(match.group("area"))
        location_index = int(match.group("location"))
        try:
            area = areas[area_index]
            location = area["locations"][location_index]
        except (IndexError, KeyError, TypeError):
            raise ModuleDoctorScopeError("reference target is missing") from None
        key = (location["locationId"], match.group("field"), offending["reference"])
        if key in seen:
            continue
        seen.add(key)
        defects.append(
            {
                "kind": "undefined_public_reference",
                "areaId": area["areaId"],
                "locationId": location["locationId"],
                "fieldPath": match.group("field"),
                "reference": offending["reference"],
            }
        )
    return tuple(defects)


def _location_index(areas: Sequence[Mapping[str, Any]]):
    result = {}
    for area_index, area in enumerate(areas):
        for location_index, location in enumerate(area["locations"]):
            location_id = location["locationId"]
            if location_id in result:
                raise ModuleDoctorScopeError("duplicate location identity")
            result[location_id] = (area_index, location_index, area["areaId"])
    return result


def _validate_artifacts(
    areas,
    plot,
    monsters,
    *,
    loca_schema,
    locationfile_schema,
    plot_schema,
    monster_schema,
):
    require_ascii(areas, "module-doctor areas")
    require_ascii(plot, "module-doctor plot")
    require_ascii(monsters, "module-doctor monsters")
    for area in areas:
        jsonschema.validate({"locations": area["locations"]}, mutable_copy(loca_schema))
        jsonschema.validate(area, mutable_copy(locationfile_schema))
    jsonschema.validate(plot, mutable_copy(plot_schema))
    for monster in monsters:
        jsonschema.validate(monster, mutable_copy(monster_schema))


def run(
    *,
    areas: Sequence[Mapping[str, Any]],
    plot: Mapping[str, Any],
    monsters: Sequence[Mapping[str, Any]],
    defects: Iterable[Mapping[str, Any]],
    entry_location_id: str,
    loca_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
    plot_schema: Mapping[str, Any],
    monster_schema: Mapping[str, Any],
    provider=None,
    model=None,
    model_options=None,
    gateway=None,
    policy=None,
) -> ModuleDoctorResult:
    """Apply objective deterministic repairs with zero provider calls.

    Compatibility-only provider arguments remain accepted so retained diagnostic
    harnesses can prove that the retired model-repair path is never invoked.
    """
    del provider, model, model_options, gateway, policy
    area_values = mutable_copy(areas)
    original_plot = mutable_copy(plot)
    original_monsters = mutable_copy(monsters)
    defect_values = [dict(item) for item in defects]
    unsupported = sorted(
        {
            item.get("kind", "")
            for item in defect_values
            if item.get("kind") not in _OBJECTIVE_DEFECT_KINDS
        }
    )
    if unsupported:
        raise ModuleDoctorScopeError(
            "advisory or unsupported defects cannot trigger repair: "
            + ", ".join(unsupported)
        )

    locations = _location_index(area_values)
    seen = set()
    for defect in defect_values:
        key = (
            defect.get("locationId"),
            defect.get("fieldPath"),
            defect.get("reference"),
        )
        if key in seen:
            raise ModuleDoctorScopeError("duplicate objective repair target")
        seen.add(key)
        if key[0] not in locations:
            raise ModuleDoctorScopeError("objective repair location is missing")
        area_index, location_index, area_id = locations[key[0]]
        if defect.get("areaId") != area_id:
            raise ModuleDoctorScopeError("objective repair area does not match")
        location = area_values[area_index]["locations"][location_index]
        current = _get_text_field(location, key[1])
        _set_text_field(
            location,
            key[1],
            _scrub_unresolved_public_reference(current, key[2]),
        )

    _validate_artifacts(
        area_values,
        original_plot,
        original_monsters,
        loca_schema=loca_schema,
        locationfile_schema=locationfile_schema,
        plot_schema=plot_schema,
        monster_schema=monster_schema,
    )
    integrity = validate_public_candidate_references_and_keys(
        area_values, original_plot, entry_location_id
    )
    return ModuleDoctorResult(
        areas=tuple(area_values),
        plot=original_plot,
        monsters=tuple(original_monsters),
        evidence=StageEvidence(stage="module_doctor", attempts=0, result="accepted"),
        metrics={
            "deterministicReferenceScrubCount": len(defect_values),
            "monsterProfileMutationCount": 0,
            "advisories": mutable_copy(integrity["advisories"]),
        },
    )


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temp.open("x", encoding="ascii", newline="\n") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=True, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def heal_module_snapshot(
    *,
    source_dir: Path,
    target_dir: Path,
    defects: Iterable[Mapping[str, Any]],
    entry_location_id: str,
    loca_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
    plot_schema: Mapping[str, Any],
    monster_schema: Mapping[str, Any],
    provider=None,
    model=None,
    model_options=None,
    gateway=None,
    policy=None,
) -> ModuleDoctorResult:
    """Publish an objective-only repaired sibling; never rewrite monster files."""
    source = Path(source_dir).resolve()
    target = Path(target_dir).resolve()
    if not source.is_dir() or source.is_symlink():
        raise ValueError("module-doctor source must be a real directory")
    if target.exists() or target.is_symlink():
        raise ValueError("module-doctor target already exists")
    if any(path.is_symlink() for path in source.rglob("*")):
        raise ValueError("module-doctor source cannot contain symbolic links")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".{target.name}.doctor-{secrets.token_hex(8)}"
    try:
        shutil.copytree(source, staging)
        area_paths = [
            path
            for path in sorted((staging / "areas").glob("*.json"))
            if not path.name.endswith("_BU.json")
        ]
        monster_paths = [
            path
            for path in sorted((staging / "monsters").glob("*.json"))
            if not path.name.endswith("_BU.json")
        ]
        monster_bytes = {path.name: path.read_bytes() for path in monster_paths}
        areas = [_read_json(path) for path in area_paths]
        monsters = [_read_json(path) for path in monster_paths]
        plot = _read_json(staging / "module_plot.json")
        result = run(
            areas=areas,
            plot=plot,
            monsters=monsters,
            defects=defects,
            entry_location_id=entry_location_id,
            loca_schema=loca_schema,
            locationfile_schema=locationfile_schema,
            plot_schema=plot_schema,
            monster_schema=monster_schema,
            provider=provider,
            model=model,
            model_options=model_options,
            gateway=gateway,
            policy=policy,
        )
        area_by_id = {area["areaId"]: area for area in result.areas}
        if len(area_by_id) != len(area_paths):
            raise ValueError("module-doctor output area identity changed")
        for path in area_paths:
            original = _read_json(path)
            _atomic_write_json(path, mutable_copy(area_by_id[original["areaId"]]))
        if any(path.read_bytes() != monster_bytes[path.name] for path in monster_paths):
            raise ValueError("module-doctor modified a monster profile")
        os.replace(staging, target)
        return result
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


__all__ = [
    "ModuleDoctorResult",
    "ModuleDoctorScopeError",
    "collect_candidate_integrity_defects",
    "heal_module_snapshot",
    "run",
]
