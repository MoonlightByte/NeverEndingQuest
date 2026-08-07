# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Adapter from the existing persisted preroll text to scoped dice pools."""

from copy import deepcopy
import random
import re


_GENERIC_PAIR = re.compile(r"\b(d(?:4|6|8|10|12|20|100)):\s*\[([^]]*)\]", re.I)
_ATTACK = re.compile(r"Attack\[(\d+)\]", re.I)
_SAVE = re.compile(r"\b(STR|DEX|CON|INT|WIS|CHA):(\d+)\b", re.I)


class PersistedPrerollSource(object):
    """Consume actor attacks, target saves, then generic dice deterministically."""

    def __init__(self, preroll_text, encounter):
        self.generic = {}
        self.attacks = {}
        self.saves = {}
        self._primary_attack_counts = {}
        cache = encounter.get("preroll_cache") or {}
        consumed = cache.get("consumed")
        self._consumed = deepcopy(consumed) if isinstance(consumed, dict) else {}
        self._consumed.setdefault("generic", {})
        self._consumed.setdefault("attacks", {})
        self._consumed.setdefault("saves", {})
        creatures_by_id = {
            creature.get("combatantId"): creature
            for creature in encounter.get("creatures", [])
            if creature.get("combatantId")
        }
        persisted_order = (encounter.get("preroll_cache") or {}).get(
            "combatantOrder"
        )
        if not isinstance(persisted_order, list):
            persisted_order = list(creatures_by_id)
        self._ids_by_name = {}
        for actor_id in persisted_order:
            creature = creatures_by_id.get(actor_id)
            if not creature:
                continue
            actor_id = creature.get("combatantId")
            name = str(creature.get("name", "")).strip().casefold()
            if not actor_id or not name:
                continue
            self._ids_by_name.setdefault(name, []).append(actor_id)
        self._parse(str(preroll_text or ""))
        self._primary_attack_counts = {
            actor_id: len(values) for actor_id, values in self.attacks.items()
        }
        self._merge_reserve(cache.get("agenticRollReserve"))
        self._discard_consumed()

    def _merge_reserve(self, reserve):
        if not isinstance(reserve, dict):
            return
        for die, values in (reserve.get("generic") or {}).items():
            if isinstance(values, list):
                self.generic.setdefault(str(die).lower(), []).extend(values)
        for actor_id, values in (reserve.get("attacks") or {}).items():
            if isinstance(values, list):
                self.attacks.setdefault(actor_id, []).extend(values)
        for actor_id, abilities in (reserve.get("saves") or {}).items():
            if not isinstance(abilities, dict):
                continue
            target = self.saves.setdefault(actor_id, {})
            for ability, values in abilities.items():
                if isinstance(values, list):
                    target.setdefault(str(ability).upper(), []).extend(values)

    @staticmethod
    def _drop_prefix(pool, count):
        count = max(0, int(count or 0))
        del pool[: min(count, len(pool))]

    def _discard_consumed(self):
        for die, count in self._consumed["generic"].items():
            self._drop_prefix(self.generic.setdefault(die, []), count)
        for actor_id, count in self._consumed["attacks"].items():
            self._drop_prefix(self.attacks.setdefault(actor_id, []), count)
        for actor_id, abilities in self._consumed["saves"].items():
            if not isinstance(abilities, dict):
                continue
            for ability, count in abilities.items():
                self._drop_prefix(
                    self.saves.setdefault(actor_id, {}).setdefault(ability, []),
                    count,
                )

    def _parse(self, text):
        generic_match = re.search(
            r"=== GENERIC DICE.*?=== CREATURE ATTACKS",
            text,
            flags=re.I | re.S,
        )
        generic_text = generic_match.group(0) if generic_match else text
        for die, values in _GENERIC_PAIR.findall(generic_text):
            self.generic[die.lower()] = [
                int(value) for value in values.split(",") if value.strip().isdigit()
            ]

        section = None
        seen = {"attacks": {}, "saves": {}}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if line.startswith("=== CREATURE ATTACKS"):
                section = "attacks"
                continue
            if line.startswith("=== SAVING THROWS"):
                section = "saves"
                continue
            if line.startswith("==="):
                section = None
                continue
            if not line or ":" not in line:
                continue
            name, rest = line.split(":", 1)
            normalized_name = name.strip().casefold()
            candidates = self._ids_by_name.get(normalized_name, [])
            offset = seen.get(section, {}).get(normalized_name, 0)
            actor_id = candidates[offset] if offset < len(candidates) else None
            if not actor_id:
                continue
            seen[section][normalized_name] = offset + 1
            if section == "attacks":
                values = [int(value) for value in _ATTACK.findall(rest)]
                if values:
                    self.attacks[actor_id] = values
            elif section == "saves":
                self.saves[actor_id] = {
                    ability.upper(): [int(value)]
                    for ability, value in _SAVE.findall(rest)
                }

    @staticmethod
    def _pop(pool, label):
        if not pool:
            raise IndexError("Persisted preroll pool exhausted for %s" % label)
        return pool.pop(0)

    def take(self, die):
        key = str(die).lower()
        value = self._pop(self.generic.get(key), key)
        consumed = self._consumed["generic"]
        consumed[key] = int(consumed.get(key, 0) or 0) + 1
        return value

    def take_for(
        self,
        die,
        purpose,
        actor_id=None,
        target_id=None,
        ability=None,
    ):
        if purpose == "attack" and actor_id in self.attacks:
            value = self._pop(self.attacks[actor_id], "attack:%s" % actor_id)
            consumed = self._consumed["attacks"]
            consumed[actor_id] = int(consumed.get(actor_id, 0) or 0) + 1
            return value
        if purpose == "save" and target_id in self.saves:
            key = str(ability or "")[:3].upper()
            if key in self.saves[target_id]:
                value = self._pop(
                    self.saves[target_id][key],
                    "save:%s:%s" % (target_id, key),
                )
                target = self._consumed["saves"].setdefault(target_id, {})
                target[key] = int(target.get(key, 0) or 0) + 1
                return value
        return self.take(die)

    def attack_count(self, actor_id):
        """Return the legacy preroll-declared attacks available this action."""
        return max(1, int(self._primary_attack_counts.get(actor_id, 1) or 1))

    def consumption(self):
        """Return durable absolute cursors for every consumed persisted pool."""
        return deepcopy(self._consumed)


