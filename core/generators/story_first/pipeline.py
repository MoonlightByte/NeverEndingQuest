# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Crash-safe orchestration for the story-first module-generation stages."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
from typing import Any, Callable, Dict, Iterable, Mapping, Optional

import jsonschema

from .compilers import (
    compile_area_binding,
    migrate_initial_encounters_to_dm_guidance,
    safe_filename,
)
from .compatibility import derive_entry_projection
from .contracts import (
    AcceptedAreaBinding,
    AcceptedAreas,
    AcceptedCreatures,
    AcceptedOutline,
    AcceptedPlot,
    CompiledWorld,
    StageEvidence,
    StoryFirstBuildResult,
    StorySeed,
    area_binding_schema,
    mutable_copy,
    outline_schema,
)
from .execution import CompletionGateway, SemanticCorrectionError, StageExecutionError
from .stages import (
    area_binding,
    candidate_hardening,
    creature_compile,
    location_fill,
    npc_repair,
    outline,
    plot_derivation,
)
from .validators import (
    duplicate_npc_placements,
    require_ascii,
    semantic_area_binding_checks,
    semantic_outline_checks,
    semantic_plot_checks,
    social_monster_overlaps,
    validate_compiled_world,
    validate_public_candidate_references_and_keys,
    validate_side_thread_location_projection,
    validate_story_first_location_result,
)
from utils.transient_filesystem import retry_transient_filesystem


PIPELINE_VERSION = 1
_STAGES = (
    "outline",
    "area_binding",
    "plot_derivation",
    "location_fill",
    "npc_repair",
    "candidate_hardening",
    "creature_compile",
)
_ARTIFACTS = {name: f"{index:02d}_{name}.json" for index, name in enumerate(_STAGES, 1)}
_REQUIRED_SCHEMAS = frozenset({"map", "plot", "location", "locationfile", "monster"})
_MODEL_STAGES = tuple(name for name in _STAGES if name != "location_fill")
_CREDENTIAL_TEXT = re.compile(
    r"(?i)(?:bearer\s+[A-Za-z0-9._~-]{12,}|sk-[A-Za-z0-9_-]{12,}|"
    r"AIza[A-Za-z0-9_-]{20,})"
)


class StoryFirstPipelineError(RuntimeError):
    """Safe pipeline failure without raw model or provider content."""

    def __init__(self, stage: str, failure_class: str, diagnostics=()):
        self.stage = stage
        self.failure_class = failure_class
        self.diagnostics = (
            tuple(dict(issue) for issue in SemanticCorrectionError(diagnostics).issues)
            if diagnostics
            else ()
        )
        super().__init__(f"story-first stage {stage} failed ({failure_class})")


def _json_value(value: Any) -> Any:
    return mutable_copy(value)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _json_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _value_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key in pipeline artifact")
        result[key] = value
    return result


def _read_json(path: Path) -> Dict[str, Any]:
    if path.is_symlink():
        raise ValueError("pipeline artifact cannot be a symbolic link")
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    if not isinstance(value, dict):
        raise ValueError("pipeline artifact root must be an object")
    return value


