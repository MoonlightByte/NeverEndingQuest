# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0

"""Story-first module generation, isolated behind a default-off development flag."""

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
)
from .settings import STAGE_POLICIES, StagePolicy, story_first_enabled
from .pipeline import StoryFirstPipeline, StoryFirstPipelineError
from .compatibility import (
    build_story_first_summary,
    derive_entry_projection,
    expected_context_projection,
    project_overview,
    validate_reconciled_context,
)

__all__ = [
    "AcceptedAreaBinding",
    "AcceptedAreas",
    "AcceptedCreatures",
    "AcceptedOutline",
    "AcceptedPlot",
    "CompiledWorld",
    "STAGE_POLICIES",
    "StageEvidence",
    "StagePolicy",
    "StoryFirstBuildResult",
    "StoryFirstPipeline",
    "StoryFirstPipelineError",
    "StorySeed",
    "build_story_first_summary",
    "derive_entry_projection",
    "expected_context_projection",
    "project_overview",
    "story_first_enabled",
    "validate_reconciled_context",
]