def ensure_agentic_roll_reserve(encounter, actor_ids):
    """Persist a bounded round reserve before model intent resolution.

    Consumption cursors prevent later windows in the same round from reusing
    the first values. The reserve is created only once per round and staged
    events retain the exact rolls used for crash replay.
    """
    cache = encounter.setdefault("preroll_cache", {})
    if isinstance(cache.get("agenticRollReserve"), dict):
        return cache["agenticRollReserve"]
    creatures = [
        creature
        for creature in encounter.get("creatures", [])
        if isinstance(creature, dict) and creature.get("combatantId")
    ]
    abilities = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
    save_count = max(8, len(actor_ids or []) * 2, len(creatures) * 2)
    reserve = {
        "generic": {
            "d%d" % sides: [random.randint(1, sides) for _ in range(256)]
            for sides in (4, 6, 8, 10, 12, 20, 100)
        },
        "attacks": {
            creature["combatantId"]: [random.randint(1, 20) for _ in range(8)]
            for creature in creatures
            if creature.get("type") != "player"
        },
        "saves": {
            creature["combatantId"]: {
                ability: [random.randint(1, 20) for _ in range(save_count)]
                for ability in abilities
            }
            for creature in creatures
        },
    }
    cache["agenticRollReserve"] = reserve
    cache.setdefault("consumed", {"generic": {}, "attacks": {}, "saves": {}})
    return reserve
