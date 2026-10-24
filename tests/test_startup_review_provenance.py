"""Offline startup replay: real schema/NQL, scripted model verdicts, no networking.

The synthetic authored fixture is the 2026-10-03 17:21:20.595263 response from
desktop-game-001. Only the fictional wire object is retained, not its capture,
request history, credentials, world settings or provider metadata.
"""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import types

import pytest

ROOT = Path(os.environ.get("NEQ_STARTUP_TEST_ROOT", Path(__file__).resolve().parents[1]))
FIXTURE = Path(__file__).parent / "fixtures" / "startup-authored-alden.json"
CAPTURED_STYLE_NOTE = ("Fighting Style: Defense set in classFeatures "
                       "(was classFeatures 'Fighting Style (Defense)')")
SECOND_WIND_NOTE = "Second Wind usage None -> 2/2 shortRest (a Short Rest regains 1) (SRD level 1)"


def _style_entries(sheet):
    return [f["name"] for f in sheet.get("classFeatures") or [] if f["name"].startswith("Fighting Style")]


def _usage(sheet, name):
    return next(f for f in sheet["classFeatures"] if f["name"] == name).get("usage")


@pytest.fixture
def wizard(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Network and operator credential access forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(ROOT))
    for name in list(os.environ):
        if any(word in name.upper() for word in ("API_KEY", "TOKEN", "SECRET")):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NEQ_MULTI_MODEL_CAPTURE", "0")
    monkeypatch.setenv("NQL_APPLY_BINARY", str(ROOT / "bin" /
                       ("nql-apply.exe" if os.name == "nt" else "nql-apply")))
    keyring = types.ModuleType("keyring")
    keyring.get_keyring = lambda: keyring
    keyring.get_password = forbidden
    keyring.set_password = forbidden
    keyring.delete_password = forbidden
    monkeypatch.setitem(sys.modules, "keyring", keyring)
    spec = importlib.util.spec_from_file_location("config", ROOT / "config_template.py")
    config = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "config", config)
    spec.loader.exec_module(config)
    config.OPENAI_API_KEY = "offline-provenance-no-network"
    config.GEMINI_API_KEY = ""
    shutil.copytree(ROOT / "schemas", tmp_path / "schemas")
    (tmp_path / "prompts" / "leveling").mkdir(parents=True)
    shutil.copy2(ROOT / "prompts" / "leveling" / "leveling_info.txt",
                 tmp_path / "prompts" / "leveling" / "leveling_info.txt")
    from utils import startup_wizard
    import model_config
    # These rows drive the whole-reference path (#1278), kept as the rollback profile (D-CREATE-COST-4).
    monkeypatch.setattr(model_config, "STARTUP_REVIEW_MODE", "whole")
    monkeypatch.setattr(startup_wizard.api_client, "create_completion", forbidden)
    monkeypatch.setattr(startup_wizard, "capture_and_fanout", forbidden)
    return startup_wizard


@pytest.fixture
def authored():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_captured_author_replays_through_real_normalization(wizard, authored):
    original = copy.deepcopy(authored)
    assert authored["character"]["equipment_effects"] == []
    assert "savingThrowBonuses" not in authored["character"]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert authored == original
    # #569: the captured "Fighting Style (Defense)" is committed as level-up
    # writes it, so the engine grants Defense's +1 (Chain Mail 16 + 1; the gear is
    # Fighter package A, the authored Shield is not granted).
    assert candidate["character"]["armorClass"] == 17
    assert _style_entries(candidate["character"]) == ["Fighting Style: Defense"]
    assert candidate["character"]["maxHitPoints"] == 12
    assert candidate["character"]["equipment_effects"]
    assert candidate["character"]["savingThrowBonuses"]["constitution"] == 4
    engine = provenance["engine_projection"]
    assert engine["applied"] is True
    assert engine["armorClass"] == 17
    assert engine["equipment_effects"]["entries"] == candidate["character"]["equipment_effects"]
    from core.nql import stats
    totals = stats.totals(engine["status"])
    assert totals["save:constitution"] == candidate["character"]["savingThrowBonuses"]["constitution"]
    # #704: the captured Second Wind "usage": null gets its level-1 pool.
    assert _usage(candidate["character"], "Second Wind") == {"current": 2, "max": 2, "refreshOn": "shortRest",
                                                              "shortRestRegain": 1}
    notes = provenance["mechanics_notes"]
    assert notes[:2] == [CAPTURED_STYLE_NOTE, SECOND_WIND_NOTE] and len(notes) == 3
    assert notes[2].startswith("armorClass 18 -> 17 (engine defense:")
    # Repeated projection, including a sheet already carrying identical totals.
    repeated, repeated_provenance = wizard._prepare_startup_proposal(authored)
    stable, stable_provenance = wizard._prepare_startup_proposal(candidate)
    assert repeated == stable == candidate
    assert repeated_provenance["engine_projection"] == engine
    assert stable_provenance["engine_projection"] == engine
    assert authored == original


@pytest.mark.parametrize("failure", ["unavailable", "gaps"])
def test_failed_or_incomplete_projection_has_no_engine_certificate(wizard, authored, monkeypatch, failure):
    from core.nql import armor_class
    # No engine total to fall back on: the authored one must already be right
    # (Chain Mail 16 + Shield 2 + Defense 1) for the ordinary-armor check.
    authored["character"]["armorClass"] = 19
    projection = armor_class.Projection(
        copy.deepcopy(authored["character"]), failure == "gaps",
        reason="offline unavailable" if failure == "unavailable" else "",
        gaps=["unknown armor"] if failure == "gaps" else [])
    monkeypatch.setattr(armor_class, "project", lambda sheet: projection)
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert provenance["engine_projection"]["applied"] is False
    assert "status" not in provenance["engine_projection"]
    assert "equipment_effects" not in provenance["engine_projection"]
    assert candidate["character"]["equipment_effects"] == []
    assert "savingThrowBonuses" not in candidate["character"]


def test_narrow_engine_certificate_does_not_claim_other_effects(wizard, authored):
    effect = {"name": "Unverified damage boost", "type": "bonus", "target": "damage",
              "value": 99, "description": "Unverified", "source": "author"}
    authored["character"]["equipment_effects"] = [effect]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    # Authored gear is set aside at creation, its effects with it (W8).
    assert effect not in candidate["character"]["equipment_effects"]
    assert effect not in provenance["engine_projection"]["equipment_effects"]["entries"]
    assert provenance["engine_projection"]["equipment_effects"]["selector"] == {"target": "AC"}


def test_authored_hit_points_are_set_exactly_before_projection(wizard, authored):
    # #570: an authored maximum above the derivation is not kept. #696: the
    # projection status the reviewer sees carries the committed maximum.
    authored["character"]["hitPoints"] = authored["character"]["maxHitPoints"] = 13
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert candidate["character"]["maxHitPoints"] == candidate["character"]["hitPoints"] == 12
    assert authored["character"]["maxHitPoints"] == 13
    assert provenance["hit_points"]["expected_maximum"] == 12
    assert provenance["hit_points"]["policy"].startswith("Set exactly")
    assert any(note.startswith("maxHitPoints 13 -> 12") for note in provenance["mechanics_notes"])
    assert any(note.startswith("hitPoints 13 -> 12") for note in provenance["mechanics_notes"])
    hp = provenance["engine_projection"]["status"]["resources"]["hp"]
    assert hp["maximum"] == hp["current"] == candidate["character"]["maxHitPoints"]


@pytest.mark.parametrize("cls, con, race, feats, expected", [
    ("Wizard", 8, "Human", [], 5),                               # 6 - 1
    ("Cleric", 12, "Dwarf", [], 10),                             # 8 + 1 + Dwarven Toughness 1
    ("Barbarian", 10, "Human", [], 12),
    ("Fighter", 14, "Human", ["Tough"], 12),                      # SRD 5.2.1 has no Tough feat
    ("Sorcerer", 1, "Human", [], 1),                              # 6 - 5
])
def test_level_one_hit_points_come_from_progression(wizard, authored, cls, con, race, feats, expected):
    sheet = copy.deepcopy(authored["character"])
    sheet["class"], sheet["race"] = cls, race
    sheet["abilities"]["constitution"] = con
    sheet["feats"] = [{"name": name, "description": "typed"} for name in feats]
    maximum, terms = wizard.expected_starting_hit_points(sheet)
    assert maximum == expected
    from core.leveling import tables
    die = tables.tables()["classes"][cls.casefold()]["hp_at_first_level_base"]
    assert terms[0] == f"{cls} d{die} maximum {die}"
    assert not any(term.startswith("Tough feat") for term in terms)


def test_only_level_one_sheets_are_derived(wizard, authored):
    sheet = copy.deepcopy(authored["character"])
    sheet["level"] = 2
    sheet["hitPoints"] = sheet["maxHitPoints"] = 21
    assert wizard.expected_starting_hit_points(sheet) == (None, [])
    provenance = {}
    result, notes = wizard.startup_mechanics(sheet, provenance=provenance)
    assert result["maxHitPoints"] == result["hitPoints"] == 21
    assert "hit_points" not in provenance
    assert not any("HitPoints" in note for note in notes)


def test_existing_hero_is_never_rederived(wizard, authored, monkeypatch, tmp_path):
    # A saved hero chosen at startup keeps its sheet: no startup_mechanics run.
    hero = copy.deepcopy(authored["character"])
    hero["hitPoints"] = hero["maxHitPoints"] = 15
    path = tmp_path / "saved-hero.json"
    path.write_text(json.dumps(hero), encoding="utf-8")
    monkeypatch.setattr(wizard, "startup_mechanics", lambda *a, **k: pytest.fail("existing hero re-derived"))
    monkeypatch.setattr(wizard, "_set_startup_progress", lambda *a, **k: None)
    commits = []
    monkeypatch.setattr(wizard, "_commit_startup_build",
                        lambda conversation, module, character, **k: commits.append(copy.deepcopy(character)))
    assert wizard._use_existing_startup_character([], "Test_Module", {"path": str(path)}) == hero["name"]
    assert commits == [hero]


@pytest.mark.parametrize("variant, was", [
    ("captured", "classFeatures 'Fighting Style (Defense)'"),
    ("canonical", None),
    ("feat_name", "feats 'Defense'"),
    ("feat_labelled", "feats 'Fighting Style: Defense'"),
    ("double_write", "classFeatures 'Fighting Style (Defense)', feats 'Defense'"),
])
def test_chosen_fighting_style_is_committed_as_level_up_writes_it(wizard, authored, variant, was):
    # #569: the engine grants Defense's +1 only for "Fighting Style: Defense". The
    # entries recording the style are replaced by that one entry, never kept beside it.
    sheet = authored["character"]
    assert sheet["classFeatures"][0]["name"] == "Fighting Style (Defense)"
    if variant == "canonical":
        sheet["classFeatures"][0]["name"] = "Fighting Style: Defense"
    elif variant in ("feat_name", "feat_labelled"):
        moved = sheet["classFeatures"].pop(0)
        moved["name"] = "Defense" if variant == "feat_name" else "Fighting Style: Defense"
        sheet["feats"] = [moved]
    elif variant == "double_write":
        sheet["feats"] = [{"name": "Defense", "description": "Fighting Style feat.", "source": "Fighter level 1"}]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    committed = candidate["character"]
    assert _style_entries(committed) == ["Fighting Style: Defense"]
    assert "Second Wind" in [f["name"] for f in committed["classFeatures"]]
    assert committed.get("feats", []) == []
    assert committed["armorClass"] == provenance["engine_projection"]["armorClass"] == 17
    assert provenance["fighting_style"]["style"] == "Defense"
    style_notes = [note for note in provenance["mechanics_notes"] if note.startswith("Fighting Style")]
    assert style_notes == ([] if was is None else [f"Fighting Style: Defense set in classFeatures (was {was})"])


def test_archery_is_committed_without_an_armor_class_bonus(wizard, authored):
    authored["character"]["classFeatures"][0]["name"] = "Fighting Style (Archery)"
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    committed = candidate["character"]
    assert _style_entries(committed) == ["Fighting Style: Archery"]
    assert committed["classFeatures"][0]["description"].startswith("You gain a +2 bonus to attack rolls")
    assert committed["armorClass"] == 16


