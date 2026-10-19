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


@pytest.mark.parametrize("cls, con, traits, feats, expected", [
    ("Wizard", 8, [], [], 5),                                    # 6 - 1
    ("Cleric", 12, ["Dwarven Toughness"], [], 10),               # 8 + 1 + 1
    ("Barbarian", 10, [], [], 12),
    ("Fighter", 14, [], ["Tough"], 12),                           # SRD 5.2.1 has no Tough feat
    ("Sorcerer", 1, [], [], 1),                                   # 6 - 5
])
def test_level_one_hit_points_come_from_progression(wizard, authored, cls, con, traits, feats, expected):
    sheet = copy.deepcopy(authored["character"])
    sheet["class"] = cls
    sheet["abilities"]["constitution"] = con
    sheet["racialTraits"] = [{"name": name, "description": "typed"} for name in traits]
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


@pytest.mark.parametrize("race, traits, bonus", [
    ("Dwarf", ["Dwarven Toughness"], 1),
    ("Dwarf", ["Dwarven Toughness (Hill)"], 1),
    ("Dwarf", [], 1),
    ("Dwarf", ["Dwarven Toughness", "Dwarven Toughness"], 1),
    ("Hill Dwarf", ["Dwarven Toughness"], 1),
    # No SRD 5.2.1 species is named "Hill Dwarf" and the engine has no species
    # hit point rule, so neither side adds the bonus without the exact trait.
    ("Hill Dwarf", [], 0),
    ("Hill Dwarf", ["Dwarven Toughness (Hill)"], 0),
    ("Human", [], 0),
])
def test_dwarven_toughness_comes_from_the_species(wizard, authored, race, traits, bonus):
    # #855: keyed on race against progression.json hp_bonuses; the exact trait
    # name still counts, once.
    sheet = copy.deepcopy(authored["character"])
    sheet["class"], sheet["race"] = "Cleric", race
    sheet["abilities"]["constitution"] = 12
    sheet["racialTraits"] = [{"name": name, "description": "typed"} for name in traits]
    maximum, terms = wizard.expected_starting_hit_points(sheet)
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


def run_interview(wizard, authored, monkeypatch, *, review, stop_after_rejection=False):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = copy.deepcopy(authored)
    proposal["confirmation"]["player_message_index"] = 0
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
        if len(author_requests) > 1 and stop_after_rejection:
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


def test_actual_interview_reviews_both_sources_and_publishes_canonical(wizard, authored, monkeypatch):
    def review(payload):
        assert payload["authored_proposal"]["character"]["equipment_effects"] == []
        assert "savingThrowBonuses" not in payload["authored_proposal"]["character"]
        assert payload["proposal"]["character"]["equipment_effects"]
        assert payload["proposal"]["character"]["savingThrowBonuses"]
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        # The reviewer receives the Fighting Style move, the Second Wind pool and
        # the AC result as committed facts.
        changes = payload["committed_facts"]["startup_mechanics"]["changes"]
        assert changes[:2] == [CAPTURED_STYLE_NOTE, SECOND_WIND_NOTE]
        assert changes[2].startswith("armorClass 18 -> 17")
        return {"version": 1, "accepted": True, "feedback": "Both sources reviewed.",
                "needs_player_clarification": False}

    result, conversation, commits, authors, reviewers = run_interview(wizard, authored, monkeypatch, review=review)
    assert len(authors) == len(reviewers) == len(commits) == 1
    assert result == commits[0] == reviewers[0]["proposal"]["character"]
    assert wizard._startup_progress(conversation)["phase"] == "approved"


@pytest.mark.parametrize("defect", ["narration", "mechanics", "identity", "author_saves", "author_effects"])
@pytest.mark.parametrize("needs_clarification", [False, True])
def test_negative_review_retains_authorship_and_never_commits(wizard, authored, monkeypatch, defect, needs_clarification):
    if defect == "narration":
        authored["narration"] = "You have arrived and your character was saved."
    elif defect == "mechanics":
        authored["character"]["hitPoints"] = authored["character"]["maxHitPoints"] = 99
    elif defect == "identity":
        authored["character"]["name"] = "Unapproved replacement"
    elif defect == "author_saves":
        authored["character"]["savingThrowBonuses"] = {"strength": 99}
    else:
        authored["character"]["equipment_effects"] = [{
            "name": "Authored AC", "type": "bonus", "target": "AC", "value": 99,
            "description": "Invented", "source": "author"}]

    def review(payload):
        assert payload["normalization_provenance"]["engine_projection"]["applied"]
        if defect == "mechanics":
            # Hit points are code output (#570): the candidate carries the exact
            # maximum; the authored 99 stays visible as authorship.
            assert payload["proposal"]["character"]["maxHitPoints"] == 12
            assert payload["authored_proposal"]["character"]["maxHitPoints"] == 99
            assert payload["normalization_provenance"]["hit_points"]["expected_maximum"] == 12
        if defect == "author_saves":
            assert payload["authored_proposal"]["character"]["savingThrowBonuses"]["strength"] == 99
            assert payload["proposal"]["character"]["savingThrowBonuses"]["strength"] == 5
        return {"version": 1, "accepted": False, "feedback": "Rejected " + defect,
                "needs_player_clarification": needs_clarification}

    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=review, stop_after_rejection=True)
    assert result is None and commits == []
    assert len(reviewers) == 1 and len(authors) == 2
    correction = next(json.loads(m["content"]) for m in authors[1]
                      if m["role"] == "system" and '"rejected_proposal"' in m["content"])
    assert correction["rejected_proposal"] == reviewers[0]["authored_proposal"]
    assert correction["canonical_candidate"] == reviewers[0]["proposal"]
    assert correction["normalization_provenance"] == reviewers[0]["normalization_provenance"]
    assert correction["needs_player_clarification"] is needs_clarification
    if needs_clarification:
        assert correction["instruction"] == "Propose a continue_interview question; do not finalize."
    assert not any(m["role"] == "assistant" for m in conversation)


@pytest.mark.parametrize("defect", ["approval", "index", "schema"])
def test_invalid_consent_or_schema_cannot_reach_review(wizard, authored, monkeypatch, defect):
    if defect == "approval":
        authored["confirmation"]["whole_build_approved"] = False
    elif defect == "index":
        # run_interview uses 0; intercept parsing's reference instead.
        monkeypatch.setattr(wizard, "_latest_player_index", lambda messages: 99)
    else:
        authored["character"]["spellcasting"]["ability"] = None
    result, conversation, commits, authors, reviewers = run_interview(
        wizard, authored, monkeypatch, review=lambda p: pytest.fail("Review must not run"),
        stop_after_rejection=True)
    assert result is None and not commits and not reviewers
    assert len(authors) == 2


def test_fenced_json_uses_real_startup_parser_without_changing_probe(wizard, authored):
    from utils.startup_contract import parse_startup_response
    assert parse_startup_response("```json\n" + json.dumps(authored) + "\n```",
                                  latest_user_index=12) == authored


def test_network_is_forbidden(wizard):
    with pytest.raises(AssertionError, match="forbidden"):
        socket.create_connection(("openrouter.ai", 443))


def test_superseded_review_cannot_publish(wizard, authored, monkeypatch):
    from utils.capture.live_provider_call import LiveProviderSuperseded
    proposal = copy.deepcopy(authored)
    proposal["confirmation"]["player_message_index"] = 0
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
