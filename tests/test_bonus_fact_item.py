"""#1338: T097 receives the typed item Bonus Action the engine applied."""
from core.ai.combat_narration import _bonus_fact

CREATURES = {"p": {"name": "Mira"}}
ITEM = {"nqlId": "item:potion:mira"}
OUTCOME = {"kind": "healing", "targets": [
    {"combatantId": "p", "hpBefore": 3, "hpAfter": 8, "statusAfter": "alive"}]}
RESOURCES = [{"owner": "Mira", "kind": "item", "name": "Potion of Healing", "item": ITEM,
              "delta": -1, "before": 1, "after": 0, "engine": True}]


def test_item_bonus_reaches_the_narrator():
    record = {"item": ITEM, "targetId": "p", "outcome": OUTCOME, "resources": RESOURCES}
    fact = _bonus_fact({"bonusAction": record}, CREATURES)
    assert fact["item"] == ITEM
    assert fact["itemName"] == "Potion of Healing"
    assert fact["targets"] == [{"targetName": "Mira", "hpBefore": 3, "hpAfter": 8, "hpDelta": 5}]
    assert fact["resources"][0]["before"] == 1 and fact["resources"][0]["after"] == 0


def test_feature_bonus_unchanged():
    record = {"featureName": "Second Wind", "outcome": OUTCOME}
    assert _bonus_fact({"bonusAction": record}, CREATURES) == {
        "featureName": "Second Wind",
        "targets": [{"targetName": "Mira", "hpBefore": 3, "hpAfter": 8, "hpDelta": 5}]}


def test_untyped_bonus_dropped():
    assert _bonus_fact({"bonusAction": {"outcome": OUTCOME}}, CREATURES) is None
    assert _bonus_fact({}, CREATURES) is None