def test_ineligible_style_is_left_and_noted(wizard, authored):
    # Paladins gain Fighting Style at level 2.
    sheet = authored["character"]
    sheet["class"] = "Paladin"
    _as_origin(authored, "Paladin", "A", [{"slot": "paladin.A.holy_symbol", "catalog_id": "itemdef:srd/holy-symbol-amulet"}],
               ["itemdef:srd/chain-mail", "itemdef:srd/shield"])
    authored_features = [f["name"] for f in sheet["classFeatures"]]
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    committed = candidate["character"]
    assert [f["name"] for f in committed["classFeatures"]] == authored_features
    assert committed.get("feats", []) == []
    assert committed["armorClass"] == 18
    assert [n for n in provenance["mechanics_notes"] if "Fighting Style" in n] == [
        "Fighting Style Defense is listed, but Paladin level 1 has no Fighting Style feature; "
        "left as written, not applied"]
    assert provenance["fighting_style"]["style"] is None
    assert provenance["fighting_style"]["left_as_written"]


@pytest.mark.parametrize("variant", ["unknown", "two_styles", "reworded", "missing"])
def test_style_not_recorded_as_level_up_writes_it_is_sent_back(wizard, authored, variant):
    # #855: a class that has gained a Fighting Style records it as level-up writes
    # it, the only name the engine grants; otherwise the author gets the exact form
    # back as a correction, never a commit without the style.
    sheet = authored["character"]
    if variant == "unknown":
        sheet["classFeatures"][0]["name"] = "Fighting Style (Protection)"
    elif variant == "two_styles":
        sheet["feats"] = [{"name": "Archery", "description": "Fighting Style feat.", "source": "Fighter level 1"}]
    elif variant == "reworded":
        # The ordinary-armor check follows the engine, which grants nothing for this name.
        sheet["classFeatures"][0]["name"] = "Defense Fighting Style"
    else:
        sheet["classFeatures"].pop(0)
    with pytest.raises(ValueError) as refused:
        wizard._prepare_startup_proposal(authored)
    message = str(refused.value)
    assert message.startswith("Fighter level 1 has 1 Fighting Style and the sheet records 0.")
    assert 'named exactly "Fighting Style: <name>"' in message
    assert "one of: Archery, Defense, Great Weapon Fighting, Two-Weapon Fighting." in message


@pytest.mark.parametrize("race, traits, intent, bonus", [
    ("Dwarf", ["Dwarven Toughness"], None, 1),
    ("Dwarf", [], None, 1),
    ("Dwarf", ["Dwarven Toughness", "Dwarven Toughness"], None, 1),
    # A supplied sheet (no intent) is keyed on its race by exact canonical name only (EXC-COST5-1); a trait
    # name is display text and never grants (B1, nql-c0 S2).
    ("Hill Dwarf", ["Dwarven Toughness"], None, 0),
    ("dwarf", [], None, 0),
    ("Human", ["Dwarven Toughness"], None, 0),
    # The interview passes its typed intent, and race text is never read.
    ("Hill Dwarf", [], {"species_key": "dwarf", "choices": {}}, 1),
    ("Dwarf", [], {"species_key": "human", "choices": {}}, 0),
    ("Dwarf", [], {}, 0),
])
def test_dwarven_toughness_comes_from_the_species(wizard, authored, race, traits, intent, bonus):
    # #855: keyed on the typed species against progression.json hp_bonuses, once.
    sheet = copy.deepcopy(authored["character"])
    sheet["class"], sheet["race"] = "Cleric", race
    sheet["abilities"]["constitution"] = 12
    sheet["racialTraits"] = [{"name": name, "description": "typed"} for name in traits]
    maximum, terms = wizard.expected_starting_hit_points(sheet, intent)
    assert maximum == 8 + 1 + bonus
    assert ("Dwarven Toughness (+1)" in terms) == bool(bonus)


def test_sheet_text_keeps_other_scripts_and_strips_emoji(wizard):
    # #855: only emoji are stripped; Han, kana and Hangul names are kept.
    for text in ("\u674e\u660e", "\u3055\u304f\u3089", "\uc9c0\uc6b0", "\u0418\u0432\u0430\u043d", "Ji-woo"):
        assert wizard.sanitize_character_data(text) == text
    for emoji in ("\U0001F600", "\u2B50", "\U0001F004", "\U0001F170", "\U0001F201", "\u24C2", "\u2694",
                  "\u25B6", "\u2934"):
        assert wizard.sanitize_character_data("Kira" + emoji) == "Kira"


def test_saved_old_shape_style_projects_as_before(wizard, authored):
    # Existing heroes are untouched: genesis matching stays exact, so a saved
    # "Fighting Style (Defense)" sheet projects as it did before #569.
    from core.nql import armor_class
    hero = copy.deepcopy(authored["character"])
    before = copy.deepcopy(hero)
    projection = armor_class.project(hero)
    assert hero == before
    assert projection.applied and projection.armor_class == 18

# ---- #704: use pools and spell slots from the class tables -------------------
# Expected values are the SRD 5.2.1 class tables, written out by hand.

def _pool(current, maximum, refresh, regain=None):
    usage = {"current": current, "max": maximum, "refreshOn": refresh}
    if regain is not None:
        usage["shortRestRegain"] = regain
    return usage


def _as_origin(proposal, cls, package="B", slot_picks=(), equipped=()):
    """The typed class key and package the game writes the class and gear from."""
    proposal["origin"]["class_key"] = cls.casefold()
    proposal["starting_equipment"].update(class_package=package, slot_picks=list(slot_picks), equipped=list(equipped))
    return proposal


def _as_class(sheet, cls, features, **abilities):
    sheet["class"] = cls
    sheet["abilities"].update(abilities)
    if features is not None:
        sheet["classFeatures"] = [{"name": name, "description": "typed", "source": f"{cls} level 1",
                                   "usage": usage} for name, usage in features]
    return sheet


@pytest.mark.parametrize("cls, abilities, pools, slots", [
    ("Fighter", {}, {"Second Wind": _pool(2, 2, "shortRest", 1)}, {}),
    ("Barbarian", {}, {"Rage": _pool(2, 2, "shortRest", 1)}, {}),
    ("Bard", {"charisma": 8}, {"Bardic Inspiration": _pool(1, 1, "longRest")}, {"level1": 2}),
    ("Bard", {"charisma": 16}, {"Bardic Inspiration": _pool(3, 3, "longRest")}, {"level1": 2}),
    ("Paladin", {}, {"Lay On Hands": _pool(5, 5, "longRest")}, {"level1": 2}),
    ("Ranger", {}, {"Favored Enemy": _pool(2, 2, "longRest")}, {"level1": 2}),
    ("Sorcerer", {}, {"Innate Sorcery": _pool(2, 2, "longRest")}, {"level1": 2}),
    ("Wizard", {}, {"Arcane Recovery": _pool(1, 1, "longRest")}, {"level1": 2}),
    ("Warlock", {}, {}, {"level1": 1}),
])
def test_level_one_pools_and_slots_come_from_the_tables(wizard, authored, cls, abilities, pools, slots):
    sheet = authored["character"]
    if cls == "Fighter":
        sheet["abilities"].update(abilities)
    else:
        _as_class(sheet, cls, [(name, None) for name in pools], **abilities)
        _as_origin(authored, cls)
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    committed = candidate["character"]
    assert {name: _usage(committed, name) for name in pools} == pools
    assert {k: v for k, v in committed["spellcasting"]["spellSlots"].items() if v["max"]} == {
        level: {"current": n, "max": n} for level, n in slots.items()}
    assert provenance["use_pools"]["pools"] == pools
    assert provenance["use_pools"]["slots"] == slots
    assert provenance["use_pools"]["missing_features"] == []
    # The engine projection the reviewer sees declares the same pools and slots.
    resources = provenance["engine_projection"]["status"]["resources"]
    for level, n in slots.items():
        assert resources[f"slot:{level[5:]}"]["maximum"] == n
    # Projecting the committed sheet again changes nothing.
    again, _ = wizard._prepare_startup_proposal(candidate)
    assert again == candidate


def test_missing_pool_feature_is_noted_not_invented(wizard, authored):
    _as_class(authored["character"], "Barbarian", [("Unarmored Defense", None)])
    _as_origin(authored, "Barbarian")
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    assert [f["name"] for f in candidate["character"]["classFeatures"]] == ["Unarmored Defense"]
    assert provenance["use_pools"]["missing_features"] == ["Rage"]
    assert ("Rage: no classFeatures entry of that name; its level-1 use pool (2/2 shortRest "
            "(a Short Rest regains 1)) is not set") in provenance["mechanics_notes"]


def test_pools_and_slots_are_set_only_on_level_one_sheets(wizard, authored):
    sheet = _as_class(copy.deepcopy(authored["character"]), "Wizard", [("Arcane Recovery", None)])
    sheet["level"] = 2
    before = copy.deepcopy(sheet)
    provenance = {}
    result, notes = wizard.startup_mechanics(sheet, provenance=provenance)
    assert "use_pools" not in provenance
    assert _usage(result, "Arcane Recovery") is None
    assert result["spellcasting"]["spellSlots"] == before["spellcasting"]["spellSlots"]


def _level_up(sheet, new_level, monkeypatch, tmp_path, choices=None):
    """Commit one level-up through the real session commit, with the tables'
    settled facts, the given choices and no agent; returns the sheet the session
    would write."""
    from core.leveling import tables
    from core.managers import level_up_session
    import updates.update_character_info as character_info
    written = []
    monkeypatch.setattr(character_info, "commit_character_sheet",
                        lambda path, after, **kwargs: written.append(copy.deepcopy(after)))
    monkeypatch.setattr(character_info, "create_character_backup", lambda path: None)
    session = level_up_session.LevelUpSession(sheet["name"], sheet["level"], new_level)
    session._sheet = sheet
    session._path = str(tmp_path / f"{sheet['name'].lower()}.json")
    session._settled = tables.settle(sheet, new_level)
    session._choices = dict(choices or {})
    turn = session._commit("")
    assert len(written) == 1, turn
    return written[0]


@pytest.mark.parametrize("cls, level, abilities, before, after", [
    # Action Surge is gained; a Short Rest refills it, so it has no regain field.
    ("Fighter", 1, {}, [("Second Wind", _pool(1, 2, "shortRest", 1))],
     {"Second Wind": _pool(1, 2, "shortRest", 1), "Action Surge (one use)": _pool(1, 1, "shortRest")}),
    # Lay On Hands grows by 5 (current too); Channel Divinity regains one on a Short Rest.
    ("Paladin", 2, {}, [("Lay On Hands", _pool(4, 10, "longRest")), ("Paladin's Smite", _pool(1, 1, "longRest"))],
     {"Lay On Hands": _pool(9, 15, "longRest"), "Paladin's Smite": _pool(1, 1, "longRest"),
      "Channel Divinity": _pool(2, 2, "shortRest", 1)}),
    # Font of Inspiration: same maximum, now refilled by a Short Rest.
    ("Bard", 4, {"charisma": 16}, [("Bardic Inspiration", _pool(1, 3, "longRest"))],
     {"Bardic Inspiration": _pool(1, 3, "shortRest")}),
    ("Fighter", 10, {}, [("Second Wind", _pool(4, 4, "shortRest", 1)), ("Action Surge", _pool(1, 1, "shortRest")),
                         ("Indomitable", _pool(1, 1, "longRest"))],
     {"Second Wind": _pool(4, 4, "shortRest", 1), "Action Surge": _pool(1, 1, "shortRest"),
      "Indomitable": _pool(1, 1, "longRest")}),
    # A Rage saved with the old longRest refresh is corrected at its next level-up.
    ("Barbarian", 1, {}, [("Rage", _pool(2, 2, "longRest"))], {"Rage": _pool(2, 2, "shortRest", 1)}),
    # Charisma dropped since level 1: the maximum follows it down and current is
    # clamped, since the engine refuses a current above the maximum.
    ("Bard", 5, {"charisma": 12}, [("Bardic Inspiration", _pool(3, 3, "shortRest"))],
     {"Bardic Inspiration": _pool(1, 1, "shortRest")}),
])
def test_level_up_writes_pools_from_the_tables(wizard, authored, monkeypatch, tmp_path,
                                               cls, level, abilities, before, after):
    from core.leveling import tables
    sheet = _as_class(authored["character"], cls, before, **abilities)
    sheet["level"] = level
    sheet["experience_points"] = tables.xp_threshold(level + 1)
    leveled = _level_up(sheet, level + 1, monkeypatch, tmp_path)
    assert leveled["level"] == level + 1
    assert {name: _usage(leveled, name) for name in after} == after
    from core.nql import armor_class
    assert armor_class.project(leveled).applied  # the engine's genesis accepts every pool