def _assert_no_credentials(value: Any) -> None:
    if isinstance(value, Mapping):
        for item in value.values():
            _assert_no_credentials(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_no_credentials(item)
    elif isinstance(value, str) and _CREDENTIAL_TEXT.search(value):
        raise ValueError("credential-shaped text cannot enter a pipeline artifact")


def _atomic_write_json(path: Path, value: Any) -> None:
    """Durably replace one controlled JSON file without accepting partial output."""
    _assert_no_credentials(value)
    payload = (
        json.dumps(_json_value(value), indent=2, ensure_ascii=True, sort_keys=True)
        + "\n"
    )
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
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


def _evidence_value(evidence: StageEvidence) -> Dict[str, Any]:
    return {
        "stage": evidence.stage,
        "attempts": evidence.attempts,
        "result": evidence.result,
        "failureClass": evidence.failure_class,
        "failureClasses": list(evidence.failure_classes),
    }


def _evidence_from(value: Mapping[str, Any]) -> StageEvidence:
    if set(value) != {
        "stage",
        "attempts",
        "result",
        "failureClass",
        "failureClasses",
    }:
        raise ValueError("invalid stage evidence artifact")
    if type(value["attempts"]) is not int or value["attempts"] < 0:
        raise ValueError("invalid stage evidence attempt count")
    if value["result"] not in {"accepted", "skipped", "upstream"}:
        raise ValueError("invalid accepted stage evidence result")
    failure_class = value["failureClass"]
    if failure_class is not None and not isinstance(failure_class, str):
        raise ValueError("invalid stage evidence failure class")
    failures = value["failureClasses"]
    if not isinstance(failures, list) or not all(
        isinstance(item, str) for item in failures
    ):
        raise ValueError("invalid stage evidence failure history")
    return StageEvidence(
        stage=str(value["stage"]),
        attempts=value["attempts"],
        result=value["result"],
        failure_class=failure_class,
        failure_classes=tuple(failures),
    )


def _accepted_value(value, evidence, metrics) -> Dict[str, Any]:
    return {
        "value": _json_value(value),
        "evidence": _evidence_value(evidence),
        "metrics": _json_value(metrics),
    }


def _accepted_areas_value(value: AcceptedAreas) -> Dict[str, Any]:
    return {
        "areas": _json_value(value.areas),
        "evidence": [_evidence_value(item) for item in value.evidence],
        "metrics": _json_value(value.metrics),
    }


def _accepted_areas_from(value: Mapping[str, Any]) -> AcceptedAreas:
    if set(value) != {"areas", "evidence", "metrics"}:
        raise ValueError("invalid accepted-areas artifact")
    if not isinstance(value["areas"], list) or not isinstance(value["evidence"], list):
        raise ValueError("invalid accepted-areas artifact shape")
    return AcceptedAreas(
        areas=tuple(value["areas"]),
        evidence=tuple(_evidence_from(item) for item in value["evidence"]),
        metrics=value["metrics"],
    )


def _schema_validate_areas(
    areas: AcceptedAreas,
    location_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
) -> None:
    for area in areas.areas:
        jsonschema.validate(
            {"locations": _json_value(area["locations"])},
            _json_value(location_schema),
        )
        jsonschema.validate(_json_value(area), _json_value(locationfile_schema))


def _non_allowed_location_fields_equal(
    before: AcceptedAreas, after: AcceptedAreas, allowed: Iterable[str]
) -> None:
    allowed_set = set(allowed)
    before_areas = _json_value(before.areas)
    after_areas = _json_value(after.areas)
    if len(before_areas) != len(after_areas):
        raise ValueError("accepted area count changed")
    for source_area, final_area in zip(before_areas, after_areas):
        if set(source_area) != set(final_area):
            raise ValueError("accepted area fields changed")
        for key in source_area:
            if key != "locations" and source_area[key] != final_area[key]:
                raise ValueError("accepted area metadata changed")
        if len(source_area["locations"]) != len(final_area["locations"]):
            raise ValueError("accepted location count changed")
        for source, final in zip(source_area["locations"], final_area["locations"]):
            if set(source) != set(final):
                raise ValueError("accepted location fields changed")
            for key in source:
                if key not in allowed_set and source[key] != final[key]:
                    raise ValueError("accepted location field drift")


def _place_creature_guidance(
    areas: AcceptedAreas,
    creatures: AcceptedCreatures,
    location_schema: Mapping[str, Any],
    locationfile_schema: Mapping[str, Any],
) -> AcceptedAreas:
    guidance = {
        name.casefold(): (name, text) for name, text in creatures.guidance.items()
    }
    result = _json_value(areas.areas)
    for area in result:
        for location in area["locations"]:
            names = {
                monster["name"].strip().casefold()
                for monster in location.get("monsters", [])
            }
            entries = [guidance[name] for name in sorted(names) if name in guidance]
            if not entries:
                continue
            block = "CREATURE GUIDANCE (non-mechanical):\n" + "\n".join(
                f"- {name}: {text}" for name, text in entries
            )
            location["dmInstructions"] = (
                location["dmInstructions"].rstrip() + "\n\n" + block
            )
    accepted = AcceptedAreas(
        areas=tuple(result), evidence=areas.evidence, metrics=areas.metrics
    )
    _schema_validate_areas(accepted, location_schema, locationfile_schema)
    _non_allowed_location_fields_equal(areas, accepted, {"dmInstructions"})
    return accepted


class StoryFirstPipeline:
    """Run or safely resume one lifecycle-owned hidden candidate transaction."""

    def __init__(
        self,
        *,
        candidate_dir: Path,
        provider: str,
        model: Optional[str] = None,
        model_options: Optional[Mapping[str, Any]] = None,
        stage_model_configs: Optional[Mapping[str, Mapping[str, Any]]] = None,
        schemas: Mapping[str, Mapping[str, Any]],
        blocklist: Iterable[str],
        gateway: CompletionGateway,
        generate_batch: Optional[Callable[..., Dict[str, Any]]] = None,
    ):
        self.candidate_dir = Path(candidate_dir)
        if not self.candidate_dir.is_dir() or self.candidate_dir.is_symlink():
            raise ValueError("candidate directory must be a real existing directory")
        if set(schemas) != _REQUIRED_SCHEMAS:
            raise ValueError("story-first pipeline received the wrong schema set")
        self.provider = provider
        if stage_model_configs is None:
            if not isinstance(model, str) or not model:
                raise ValueError("story-first pipeline requires a model")
            base = {"model": model, **dict(model_options or {})}
            stage_model_configs = {stage: base for stage in _MODEL_STAGES}
        if set(stage_model_configs) != set(_MODEL_STAGES):
            raise ValueError("story-first pipeline received the wrong stage model set")
        self.stage_model_configs = copy.deepcopy(dict(stage_model_configs))
        for stage, stage_config in self.stage_model_configs.items():
            if not isinstance(stage_config, dict) or not isinstance(
                stage_config.get("model"), str
            ):
                raise ValueError(f"invalid story-first model config for {stage}")
        self.schemas = copy.deepcopy(dict(schemas))
        self.blocklist = tuple(blocklist)
        self.gateway = gateway
        self.generate_batch = generate_batch
        self.workspace = self.candidate_dir / ".story_first"
        if self.workspace.is_symlink():
            raise ValueError("story-first workspace cannot be a symbolic link")
        self.workspace.mkdir(mode=0o700, exist_ok=True)
        self.state_path = self.workspace / "pipeline_state.json"
        self.result_path = self.workspace / "build_result.json"
        self.implementation_hash = self._implementation_hash()
        self.state = self._load_state()

    def _implementation_hash(self) -> str:
        root = Path(__file__).resolve().parent
        digest = hashlib.sha256()
        for path in sorted(root.rglob("*.py")):
            digest.update(str(path.relative_to(root)).encode("ascii"))
            digest.update(path.read_bytes())
        return digest.hexdigest()

    def cleanup_workspace(self) -> None:
        """Remove only this pipeline's verified private artifacts after publication."""
        if self.workspace.is_symlink() or not self.workspace.is_dir():
            raise ValueError("story-first workspace is not a real directory")
        records = self.state.get("stages")
        if not isinstance(records, dict) or set(records) != set(_STAGES):
            raise ValueError("story-first workspace is not complete")
        if any(record.get("status") != "accepted" for record in records.values()):
            raise ValueError("story-first workspace contains an unaccepted stage")
        result_hash = self.state.get("resultArtifactHash")
        if (
            not isinstance(result_hash, str)
            or not self.result_path.is_file()
            or self.result_path.is_symlink()
            or _file_hash(self.result_path) != result_hash
        ):
            raise ValueError("story-first result artifact is not verified")

        allowed = {
            "pipeline_state.json",
            "build_result.json",
            *_ARTIFACTS.values(),
        }
        entries = list(self.workspace.iterdir())
        if any(
            entry.name not in allowed or entry.is_symlink() or not entry.is_file()
            for entry in entries
        ):
            raise ValueError("story-first workspace contains an unexpected entry")
        if {entry.name for entry in entries} != allowed:
            raise ValueError("story-first workspace is missing an accepted artifact")

        # State remains authoritative until every content artifact is gone. If
        # interruption occurs, the managed candidate is still not publishable.
        for name in sorted(allowed - {"pipeline_state.json"}):
            (self.workspace / name).unlink()
        self.state_path.unlink()
        self.workspace.rmdir()

    def _blank_state(self) -> Dict[str, Any]:
        return {"version": PIPELINE_VERSION, "stages": {}}

    def _load_state(self) -> Dict[str, Any]:
        try:
            retry_transient_filesystem(
                lambda: os.lstat(self.state_path),
                allow_missing=True,
            )
        except FileNotFoundError:
            return self._blank_state()
        state = retry_transient_filesystem(
            lambda: _read_json(self.state_path),
            allow_missing=True,
        )
        if set(state) - {"version", "stages", "resultArtifactHash"}:
            raise ValueError("unknown pipeline-state fields")
        if state.get("version") != PIPELINE_VERSION or not isinstance(
            state.get("stages"), dict
        ):
            raise ValueError("unsupported pipeline state")
        return state

    def _write_state(self) -> None:
        _atomic_write_json(self.state_path, self.state)

    def _artifact_path(self, stage: str) -> Path:
        return self.workspace / _ARTIFACTS[stage]

    def _invalidate_from(self, stage: str) -> None:
        start = _STAGES.index(stage)
        for name in _STAGES[start:]:
            self.state["stages"].pop(name, None)
        self.state.pop("resultArtifactHash", None)
        self._write_state()
        for name in _STAGES[start:]:
            path = self._artifact_path(name)
            if path.exists() or path.is_symlink():
                path.unlink()
        if self.result_path.exists() or self.result_path.is_symlink():
            self.result_path.unlink()

    def _failure_class(self, exc: BaseException) -> str:
        if isinstance(exc, StageExecutionError):
            return exc.evidence.failure_class or "provider"
        if isinstance(exc, (KeyboardInterrupt, SystemExit, InterruptedError)):
            return "interrupted"
        if isinstance(exc, TimeoutError):
            return "timeout"
        if isinstance(exc, jsonschema.ValidationError):
            return "schema"
        if isinstance(exc, (ValueError, KeyError, TypeError)):
            return "semantic"
        return "pipeline"

    def _stage(
        self,
        name: str,
        source: Any,
        build: Callable[[], Any],
        serialize: Callable[[Any], Dict[str, Any]],
        restore: Callable[[Dict[str, Any]], Any],
    ) -> Any:
        source_hash = _value_hash(source)
        path = self._artifact_path(name)
        record = self.state["stages"].get(name)
        if (
            isinstance(record, dict)
            and record.get("status") == "accepted"
            and record.get("sourceHash") == source_hash
            and record.get("implementationHash") == self.implementation_hash
            and isinstance(record.get("artifactHash"), str)
            and path.is_file()
            and not path.is_symlink()
        ):
            try:
                if _file_hash(path) != record["artifactHash"]:
                    raise ValueError("artifact hash mismatch")
                return restore(_read_json(path))
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                jsonschema.ValidationError,
            ):
                pass
        self._invalidate_from(name)
        self.state["stages"][name] = {
            "status": "running",
            "sourceHash": source_hash,
            "implementationHash": self.implementation_hash,
            "safeFailureClass": None,
        }
        self._write_state()
        try:
            result = build()
            artifact = serialize(result)
            _atomic_write_json(path, artifact)
            accepted_hash = _file_hash(path)
            restored = restore(_read_json(path))
        except BaseException as exc:
            failure_class = self._failure_class(exc)
            self.state["stages"][name] = {
                "status": "failed",
                "sourceHash": source_hash,
                "implementationHash": self.implementation_hash,
                "safeFailureClass": failure_class,
            }
            self._write_state()
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            diagnostics = (
                exc.semantic_issues if isinstance(exc, StageExecutionError) else ()
            )
            raise StoryFirstPipelineError(
                name, failure_class, diagnostics=diagnostics
            ) from None
        self.state["stages"][name] = {
            "status": "accepted",
            "sourceHash": source_hash,
            "implementationHash": self.implementation_hash,
            "artifactHash": accepted_hash,
            "safeFailureClass": None,
        }
        self._write_state()
        return restored

    def _common_source(self, seed: StorySeed) -> Dict[str, Any]:
        return {
            "seed": seed.to_prompt_value(),
            "provider": self.provider,
            "stageModels": self.stage_model_configs,
            "blocklist": list(self.blocklist),
            "schemas": self.schemas,
        }

    def _model_for(self, stage: str):
        config = self.stage_model_configs[stage]
        return config["model"], {
            key: value for key, value in config.items() if key != "model"
        }

    def accept_outline(self, seed: StorySeed) -> AcceptedOutline:
        """Accept or resume the outline before the compatibility T031 overview."""
        common = self._common_source(seed)

        def restore_outline(value):
            if set(value) != {"value", "evidence", "metrics"}:
                raise ValueError("invalid outline artifact")
            jsonschema.validate(value["value"], outline_schema())
            semantic_outline_checks(
                value["value"],
                seed.to_prompt_value(),
                self.blocklist,
            )
            return AcceptedOutline(
                value=value["value"],
                evidence=_evidence_from(value["evidence"]),
                metrics=value["metrics"],
            )

        return self._stage(
            "outline",
            common,
            lambda: outline.run(
                seed=seed,
                blocklist=self.blocklist,
                provider=self.provider,
                model=self._model_for("outline")[0],
                model_options=self._model_for("outline")[1],
                gateway=self.gateway,
            ),
            lambda item: _accepted_value(item.value, item.evidence, item.metrics),
            restore_outline,
        )

    def run(self, seed: StorySeed) -> StoryFirstBuildResult:
        common = self._common_source(seed)
        accepted_outline = self.accept_outline(seed)

        def serialize_binding(pair):
            accepted, world = pair
            entry = derive_entry_projection(
                accepted_outline.value, world.areas, world.beat_locations
            )
            return {
                "binding": _json_value(accepted.value),
                "evidence": _evidence_value(accepted.evidence),
                "metrics": _json_value(accepted.metrics),
                "world": {
                    "areas": _json_value(world.areas),
                    "maps": _json_value(world.maps),
                    "beatLocations": _json_value(world.beat_locations),
                    "entry": _json_value(entry),
                },
            }

        def restore_binding(value):
            if set(value) != {"binding", "evidence", "metrics", "world"}:
                raise ValueError("invalid area-binding artifact")
            binding = value["binding"]
            jsonschema.validate(
                binding,
                area_binding_schema(
                    seed.to_prompt_value(), _json_value(accepted_outline.value)
                ),
            )
            semantic_area_binding_checks(
                binding, seed.to_prompt_value(), _json_value(accepted_outline.value)
            )
            areas, maps, beat_locations = compile_area_binding(copy.deepcopy(binding))
            expected_world = {
                "areas": areas,
                "maps": maps,
                "beatLocations": beat_locations,
                "entry": _json_value(
                    derive_entry_projection(
                        accepted_outline.value, areas, beat_locations
                    )
                ),
            }
            if value["world"] != expected_world:
                raise ValueError("compiled world differs from accepted binding")
            validate_compiled_world(areas, maps, beat_locations, self.schemas["map"])
            return (
                AcceptedAreaBinding(
                    value=binding,
                    evidence=_evidence_from(value["evidence"]),
                    metrics=value["metrics"],
                ),
                CompiledWorld(
                    areas=tuple(areas),
                    maps=tuple(maps),
                    beat_locations=beat_locations,
                    entry=expected_world["entry"],
                ),
            )

        accepted_binding, world = self._stage(
            "area_binding",
            {**common, "outline": _json_value(accepted_outline.value)},
            lambda: area_binding.run(
                seed=seed,
                outline=accepted_outline,
                map_schema=self.schemas["map"],
                provider=self.provider,
                model=self._model_for("area_binding")[0],
                model_options=self._model_for("area_binding")[1],
                gateway=self.gateway,
            ),
            serialize_binding,
            restore_binding,
        )

        def restore_plot(value):
            if set(value) != {"value", "evidence", "metrics"}:
                raise ValueError("invalid plot artifact")
            jsonschema.validate(value["value"], self.schemas["plot"])
            beat_to_plot, thread_to_quest = plot_derivation.trusted_mappings(
                accepted_outline
            )
            semantic_plot_checks(
                value["value"],
                _json_value(accepted_outline.value),
                _json_value(world.areas),
                _json_value(world.beat_locations),
                beat_to_plot,
                thread_to_quest,
            )
            return AcceptedPlot(
                value=value["value"],
                evidence=_evidence_from(value["evidence"]),
                metrics=value["metrics"],
            )

        accepted_plot = self._stage(
            "plot_derivation",
            {
                **common,
                "outline": _json_value(accepted_outline.value),
                "world": serialize_binding((accepted_binding, world))["world"],
            },
            lambda: plot_derivation.run(
                seed=seed,
                outline=accepted_outline,
                world=world,
                production_schema=self.schemas["plot"],
                provider=self.provider,
                model=self._model_for("plot_derivation")[0],
                model_options=self._model_for("plot_derivation")[1],
                gateway=self.gateway,
            ),
            lambda item: _accepted_value(item.value, item.evidence, item.metrics),
            restore_plot,
        )

        def restore_filled(value):
            accepted = _accepted_areas_from(value)
            _schema_validate_areas(
                accepted, self.schemas["location"], self.schemas["locationfile"]
            )
            by_id = {area["areaId"]: area for area in world.areas}
            for area in accepted.areas:
                validate_story_first_location_result(
                    {"locations": _json_value(area["locations"])},
                    _json_value(by_id[area["areaId"]]),
                    _json_value(accepted_outline.value),
                    seed.to_prompt_value(),
                    self.blocklist,
                )
            _, thread_to_quest = plot_derivation.trusted_mappings(accepted_outline)
            validate_side_thread_location_projection(
                _json_value(accepted.areas),
                _json_value(accepted_plot.value),
                _json_value(accepted_outline.value),
                _json_value(world.beat_locations),
                thread_to_quest,
            )
            return accepted

        filled = self._stage(
            "location_fill",
            {
                **common,
                "outline": _json_value(accepted_outline.value),
                "world": serialize_binding((accepted_binding, world))["world"],
                "plot": _json_value(accepted_plot.value),
            },
            lambda: location_fill.run(
                seed=seed,
                outline=accepted_outline,
                world=world,
                plot=accepted_plot,
                provider=self.provider,
                loca_schema=self.schemas["location"],
                locationfile_schema=self.schemas["locationfile"],
                blocklist=self.blocklist,
                generate_batch=self.generate_batch,
            ),
            _accepted_areas_value,
            restore_filled,
        )

        def restore_repaired(value):
            accepted = _accepted_areas_from(value)
            _schema_validate_areas(
                accepted, self.schemas["location"], self.schemas["locationfile"]
            )
            duplicates_before = duplicate_npc_placements(_json_value(filled.areas))
            targets = {
                location_id
                for placements in duplicates_before.values()
                for location_id in placements
            }
            before_by_id = {
                location["locationId"]: location
                for area in filled.areas
                for location in area["locations"]
            }
            after_by_id = {
                location["locationId"]: location
                for area in accepted.areas
                for location in area["locations"]
            }
            _non_allowed_location_fields_equal(
                filled, accepted, {"description", "dmInstructions", "npcs"}
            )
            for location_id in set(before_by_id) - targets:
                if before_by_id[location_id] != after_by_id[location_id]:
                    raise ValueError("NPC repair changed an untargeted location")
            if duplicate_npc_placements(_json_value(accepted.areas)):
                raise ValueError("accepted NPC repair contains duplicates")
            before_names = {
                npc["name"].strip().casefold()
                for area in filled.areas
                for location in area["locations"]
                for npc in location.get("npcs", ())
            }
            after_names = {
                npc["name"].strip().casefold()
                for area in accepted.areas
                for location in area["locations"]
                for npc in location.get("npcs", ())
            }
            if before_names != after_names:
                raise ValueError("accepted NPC identity set changed")
            require_ascii(_json_value(accepted.areas), "accepted NPC repair")
            return accepted

        repaired = self._stage(
            "npc_repair",
            {
                **common,
                "outline": _json_value(accepted_outline.value),
                "filledAreas": _json_value(filled.areas),
            },
            lambda: npc_repair.run(
                seed=seed,
                outline=accepted_outline,
                filled=filled,
                loca_schema=self.schemas["location"],
                locationfile_schema=self.schemas["locationfile"],
                provider=self.provider,
                model=self._model_for("npc_repair")[0],
                model_options=self._model_for("npc_repair")[1],
                gateway=self.gateway,
            ),
            _accepted_areas_value,
            restore_repaired,
        )

        def restore_hardened(value):
            accepted = _accepted_areas_from(value)
            _schema_validate_areas(
                accepted, self.schemas["location"], self.schemas["locationfile"]
            )
            _non_allowed_location_fields_equal(
                repaired, accepted, {"dmInstructions", "encounters"}
            )
            if any(
                location.get("encounters")
                for area in accepted.areas
                for location in area["locations"]
            ):
                raise ValueError("accepted candidate contains encounter history")
            migrated, _ = migrate_initial_encounters_to_dm_guidance(
                _json_value(repaired.areas)
            )
            overlaps = social_monster_overlaps(migrated)
            crescendo = next(
                beat["id"]
                for beat in accepted_outline.value["beats"]
                if beat["isCrescendo"]
            )
            beat_to_plot, _ = plot_derivation.trusted_mappings(accepted_outline)
            climax_id = next(
                point["location"]
                for point in accepted_plot.value["plotPoints"]
                if point["id"] == beat_to_plot[crescendo]
            )
            targets = set(overlaps) | {climax_id}
            migrated_by_id = {
                location["locationId"]: location
                for area in migrated
                for location in area["locations"]
            }
            for area in accepted.areas:
                for location in area["locations"]:
                    source = migrated_by_id[location["locationId"]]
                    if location["locationId"] not in targets and (
                        location["dmInstructions"] != source["dmInstructions"]
                    ):
                        raise ValueError("hardening changed untargeted guidance")
                    marker = "POTENTIAL SCENE GUIDANCE (not completed history):"
                    if marker in source["dmInstructions"]:
                        source_tail = source["dmInstructions"].split(marker, 1)[1]
                        if marker not in location["dmInstructions"] or (
                            location["dmInstructions"].split(marker, 1)[1]
                            != source_tail
                        ):
                            raise ValueError("potential-scene guidance changed")
                    if location["locationId"] in overlaps and (
                        "never instantiate both"
                        not in location["dmInstructions"].casefold()
                    ):
                        raise ValueError("accepted same-entity guard is missing")
            climax = next(
                location
                for area in accepted.areas
                for location in area["locations"]
                if location["locationId"] == climax_id
            )
            climax_text = climax["dmInstructions"].casefold()
            for level in range(
                seed.module_controls["levelMin"], seed.module_controls["levelMax"] + 1
            ):
                if f"level {level}" not in climax_text:
                    raise ValueError("accepted climax level guidance is incomplete")
            climax_source = migrated_by_id[climax_id]["dmInstructions"]
            if (
                "POTENTIAL SCENE GUIDANCE (not completed history):" in climax_source
                and "level-specific roster limits above override" not in climax_text
            ):
                raise ValueError("accepted climax scaling precedence is missing")
            require_ascii(_json_value(accepted.areas), "accepted hardened candidate")
            return accepted

        hardened = self._stage(
            "candidate_hardening",
            {
                **common,
                "outline": _json_value(accepted_outline.value),
                "plot": _json_value(accepted_plot.value),
                "repairedAreas": _json_value(repaired.areas),
            },
            lambda: candidate_hardening.run(
                seed=seed,
                outline=accepted_outline,
                filled=repaired,
                plot=accepted_plot,
                loca_schema=self.schemas["location"],
                locationfile_schema=self.schemas["locationfile"],
                provider=self.provider,
                model=self._model_for("candidate_hardening")[0],
                model_options=self._model_for("candidate_hardening")[1],
                gateway=self.gateway,
            ),
            _accepted_areas_value,
            restore_hardened,
        )

        def serialize_creatures(value):
            return {
                "monsters": _json_value(value.monsters),
                "guidance": _json_value(value.guidance),
                "evidence": [_evidence_value(item) for item in value.evidence],
                "metrics": _json_value(value.metrics),
            }

        def restore_creatures(value):
            if set(value) != {"monsters", "guidance", "evidence", "metrics"}:
                raise ValueError("invalid creature artifact")
            accepted = AcceptedCreatures(
                monsters=tuple(value["monsters"]),
                guidance=value["guidance"],
                evidence=tuple(_evidence_from(item) for item in value["evidence"]),
                metrics=value["metrics"],
            )
            if not all(
                isinstance(name, str) and isinstance(text, str)
                for name, text in accepted.guidance.items()
            ):
                raise ValueError("creature guidance must map names to text")
            refs = creature_compile.referenced_creatures(_json_value(hardened.areas))
            filenames = [safe_filename(name) for name in refs]
            if any(not name for name in filenames) or len(filenames) != len(
                set(filenames)
            ):
                raise ValueError(
                    "creature references have unsafe or colliding filenames"
                )
            briefs = {
                brief["name"].strip().casefold(): brief
                for brief in accepted_outline.value["creatureBriefs"]
            }
            if [monster["name"] for monster in accepted.monsters] != refs:
                raise ValueError("compiled creature identity/order changed")
            creature_metrics = accepted.metrics["creatures"]
            if len(creature_metrics) != len(refs):
                raise ValueError("compiled creature metrics count changed")
            if refs and len(accepted.evidence) != len(refs):
                raise ValueError("compiled creature evidence count changed")
            if not refs:
                if (
                    len(accepted.evidence) != 1
                    or accepted.evidence[0].result != "skipped"
                    or accepted.evidence[0].attempts != 0
                ):
                    raise ValueError("skipped creature evidence changed")
            for index, monster in enumerate(accepted.monsters):
                name = monster["name"]
                response_value = _json_value(monster)
                creature_compile._validate_production_creature(
                    response_value,
                    briefs[name.casefold()],
                    self.schemas["monster"],
                    accepted.guidance.get(name, ""),
                )
                metric = creature_metrics[index]
                evidence = accepted.evidence[index]
                expected_stage = f"creature_compile:{safe_filename(name)}"
                if evidence.stage != expected_stage or evidence.result != "accepted":
                    raise ValueError("compiled creature evidence identity changed")
                if (
                    evidence.attempts < 1
                    or metric.get("provenanceMode") != "original"
                    or metric.get("compendiumKey") != ""
                    or metric.get("compendiumSourceHash") is not None
                    or metric.get("attempts") != evidence.attempts
                ):
                    raise ValueError("restored AI-authored creature metadata changed")
            if (
                accepted.metrics.get("originalCount") != len(accepted.monsters)
                or accepted.metrics.get("srdExactCount") != 0
            ):
                raise ValueError("compiled creature authorship counts changed")
            if set(accepted.guidance) - set(refs):
                raise ValueError("creature guidance has an unknown identity")
            return accepted

        creatures = self._stage(
            "creature_compile",
            {
                **common,
                "outline": _json_value(accepted_outline.value),
                "hardenedAreas": _json_value(hardened.areas),
            },
            lambda: creature_compile.run(
                outline=accepted_outline,
                areas=hardened,
                production_schema=self.schemas["monster"],
                provider=self.provider,
                model=self._model_for("creature_compile")[0],
                model_options=self._model_for("creature_compile")[1],
                gateway=self.gateway,
            ),
            serialize_creatures,
            restore_creatures,
        )

        final_areas = _place_creature_guidance(
            hardened,
            creatures,
            self.schemas["location"],
            self.schemas["locationfile"],
        )
        entry = derive_entry_projection(
            accepted_outline.value, final_areas.areas, world.beat_locations
        )
        if entry != world.entry:
            raise ValueError("accepted entry projection changed after area compilation")
        try:
            candidate_integrity = validate_public_candidate_references_and_keys(
                _json_value(final_areas.areas),
                _json_value(accepted_plot.value),
                entry["entryLocationId"],
            )
        except SemanticCorrectionError as exc:
            raise StoryFirstPipelineError(
                "candidate_validation", "semantic", diagnostics=exc.issues
            ) from None
        evidence = (
            accepted_outline.evidence,
            accepted_binding.evidence,
            accepted_plot.evidence,
            *filled.evidence,
            *repaired.evidence,
            *hardened.evidence,
            *creatures.evidence,
        )
        result = StoryFirstBuildResult(
            outline=accepted_outline.value,
            areas=final_areas.areas,
            maps=world.maps,
            plot=accepted_plot.value,
            monsters=creatures.monsters,
            evidence=tuple(evidence),
            entry=entry,
            advisories=tuple(candidate_integrity["advisories"]),
        )
        result_value = {
            "outline": _json_value(result.outline),
            "areas": _json_value(result.areas),
            "maps": _json_value(result.maps),
            "plot": _json_value(result.plot),
            "monsters": _json_value(result.monsters),
            "evidence": [_evidence_value(item) for item in result.evidence],
            "entry": _json_value(result.entry),
            "advisories": _json_value(result.advisories),
        }
        _atomic_write_json(self.result_path, result_value)
        self.state["resultArtifactHash"] = _file_hash(self.result_path)
        self._write_state()
        return result


__all__ = ["StoryFirstPipeline", "StoryFirstPipelineError"]
