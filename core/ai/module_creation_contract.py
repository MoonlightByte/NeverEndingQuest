"""Canonical contracts for creating a new adventure module.

The DM-facing action has one deliberately small shape: a single non-empty
``narrative`` parameter.  The richer six-field specification is internal and
is validated against an explicit game or standalone-toolkit policy before the
module builder is allowed to create directories.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, Mapping, Optional, Union


CREATE_NEW_MODULE_ACTION = "createNewModule"
CREATE_NEW_MODULE_PARAMETER_KEYS = frozenset({"narrative"})

MODULE_SPEC_FIELDS = frozenset(
    {
        "module_name",
        "num_areas",
        "locations_per_area",
        "level_range",
        "adventure_type",
        "plot_themes",
    }
)
MODULE_ADVENTURE_TYPES = frozenset(
    {"dungeon", "wilderness", "urban", "nautical", "mixed"}
)


class ModuleCreationContractError(ValueError):
    """Raised when a module-creation action or specification is malformed."""


class ModuleCreationRecoveryRequiredError(RuntimeError):
    """Raised when failed-build cleanup cannot be proven complete.

    The message is intentionally static and safe for orchestration/UI handling;
    provider output and low-level filesystem details must stay out of it.
    """


def validate_create_new_module_parameters(parameters: Any) -> str:
    """Validate and return the canonical DM-action narrative.

    No aliases or one-string coercion are accepted.  Keeping this function
    pure lets both pre-semantic validation and the execution boundary enforce
    exactly the same contract.
    """

    if not isinstance(parameters, dict):
        raise ModuleCreationContractError(
            "createNewModule parameters must be an object"
        )
    if set(parameters) != CREATE_NEW_MODULE_PARAMETER_KEYS:
        raise ModuleCreationContractError(
            "createNewModule parameters must contain exactly 'narrative'"
        )
    narrative = parameters["narrative"]
    if not isinstance(narrative, str) or not narrative.strip():
        raise ModuleCreationContractError(
            "createNewModule narrative must be a non-empty string"
        )
    return narrative


def validate_create_new_module_action(action: Any) -> str:
    """Validate one canonical ``createNewModule`` action and return narrative."""

    if not isinstance(action, dict):
        raise ModuleCreationContractError("createNewModule action must be an object")
    if set(action) != {"action", "parameters"}:
        raise ModuleCreationContractError(
            "createNewModule action must contain exactly 'action' and 'parameters'"
        )
    if action.get("action") != CREATE_NEW_MODULE_ACTION:
        raise ModuleCreationContractError("action must be named 'createNewModule'")
    if "parameters" not in action:
        raise ModuleCreationContractError("createNewModule action requires parameters")
    return validate_create_new_module_parameters(action["parameters"])


def validate_create_new_module_actions(actions: Any) -> Optional[str]:
    """Validate the creation action in an action array, if present.

    A creation action must be the sole action so a failed module publication
    cannot follow another state mutation from the same candidate response.
    ``None`` is returned when the array contains no creation action.
    """

    if not isinstance(actions, list):
        raise ModuleCreationContractError("actions must be an array")
    creation_actions = [
        action
        for action in actions
        if isinstance(action, dict) and action.get("action") == CREATE_NEW_MODULE_ACTION
    ]
    if not creation_actions:
        return None
    if len(actions) != 1 or len(creation_actions) != 1:
        raise ModuleCreationContractError(
            "createNewModule must be the sole action in the response"
        )
    return validate_create_new_module_action(creation_actions[0])


@dataclass(frozen=True)
class ModuleCreationPolicy:
    """Allowed dimensions for one module-creation entry point."""

    name: str
    min_areas: int
    max_areas: int
    min_locations_per_area: int
    max_locations_per_area: int


GAME_MODULE_POLICY = ModuleCreationPolicy(
    name="game",
    min_areas=2,
    max_areas=3,
    min_locations_per_area=3,
    max_locations_per_area=7,
)
TOOLKIT_MODULE_POLICY = ModuleCreationPolicy(
    name="toolkit",
    min_areas=1,
    max_areas=10,
    min_locations_per_area=1,
    max_locations_per_area=30,
)
MODULE_CREATION_POLICIES = {
    GAME_MODULE_POLICY.name: GAME_MODULE_POLICY,
    TOOLKIT_MODULE_POLICY.name: TOOLKIT_MODULE_POLICY,
}


def get_module_creation_policy(
    policy: Union[str, ModuleCreationPolicy],
) -> ModuleCreationPolicy:
    if isinstance(policy, ModuleCreationPolicy):
        return policy
    try:
        return MODULE_CREATION_POLICIES[policy]
    except (KeyError, TypeError):
        raise ModuleCreationContractError(
            "module creation policy must be 'game' or 'toolkit'"
        )


def _word_count(value: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", value))


def _validate_plot_themes(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModuleCreationContractError("plot_themes must be useful non-empty text")
    normalized = " ".join(value.strip().split())
    words = _word_count(normalized)
    if not 3 <= words <= 40:
        raise ModuleCreationContractError("plot_themes must contain 3 to 40 words")

    # Prompts request comma/semicolon-separated concrete goals.  Counting those
    # explicit separators is deterministic while avoiding guesses about every
    # natural-language use of "and" within a goal.
    goals = [
        goal.strip()
        for goal in re.split(r"\s*(?:,|;|\n+)\s*", normalized)
        if goal.strip()
    ]
    if not 1 <= len(goals) <= 3:
        raise ModuleCreationContractError(
            "plot_themes must contain 1 to 3 comma- or semicolon-separated goals"
        )
    return normalized


def _validate_module_name(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModuleCreationContractError("module_name must be a non-empty string")
    normalized = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*", normalized):
        raise ModuleCreationContractError(
            "module_name must contain only letters, numbers, and underscore separators"
        )
    return normalized


def _validate_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ModuleCreationContractError(
            f"{field} must be an integer from {minimum} to {maximum}"
        )
    return value


def _validate_level_range(value: Any) -> Dict[str, int]:
    if not isinstance(value, dict) or set(value) != {"min", "max"}:
        raise ModuleCreationContractError(
            "level_range must contain exactly min and max"
        )
    min_level = value["min"]
    max_level = value["max"]
    if type(min_level) is not int or type(max_level) is not int:
        raise ModuleCreationContractError("level_range min and max must be integers")
    if not 1 <= min_level <= max_level <= 20:
        raise ModuleCreationContractError(
            "level_range must satisfy 1 <= min <= max <= 20"
        )
    return {"min": min_level, "max": max_level}


def _validate_adventure_type(value: Any) -> str:
    if type(value) is not str or value not in MODULE_ADVENTURE_TYPES:
        raise ModuleCreationContractError(
            "adventure_type must be one of: "
            + ", ".join(sorted(MODULE_ADVENTURE_TYPES))
        )
    return value


@dataclass(frozen=True)
class ModuleCreationSpec:
    """The exact validated specification consumed by ``BuilderConfig``."""

    module_name: str
    num_areas: int
    locations_per_area: int
    level_range: Dict[str, int]
    adventure_type: str
    plot_themes: str

    @classmethod
    def from_mapping(
        cls,
        value: Any,
        policy: Union[str, ModuleCreationPolicy] = GAME_MODULE_POLICY,
    ) -> "ModuleCreationSpec":
        resolved_policy = get_module_creation_policy(policy)
        if not isinstance(value, dict):
            raise ModuleCreationContractError("module parameters must be a JSON object")
        actual_fields = set(value)
        if actual_fields != MODULE_SPEC_FIELDS:
            missing = sorted(MODULE_SPEC_FIELDS - actual_fields)
            extra = sorted(actual_fields - MODULE_SPEC_FIELDS)
            raise ModuleCreationContractError(
                "module parameters require exactly six fields; "
                f"missing={missing}, extra={extra}"
            )
        return cls(
            module_name=_validate_module_name(value["module_name"]),
            num_areas=_validate_int(
                value["num_areas"],
                "num_areas",
                resolved_policy.min_areas,
                resolved_policy.max_areas,
            ),
            locations_per_area=_validate_int(
                value["locations_per_area"],
                "locations_per_area",
                resolved_policy.min_locations_per_area,
                resolved_policy.max_locations_per_area,
            ),
            level_range=_validate_level_range(value["level_range"]),
            adventure_type=_validate_adventure_type(value["adventure_type"]),
            plot_themes=_validate_plot_themes(value["plot_themes"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "num_areas": self.num_areas,
            "locations_per_area": self.locations_per_area,
            "level_range": dict(self.level_range),
            "adventure_type": self.adventure_type,
            "plot_themes": self.plot_themes,
        }


_LABEL_ALIASES = {
    "module name": "module_name",
    "number of areas": "num_areas",
    "locations per area": "locations_per_area",
    "level range": "level_range",
    "adventure type": "adventure_type",
    "plot themes": "plot_themes",
}
_LABEL_PATTERN = re.compile(
    r"\b(module\s+name|number\s+of\s+areas|locations\s+per\s+area|"
    r"level\s+range|adventure\s+type|plot\s+themes)\s*(?:\*\*)?\s*:\s*(?:\*\*)?\s*",
    re.IGNORECASE,
)


def _unquote(value: str) -> str:
    value = value.strip().strip(",;").rstrip(".").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def normalize_explicit_module_value(
    field: str,
    value: Any,
    policy: Union[str, ModuleCreationPolicy] = GAME_MODULE_POLICY,
) -> Any:
    """Normalize one labeled or typed explicit value, then validate it."""

    resolved_policy = get_module_creation_policy(policy)
    if field == "module_name":
        if not isinstance(value, str):
            raise ModuleCreationContractError("module_name must be text")
        normalized = re.sub(r"\s+", "_", _unquote(value))
        return _validate_module_name(normalized)
    if field in {"num_areas", "locations_per_area"}:
        if isinstance(value, str):
            text = _unquote(value)
            if not re.fullmatch(r"\d+", text):
                raise ModuleCreationContractError(f"{field} must be an integer")
            value = int(text)
        if field == "num_areas":
            return _validate_int(
                value,
                field,
                resolved_policy.min_areas,
                resolved_policy.max_areas,
            )
        return _validate_int(
            value,
            field,
            resolved_policy.min_locations_per_area,
            resolved_policy.max_locations_per_area,
        )
    if field == "level_range":
        if isinstance(value, str):
            match = re.fullmatch(
                r"\s*(\d+)\s*(?:-|to)\s*(\d+)\s*", _unquote(value), re.I
            )
            if not match:
                raise ModuleCreationContractError(
                    "level_range must use 'min-max' or contain min/max"
                )
            value = {"min": int(match.group(1)), "max": int(match.group(2))}
        return _validate_level_range(value)
    if field == "adventure_type":
        if not isinstance(value, str):
            raise ModuleCreationContractError("adventure_type must be text")
        return _validate_adventure_type(_unquote(value).lower())
    if field == "plot_themes":
        if not isinstance(value, str):
            raise ModuleCreationContractError("plot_themes must be text")
        return _validate_plot_themes(_unquote(value))
    raise ModuleCreationContractError(f"unknown module specification field: {field}")


def extract_labeled_module_values(
    narrative: str,
    policy: Union[str, ModuleCreationPolicy] = GAME_MODULE_POLICY,
) -> Dict[str, Any]:
    """Deterministically extract recognized ``Label: value`` fields.

    Values run until the next recognized label, allowing both newline and
    compact comma-separated technical blocks.  Equivalent duplicate labels
    are accepted; contradictory normalized duplicates fail closed.
    """

    if not isinstance(narrative, str) or not narrative.strip():
        raise ModuleCreationContractError("module narrative must be non-empty text")
    matches = list(_LABEL_PATTERN.finditer(narrative))
    extracted: Dict[str, Any] = {}
    for index, match in enumerate(matches):
        label = " ".join(match.group(1).lower().split())
        field = _LABEL_ALIASES[label]
        end = matches[index + 1].start() if index + 1 < len(matches) else len(narrative)
        raw_value = narrative[match.end() : end].rstrip(",;|*- \t\r\n")
        normalized = normalize_explicit_module_value(field, raw_value, policy)
        if field in extracted and extracted[field] != normalized:
            raise ModuleCreationContractError(
                f"conflicting duplicate label for {field}"
            )
        extracted[field] = normalized
    return extracted


def extract_typed_module_overrides(
    parameters: Mapping[str, Any],
    policy: Union[str, ModuleCreationPolicy] = TOOLKIT_MODULE_POLICY,
) -> Dict[str, Any]:
    """Return validated snake-case toolkit overrides using ``is not None``."""

    overrides: Dict[str, Any] = {}
    for field in MODULE_SPEC_FIELDS:
        if field in parameters and parameters[field] is not None:
            overrides[field] = normalize_explicit_module_value(
                field, parameters[field], policy
            )
    return overrides