@pytest.mark.parametrize("level, before, after", [
    (1, {"level1": {"current": 1, "max": 1}}, {"level1": {"current": 1, "max": 2}}),
    (2, {"level1": {"current": 2, "max": 2}}, {"level2": {"current": 2, "max": 2}}),
    (4, {"level2": {"current": 0, "max": 2}}, {"level3": {"current": 0, "max": 2}}),
])
def test_warlock_level_up_moves_pact_slots_as_one_set(wizard, authored, monkeypatch, tmp_path, level, before, after):
    # H4-Q4 (a): Warlock pact slots are level 1 at Warlock 1-2, level 2 at 3-4, level 3 at 5-6.
    from core.leveling import tables
    sheet = _as_class(authored["character"], "Warlock", None)
    sheet["level"] = level
    sheet["experience_points"] = tables.xp_threshold(level + 1)
    sheet["spellcasting"]["spellSlots"].update(before)
    leveled = _level_up(sheet, level + 1, monkeypatch, tmp_path)
    assert {k: v for k, v in leveled["spellcasting"]["spellSlots"].items() if v["max"] or v["current"]} == after
    from core.nql import armor_class
    assert armor_class.project(leveled).applied


# ---- #769: level-up reads and writes list-form skills ------------------------
# Startup writes skills as a list of proficient names (the schema's recommended
# form); expertise is the typed "expertise" field.

def _expertise_point(sheet, new_level):
    from core.leveling import tables
    return next(p for p in tables.settle(sheet, new_level).choice_points if p.get("kind") == "expertise")


@pytest.mark.parametrize("expertise, offered", [
    (None, ["Athletics", "Intimidation", "Perception", "Survival"]),
    (["Perception"], ["Athletics", "Intimidation", "Survival"]),
])
def test_list_form_skills_offer_expertise_in_proficient_skills(wizard, authored, expertise, offered):
    sheet = _as_class(authored["character"], "Bard", None)
    assert sheet["skills"] == ["Athletics", "Intimidation", "Perception", "Survival"]
    if expertise is not None:
        sheet["expertise"] = expertise
    assert sorted(_expertise_point(sheet, 2)["options"]) == offered


def test_list_form_expertise_round_trip_keeps_every_skill(wizard, authored, monkeypatch, tmp_path):
    from core.leveling import tables
    from core.nql import armor_class, stats
    sheet = _as_class(authored["character"], "Bard", None)
    sheet["experience_points"] = tables.xp_threshold(2)
    point = _expertise_point(sheet, 2)
    leveled = _level_up(sheet, 2, monkeypatch, tmp_path, {point["id"]: ["Perception", "Athletics"]})
    assert leveled["skills"] == ["Athletics", "Intimidation", "Perception", "Survival"]
    assert leveled["expertise"] == ["Perception", "Athletics"]
    projection = armor_class.project(leveled)
    assert projection.applied
    totals = stats.totals(projection.status)
    wisdom = tables.modifier(leveled["abilities"]["wisdom"])
    strength = tables.modifier(leveled["abilities"]["strength"])
    pb = tables.proficiency_bonus(2)
    assert totals["skill:perception"] == wisdom + 2 * pb
    assert totals["skill:athletics"] == strength + 2 * pb
    assert totals["skill:survival"] == wisdom + pb


def test_list_form_new_skill_is_appended_once(wizard, authored, monkeypatch, tmp_path):
    # The commit's write path, given picks directly (the offered options are
    # checked before the commit): a skill not yet listed is appended in its
    # display form, and a second spelling of a listed skill adds nothing.
    from core.leveling import tables
    sheet = _as_class(authored["character"], "Bard", None)
    sheet["skills"] = ["Athletics", "Sleight of Hand"]
    sheet["experience_points"] = tables.xp_threshold(2)
    point = _expertise_point(sheet, 2)
    leveled = _level_up(sheet, 2, monkeypatch, tmp_path, {point["id"]: ["sleight_of_hand", "stealth"]})
    assert leveled["skills"] == ["Athletics", "Sleight of Hand", "Stealth"]
    assert leveled["expertise"] == ["Sleight of Hand", "Stealth"]


def test_list_form_skills_survive_consecutive_level_ups(wizard, authored, monkeypatch, tmp_path):
    # Each level-up starts from the sheet the last one wrote: a level with no
    # skill choice leaves the list and expertise as they were, and the next
    # Expertise menu (Bard 9) does not offer the skills already taken.
    import copy
    from core.leveling import tables
    sheet = _as_class(authored["character"], "Bard", None)
    sheet["experience_points"] = tables.xp_threshold(2)
    point = _expertise_point(sheet, 2)
    two = _level_up(sheet, 2, monkeypatch, tmp_path, {point["id"]: ["Perception", "Athletics"]})
    two["experience_points"] = tables.xp_threshold(3)
    three = _level_up(copy.deepcopy(two), 3, monkeypatch, tmp_path)
    assert three["level"] == 3
    assert three["skills"] == ["Athletics", "Intimidation", "Perception", "Survival"]
    assert three["expertise"] == ["Perception", "Athletics"]
    three["level"], three["experience_points"] = 8, tables.xp_threshold(9)
    point = _expertise_point(three, 9)
    assert sorted(point["options"]) == ["Intimidation", "Survival"]
    nine = _level_up(three, 9, monkeypatch, tmp_path, {point["id"]: ["Intimidation", "Survival"]})
    assert nine["skills"] == ["Athletics", "Intimidation", "Perception", "Survival"]
    assert nine["expertise"] == ["Perception", "Athletics", "Intimidation", "Survival"]


def test_legacy_dict_skills_read_as_before(wizard, authored):
    from core.leveling import choices
    sheet = authored["character"]
    sheet["skills"] = {"Athletics": 5, "Perception": 5, "Survival": 3}
    sheet["proficiencyBonus"] = 2
    # Wis 13 (+1): Perception 5 = 1 + 2 x 2 is expertise; Survival 3 = 1 + 2 is proficient.
    assert choices._skill_multipliers(sheet) == {"athletics": 1, "perception": 2, "survival": 1}


def _rest(sheet, kind):
    from core.nql import resources
    outcome = resources.rest([sheet], kind)
    assert outcome.ok, outcome.reason
    return outcome.sheets[0], outcome.restored[sheet["name"]]


def test_short_rest_regains_one_second_wind_and_long_rest_refills(wizard, authored):
    sheet = authored["character"]
    next(f for f in sheet["classFeatures"] if f["name"] == "Second Wind")["usage"] = _pool(0, 2, "shortRest", 1)
    seen = []
    for kind in ("short", "short", "short"):
        sheet, restored = _rest(sheet, kind)
        seen.append((_usage(sheet, "Second Wind")["current"], restored))
    assert seen == [(1, ["Second Wind uses"]), (2, ["Second Wind uses"]), (2, [])]
    next(f for f in sheet["classFeatures"] if f["name"] == "Second Wind")["usage"]["current"] = 0
    sheet, restored = _rest(sheet, "long")
    assert _usage(sheet, "Second Wind") == _pool(2, 2, "shortRest", 1) and "Second Wind uses" in restored


def test_short_rest_refills_a_pool_without_a_regain_and_pact_slots(wizard, authored):
    sheet = _as_class(authored["character"], "Warlock", [("Magical Cunning", _pool(0, 3, "shortRest"))])
    sheet["spellcasting"]["spellSlots"]["level1"] = {"current": 0, "max": 1}
    sheet, restored = _rest(sheet, "short")
    assert _usage(sheet, "Magical Cunning") == _pool(3, 3, "shortRest")
    assert sheet["spellcasting"]["spellSlots"]["level1"] == {"current": 1, "max": 1}
    assert restored == ["level 1 spell slots", "Magical Cunning uses"]


def test_saved_hero_below_the_table_is_raised_on_its_next_write(wizard, authored):
    # H4-Q1 (A): raise only, current untouched, journaled; the next rest refills.
    from core.validation.character_validator import AICharacterValidator
    hero = _as_class(copy.deepcopy(authored["character"]), "Wizard", [("Arcane Recovery", None)])
    validator = AICharacterValidator()
    raised = validator._raise_pools_to_tables(hero)
    assert _usage(hero, "Arcane Recovery") is None  # the caller's sheet is not mutated
    assert _usage(raised, "Arcane Recovery") == _pool(0, 1, "longRest")
    assert raised["spellcasting"]["spellSlots"]["level1"] == {"current": 0, "max": 2}
    assert validator.corrections_made == ["Arcane Recovery usage added: 0/1 longRest (SRD Wizard level 1)",
                                          "spellSlots level1 max 0 -> 2 (SRD Wizard level 1)"]
    rested, _ = _rest(raised, "long")
    assert _usage(rested, "Arcane Recovery") == _pool(1, 1, "longRest")
    assert rested["spellcasting"]["spellSlots"]["level1"] == {"current": 2, "max": 2}
    assert validator._raise_pools_to_tables(rested) is rested


def test_raise_never_lowers_and_leaves_ability_pools_to_level_up(wizard, authored):
    from core.leveling import tables
    from core.validation.character_effects_validator import AICharacterEffectsValidator
    above = copy.deepcopy(authored["character"])
    next(f for f in above["classFeatures"] if f["name"] == "Second Wind")["usage"] = _pool(1, 5, "shortRest", 1)
    before = copy.deepcopy(above)
    assert tables.raise_to_tables(above) == [] and above == before
    # H4-Q2 (A): a Charisma rise does not move Bardic Inspiration until level-up.
    bard = _as_class(copy.deepcopy(authored["character"]), "Bard", [("Bardic Inspiration", _pool(1, 1, "longRest"))],
                     charisma=16)
    bard["spellcasting"]["spellSlots"]["level1"] = {"current": 2, "max": 2}
    before = copy.deepcopy(bard)
    assert tables.raise_to_tables(bard) == [] and bard == before
    # A pool feature written with a suffix is matched by the typed srd_name T125
    # gave it, as level-up matches it; its whole name alone is no pool (keyword
    # validation V4: no name is cut).
    cleric = _as_class(copy.deepcopy(authored["character"]), "Cleric",
                       [("Channel Divinity (2/rest)", _pool(1, 1, "shortRest"))])
    cleric["level"] = 2
    unnamed = copy.deepcopy(cleric)
    assert not [note for note in tables.raise_to_tables(unnamed) if note.startswith("Channel Divinity")]
    next(f for f in cleric["classFeatures"] if f["name"] == "Channel Divinity (2/rest)")["srd_name"] = "Channel Divinity"
    assert tables.raise_to_tables(cleric)[0] == "Channel Divinity (2/rest) max 1 -> 2 (SRD Cleric level 2)"
    assert _usage(cleric, "Channel Divinity (2/rest)") == _pool(1, 2, "shortRest")
    # H4-Q4 (a): a stale Warlock 3's pact slots move to level 2 as one set; they
    # are not raised beside the level 1 slots (4 slots).
    warlock = _as_class(copy.deepcopy(authored["character"]), "Warlock", None)
    warlock["level"] = 3
    warlock["spellcasting"]["spellSlots"]["level1"] = {"current": 1, "max": 2}
    assert tables.raise_to_tables(warlock) == [
        "spellSlots level1 1/2 -> 0/0 (pact slots are level2 at Warlock level 3)",
        "spellSlots level2 0/0 -> 1/2 (SRD Warlock level 3 pact slots)"]
    assert {k: v for k, v in warlock["spellcasting"]["spellSlots"].items() if v["max"]} == {
        "level2": {"current": 1, "max": 2}}
    assert tables.raise_to_tables(warlock) == []
    # The effects validator runs the same step before its AC projection.
    short = _as_class(copy.deepcopy(authored["character"]), "Sorcerer", [("Innate Sorcery", _pool(1, 1, "longRest"))])
    effects = AICharacterEffectsValidator()
    effects.corrections_made = []
    corrected = effects.calculate_equipment_effects(short)
    assert _usage(corrected, "Innate Sorcery") == _pool(1, 2, "longRest")
    assert "Innate Sorcery max 1 -> 2 (SRD Sorcerer level 1)" in effects.corrections_made
    assert "spellSlots level1 max 0 -> 2 (SRD Sorcerer level 1)" in effects.corrections_made


