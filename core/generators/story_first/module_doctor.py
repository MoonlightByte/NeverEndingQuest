# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Objective-only, transactional repair for accepted story-first modules.

The doctor deliberately does not interpret or rewrite prose and does not modify
monster profiles. Descriptive abilities and lock-answer concerns are advisory until
an agentic playthrough demonstrates a real failure. No repair kind is currently
implemented: every objective defect returns to its owning stage, and a snapshot
heal only revalidates and republishes the accepted files.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shutil
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

import jsonschema

from .contracts import StageEvidence, freeze_value, mutable_copy
from .execution import NonRetryableStageError
from .validators import (
    require_ascii,
    validate_public_candidate_references_and_keys,
)


_OBJECTIVE_DEFECT_KINDS: frozenset = frozenset()


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

    _location_index(area_values)

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
        area_values, entry_location_id
    )
    return ModuleDoctorResult(
        areas=tuple(area_values),
        plot=original_plot,
        monsters=tuple(original_monsters),
        evidence=StageEvidence(stage="module_doctor", attempts=0, result="accepted"),
        metrics={
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
    "heal_module_snapshot",
    "run",
]
