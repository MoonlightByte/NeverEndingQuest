# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Level Up Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

"""Level-up helpers shared with the table-driven level-up session (core/managers/level_up_session.py).

The model-guided interview, its validator and the domain author/reviewer layer that lived here were
retired by D-COST-2 (#193): the session's one conversational callsite is the only level-up path.
"""

from contextlib import contextmanager

from utils.capture.live_provider_call import LiveProviderSuperseded
from utils.level_up_contract import LevelUpTurn  # re-exported for the session

__all__ = ["LevelUpTurn", "_level_up_commit_guard"]


@contextmanager
def _level_up_commit_guard(scope):
    if scope is None:
        yield
        return
    with scope.lock:
        if scope.supersession is not None:
            raise LiveProviderSuperseded("level-up operation superseded")
        yield