_NO_CLAIMS = {"asks": [], "refused": []}


def _engine_finalize(authored):
    """A captured whole-path finalize as the engine path sends it (D-CREATE-COST-5): typed intent, creative and
    starting_equipment, no sheet. Each pick is the option the captured sheet names, never one granted twice;
    the base scores are its scores less the background increase that leaves a standard array (else a point
    buy)."""
    import re
    from core.nql import creation_scope
    sheet = authored["character"]
    text = json.dumps(sheet)
    keys = {"Human": "human", "Dwarf": "dwarf"}
    origin = authored.get("origin") or {"class_key": "fighter", "background_key": "soldier"}
    intent = {"class_key": origin["class_key"], "species_key": keys[sheet["race"]],
              "background_key": origin["background_key"], "choices": {},
              "considering": {"class_keys": [], "species_keys": [], "background_keys": []}, "ability_scores": None}
    origins = json.loads((ROOT / "data" / "srd_character_origins.json").read_text(encoding="utf-8"))
    taken = set(next(b for b in origins["backgrounds"] if b["key"] == intent["background_key"])["skill_keys"])
    mastery = next((f["description"] for f in sheet.get("classFeatures") or [] if f["name"] == "Weapon Mastery"), "")
    named = re.findall(r"properties of (.+?)\.", mastery)
    # A sheet that never names its masteries (Alden) masters the weapons it attacks with.
    mastered = (re.split(r",? and |, ", named[0]) if named
                else [row["name"] for row in sheet.get("attacksAndSpellcasting") or [] if row.get("type") != "spell"])
    for _ in range(4):  # a pick opens its own sub-picks
        for cid, point in creation_scope.issued_points(intent).items():
            if cid in intent["choices"]:
                continue
            options = list(point.get("option_keys") or [])
            if cid.endswith(".ability-scores"):
                fits = []
                for option in options:
                    base = dict(sheet["abilities"])
                    raises = re.findall(r"\+(\d) (\w+)", option)
                    if raises and raises[0][1] == "each":  # "+1 each to Strength, Dexterity and Constitution"
                        raises = [("1", a) for a in re.findall(r"[A-Z]\w+", option)]
                    for amount, ability in raises:
                        base[ability.lower()] -= int(amount)
                    if sorted(base.values()) == [8, 10, 12, 13, 14, 15]:
                        fits.insert(0, (option, "standard_array", base))
                    elif all(8 <= v <= 15 for v in base.values()):
                        fits.append((option, "point_buy", base))
                intent["choices"][cid] = [fits[0][0]]
                intent["ability_scores"] = {"method": fits[0][1], "assignment": fits[0][2]}
                continue
            if point.get("free_pick") and point["name"] == "Weapon Mastery":
                padded = mastered + [w for w in ("Longsword", "Greatsword", "Javelin") if w not in mastered]
                intent["choices"][cid] = padded[:point["count"]]
                continue
            options = [o for o in options if o not in taken]
            named = [o for o in options if re.search(r"\b%s\b" % re.escape(str(o)), text)]
            intent["choices"][cid] = (named + [o for o in options if o not in named])[:point["count"]]
            taken.update(intent["choices"][cid])
    creative = {k: sheet[k] for k in ("name", "alignment", "personality_traits", "ideals", "bonds", "flaws")}
    return {"version": 1, "decision": "finalize_character", "narration": authored["narration"],
            "confirmation": dict(authored["confirmation"], player_message_index=0), "intent": intent,
            "starting_equipment": copy.deepcopy(authored["starting_equipment"]),
            "creative": dict(creative, backstory=None, appearance=None, feature_descriptions=None),
            "choice_turn": _NO_CLAIMS}


def run_interview(wizard, authored, monkeypatch, *, review, stop_after_rejection=False):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = _engine_finalize(authored)
    original = copy.deepcopy(proposal)
    conversation = [{"role": "user", "content": "I approve Alden's complete current build."}]
    commits = []
    author_requests = []
    reviewer_requests = []
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda c, m, s, **k: commits.append(copy.deepcopy(s)))

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            payload = json.loads(messages[-1]["content"])  # the review payload is the last item (D-CREATE-COST-1)
            reviewer_requests.append(copy.deepcopy(payload))
            return json.dumps(review(payload))
        author_requests.append(copy.deepcopy(messages))
        if stop_after_rejection and any("Rejected startup proposal" in m["content"] or '"rejected_proposal"' in m["content"]
                                        for m in messages if m["role"] == "system"):
            raise LiveProviderSuperseded("test-only stop after observed rejection")
        return json.dumps(proposal)

    monkeypatch.setattr(wizard, "get_ai_response", model)
    if stop_after_rejection:
        with pytest.raises(LiveProviderSuperseded):
            wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
        result = None
    else:
        result = wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    assert proposal == original
    return result, conversation, commits, author_requests, reviewer_requests


def test_actual_interview_reviews_the_engine_built_sheet_and_publishes_it(wizard, authored, monkeypatch):
    def review(payload):
        # D-CREATE-COST-5: the author sent intent and creative; the engine built the sheet under review.
        assert "character" not in payload["authored_proposal"]
        assert payload["authored_proposal"]["creative"]["name"] == authored["character"]["name"]
        candidate = payload["proposal"]["character"]
        assert candidate["name"] == authored["character"]["name"]
        assert candidate["armorClass"] == 17 and candidate["maxHitPoints"] == 12
        assert candidate["equipment_effects"] and candidate["savingThrowBonuses"]
        assert _style_entries(candidate) == ["Fighting Style: Defense"]
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        assert payload["normalization_provenance"]["engine_build"]["untyped"] == []
        changes = payload["committed_facts"]["startup_mechanics"]["changes"]
        assert SECOND_WIND_NOTE in changes
        assert changes[-1].startswith("armorClass 11 -> 17")
        return {"version": 1, "accepted": True, "feedback": "Engine-built sheet reviewed.",
                "needs_player_clarification": False}

    result, conversation, commits, authors, reviewers = run_interview(wizard, authored, monkeypatch, review=review)
    # The first answer re-scopes once (the menu becomes the build's scope), then it is reviewed.
    assert len(authors) == 2 and len(reviewers) == len(commits) == 1
    assert result == commits[0] == reviewers[0]["proposal"]["character"]
    assert wizard._startup_progress(conversation)["phase"] == "approved"
    records = [json.loads(m["content"]) for m in conversation
               if m["role"] == "system" and m["content"].startswith("{")]
    built = next(i for i, r in enumerate(records) if r.get("task_purpose") == "startup_engine_build")
    approved = next(i for i, r in enumerate(records) if r.get("phase") == "approved")
    # The typed build record precedes the approved checkpoint, so the archive keeps it.
    assert built < approved
    built = records[built]
    assert built["untyped"] == [] and built["engine_build"] and "creative_extra" in built


@pytest.mark.parametrize("defect", ["narration", "identity"])
@pytest.mark.parametrize("needs_clarification", [False, True])
def test_negative_review_retains_authorship_and_never_commits(wizard, authored, monkeypatch, defect, needs_clarification):
    if defect == "narration":
        authored["narration"] = "You have arrived and your character was saved."
    else:
        authored["character"]["name"] = "Unapproved replacement"

    def review(payload):
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        if defect == "identity":
            # Creative fields are copied as written (amendment 1a): the reviewer sees the authored name.
            assert payload["proposal"]["character"]["name"] == "Unapproved replacement"
        return {"version": 1, "accepted": False, "feedback": "Rejected " + defect,
                "needs_player_clarification": needs_clarification}

    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=review, stop_after_rejection=True)
    assert result is None and commits == []
    assert len(reviewers) == 1
    correction = next(json.loads(m["content"]) for m in authors[-1]
                      if m["role"] == "system" and '"rejected_proposal"' in m["content"])
    assert correction["rejected_proposal"] == reviewers[0]["authored_proposal"]
    assert correction["canonical_candidate"] == reviewers[0]["proposal"]
    assert correction["normalization_provenance"] == reviewers[0]["normalization_provenance"]
    assert correction["needs_player_clarification"] is needs_clarification
    if needs_clarification:
        assert correction["instruction"] == "Propose a continue_interview question; do not finalize."
    assert not any(m["role"] == "assistant" for m in conversation)
    assert not any('"startup_engine_build"' in m["content"] for m in conversation)


@pytest.mark.parametrize("defect", ["approval", "index", "schema", "refusal"])
def test_invalid_consent_or_schema_cannot_reach_review(wizard, authored, monkeypatch, defect):
    def defective(proposal):
        if defect == "approval":
            proposal["confirmation"]["whole_build_approved"] = False
        elif defect == "schema":
            proposal["intent"]["ability_scores"] = None
        elif defect == "refusal":  # an engine refusal is a typed rejection of the turn (amendment 1e)
            proposal["intent"]["ability_scores"]["assignment"]["strength"] = 16
        return proposal

    engine_finalize = _engine_finalize
    monkeypatch.setitem(globals(), "_engine_finalize", lambda a: defective(engine_finalize(a)))
    if defect == "index":
        # run_interview uses 0; intercept parsing's reference instead.
        monkeypatch.setattr(wizard, "_latest_player_index", lambda messages: 99)
    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=lambda p: pytest.fail("Review must not run"),
        stop_after_rejection=True)
    assert result is None and not commits and not reviewers
    rejection = next(m["content"] for m in authors[-1]
                     if m["role"] == "system" and "Rejected startup proposal" in m["content"])
    if defect == "refusal":
        assert "The engine cannot build this character" in rejection


def test_fenced_json_uses_real_startup_parser_without_changing_probe(wizard, authored):
    from utils.startup_contract import parse_startup_response
    assert parse_startup_response("```json\n" + json.dumps(authored) + "\n```",
                                  latest_user_index=12) == authored


def test_network_is_forbidden(wizard):
    with pytest.raises(AssertionError, match="forbidden"):
        socket.create_connection(("openrouter.ai", 443))


def test_superseded_review_cannot_publish(wizard, authored, monkeypatch):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = _engine_finalize(authored)
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda *a, **k: pytest.fail("No commit after cancellation"))

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            kwargs["live_scope"].request_supersession("offline-cancellation")
            return json.dumps({"version": 1, "accepted": True, "feedback": "Reviewed.",
                               "needs_player_clarification": False})
        return json.dumps(proposal)

    monkeypatch.setattr(wizard, "get_ai_response", model)
    conversation = [{"role": "user", "content": "I approve the complete build."}]
    with pytest.raises(LiveProviderSuperseded):
        wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    assert not any(m["role"] == "assistant" for m in conversation)


