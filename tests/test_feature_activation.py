"""R2: the typed SRD activation of class features (data/srd/progression.json
feature_activation) and the Bonus Actions built from it. Offline, data only."""
from core.combat.bonus_actions import R0_FEATURES, bonus_action_names, bonus_action_problem
from core.leveling.tables import tables

ACTIVATIONS = {"bonusAction", "action", "magicAction", "reaction", "noAction", "passive"}
GENERIC = {"Ability Score Improvement", "Epic Boon", "Fighter Subclass", "Rogue Subclass", "Subclass feature"}


def _table_features(cls):
    rows = tables()["classes"][cls]
    variants = {name: base for base, entry in rows["feature_activation"].items()
                for name in entry.get("table_names") or []}
    return {variants.get(name, name) for level in rows["features_by_level"].values() for name in level} - GENERIC


def test_every_fighter_and_rogue_feature_has_one_typed_activation():
    for cls in ("fighter", "rogue"):
        records = tables()["classes"][cls]["feature_activation"]
        assert set(records) == _table_features(cls)
        for name, entry in records.items():
            assert entry["activation"] in ACTIVATIONS, name
            assert entry["evidence"] and all(e.isascii() and e.strip() for e in entry["evidence"]), name
            assert type(entry["source"]["page"]) is int and entry["source"]["section"].startswith("Classes > "), name


def test_bonus_action_records_quote_the_srd():
    fighter = tables()["classes"]["fighter"]["feature_activation"]
    rogue = tables()["classes"]["rogue"]["feature_activation"]
    assert {n for n, e in fighter.items() if e["activation"] == "bonusAction"} == {"Second Wind"}
    assert {n for n, e in rogue.items() if e["activation"] == "bonusAction"} == {"Cunning Action", "Steady Aim"}
    assert "As a Bonus Action" in fighter["Second Wind"]["evidence"][0]
    assert fighter["Second Wind"]["source"]["page"] == 48
    assert "as a Bonus Action: Dash, Disengage, or Hide" in rogue["Cunning Action"]["evidence"][0]
    assert rogue["Cunning Action"]["source"]["page"] == 62


def test_other_classes_carry_no_activation_yet():
    for cls, rows in tables()["classes"].items():
        assert ("feature_activation" in rows) == (cls in ("fighter", "rogue")), cls


def test_bonus_action_names_follow_class_and_level():
    assert bonus_action_names({"class": "Fighter", "level": 1}) == ["Second Wind"]
    assert bonus_action_names({"class": "Rogue", "level": 1}) == []
    assert bonus_action_names({"class": "Rogue", "level": 2}) == ["Cunning Action"]
    # Steady Aim (Rogue 3) is a Bonus Action in the SRD but not resolved in r0.
    assert bonus_action_names({"class": "Rogue", "level": 3}) == ["Cunning Action"]
    assert bonus_action_names({"class": "Wizard", "level": 5}) == []
    assert bonus_action_names({"class": "Fighter"}) == []
    assert bonus_action_names(None) == []
    assert R0_FEATURES == ("Second Wind", "Cunning Action")


def test_bonus_action_problem():
    fighter = {"class": "Fighter", "level": 1}
    rogue = {"class": "Rogue", "level": 2}
    heal = {"featureName": "Second Wind", "targets": [{"combatantId": "a", "hpDelta": 4, "rolled": 3}]}
    assert bonus_action_problem(fighter, heal) is None
    assert "'Second Wind'" in bonus_action_problem(fighter, {"featureName": "Action Surge"})
    assert "one object" in bonus_action_problem(fighter, [heal, heal])
    assert "heals its user" in bonus_action_problem(fighter, {"featureName": "Second Wind"})
    assert bonus_action_problem(rogue, {"featureName": "Cunning Action", "option": "hide"}) is None
    assert "'disengage'" in bonus_action_problem(rogue, {"featureName": "Cunning Action"})
    assert "'Cunning Action'" in bonus_action_problem(rogue, heal)


def test_second_wind_face_alone_is_enough_and_the_use_is_spent_once():
    from core.combat.bonus_actions import bonus_subintent, drop_bonus_spend
    fighter = {"class": "Fighter", "level": 1}
    live = {"featureName": "Second Wind", "targets": [{"combatantId": "p", "hpDelta": 0, "rolled": 6}]}
    assert bonus_action_problem(fighter, live) is None
    sub = bonus_subintent({"actorId": "p"}, live, "Brannoc Vale")
    assert sub["targets"] == [{"combatantId": "p", "hpDelta": 6, "rolled": 6}]
    assert "heals its user" in bonus_action_problem(
        fighter, {"featureName": "Second Wind", "targets": [{"combatantId": "p", "hpDelta": 0, "rolled": 0}]})
    spend = {"owner": "Brannoc Vale", "kind": "featureUse", "name": "Second Wind", "delta": -1}
    intent = {"resources": [dict(spend), {"owner": "Brannoc Vale", "kind": "ammunition", "name": "Bolt", "delta": -1}]}
    assert drop_bonus_spend(intent, {"resources": [dict(spend, after=0)]}, "Brannoc Vale") == [spend]
    assert intent["resources"] == [{"owner": "Brannoc Vale", "kind": "ammunition", "name": "Bolt", "delta": -1}]
