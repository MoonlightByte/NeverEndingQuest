#!/usr/bin/env python3
"""Regression coverage for companion memory parser hardening."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.ai.conversation_utils import (
    _classify_companion_memory_packet,
    _project_companion_memory_packet,
)
from core.memories.action_parser import ActionParser
from core.memories.companion_memory import (
    MEMORY_QUALITY_DEGRADED,
    MEMORY_QUALITY_HEALTHY,
    MEMORY_QUALITY_MALFORMED,
    MEMORY_QUALITY_SPARSE,
    build_recent_meaningful_event,
    classify_npc_memory_data,
)


BLARG_LEVERAGE_EXCERPT = (
    "Lidda's deft fingers uncovered a hidden bundle of letters concealed in Blarg's coat, "
    "revealing the half-orc's clandestine correspondence. Redax confronted Blarg, demanding "
    "his aid in their quest; after a grim deliberation, Blarg consented, agreeing to accompany "
    "the party on his own terms."
)

BLARG_FOLLOW_EXCERPT = (
    "Today, our party--Redax, Xorn, Athelon, Lidda, and Blarg--continued our grim mission. "
    "The rest of us followed closely: Xorn and Lidda flanking Redax, Athelon and Blarg bringing "
    "up the rear."
)

BLARG_COMBAT_EXCERPT = (
    "Our careful progress through the dim corridors led us to a shadowed ritual chamber. "
    "Meanwhile, Blarg's savage fury scattered the enemy ranks, his strikes relentless and unyielding."
)

BLARG_WATCH_EXCERPT = (
    "Following Redax's commands, Athelon ascended the ladder to the belfry to prepare the bell, "
    "with Xorn stationed below to signal him, and Blarg standing watch at the main doors."
)

BLARG_MENTION_ONLY_EXCERPT = (
    "Blarg sat near the hearth in silence while the party counted rations and prepared for sleep."
)


class TestActionParserHardening(unittest.TestCase):
    def setUp(self):
        self.parser = ActionParser()

    def test_leverage_and_recruitment_are_detected(self):
        actions = self.parser.parse_entry(BLARG_LEVERAGE_EXCERPT, "Blarg")
        readable = {action.get_readable_action() for action in actions}

        self.assertIn("secret exposed", readable)
        self.assertIn("faced coercion", readable)
        self.assertTrue(
            "agreed to accompany" in readable or "joined the party" in readable,
            msg=f"Expected recruitment action in {readable}",
        )

    def test_follow_into_danger_and_rear_guard_are_detected(self):
        actions = self.parser.parse_entry(BLARG_FOLLOW_EXCERPT, "Blarg")
        readable = {action.get_readable_action() for action in actions}

        self.assertIn("stood watch", readable)

    def test_narrative_combat_contribution_is_detected(self):
        actions = self.parser.parse_entry(BLARG_COMBAT_EXCERPT, "Blarg")
        readable = {action.get_readable_action() for action in actions}

        self.assertTrue(
            "broke enemy ranks" in readable or "fought fiercely" in readable,
            msg=f"Expected combat-contribution action in {readable}",
        )

    def test_watch_duty_is_detected(self):
        actions = self.parser.parse_entry(BLARG_WATCH_EXCERPT, "Blarg")
        readable = {action.get_readable_action() for action in actions}

        self.assertIn("kept watch", readable)

    def test_mention_only_entry_does_not_overmatch(self):
        actions = self.parser.parse_entry(BLARG_MENTION_ONLY_EXCERPT, "Blarg")
        self.assertEqual(actions, [])


class TestRawMemoryQualityClassification(unittest.TestCase):
    def test_sparse_packet_classifies_as_sparse(self):
        quality = classify_npc_memory_data({
            "npc_name": "Blarg",
            "core_memories": [],
            "current_emotional_state": {
                "trust": 0.0,
                "power": 0.0,
                "intimacy": 0.0,
                "fear": 0.0,
                "respect": 0.0,
            },
            "behavioral_model": {},
            "total_interactions": 0,
            "mention_count": 2,
            "meaningful_interaction_count": 0,
            "recent_meaningful_events": [],
        })

        self.assertEqual(quality, MEMORY_QUALITY_SPARSE)

    def test_degraded_packet_classifies_as_degraded(self):
        quality = classify_npc_memory_data({
            "npc_name": "Blarg",
            "core_memories": [],
            "current_emotional_state": {
                "trust": 0.0,
                "power": 0.0,
                "intimacy": 0.0,
                "fear": 0.0,
                "respect": 0.0,
            },
            "behavioral_model": {},
            "total_interactions": 4,
            "mention_count": 4,
            "meaningful_interaction_count": 4,
            "recent_meaningful_events": [{
                "timestamp": "1492 Springmonth 2 10:16:00",
                "location": "Ma's Watering Hole",
                "summary": "secret exposed, faced coercion, agreed to accompany",
            }],
        })

        self.assertEqual(quality, MEMORY_QUALITY_DEGRADED)

    def test_healthy_packet_classifies_as_healthy(self):
        quality = classify_npc_memory_data({
            "npc_name": "Blarg",
            "core_memories": [{"id": "blarg_mem_001"}],
            "current_emotional_state": {
                "trust": -0.2,
                "power": 0.1,
                "intimacy": 0.0,
                "fear": 0.2,
                "respect": 0.2,
            },
            "behavioral_model": {},
            "total_interactions": 4,
            "mention_count": 4,
            "meaningful_interaction_count": 4,
            "recent_meaningful_events": [],
        })

        self.assertEqual(quality, MEMORY_QUALITY_HEALTHY)

    def test_bad_shapes_classify_as_malformed(self):
        quality = classify_npc_memory_data({
            "npc_name": "Blarg",
            "core_memories": {},
            "current_emotional_state": [],
            "behavioral_model": {},
            "total_interactions": "four",
        })

        self.assertEqual(quality, MEMORY_QUALITY_MALFORMED)

    def test_recent_meaningful_event_summary_is_bounded(self):
        parser = ActionParser()
        actions = parser.parse_entry(BLARG_LEVERAGE_EXCERPT, "Blarg")
        event = build_recent_meaningful_event("Ma's Watering Hole", actions, "1492 Springmonth 2 10:16:00")

        self.assertIn("summary", event)
        self.assertLessEqual(len(event["summary"]), 90)
        self.assertIn("location", event)


class TestCompressedPacketFallback(unittest.TestCase):
    def test_sparse_packet_projects_bounded_fallback(self):
        packet = {
            "n": "Blarg",
            "ti": 0,
            "mc": 2,
            "es": [0.0, 0.0, 0.0, 0.0, 0.0],
            "bm": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mem": [],
        }

        self.assertEqual(_classify_companion_memory_packet(packet), MEMORY_QUALITY_SPARSE)
        projected = _project_companion_memory_packet(packet, "Berserker")

        self.assertEqual(projected["q"], MEMORY_QUALITY_SPARSE)
        self.assertEqual(projected["r"], "Berserker")
        self.assertEqual(projected["mem"], [])

    def test_degraded_packet_projects_recent_notes(self):
        packet = {
            "n": "Blarg",
            "ti": 4,
            "mc": 4,
            "es": [0.0, 0.0, 0.0, 0.0, 0.0],
            "bm": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mem": [],
            "rm": [
                "secret exposed, faced coercion, agreed to accompany@Ma's Watering Hole",
                "broke enemy ranks, fought fiercely@Cathedral Storage",
            ],
        }

        self.assertEqual(_classify_companion_memory_packet(packet), MEMORY_QUALITY_DEGRADED)
        projected = _project_companion_memory_packet(packet)

        self.assertEqual(projected["q"], MEMORY_QUALITY_DEGRADED)
        self.assertEqual(projected["mem"], [])
        self.assertEqual(len(projected["rm"]), 2)

    def test_healthy_packet_retains_memory_payload(self):
        packet = {
            "n": "Blarg",
            "ti": 2,
            "mc": 2,
            "es": [-0.2, 0.1, 0.0, 0.2, 0.2],
            "bm": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mem": [{"i": "001", "a": ["sx"], "e": [-0.2, 0.0, 0.0, 0.2, 0.0]}],
        }

        self.assertEqual(_classify_companion_memory_packet(packet), MEMORY_QUALITY_HEALTHY)
        projected = _project_companion_memory_packet(packet)

        self.assertEqual(projected["q"], MEMORY_QUALITY_HEALTHY)
        self.assertEqual(len(projected["mem"]), 1)

    def test_malformed_packet_is_excluded(self):
        packet = {
            "n": "Blarg",
            "ti": "bad",
            "es": [0.0, 0.0],
            "bm": [0.0, 0.0, 0.0, 0.0, 0.0],
            "mem": [],
        }

        self.assertEqual(_classify_companion_memory_packet(packet), MEMORY_QUALITY_MALFORMED)
        self.assertIsNone(_project_companion_memory_packet(packet))


if __name__ == "__main__":
    unittest.main()