def test_continue_interview_never_projects_or_commits(wizard, monkeypatch):
    monkeypatch.setattr(wizard, "startup_mechanics", lambda *a, **k: pytest.fail("No projection of an interview"))
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda *a, **k: pytest.fail("No character commit"))
    def leave(*a):  # end the interview the way Ctrl+D does; "cancel" is an answer now
        raise EOFError

    monkeypatch.setattr("builtins.input", leave)

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            payload = json.loads(messages[-1]["content"])  # the review payload is the last item (D-CREATE-COST-1)
            assert payload["authored_proposal"] == payload["proposal"]
            assert payload["normalization_provenance"] == {}
            return json.dumps({"version": 1, "accepted": True, "feedback": "Valid question.",
                               "needs_player_clarification": False})
        return json.dumps({"version": 1, "decision": "continue_interview", "narration": "What is your name?",
                           "confirmation": {"whole_build_approved": False, "player_message_index": None},
                           "character": None, "origin": None, "starting_equipment": None})

    monkeypatch.setattr(wizard, "get_ai_response", model)
    with pytest.raises(wizard.StartupCancelled):
        wizard.ai_character_interview([], {"name": "The_Thornwood_Watch"})


def test_invalid_review_verdict_is_repaired_without_changing_sources(wizard, authored, monkeypatch):
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    calls = []

    def model(messages, *args, **kwargs):
        calls.append(copy.deepcopy(messages))
        return json.dumps({"version": 1, "accepted": True, "feedback": "Reviewed.",
                           "needs_player_clarification": len(calls) == 1})

    monkeypatch.setattr(wizard, "get_ai_response", model)
    review = wizard._review_startup_response(
        [], candidate, {"character_saved": False}, authored_proposal=authored,
        normalization_provenance=provenance, live_scope=None)
    assert review["accepted"] is True and len(calls) == 2
    assert calls[0][1] == calls[1][1]
    assert "invalid structure" in calls[1][-1]["content"]

def test_declared_module_entry_bypasses_provider_after_main_integration(wizard, monkeypatch):
    entry = {'areaId': 'AREA01', 'locationId': 'ROOM01', 'areaName': 'Fixture',
             'locationName': 'Entry', 'weather': '', 'politicalClimate': ''}
    monkeypatch.setattr(wizard, '_declared_starting_location', lambda name: entry)
    # The fixture forbids network/provider calls; declared entries must retain
    # public main's deterministic bypass even with provenance/recovery changes.
    assert wizard.get_ai_starting_location({'moduleName': 'Fixture'}) == entry


# The engine-scoped path (D-CREATE-COST-4): the default sectioned mode, scripted T092 and section verdicts.
SCOPED_BLANK = {"class_key": None, "species_key": None, "background_key": None, "choices": {},
                "considering": {"class_keys": [], "species_keys": [], "background_keys": []}}
SCOPED_CLERIC = dict(SCOPED_BLANK, class_key="cleric", species_key="dwarf", background_key="acolyte",
                     choices={"cleric.divine-order.divine-order": ["Thaumaturge"]})


@pytest.fixture
def scoped(wizard, monkeypatch):
    import model_config
    monkeypatch.setattr(model_config, "STARTUP_REVIEW_MODE", "engine")
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_review_startup_response",
                        lambda *a, **k: pytest.fail("No whole review in the engine mode"))
    return wizard


def _scoped_turn(intent, narration="Which divine order calls to her?", claims=None):
    intent = dict({"ability_scores": None}, **intent) if isinstance(intent, dict) else intent
    return json.dumps({"version": 1, "decision": "continue_interview", "narration": narration,
                       "confirmation": {"player_message_index": None, "whole_build_approved": False},
                       "starting_equipment": None, "intent": intent, "creative": None,
                       "choice_turn": claims or _NO_CLAIMS})


def _run_scoped(wizard, monkeypatch, answers, lines, conversation=None):
    """Drive ai_character_interview with scripted T092 answers and player lines; returns the history and calls."""
    calls = []

    def model(messages, *args, **kwargs):
        task = kwargs.get("task_id", "T092")
        calls.append((task, copy.deepcopy(messages)))
        return answers.pop(0)

    lines = iter(lines)

    def player(prompt=""):
        try:
            return next(lines)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr(wizard, "get_ai_response", model)
    monkeypatch.setattr("builtins.input", player)
    conversation = [] if conversation is None else conversation
    with pytest.raises(wizard.StartupCancelled):
        wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    return conversation, calls


def _purposes(conversation):
    out = []
    for message in conversation:
        try:
            record = json.loads(message.get("content", ""))
        except (TypeError, ValueError):
            record = None
        out.append(record.get("task_purpose") if isinstance(record, dict) else None)
    return out


def test_the_roll_is_saved_when_made_and_a_handback_never_rolls_again(scoped, monkeypatch):
    # Amendment 1f, N7: one roll per interview. The roll item is saved the moment it is made, outside the
    # turn's discardable items, so four rejections and a handback keep it and the next turn reuses it.
    saved = []
    monkeypatch.setattr(scoped, "save_startup_conversation", lambda c, **k: saved.append(copy.deepcopy(c)))
    random_intent = {"class_key": None, "species_key": None, "background_key": None, "choices": {},
                     "considering": {"class_keys": [], "species_keys": [], "background_keys": []},
                     "ability_scores": {"method": "random", "assignment": None}}
    answers = ([_scoped_turn(random_intent)] + ["not a startup response"] * scoped.STARTUP_TURN_REJECTION_LIMIT
               + [_scoped_turn(random_intent, "Here are your six rolled scores.")])
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["Roll for me."])
    rolls = [json.loads(m["content"]) for m in conversation if '"startup_ability_roll"' in m.get("content", "")]
    assert len(rolls) == 1 and len(rolls[0]["rolled"]) == 6
    handback = _purposes(conversation).index("startup_turn_handback")
    assert _purposes(conversation).index("startup_ability_roll") < handback
    assert scoped._ability_roll(saved[-1]) == rolls[0]
    assert [m["role"] for m in conversation].count("assistant") == 1   # only the second turn published


def test_a_complete_intent_shows_the_engine_built_summary_once(scoped, monkeypatch, authored, capsys):
    # D2 (#1275): once no id is open, the player sees the summary the game renders from the engine-built sheet,
    # and the author gets it as a typed startup_sheet_preview item; an unchanged build is not shown again.
    intent = _engine_finalize(authored)["intent"]
    # The first answer re-scopes once (menu to build scope); the second turn's build is unchanged.
    answers = [_scoped_turn(intent, "Here is Alden.")] * 2 + [_scoped_turn(intent, "Anything to change?")]
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["Show me."])
    previews = [json.loads(m["content"]) for m in conversation if '"startup_sheet_preview"' in m.get("content", "")]
    assert len(previews) == 1 and previews[0]["untyped"] == []
    summary = previews[0]["summary"]
    assert summary.startswith("Human Fighter, Soldier background") and "- Strength 16 (+3)" in summary
    assert "itemdef:" not in summary and "fighter." not in summary
    assert capsys.readouterr().out.count(summary) == 1


def test_engine_prompt_rewrite_anchors_hold():
    # A T092 prompt edit must fail here, not at a player's first interview (Sentinel N8).
    from utils import startup_prompt_builder as builder
    import utils.encoding_utils as encoding
    schema = encoding.safe_json_load(str(ROOT / "schemas" / "char_schema.json"))
    whole = builder.build_character_creation_system_prompt()
    assert builder.engine_prompt_drift(whole.replace(builder._WHOLE_FACTS, builder._SCOPED_FACTS)
                                       .replace(builder._WHOLE_COMPLETE, builder._SCOPED_COMPLETE), schema) == []
    engine = builder.build_character_creation_system_prompt(scoped=True)
    assert "CHARACTER SCHEMA:" not in engine and "THE ENGINE BUILDS THE SHEET" in engine
    for _old, new in builder._ENGINE_EDITS:
        assert new in engine


def test_engine_prompt_drift_fails_forward_and_a_finalize_still_builds(wizard, authored, monkeypatch):
    from utils import startup_prompt_builder as builder
    monkeypatch.setattr(builder, "_ENGINE_EDITS", (("not in the T092 text", "x"),))
    engine = builder.build_character_creation_system_prompt(scoped=True)
    # The interview goes on (N8): the rewrites are skipped, the engine lines are in the facts block, and
    # (N9) the sheet schema is gone and the contract line stands before the response schema.
    assert "THE ENGINE BUILDS THE SHEET" in engine and "CHARACTER SCHEMA:" not in engine
    assert engine.index(builder.ENGINE_CONTRACT_OVERRIDE) < engine.index("STARTUP RESPONSE SCHEMA:")
    # A finalize under the fallback prompt is the engine shape, and the game builds and commits it.
    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=lambda p: {"version": 1, "accepted": True, "feedback": "",
                                                         "needs_player_clarification": False})
    assert any(builder.ENGINE_CONTRACT_OVERRIDE in m["content"] for m in authors[0] if m["role"] == "system")
    assert len(commits) == 1 and commits[0]["maxHitPoints"] == 12


def test_new_interview_gets_the_scoped_prompt_and_menu_not_the_reference(scoped, monkeypatch):
    conversation, calls = _run_scoped(scoped, monkeypatch, [_scoped_turn(SCOPED_BLANK)], [])
    purposes = _purposes(conversation)
    assert "startup_rules_reference" not in purposes
    assert purposes.count("startup_creation_scope") == 1 and purposes.count("startup_scope_state") >= 1
    assert [task for task, _ in calls] == ["T092"]  # D-ALLCLASS-4: one model call per interview turn, no review


def test_intent_rescopes_once_and_no_review_call_follows(scoped, monkeypatch):
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC), _scoped_turn(SCOPED_CLERIC)]
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte, please."])
    assert [task for task, _ in calls] == ["T092"] * 3  # the menu answer, then the re-ask after the re-scope
    assert "startup_engine_review" not in _purposes(conversation)
    scopes = scoped._system_records(conversation, "startup_creation_scope")
    assert len({s["scope_id"] for s in scopes}) == 2
    assert scoped._scope_states(conversation)[-1]["intent"]["class_key"] == "cleric"


def test_unanswered_required_lists_what_no_choice_id_stands_for():
    from core.nql import creation_scope
    scope = creation_scope.creation_scope({"class_key": "paladin", "species_key": "orc",
                                           "background_key": "soldier", "choices": {}})
    slots = [{"id": "starting_equipment.slot:paladin.A.holy_symbol",
              "package_choice_id": "paladin.core-paladin-traits.starting-equipment"},
             {"id": "starting_equipment.slot:soldier.A.gaming_set", "package_choice_id": None}]
    assert creation_scope.unanswered_required(scope, {}) == [
        {"id": "ability_scores.method"}, {"id": "ability_scores.assignment"},
        {"id": "starting_equipment.background_package"}] + slots
    scores = {"ability_scores": {"method": "standard_array", "assignment": {"strength": 15}}}
    assert creation_scope.unanswered_required(scope, scores) == [
        {"id": "starting_equipment.background_package"}] + slots
    equipment = {"background_package": "A", "class_package": "A", "equipped": [],
                 "slot_picks": [{"slot": "paladin.A.holy_symbol", "display_name": "Amulet"},
                                {"slot": "soldier.A.gaming_set", "display_name": "Playing Cards"}]}
    assert creation_scope.unanswered_required(scope, scores, equipment) == []


@pytest.mark.parametrize("field", ["flaws", "ideals", "name"])
@pytest.mark.parametrize("value", ["", "   "])
def test_an_empty_creative_field_is_a_schema_retry_not_a_build_refusal(wizard, authored, field, value):
    # Leg 1: every captured finalize left flaws empty. The author fills it (proposing one for approval).
    from utils.startup_contract import parse_startup_response
    proposal = _engine_finalize(authored)
    proposal["creative"][field] = value
    with pytest.raises(ValueError):
        parse_startup_response(json.dumps(proposal), latest_user_index=0, scoped=True)
    proposal["creative"][field] = "Too proud to retreat"
    assert parse_startup_response(json.dumps(proposal), latest_user_index=0, scoped=True)


@pytest.mark.parametrize("value, mode", [("engine", "engine"), ("whole", "whole"), ("sectioned", "engine"),
                                         ("bogus", "engine")])
def test_review_mode_values_and_the_stale_fallback(wizard, monkeypatch, value, mode):
    import model_config
    monkeypatch.setattr(model_config, "STARTUP_REVIEW_MODE", value)
    assert wizard._startup_review_mode() == mode


