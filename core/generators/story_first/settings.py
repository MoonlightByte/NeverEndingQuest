# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Default-off feature state and immutable gold-path stage policies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class StagePolicy:
    temperature: float
    max_attempts: int


STAGE_POLICIES: Mapping[str, StagePolicy] = MappingProxyType(
    {
        "outline": StagePolicy(temperature=0.8, max_attempts=3),
        "area_binding": StagePolicy(temperature=0.45, max_attempts=3),
        "plot_derivation": StagePolicy(temperature=0.55, max_attempts=3),
        "location_fill": StagePolicy(temperature=0.8, max_attempts=3),
        "npc_repair": StagePolicy(temperature=0.35, max_attempts=3),
        "candidate_hardening": StagePolicy(temperature=0.3, max_attempts=3),
        "creature_compile": StagePolicy(temperature=0.45, max_attempts=3),
    }
)

GOLD_PRIOR_BLOCKLIST = (
    "ember",
    "forge",
    "elara",
    "vane",
    "kaelen",
    "orell",
    "rusk",
    "sorell",
)

_GOLD_STAGE_TASK_IDS: Mapping[str, str] = MappingProxyType(
    {
        "outline": "T098",
        "area_binding": "T099",
        "plot_derivation": "T100",
        "npc_repair": "T101",
        "candidate_hardening": "T102",
        "creature_compile": "T103",
    }
)


class StoryFirstProviderUnsupportedError(RuntimeError):
    """The selected provider has no approved story-first gold configuration."""


def gold_model_config(
    provider: str,
    stage: str,
    model_config_module: Optional[ModuleType] = None,
) -> Dict[str, Any]:
    """Return a detached named cloud configuration for one gold-path stage."""
    if provider not in {"openai", "gemini", "lmstudio"}:
        raise StoryFirstProviderUnsupportedError(
            "The story-first gold path requires OpenAI, Gemini, or LM Studio."
        )
    if stage not in _GOLD_STAGE_TASK_IDS:
        raise ValueError(f"unknown story-first model stage: {stage}")
    if model_config_module is None:
        import model_config as model_config_module

    resolver = getattr(model_config_module, "resolve_callsite_config", None)
    if callable(resolver):
        value = resolver(_GOLD_STAGE_TASK_IDS[stage], provider)
    else:
        # Compatibility for isolated consumers that supply the historical
        # config-only module object. Production always takes the registry path.
        legacy_name = {
            "openai": "DM_MAIN_GPT52_NONE",
            "gemini": "DM_MAIN_GEMINI_PRO_LOW",
            "lmstudio": "DM_MAIN_LMSTUDIO",
        }[provider]
        value = getattr(model_config_module, legacy_name, None)
    if not isinstance(value, dict) or not isinstance(value.get("model"), str):
        raise ValueError(f"invalid story-first model configuration: {stage}")
    allowed = {
        "model",
        "reasoning_effort",
        "thinking_level",
        "max_tokens",
        "max_completion_tokens",
    }
    if set(value) - allowed:
        raise ValueError(
            f"unsupported options in story-first model configuration: {stage}"
        )
    return dict(value)


def story_first_enabled(config_module: Optional[ModuleType] = None) -> bool:
    """Return the explicit config flag or headless evaluation opt-in."""
    if config_module is None:
        try:
            import config as config_module
        except ImportError:
            return False

    environment_opt_in = os.environ.get(
        "NEQ_STORY_FIRST_GENERATOR", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    return (
        getattr(config_module, "USE_STORY_FIRST_GENERATOR", False) is True
        or environment_opt_in
    )
