# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""The level-up turn the session returns (#323); the retired interview's stage and verdict parsers went with D-COST-2."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LevelUpTurn:
    kind: Literal["interview", "complete", "not_applied"]
    narration: str