def test_the_whole_mode_reviews_the_engine_built_turn_with_t124(scoped, monkeypatch):
    import model_config
    monkeypatch.setattr(model_config, "STARTUP_REVIEW_MODE", "whole")
    reviewed = []

    def whole(request, *args, **kwargs):
        reviewed.append(scoped._startup_rules_reference_present(request))
        return {"version": 1, "accepted": True, "feedback": "", "needs_player_clarification": False}

    monkeypatch.setattr(scoped, "_review_startup_response", whole)
    monkeypatch.setattr(scoped, "build_startup_rules_reference",  # the data files are outside the test's cwd
                        lambda: {"task_purpose": scoped.STARTUP_RULES_REFERENCE_PURPOSE})
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC), _scoped_turn(SCOPED_CLERIC)]
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte."])
    assert reviewed and all(reviewed)
    assert not scoped._startup_rules_reference_present(conversation)  # the history stays on the engine path
    assert all(task == "T092" for task, _ in calls)



def test_a_class_switch_drops_the_old_picks_in_one_typed_item(scoped, monkeypatch):
    paladin = dict(SCOPED_CLERIC, class_key="paladin")
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC), _scoped_turn(SCOPED_CLERIC),
               _scoped_turn(paladin), _scoped_turn(dict(paladin, choices={}))]
    conversation, _ = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte.", "A paladin instead."])
    dropped = scoped._system_records(conversation, "startup_choices_dropped")
    assert [d["dropped"] for d in dropped] == [{"cleric.divine-order.divine-order": ["Thaumaturge"]}]
    assert (scoped._scope_states(conversation) or [None])[-1]["intent"]["class_key"] == "paladin"


def test_a_pick_outside_the_scope_is_refused_typed_and_never_reviewed(scoped, monkeypatch):
    bad = dict(SCOPED_CLERIC, choices={"cleric.divine-order.divine-order": ["Nope"]})
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC), _scoped_turn(bad)] + [_scoped_turn(SCOPED_CLERIC)] * 3
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte."])
    refused_at, request = next((i, m) for i, (t, m) in enumerate(calls)
                               if t == "T092" and "startup_choice_refusal" in _purposes(m))
    at = _purposes(request).index("startup_choice_refusal")
    refusal = json.loads(request[at]["content"])
    assert refusal["problems"] and refusal["open_choice_ids"] == []
    assert calls[refused_at - 1][0] == "T092"  # the refused answer had no review call
    # The refused intent never became the scope: no state in any later request carries its pick.
    for task, messages in calls[refused_at:]:
        for state in scoped._system_records(messages, "startup_scope_state"):
            assert "Nope" not in json.dumps(state["intent"])
    assert "startup_choice_refusal" not in _purposes(conversation)  # the saved history keeps only the published turn


def test_scope_items_are_saved_only_when_the_turn_publishes(scoped, monkeypatch):
    # A turn whose response never publishes leaves the saved history's scope state as it was (r3.1 T4). The
    # cleric turn re-scopes, then every answer is refused by the contract until the handback.
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC)] + ["{}"] * 12
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte."])
    assert len(calls) >= 3 and {task for task, _ in calls} == {"T092"}
    states = scoped._system_records(conversation, "startup_scope_state")
    assert states and all((s.get("intent") or {}).get("class_key") != "cleric" for s in states)
    assert len(scoped._system_records(conversation, "startup_creation_scope")) == 1  # only the menu's


def test_scope_state_is_not_a_checkpoint_and_belongs_to_its_startup(scoped, monkeypatch):
    from utils.startup_contract import parse_startup_checkpoint
    conversation, _ = _run_scoped(scoped, monkeypatch, [_scoped_turn(SCOPED_BLANK)], [])
    without = [m for m, p in zip(conversation, _purposes(conversation)) if p != "startup_scope_state"]
    assert len(without) < len(conversation)
    assert parse_startup_checkpoint(conversation) == parse_startup_checkpoint(without)
    state = (scoped._scope_states(conversation) or [None])[-1]
    assert state is not None and state["startup_id"] is None  # written before the first checkpoint
    assert (scoped._scope_states(conversation) or [None])[-1] == state
    # A later startup in the same history never reads this one's state.
    later = dict(scoped._startup_progress(conversation), startup_id="another-startup")
    conversation.append({"role": "system", "content": json.dumps(later)})
    assert (scoped._scope_states(conversation) or [None])[-1] is None


def _bard_interview_turn(equipment):
    package = "bard.core-bard-traits.starting-equipment"
    return {"version": 1, "decision": "continue_interview", "narration": "Which two cantrips would Pip like?",
            "confirmation": {"player_message_index": 0, "whole_build_approved": False}, "creative": None,
            "starting_equipment": equipment, "choice_turn": _NO_CLAIMS,
            "intent": {"class_key": "bard", "species_key": "halfling", "background_key": "acolyte",
                       "choices": {package: ["A"]},
                       "considering": {"class_keys": [], "species_keys": [], "background_keys": []},
                       "ability_scores": None}}


def test_package_and_slot_picks_have_a_typed_place_on_interview_turns():
    # D-CREATE-COST-5 amendment 2 (dplay-AC-bard-r2): the author had nowhere typed for the lute, the holy
    # symbol's form or the Acolyte package before finalize, and tried four refused shapes: slot ids in
    # intent (not_issued), a reply without its required fields, the class package dropped from intent, and
    # an invented background package choice id. Each pick now has its place in a partial starting_equipment.
    from core.nql import creation_scope
    from utils.startup_contract import parse_startup_response
    equipment = {"background_package": "A", "class_package": None, "equipped": [],
                 "slot_picks": [{"slot": "bard.A.instrument", "display_name": "Lute"},
                                {"slot": "acolyte.A.holy_symbol", "display_name": "Amulet"}]}
    turn = _bard_interview_turn(equipment)
    parsed = parse_startup_response(json.dumps(turn), latest_user_index=0, scoped=True)
    assert parsed["starting_equipment"] == equipment
    scope = creation_scope.creation_scope(turn["intent"])
    left = [entry["id"] for entry in creation_scope.unanswered_required(scope, turn["intent"], equipment)]
    assert not [entry for entry in left if entry.startswith("starting_equipment.")]
    # The four shapes stay what they were: none is needed now.
    assert parse_startup_response(json.dumps(_bard_interview_turn(None)), latest_user_index=0, scoped=True)
    missing_fields = {k: v for k, v in turn.items() if k not in ("intent", "confirmation")}
    with pytest.raises(ValueError):
        parse_startup_response(json.dumps(missing_fields), latest_user_index=0, scoped=True)
    assert set(creation_scope.issued_points(turn["intent"])).isdisjoint(
        {"bard.A.instrument", "acolyte.A.holy_symbol", "background.acolyte.equipment",
         "background.acolyte.starting-equipment"})
    from utils.startup_prompt_builder import build_character_creation_system_prompt
    text = " ".join(build_character_creation_system_prompt(scoped=True).split())
    assert "Record package and slot picks in starting_equipment as soon as the player gives them" in text


def test_finalize_needs_every_package_and_slot_pick(wizard, authored):
    # Amendment 2: the engine never fills a pick; a finalize without a needed slot is a typed rejection.
    from core.nql import creation_scope
    proposal = _engine_finalize(authored)
    proposal["starting_equipment"].update(background_package="A", slot_picks=[])
    scope = creation_scope.creation_scope(proposal["intent"])
    assert [e for e in creation_scope.unanswered_required(scope, proposal["intent"], proposal["starting_equipment"])
            if e["id"].startswith("starting_equipment.slot:")]
    with pytest.raises(ValueError, match="every package and slot pick"):
        wizard._prepare_startup_proposal(proposal)


def test_an_approval_after_the_sheet_preview_must_finalize():
    # All-class A1 (dplay-AC-ranger): after "Yes, that's her. Let's start." the author kept asking approval
    # for ideal, bond and flaw text it had just written; T128 demanded finalize 8 times before a handback.
    from utils.startup_prompt_builder import build_character_creation_system_prompt
    engine = " ".join(build_character_creation_system_prompt(scoped=True).split())
    assert ("When the player approves the whole build, finalize with your proposed creative fields; do not ask "
            "approval for details you add at finalize.") in engine
    assert "do not ask approval for details you add at finalize" not in build_character_creation_system_prompt()



def test_the_engine_author_offers_only_the_scope_options():
    # D-ALLCLASS-6 P1 (dplay-AC-difficult turn 13): Athletics was offered to a Soldier fighter.
    import hashlib
    from utils.startup_prompt_builder import build_character_creation_system_prompt
    prompt = build_character_creation_system_prompt(scoped=True)
    assert ("Offer only a choice's option_keys from the scope; a skill the background grants is never "
            "offered.") in " ".join(prompt.split())
    assert "a skill the background grants" not in build_character_creation_system_prompt()
    assert hashlib.sha256(prompt.encode()).hexdigest()[:12] == "834b56434e59"


def test_the_engine_author_asks_one_choice_per_turn_for_a_new_player():
    # D-ALLCLASS-6 P2 (dplay-AC-difficult turn 9): four long lists in one turn; the new player gave up the character.
    from utils.startup_prompt_builder import build_character_creation_system_prompt
    assert ("When the player says they are new or overwhelmed, ask one choice per turn and say how many "
            "remain.") in " ".join(build_character_creation_system_prompt(scoped=True).split())
    assert "new or overwhelmed" not in build_character_creation_system_prompt()

def test_package_items_say_whether_equipped_can_name_them_and_their_aliases():
    # D-ALLCLASS-1 facts (dplay-AC-wizard): the author put "Spellbook at hand" in narration but equipped takes
    # catalog ids, and it listed the staff twice (as the focus and as a Quarterstaff); T128 rejected three times.
    # Each package item now says, from the data, whether equipped can name it, and its other names.
    from core.nql import creation_scope
    intent = {"class_key": "wizard", "species_key": "elf", "background_key": "sage",
              "choices": {"wizard.core-wizard-traits.starting-equipment": ["A"]}}
    scope = creation_scope.creation_scope(intent)
    package = next(c for c in scope["choices"] if c["id"] == "wizard.core-wizard-traits.starting-equipment")
    items = {i.get("catalog_id") or i.get("key"): i for i in package["options"]["A"]["items"]}
    assert items["spellbook"]["equippable"] is False and "aliases" not in items["spellbook"]
    staff = items["itemdef:srd/arcane-focus-staff"]
    assert staff["equippable"] is True and staff["aliases"] == ["Arcane Focus (Quarterstaff)", "Quarterstaff"]
    assert items["itemdef:srd/robe"]["equippable"] is True
    # The aliases are authored in the data (choices.json), never read from evidence text (D-KW).
    import json as _json
    data = _json.dumps(_json.load(open(ROOT / "data" / "srd" / "choices.json", encoding="utf-8")))
    assert data.count('"aliases": ["Arcane Focus (Quarterstaff)", "Quarterstaff"]') == 1
    assert data.count('"aliases": ["Druidic Focus (Quarterstaff)", "Quarterstaff"]') == 1


def test_whole_mode_rules_reference_carries_no_engine_flags():
    # nql-ee on #1297: the whole-mode rules reference is main's bytes; equippable and aliases are engine scope only.
    import hashlib
    from utils.startup_prompt_builder import build_startup_rules_reference
    reference = json.dumps(build_startup_rules_reference(), sort_keys=True)
    assert "equippable" not in reference and '"aliases"' not in reference
    assert hashlib.sha256(reference.encode()).hexdigest()[:12] == "95e91f196259"


def test_background_ability_keys_are_authored_and_the_option_keys_unchanged():
    # D-KW-18: a background's three abilities are an authored list in the data, never split from the
    # "ability_scores" string at run time; the "+2 X, +1 Y" option keys stay the engine's enum.
    import json as _json
    from core.nql import creation_scope
    origins = _json.load(open(ROOT / "data" / "srd_character_origins.json", encoding="utf-8"))
    for background in origins["backgrounds"]:
        assert background["ability_keys"] == [a.strip() for a in background["ability_scores"].split(",")]
    sage = next(b for b in origins["backgrounds"] if b["key"] == "sage")
    assert creation_scope._ability_options(sage) == [
        "+2 Constitution, +1 Intelligence", "+2 Constitution, +1 Wisdom", "+2 Intelligence, +1 Constitution",
        "+2 Intelligence, +1 Wisdom", "+2 Wisdom, +1 Constitution", "+2 Wisdom, +1 Intelligence", "+1 each"]
    assert creation_scope._ability_options(dict(sage, ability_scores="Strength, Dexterity, Charisma")) == \
        creation_scope._ability_options(sage)


def test_a_refused_finalize_reprompts_the_author_with_typed_problems_and_no_review(scoped, monkeypatch):
    # D-ALLCLASS-4: the engine is the only gate. A finalize the contract refuses goes back to the author with the
    # typed problem in the same turn; no review call is made and no review record is written.
    finalize = json.loads(_scoped_turn(SCOPED_CLERIC))
    finalize.update(decision="finalize_character", starting_equipment=None,
                    confirmation={"player_message_index": 1, "whole_build_approved": True})
    answers = [_scoped_turn(SCOPED_BLANK), _scoped_turn(SCOPED_CLERIC), json.dumps(finalize),
               _scoped_turn(SCOPED_CLERIC)]
    conversation, calls = _run_scoped(scoped, monkeypatch, answers, ["A dwarf cleric acolyte. Finish her."])
    assert {task for task, _ in calls} == {"T092"} and len(calls) == 4
    retry = calls[3][1]
    refusal = [m["content"] for m in retry if m.get("role") == "system"
               and str(m.get("content", "")).startswith("Rejected startup proposal (not approved):")]
    assert refusal and "finalize" in refusal[-1].lower()
    assert "startup_engine_review" not in _purposes(conversation)


def _complete_order_intent(cls, order, option):
    from core.nql import creation_scope
    intent = {"class_key": cls, "species_key": "human", "background_key": "sage", "choices": {order: [option]},
              "considering": {"class_keys": [], "species_keys": [], "background_keys": []},
              "ability_scores": {"method": "standard_array", "assignment": {
                  "strength": 15, "dexterity": 14, "constitution": 13, "intelligence": 12, "wisdom": 10,
                  "charisma": 8}}}
    for _ in range(12):
        open_ids = creation_scope.open_choice_ids(intent)
        if not open_ids:
            break
        points = creation_scope.issued_points(intent)
        for cid in open_ids:
            intent["choices"][cid] = list((points[cid].get("option_keys") or [])[:points[cid].get("count") or 1])
    assert not creation_scope.open_choice_ids(intent)
    return intent


@pytest.mark.parametrize("cls, order, option, armor, weapon", [
    ("druid", "druid.primal-order.primal-order", "Warden", "Medium", "Martial"),
    ("cleric", "cleric.divine-order.divine-order", "Protector", "Heavy", "Martial"),
])
def test_the_engine_build_carries_the_order_grants_so_preview_equals_saved(cls, order, option, armor, weapon):
    # All-class D1 (dplay-AC-druid turn 9): the preview showed Light armor and Simple weapons for a Warden; the
    # order's grants were written only by the save repair. The build now runs the same pass: the preview has
    # them, and the repair adds nothing to a finalized sheet.
    import copy
    from core.nql import creation_build
    from core.leveling import choices
    intent = _complete_order_intent(cls, order, option)
    preview, _ = creation_build.build_level_one_sheet(intent, None, preview=True)
    assert armor in preview["proficiencies"]["armor"] and weapon in preview["proficiencies"]["weapons"]
    creative = {field: "x" for field in creation_build.CREATIVE_FIELDS}
    creative.update(name="Order Test", alignment="neutral")
    final, built = creation_build.build_level_one_sheet(intent, creative)
    repaired = copy.deepcopy(final)
    assert all(entry["added"] == [] for entry in choices.apply_order_grants(repaired)) and repaired == final
    assert any(t["source"].startswith("choices.order_grants.") for t in built["engine_build"])


def test_the_background_menu_carries_typed_tools_and_equipment():
    # dplay-AC-difficult turn 6: the guide said the backgrounds' tool and equipment "haven't been provided yet".
    from core.nql import creation_scope
    menu = {b["background_key"]: b for b in creation_scope.creation_scope({})["menu"]["backgrounds"]}
    assert menu["criminal"]["tools"] == {"granted": ["Thieves' Tools"]}
    assert menu["soldier"]["tools"]["choose"]["option_source"] == "tools:category=Gaming Set"
    criminal_a = menu["criminal"]["equipment"]["A"]
    assert {"name": "Thieves' Tools", "quantity": 1} in criminal_a["items"] and criminal_a["gp"] == 16
    assert menu["soldier"]["equipment"]["B"] == {"items": [], "gp": 50}


def test_a_class_skill_pick_types_the_background_granted_skills_it_excludes():
    # dplay-AC-difficult turn 13: Athletics was offered to a Soldier fighter; the engine refused the pick.
    from core.nql import creation_scope
    scope = creation_scope.creation_scope({"class_key": "fighter", "species_key": "goliath",
                                           "background_key": "soldier", "choices": {}})
    skill = next(c for c in scope["choices"] if c.get("kind") == "skill")
    assert skill["excluded_granted"] == ["Athletics", "Intimidation"]
    assert not set(skill["excluded_granted"]) & set(skill["option_keys"])


def test_the_summary_lists_a_species_trait_with_a_picked_option_once():
    # dplay-AC-difficult turn 18: "Giant Ancestry" showed twice. The sheet keeps both entries.
    from core.nql import creation_build
    intent = _complete_order_intent("cleric", "cleric.divine-order.divine-order", "Protector")
    intent["species_key"] = "goliath"
    intent["choices"] = {k: v for k, v in intent["choices"].items() if not k.startswith("species.human.")}
    intent["choices"]["species.goliath.giant-ancestry"] = ["Stone's Endurance"]
    sheet, built = creation_build.build_level_one_sheet(intent, None, preview=True)
    assert built["folded_traits"] == ["Giant Ancestry"]
    summary = creation_build.render_sheet_summary(sheet, built)
    assert "- Giant Ancestry: Stone's Endurance" in summary and "- Giant Ancestry\n" not in summary
    assert {"Giant Ancestry", "Giant Ancestry: Stone's Endurance"} <= {t["name"] for t in sheet["racialTraits"]}


def test_the_fold_keys_on_the_species_choice_authored_trait_field():
    # nql-ee on #1304: the fold reads the choice's authored "trait" field, not the choice name.
    import json
    with open("data/srd_character_origins.json") as f:
        species = {s["key"]: s for s in json.load(f)["species"]}
    choice = next(c for c in species["goliath"]["grants"]["choices"] if not c.get("kind"))
    assert choice["trait"] == "Giant Ancestry"


def test_the_preview_summary_shows_hit_points_and_the_saved_line_shows_armor_class(wizard):
    # dplay-AC-difficult turn 18: the player asked for the armor class; the preview had neither number.
    from core.nql import creation_build
    startup_wizard = wizard
    intent = _complete_order_intent("cleric", "cleric.divine-order.divine-order", "Protector")
    sheet, built = creation_build.build_level_one_sheet(intent, None, preview=True)
    built["hit_points"] = startup_wizard.expected_starting_hit_points(sheet, intent)[0]
    con = sheet["abilities"]["constitution"]
    assert built["hit_points"] == 8 + (con - 10) // 2   # cleric d8 maximum + Constitution modifier
    assert "Hit points %d" % built["hit_points"] in creation_build.render_sheet_summary(sheet, built)
    assert "armor class" not in creation_build.render_sheet_summary(sheet, built)
    assert startup_wizard._saved_defense_line({"armorClass": 17, "maxHitPoints": 12}) == \
        " Armor class 17, hit points 12."
    assert startup_wizard._saved_defense_line({"armorClass": 17}) == ""


@pytest.mark.parametrize("intent, cid, key, expected", [
    # desktop L5 turn 5: "choose how Sage improves her abilities:" with no options in the reply.
    ({"class_key": "fighter", "species_key": "dwarf", "background_key": "sage", "choices": {}},
     "background.sage.ability-scores", "options", "+2 Constitution, +1 Intelligence"),
    # desktop L5 turn 9: "choose Pip's Rogue starting equipment:" with no packages in the reply.
    ({"class_key": "rogue", "species_key": "halfling", "background_key": "criminal", "choices": {}},
     "rogue.core-rogue-traits.starting-equipment", "packages", "A"),
])
def test_the_open_choices_record_carries_each_open_choice_with_its_options(wizard, intent, cid, key, expected):
    conversation = [{"role": "system", "content": json.dumps(creation_scope_item(intent))}]
    proposal = {"decision": "continue_interview", "intent": intent, "choice_turn": _NO_CLAIMS}
    assert wizard._scoped_intent([conversation], proposal, rescoped=True) is False
    record = json.loads(conversation[-1]["content"])
    assert record["task_purpose"] == "startup_open_choices"
    entry = next(e for e in record["open_choices"] if e["id"] == cid)
    assert expected in entry[key] and entry["name"] and entry["count"] >= 1
    assert [e["id"] for e in record["open_choices"]] == record["open_choice_ids"]


def test_the_menu_turn_carries_background_tools_and_gear():
    # desktop L5 turn 1: the guide named the four backgrounds without their tools and gear.
    from core.nql import creation_scope
    for row in creation_scope.creation_scope({})["menu"]["backgrounds"]:
        assert row["tools"] and row["equipment"]


def creation_scope_item(intent):
    from core.nql import creation_scope
    return creation_scope.creation_scope(intent)


def test_a_wizard_open_choices_record_names_spells_and_points_prepared_at_the_spellbook(wizard):
    # nql-ee on #1310: the wizard's prepared spells came with no options; they are the spellbook picks.
    intent = {"class_key": "wizard", "species_key": "elf", "background_key": "sage",
              "choices": {"wizard.spellcasting.spellbook": ["alarm", "shield"]}}
    conversation = [{"role": "system", "content": json.dumps(creation_scope_item(intent))}]
    assert wizard._scoped_intent([conversation], {"decision": "continue_interview", "intent": intent,
                                                  "choice_turn": _NO_CLAIMS}, rescoped=True) is False
    record = {e["id"]: e for e in json.loads(conversation[-1]["content"])["open_choices"]}
    prepared = record["wizard.spellcasting.prepared-spells"]
    assert prepared["from_choice"] == "wizard.spellcasting.spellbook" and prepared["options"] == ["Alarm", "Shield"]
    assert "Fire Bolt" in record["wizard.spellcasting.cantrips"]["options"]
    assert all(e.get("options") or e.get("packages") or e.get("free_pick") for e in record.values())


def _t079_run(wizard, authored, monkeypatch, tmp_path, answers, changes):
    """One updateCharacterInfo through the real T079 loop with canned answers; returns the task ids called
    and the classifier calls."""
    import types as _types
    import updates.update_character_info as character_info
    from core.managers import effects_runtime
    sheet = copy.deepcopy(authored["character"])
    path = tmp_path / "hero.json"
    path.write_text(json.dumps(sheet), encoding="utf-8")
    calls, classified = [], []

    def provider(task_id, *args, **kwargs):
        calls.append(task_id)
        content = json.dumps(answers[min(len(calls), len(answers)) - 1])
        return _types.SimpleNamespace(choices=[_types.SimpleNamespace(message=_types.SimpleNamespace(content=content))])

    def classify(*args, **kwargs):
        classified.append(args[0])
        return {"operation": "none"}
    monkeypatch.setattr(character_info, "capture_and_fanout", provider)
    monkeypatch.setattr(character_info, "get_character_path", lambda name, role=None: str(path))
    monkeypatch.setattr(character_info, "detect_character_role", lambda name: "player")
    monkeypatch.setattr(effects_runtime, "classify_effect", classify)
    lazy = effects_runtime._lazy_classifier(sheet["name"], changes, sheet, 0)
    character_info._update_character_info_unlocked(sheet["name"], changes, "player", managed_effect_operation=lazy,
                                                   prepare_only=True)
    return calls, classified


def test_a_no_change_update_is_one_t079_call_and_no_classifier(wizard, authored, monkeypatch, tmp_path):
    # D-COST-6 (#193): the first {} is accepted; no confirmation re-ask and no lazy T078.
    calls, classified = _t079_run(wizard, authored, monkeypatch, tmp_path, [{}], "She admires the sunset.")
    assert calls == ["T079"] and classified == []


def test_a_flagged_effect_change_still_classifies(wizard, authored, monkeypatch, tmp_path):
    # D-COST-6: an answer that flags an effect change still runs the classifier once. D-COST-8: this is the
    # "separate" rollback mode; merged mode reads the effect object from T079 itself.
    import model_config
    monkeypatch.setattr(model_config, "EFFECTS_CLASSIFIER_MODE", "separate")
    calls, classified = _t079_run(wizard, authored, monkeypatch, tmp_path, [{"effectChange": True}],
                                  "She is blessed for one minute.")
    assert calls[0] == "T079" and len(classified) == 1


def test_an_accepted_miscellaneous_row_is_not_retyped(wizard):
    # D-COST-7 (#193): a new row typed miscellaneous (a valid schema value) no longer reaches T052.
    from core.validation.character_validator import AICharacterValidator
    validator = AICharacterValidator.__new__(AICharacterValidator)
    before = {"equipment": []}
    after = {"equipment": [{"item_name": "Lucky Pebble", "item_type": "miscellaneous", "quantity": 1},
                           {"item_name": "Odd Gadget", "item_type": "gizmo", "quantity": 1}]}
    validator._focus_names = {"Lucky Pebble", "Odd Gadget"}
    rows = [r["item_name"] for r in validator.extract_inventory_data(after)["equipment"]]
    assert rows == ["Odd Gadget"]


def test_a_level_up_calls_only_t121_and_the_retired_ids_are_gone(wizard, authored, monkeypatch, tmp_path):
    # D-COST-2 (#193): the retired level-up interview (T047), validator (T048) and domain authors and
    # reviewers (T115-T120) are deleted; the table-driven session's T121 is the one level-up call.
    import re
    import model_registry
    from core.leveling import tables
    from core.managers import level_up_session
    from utils.capture import live_provider_call
    retired = {"T047", "T048", "T115", "T116", "T117", "T118", "T119", "T120"}
    calls = []

    def record(task_id, *args, **kwargs):
        calls.append(task_id)
        raise RuntimeError("no provider in this row")
    monkeypatch.setattr(level_up_session, "capture_and_fanout", record)
    sheet = _as_class(copy.deepcopy(authored["character"]), "Fighter", [("Second Wind", None)])
    session = level_up_session.LevelUpSession(sheet["name"], 1, 2)
    session._sheet = sheet
    session._path = str(tmp_path / "fighter.json")
    session._settled = tables.settle(sheet, 2)
    try:
        session._ask_agent([])
    except RuntimeError:
        pass
    assert calls == ["T121"]
    assert not retired & set(model_registry.REGISTERED_TASK_IDS)
    assert live_provider_call._LEVEL_UP_TASK_IDS == frozenset({"T121"})
    pattern = re.compile(r"\bT(047|048|11[5-9]|120)\b")
    hits = []
    for path in list(ROOT.glob("*.py")) + list(ROOT.glob("core/**/*.py")) + list(ROOT.glob("utils/**/*.py")) \
            + list(ROOT.glob("updates/**/*.py")) + list(ROOT.glob("prompts/**/*.txt")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line) and not (path.name == "model_registry.py" and "it replaces" in line):
                hits.append("%s:%d" % (path.relative_to(ROOT), number))
    assert hits == []


_NOW = 1492 * 365 * 86400  # any valid game-seconds scalar
_BLESS = {"operation": "add", "remove": {"effectId": "", "name": ""}, "effect": {
    "name": "Bless", "description": "Adds 1d4 to attack rolls and saving throws.", "source": "Cleric",
    "modifiers": [{"stat": "attackRolls", "die": "1d4"}, {"stat": "savingThrows", "die": "1d4"}],
    "conditions": [], "incapacitates": False, "durationKind": "minutes", "durationValue": 1,
    "restKind": "none", "concentration": True, "caster": "Cleric", "onApply": [], "onRemove": []}}


def _t079_effects(wizard, authored, monkeypatch, tmp_path, answers, changes, mode="merged", classify_as=None):
    """The real T079 loop with declarative effects on, canned T079 answers and a counted T078; returns the
    task ids, the T078 calls, the lazy classifier and the first request's messages."""
    import types as _types
    import model_config
    import updates.update_character_info as character_info
    from core.managers import effects_runtime, effects_state
    monkeypatch.setattr(model_config, "EFFECTS_CLASSIFIER_MODE", mode)
    monkeypatch.setattr(effects_state, "campaign_effects_migrated", lambda: True)
    sheet = copy.deepcopy(authored["character"])
    path = tmp_path / "hero.json"
    path.write_text(json.dumps(sheet), encoding="utf-8")
    calls, classified, requests = [], [], []

    def provider(task_id, *args, **kwargs):
        calls.append(task_id)
        requests.append(copy.deepcopy(kwargs.get("messages")))
        content = json.dumps(answers[min(len(calls), len(answers)) - 1])
        return _types.SimpleNamespace(choices=[_types.SimpleNamespace(message=_types.SimpleNamespace(content=content))])

    def classify(name, change, sheet_view, now):
        classified.append(name)
        from core.ai import effects_agent
        return effects_agent.classification_from_object(classify_as or {"operation": "none", "effect": {},
                                                                         "remove": {}}, name, change, now)
    monkeypatch.setattr(character_info, "capture_and_fanout", provider)
    monkeypatch.setattr(character_info, "get_character_path", lambda name, role=None: str(path))
    monkeypatch.setattr(character_info, "detect_character_role", lambda name: "player")
    monkeypatch.setattr(effects_runtime, "classify_effect", classify)
    from core.effects.clock import scalar_from_calendar
    (tmp_path / "party_tracker.json").write_text(json.dumps({"module": "Keep", "worldConditions": {}}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    lazy = effects_runtime._lazy_classifier(sheet["name"], changes, sheet, scalar_from_calendar({}))
    character_info._update_character_info_unlocked(sheet["name"], changes, "player", managed_effect_operation=lazy,
                                                   prepare_only=True)
    return calls, classified, lazy, requests


@pytest.mark.parametrize("obj, problem", [
    (dict(_BLESS, extra=1), "requires exactly operation, effect, and remove"),
    ({"operation": "remove", "effect": {"name": "Bless"}, "remove": {"effectId": "e1", "name": "Bless"}},
     "remove result has an invalid shape"),
    ({**_BLESS, "effect": {**_BLESS["effect"], "caster": ""}}, "concentration effect requires a caster"),
    ({**_BLESS, "effect": {**_BLESS["effect"], "durationKind": "weeks"}}, "durationKind is invalid"),
])
def test_the_effect_object_is_held_to_t078s_exact_contract(obj, problem):
    # D-COST-8 (#193): T079's effectChange object and T078's answer pass the same check, with the same message.
    from core.ai import effects_agent
    for check in (lambda: effects_agent._parse(json.dumps(obj)),
                  lambda: effects_agent.classification_from_object(obj, "Hero", "x", _NOW)):
        with pytest.raises(effects_agent.EffectsAgentContractError, match=problem):
            check()
    for good in (_BLESS, {"operation": "none", "effect": {}, "remove": {}}):
        assert effects_agent.classification_from_object(good, "Hero", "x", _NOW)["operation"] == good["operation"]


def test_a_merged_effect_is_one_t079_call_and_equals_the_separate_record(wizard, authored, monkeypatch, tmp_path):
    # D-COST-8: T079 returns the classification; 0 T078 calls; the engine record equals today's T079 + T078.
    calls, classified, lazy, _ = _t079_effects(wizard, authored, monkeypatch, tmp_path,
                                               [{"effectChange": _BLESS}], "The cleric blesses her.")
    assert calls == ["T079"] and classified == []
    merged = copy.deepcopy(lazy.operation)
    calls2, classified2, lazy2, _ = _t079_effects(wizard, authored, monkeypatch, tmp_path,
                                                  [{"effectChange": True}], "The cleric blesses her.",
                                                  mode="separate", classify_as=_BLESS)
    assert calls2 == ["T079"] and len(classified2) == 1
    def without_ids(operation):  # effectId and concentrationId are minted per record
        return [{**op, "effect": {k: v for k, v in op["effect"].items() if k not in ("effectId", "concentrationId")}}
                for op in operation]
    assert without_ids(merged) == without_ids(lazy2.operation) and merged[0]["op"] == "add" and merged[0]["effect"]["name"] == "Bless"


def test_a_delta_and_an_effect_in_one_answer_apply_together(wizard, authored, monkeypatch, tmp_path):
    calls, classified, lazy, _ = _t079_effects(wizard, authored, monkeypatch, tmp_path,
                                               [{"hpDelta": -2, "effectChange": _BLESS}], "Hurt, then blessed.")
    assert calls == ["T079"] and classified == [] and lazy.operation[0]["op"] == "add"


def test_an_effect_contract_error_is_corrected_inside_t079(wizard, authored, monkeypatch, tmp_path):
    bad = {**_BLESS, "effect": {**_BLESS["effect"], "durationKind": "weeks"}}
    calls, classified, lazy, requests = _t079_effects(
        wizard, authored, monkeypatch, tmp_path, [{"effectChange": bad}, {"effectChange": _BLESS}], "Blessed.")
    assert calls == ["T079", "T079"] and classified == [] and lazy.operation[0]["op"] == "add"
    from core.ai.effects_agent import CONTRACT_CORRECTION
    assert requests[1][-1]["content"].endswith(
        CONTRACT_CORRECTION % "T078 durationKind is invalid" + " Return the complete delta again.")


def test_a_boolean_effect_change_is_refused_in_merged_mode(wizard, authored, monkeypatch, tmp_path):
    calls, classified, lazy, requests = _t079_effects(
        wizard, authored, monkeypatch, tmp_path, [{"effectChange": True}, {"effectChange": _BLESS}], "Blessed.")
    assert calls == ["T079", "T079"] and classified == [] and "not True" in requests[1][-1]["content"]


def test_none_and_omitted_change_nothing_and_remove_needs_an_exact_id(wizard, authored, monkeypatch, tmp_path):
    for answer in ({"hpDelta": -1}, {"hpDelta": -1, "effectChange": {"operation": "none", "effect": {},
                                                                      "remove": {}}}):
        calls, classified, lazy, _ = _t079_effects(wizard, authored, monkeypatch, tmp_path, [answer], "A scratch.")
        assert calls == ["T079"] and classified == [] and not lazy.operation


def test_the_merged_t079_prompt_carries_t078s_rules_verbatim(wizard, authored, monkeypatch, tmp_path):
    import hashlib
    from core.ai import effects_agent
    rules = effects_agent.EFFECT_CONTRACT_RULES
    assert hashlib.sha256(effects_agent._system_prompt().encode()).hexdigest()[:12] == "741ca35fb348"
    *_, merged = _t079_effects(wizard, authored, monkeypatch, tmp_path, [{}], "Nothing.")
    *_, separate = _t079_effects(wizard, authored, monkeypatch, tmp_path, [{}], "Nothing.", mode="separate")
    merged_system, separate_system = merged[0][0]["content"], separate[0][0]["content"]
    assert rules in merged_system and rules not in separate_system
    assert "currentEffectiveSheet means the Current" in merged_system and "An omitted effectChange means no" in merged_system
    assert "operation none is also accepted" not in merged_system
    assert '"effectChange": true in your delta' in separate_system
    # The T079 prompt pins: separate (the rollback) is main's prompt byte for byte; merged adds the block.
    assert hashlib.sha256(separate_system.encode()).hexdigest()[:12] == "79e671ba7ed1"
    assert hashlib.sha256(merged_system.encode()).hexdigest()[:12] == "361215e067fe"


