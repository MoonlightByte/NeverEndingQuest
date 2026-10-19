"""Starting packages at character creation (final playthrough F1; plan startup-package-gold r5).

Offline gates through the real `_prepare_startup_proposal`, the bundled engine
binary and scripted model verdicts, with no networking (the provenance test's
fixtures). Playthrough captures are read in place under /home/loup/nql-stage and
never copied into the repo; a gate whose capture is absent is skipped with its
path. Engine fault cases (G4) are in test_startup_package_engine.py.
"""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from contextlib import redirect_stdout

import pytest

from test_startup_review_provenance import ROOT, authored, run_interview, wizard  # noqa: F401 (fixtures)

STAGE = Path("/home/loup/nql-stage")
F557 = STAGE / "final-557" / "runs" / "seg01" / "cap" / "T092.json"
F557_EVENTS = STAGE / "final-557" / "runs" / "seg01" / "events.ndjson"
THORNWOOD = STAGE / "play-thornwood" / "runs" / "seg01" / "cap" / "T092.json"
HOLY = ["itemdef:srd/holy-symbol-amulet", "itemdef:srd/holy-symbol-emblem", "itemdef:srd/holy-symbol-reliquary"]
CLERIC_EQUIPPED = ["itemdef:srd/chain-shirt", "itemdef:srd/shield"]
CLERIC_HOLY = {"cleric.A.holy_symbol": HOLY[0], "acolyte.A.holy_symbol": HOLY[0]}
# The real overlap builds (CC): capture, record, (class, background), equipped, gold.
OVERLAPS = [
    ("pt-557r0/runs/seg01/cap/T092.json", 14, ("rogue", "criminal"), {}, ["itemdef:srd/leather-armor"], 24),
    ("pt-j/seg1b/cap/T092.json", 20, ("cleric", "acolyte"), CLERIC_HOLY, CLERIC_EQUIPPED, 15),
    ("pt-j2/seg1/cap/T092.json", 16, ("cleric", "acolyte"), CLERIC_HOLY, CLERIC_EQUIPPED, 15),
    ("pt-7d/run/cap/T092.json", 12, ("cleric", "acolyte"), CLERIC_HOLY,
     CLERIC_EQUIPPED + ["itemdef:srd/mace", "itemdef:srd/robe"], 15),
    # Wizard A and Sage A each give a Robe: one stack of 2, which the engine does not wear.
    ("pt2/run/cap/T092.json", 12, ("wizard", "sage"), {}, [], 13),
]
FIGHTER_B_ROWS = ["Studded Leather Armor", "Scimitar", "Shortsword", "Longbow", "Quiver", "Dungeoneer's Pack"]
BRAM_PICKS = {"background_package": "B", "class_package": "B", "slot_picks": [],
              "equipped": ["itemdef:srd/studded-leather-armor", "itemdef:srd/scimitar", "itemdef:srd/shortsword"]}
SPELL_ROW = {"name": "Fire Bolt", "attackBonus": 5, "damageDice": "1d10", "damageBonus": 0,
             "damageType": "fire", "type": "spell", "description": "Authored spell attack."}
HELD_ID = "item:buy:healers-kit:1"
CLASS_KEYS = ["barbarian", "bard", "cleric", "druid", "fighter", "monk", "paladin", "ranger", "rogue",
              "sorcerer", "warlock", "wizard"]


def _record(path, index):
    if not path.exists():
        pytest.skip(f"capture absent: {path}")
    return json.loads(path.read_text(encoding="utf-8"))[index]


def _captured(path, index):
    return json.loads(next(iter(_record(path, index)["outputs"].values()))["content"])


def _picked(proposal, class_key, background_key, picks):
    proposal["origin"] = {"class_key": class_key, "background_key": background_key}
    proposal["starting_equipment"] = copy.deepcopy(picks)
    return proposal


def _bram(spell_row=False):
    proposal = _picked(_captured(F557, 10), "fighter", "soldier", BRAM_PICKS)
    if spell_row:
        proposal["character"]["attacksAndSpellcasting"].append(copy.deepcopy(SPELL_ROW))
    return proposal


def _with_origins(tmp_path):
    """The origins file where the wizard's Origin feat check reads it."""
    (tmp_path / "data").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "data" / "srd_character_origins.json", tmp_path / "data" / "srd_character_origins.json")


def _names(sheet):
    return [row["item_name"] for row in sheet.get("equipment") or []]


def _weapon_rows(sheet):
    return [a for a in sheet.get("attacksAndSpellcasting") or [] if a.get("type") in ("melee", "ranged")]


def _held(sheet):
    """{catalog id, or ("named", data key): quantity} over the sheet's equipment and ammunition."""
    held = {}
    for row in sheet.get("equipment") or []:
        key = row.get("catalog_id") or ("named", row["nql_id"].split(":")[2])
        held[key] = held.get(key, 0) + row["quantity"]
    for row in sheet.get("ammunition") or []:
        held[row["catalog_id"]] = held.get(row["catalog_id"], 0) + row["quantity"]
    return held


def _expected(options, picks):
    """The merge written out again from the data: {catalog id, or ("named", data key): quantity}."""
    out = {}
    for item in (i for option in options for i in option["items"]):
        if isinstance(item.get("choose_one"), list):
            key, quantity = picks[item["slot"]], 1
        elif "catalog_id" in item:
            key, quantity = item["catalog_id"], item["quantity"]
        else:
            key, quantity = ("named", item["key"]), 1
        out[key] = out.get(key, 0) + quantity
    return out


def _assert_stock_ids(sheet, provenance):
    """Each new ammunition stock's engine id, as the grant minted it, is genesis.ammunition_id's (LN-B1),
    so a purchase in play tops up the same stock."""
    from core.nql import genesis
    stocks = provenance["starting_packages"]["ammunition"]
    assert [s["name"] for s in stocks] == [row["name"] for row in sheet["ammunition"]]
    for stock in stocks:
        assert stock["nql_id"] == genesis.ammunition_id(sheet, stock["name"])


def _records():
    from core.nql.startup_rows import package_records
    return package_records()


def assert_f1(sheet):
    """The F1 player-visible check: Soldier B 50 + Fighter B 11, and no Dice Set row."""
    assert sheet["currency"] == {"gold": 61, "silver": 0, "copper": 0}
    assert "Dice Set" not in _names(sheet)


def assert_f1_fix(candidate, provenance):
    sheet = candidate["character"]
    assert_f1(sheet)
    assert sorted(_names(sheet)) == sorted(FIGHTER_B_ROWS)
    assert [(a["name"], a["quantity"]) for a in sheet["ammunition"]] == [("Arrows", 20)]
    assert "Arrows" not in _names(sheet)  # AC-N7: no Arrows row in equipment
    assert {row["catalog_id"] for row in sheet["equipment"] if row["equipped"]} == set(BRAM_PICKS["equipped"])
    assert sheet["armorClass"] == 15
    weapons = _weapon_rows(sheet)
    assert all(a.get("engine") is True for a in weapons)  # no authored melee/ranged row survives
    assert sorted(a["name"] for a in weapons) == sorted(provenance["engine_rows"]["written"])
    assert {a["name"].split(" (")[0] for a in weapons} == {"Scimitar", "Shortsword", "Longbow", "Unarmed Strike"}
    packages = provenance["starting_packages"]
    assert packages["status"] == "applied"
    assert packages["authored"]["currency"]["gold"] == 64
    assert "Dice Set" in [row["item_name"] for row in packages["authored"]["equipment"]]
    assert [(a["name"], a["quantity"]) for a in packages["authored"]["ammunition"]] == [("Arrows", 20)]
    assert {row["name"] for row in packages["authored"]["attacksAndSpellcasting"]} >= {"Scimitar", "Shortsword", "Longbow"}


# ---- G1, F1 -------------------------------------------------------------------

MAIN_DRIVER = r'''
import importlib.util, json, os, socket, sys, types
root, proposal_path = sys.argv[1], sys.argv[2]
def forbidden(*args, **kwargs):
    raise AssertionError("Network forbidden")
socket.socket.connect = socket.socket.connect_ex = forbidden
socket.create_connection = socket.getaddrinfo = forbidden
sys.path.insert(0, root)
keyring = types.ModuleType("keyring")
keyring.get_keyring = lambda: keyring
keyring.get_password = keyring.set_password = keyring.delete_password = forbidden
sys.modules["keyring"] = keyring
spec = importlib.util.spec_from_file_location("config", os.path.join(root, "config_template.py"))
config = importlib.util.module_from_spec(spec)
sys.modules["config"] = config
spec.loader.exec_module(config)
config.OPENAI_API_KEY = "offline-main-arm-no-network"
from utils import startup_wizard
startup_wizard.api_client.create_completion = forbidden
startup_wizard.capture_and_fanout = forbidden
proposal = json.load(open(proposal_path, encoding="utf-8"))
candidate, _ = startup_wizard._prepare_startup_proposal(proposal)
print(json.dumps(candidate["character"]))
'''


@pytest.fixture(scope="module")
def main_arm(tmp_path_factory):
    """final-557 rec 10's output through f2ee68ae's own _prepare_startup_proposal, in a child process."""
    proposal = _captured(F557, 10)
    base = tmp_path_factory.mktemp("main-arm")
    archive = subprocess.run(["git", "-C", str(ROOT), "archive", "f2ee68ae", "core", "utils", "data", "schemas",
                              "prompts", "updates", ":(glob)*.py"], capture_output=True)
    if archive.returncode != 0:
        pytest.skip(f"main arm needs commit f2ee68ae in {ROOT}: {archive.stderr.decode()[:200]}")
    main = base / "f2ee68ae"
    main.mkdir()
    subprocess.run(["tar", "x", "-C", str(main)], input=archive.stdout, check=True)
    work = base / "work"
    shutil.copytree(main / "schemas", work / "schemas")
    shutil.copytree(main / "prompts" / "leveling", work / "prompts" / "leveling")
    (base / "proposal.json").write_text(json.dumps(proposal), encoding="utf-8")
    (base / "driver.py").write_text(MAIN_DRIVER, encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not any(w in k.upper() for w in ("API_KEY", "TOKEN", "SECRET"))}
    env.update(NEQ_MULTI_MODEL_CAPTURE="0", NQL_APPLY_BINARY=str(ROOT / "bin" / "nql-apply"))
    run = subprocess.run([sys.executable, "-B", str(base / "driver.py"), str(main), str(base / "proposal.json")],
                         capture_output=True, cwd=work, env=env, timeout=300)
    assert run.returncode == 0, run.stderr.decode()[-2000:]
    return json.loads(run.stdout.decode().strip().splitlines()[-1])


def test_g1_main_arm_fails_the_f1_check(main_arm):
    assert main_arm["currency"]["gold"] == 64
    assert "Dice Set" in _names(main_arm)
    with pytest.raises(AssertionError):
        assert_f1(main_arm)


def test_g1_fix_arm(wizard, tmp_path):
    _with_origins(tmp_path)
    candidate, provenance = wizard._prepare_startup_proposal(_bram(spell_row=True))
    assert_f1_fix(candidate, provenance)
    assert SPELL_ROW in candidate["character"]["attacksAndSpellcasting"]  # SP-N2: a spell row stays
    assert provenance["engine_projection"]["applied"] is True
    again, _ = wizard._prepare_startup_proposal(candidate)  # the committed candidate prepares to itself
    assert again == candidate


def test_p5_no_equipment_key_and_a_bad_item_type_reach_the_grant(wizard):
    # P5 (LC-15): the authored form is zeroed before validation, so neither blocks the grant.
    missing = _bram()
    del missing["character"]["equipment"]
    candidate, _ = wizard._prepare_startup_proposal(missing)
    assert_f1(candidate["character"])
    bad = _bram()
    bad["character"]["equipment"][0]["item_type"] = "not-a-schema-type"
    candidate, _ = wizard._prepare_startup_proposal(bad)
    assert_f1(candidate["character"])


def test_authored_breath_weapon_row_gives_way_to_the_engine_rows(wizard, authored):
    # Step 3: an authored non-weapon melee/ranged row is dropped; the engine's rows stand.
    sheet = authored["character"]
    sheet["race"] = "Dragonborn"
    sheet["attacksAndSpellcasting"].append({"name": "Breath Weapon", "attackBonus": 0, "damageDice": "1d10",
                                            "damageBonus": 0, "damageType": "fire", "type": "ranged",
                                            "description": "Authored breath weapon."})
    candidate, provenance = wizard._prepare_startup_proposal(authored)
    weapons = _weapon_rows(candidate["character"])
    assert weapons and all(a.get("engine") is True for a in weapons)
    assert sorted(a["name"] for a in weapons) == sorted(provenance["engine_rows"]["written"])
    assert "Breath Weapon" in [a["name"] for a in provenance["starting_packages"]["authored"]["attacksAndSpellcasting"]]


# ---- G2, matrix ---------------------------------------------------------------

def _class_sheet(authored, class_key):
    sheet = copy.deepcopy(authored["character"])
    orders = {"cleric": "Divine Order: Protector", "druid": "Primal Order: Warden"}
    if class_key != "fighter":
        sheet["classFeatures"] = ([{"name": orders[class_key], "description": "typed", "source": "level 1"}]
                                  if class_key in orders else [])
    return sheet


def _slot_choices(options):
    """Every combination of the choose_one picks of the chosen packages; a named slot gets a display name."""
    combos = [{}]
    named = {}
    for item in (i for option in options for i in option["items"]):
        if not isinstance(item.get("slot"), str):
            continue
        if isinstance(item.get("choose_one"), list):
            combos = [dict(c, **{item["slot"]: pick}) for c in combos for pick in item["choose_one"]]
        else:
            named[item["slot"]] = "Chosen " + item["key"]
    return combos, named


def _held_elsewhere(tmp_path):
    (tmp_path / "characters").mkdir(exist_ok=True)
    (tmp_path / "characters" / "other_hero.json").write_text(json.dumps(
        {"name": "Other Hero", "equipment": [{"item_name": "Healer's Kit", "nql_id": HELD_ID}]}), encoding="utf-8")


@pytest.mark.parametrize("class_key", CLASS_KEYS)
def test_g2_every_package_and_pick_is_granted(wizard, authored, tmp_path, class_key):
    from core.nql import item_catalog
    from jsonschema import validate
    _held_elsewhere(tmp_path)
    schema = json.loads((ROOT / "schemas" / "char_schema.json").read_text(encoding="utf-8"))
    records = _records()
    cases = 0
    for class_package, class_option in records.classes[class_key].items():
        for background_key, background in records.backgrounds.items():
            for background_package, background_option in background["equipment_options"].items():
                options = [class_option, background_option]
                combos, named = _slot_choices(options)
                for combo in combos:
                    expected = _expected(options, combo)
                    armor = sorted(i for i in expected if isinstance(i, str)
                                   and item_catalog.entry(i).get("kind") == "armor")
                    slot_picks = ([{"slot": s, "catalog_id": c} for s, c in combo.items()]
                                  + [{"slot": s, "display_name": n} for s, n in named.items()])
                    proposal = _picked(copy.deepcopy(authored), class_key, background_key, {
                        "background_package": background_package, "class_package": class_package,
                        "slot_picks": slot_picks, "equipped": armor})
                    proposal["character"] = _class_sheet(authored, class_key)
                    label = (class_key, class_package, background_key, background_package, combo)
                    candidate, provenance = wizard._prepare_startup_proposal(proposal)
                    sheet = candidate["character"]
                    assert provenance["starting_packages"]["status"] == "applied", label
                    assert sheet["currency"] == {"gold": class_option["coins"]["gp"] + background_option["coins"]["gp"],
                                                 "silver": 0, "copper": 0}, label
                    assert _held(sheet) == expected, label
                    data_items = {i["key"]: i for o in options for i in o["items"] if "key" in i}
                    for row in sheet["equipment"]:
                        if "catalog_id" not in row:  # a named row is typed from the data
                            data = data_items[row["nql_id"].split(":")[2]]
                            assert (row["item_type"], row["description"]) == (data["item_type"], data["description"])
                            assert row["item_name"] == named.get(data.get("slot"), data["uncatalogued"]), label
                    nql_ids = [row["nql_id"] for row in sheet["equipment"]]
                    assert len(set(nql_ids)) == len(nql_ids) and HELD_ID not in nql_ids, label
                    assert {r["nql_id"] for r in provenance["starting_packages"]["equipment"]} == set(nql_ids)
                    _assert_stock_ids(sheet, provenance)
                    assert [r["catalog_id"] for r in sheet["equipment"] if r["equipped"]] == [
                        r["catalog_id"] for r in sheet["equipment"] if r.get("catalog_id") in armor]
                    validate(sheet, schema)
                    cases += 1
    assert cases >= 8


def _held_ids_check(wizard, authored, tmp_path):
    _held_elsewhere(tmp_path)
    proposal = _picked(authored, "fighter", "soldier", {
        "background_package": "A", "class_package": "B", "equipped": [],
        "slot_picks": [{"slot": "soldier.A.gaming_set", "display_name": "Dice Set"}]})
    candidate, provenance = wizard._prepare_startup_proposal(proposal)
    sheet = candidate["character"]
    rows = {row["item_name"]: row for row in sheet["equipment"]}
    assert rows["Healer's Kit"]["nql_id"] == "item:buy:healers-kit:2"
    # Soldier A + Fighter B: one Quiver row of 2 and one Arrows stock of 40 (L2n).
    assert rows["Quiver"]["quantity"] == 2
    assert [(a["name"], a["quantity"], a["catalog_id"]) for a in sheet["ammunition"]] == [
        ("Arrows", 40, "itemdef:srd/arrows")]
    assert sheet["currency"]["gold"] == 25
    assert {"Spear", "Shortbow", "Healer's Kit", "Clothes, Traveler's", "Dice Set"} <= set(rows)
    _assert_stock_ids(sheet, provenance)


def test_g2_ids_step_past_held_ids_and_overlaps_merge(wizard, authored, tmp_path):
    _held_ids_check(wizard, authored, tmp_path)


def test_mutant_ammunition_id_not_genesis(wizard, authored, tmp_path, monkeypatch):
    # The grant mints the stock id under another name; the engine accepts it.
    import types
    from core.nql import genesis, startup_rows
    minted = types.ModuleType("genesis_mutant")
    minted.__dict__.update(genesis.__dict__)
    minted.ammunition_id = lambda sheet, name: genesis.ammunition_id(sheet, name + " stock")
    monkeypatch.setattr(startup_rows, "genesis", minted)
    with pytest.raises(AssertionError):
        _held_ids_check(wizard, authored, tmp_path)


def test_g2_drift_pin_bought_arrows_match_the_granted_stock(wizard, authored, tmp_path):
    # L9 drift pin (SP-F5 c3): a purchase in play writes the grant's ammunition row shape.
    from core.managers import item_acquisition
    granted, _ = wizard._prepare_startup_proposal(_picked(copy.deepcopy(authored), "fighter", "soldier", dict(
        BRAM_PICKS, equipped=[])))
    grant_row = granted["character"]["ammunition"][0]
    buyer, _ = wizard._prepare_startup_proposal(_picked(copy.deepcopy(authored), "fighter", "soldier", {
        "background_package": "B", "class_package": "C", "slot_picks": [], "equipped": []}))
    (tmp_path / "characters").mkdir(exist_ok=True)
    (tmp_path / "characters" / "alden.json").write_text(json.dumps(buyer["character"]), encoding="utf-8")
    (tmp_path / "party_tracker.json").write_text(json.dumps({"module": "The_Thornwood_Watch", "partyMembers": ["Alden"],
                                                              "partyNPCs": [], "worldConditions": {}}), encoding="utf-8")
    result = item_acquisition.execute_acquisition("Alden", "Arrows", 20)
    assert result["success"], result
    bought = json.loads((tmp_path / "characters" / "alden.json").read_text(encoding="utf-8"))["ammunition"]
    assert len(bought) == 1
    assert dict(bought[0], quantity=None) == dict(grant_row, quantity=None)


@pytest.mark.parametrize("capture, index, origin, holy, equipped, gold", OVERLAPS)
def test_g2_real_overlap_builds_replay(wizard, capture, index, origin, holy, equipped, gold):
    proposal = _picked(_captured(STAGE / capture, index), origin[0], origin[1], {
        "background_package": "A", "class_package": "A",
        "slot_picks": [{"slot": slot, "catalog_id": pick} for slot, pick in holy.items()], "equipped": equipped})
    candidate, provenance = wizard._prepare_startup_proposal(proposal)
    sheet = candidate["character"]
    assert provenance["starting_packages"]["status"] == "applied"
    assert sheet["currency"] == {"gold": gold, "silver": 0, "copper": 0}
    records = _records()
    options = [records.classes[origin[0]]["A"], records.backgrounds[origin[1]]["equipment_options"]["A"]]
    assert _held(sheet) == _expected(options, holy)
    assert sorted(r["catalog_id"] for r in sheet["equipment"] if r["equipped"]) == sorted(equipped)


def test_g2_thornwood_positive_control(wizard, tmp_path):
    # rec 11's output lacks spellcasting and was refused at f2ee68ae; rec 12 is its corrected finalize.
    _with_origins(tmp_path)
    proposal = _picked(_captured(THORNWOOD, 12), "fighter", "soldier", {
        "background_package": "A", "class_package": "A",
        "slot_picks": [{"slot": "soldier.A.gaming_set", "display_name": "Dice Set"}],
        "equipped": ["itemdef:srd/chain-mail"]})
    candidate, _ = wizard._prepare_startup_proposal(proposal)
    sheet = candidate["character"]
    assert sheet["currency"] == {"gold": 18, "silver": 0, "copper": 0}
    assert _names(sheet).count("Dice Set") == 1


def _gaming_set_name(wizard, authored):
    authored["character"].setdefault("proficiencies", {})["tools"] = ["Dice Set"]
    proposal = _picked(authored, "fighter", "soldier", {
        "background_package": "A", "class_package": "C", "equipped": [],
        "slot_picks": [{"slot": "soldier.A.gaming_set", "display_name": "Three-Dragon Ante Set"}]})
    candidate, _ = wizard._prepare_startup_proposal(proposal)
    named = [row for row in candidate["character"]["equipment"] if "catalog_id" not in row]
    assert [row["item_name"] for row in named] == ["Three-Dragon Ante Set"]


def test_g2_named_pick_keeps_the_players_display_name(wizard, authored):
    _gaming_set_name(wizard, authored)


def test_g2_mutant_name_from_proficiency_text_fails(wizard, authored, monkeypatch):
    from core.nql import startup_rows
    real = startup_rows.grant_starting_packages

    def from_proficiency(sheet, origin, picks, faults):
        granted, report = real(sheet, origin, picks, faults)
        for row in granted["equipment"]:
            if "catalog_id" not in row:
                row["item_name"] = sheet["proficiencies"]["tools"][0]
        return granted, report

    monkeypatch.setattr(startup_rows, "grant_starting_packages", from_proficiency)
    with pytest.raises(AssertionError):
        _gaming_set_name(wizard, authored)


# ---- G3, refusals (b) ---------------------------------------------------------

def _refusal(wizard, authored, class_key, background_key, picks):
    with pytest.raises(ValueError) as refused:
        wizard._prepare_startup_proposal(_picked(authored, class_key, background_key, picks))
    return str(refused.value)


CLERIC_PICKS = {"background_package": "A", "class_package": "A", "equipped": [],
                "slot_picks": [{"slot": "cleric.A.holy_symbol", "catalog_id": HOLY[0]},
                               {"slot": "acolyte.A.holy_symbol", "catalog_id": HOLY[1]}]}


@pytest.mark.parametrize("case", ["class_key", "background_key", "class_package", "background_package",
                                  "unknown_slot", "missing_pick", "display_name_on_catalog_slot",
                                  "catalog_id_on_named_slot", "equipped_outside"])
def test_g3_every_refusal_names_every_legal_value(wizard, authored, case):
    picks, keys, legal = copy.deepcopy(CLERIC_PICKS), ["cleric", "acolyte"], []
    if case == "class_key":
        keys[0], legal = "knight", CLASS_KEYS
    elif case == "background_key":
        keys[1], legal = "noble", ["acolyte", "criminal", "sage", "soldier"]
    elif case == "class_package":
        picks["class_package"], legal = "D", ["A", "B"]
    elif case == "background_package":
        picks["background_package"], legal = "C", ["A", "B"]
    elif case == "unknown_slot":
        picks["slot_picks"].append({"slot": "soldier.A.gaming_set", "display_name": "Dice"})
        legal = ["soldier.A.gaming_set", "cleric.A.holy_symbol", "acolyte.A.holy_symbol"]
    elif case == "missing_pick":
        picks["slot_picks"].pop()
        legal = ["acolyte.A.holy_symbol"] + HOLY
    elif case == "display_name_on_catalog_slot":
        picks["slot_picks"][0] = {"slot": "cleric.A.holy_symbol", "display_name": "My holy symbol"}
        legal = ["cleric.A.holy_symbol"] + HOLY
    elif case == "catalog_id_on_named_slot":
        keys, picks = ["fighter", "soldier"], {
            "background_package": "A", "class_package": "C", "equipped": [],
            "slot_picks": [{"slot": "soldier.A.gaming_set", "catalog_id": "itemdef:srd/dagger"}]}
        legal = ["soldier.A.gaming_set", "display_name"]
    else:
        picks["equipped"] = ["itemdef:srd/longsword"]
        legal = ["itemdef:srd/longsword", "itemdef:srd/chain-shirt", "itemdef:srd/shield", "itemdef:srd/mace",
                 "itemdef:srd/priests-pack", "itemdef:srd/book", "itemdef:srd/parchment", "itemdef:srd/robe",
                 HOLY[0], HOLY[1]]
    message = _refusal(wizard, authored, keys[0], keys[1], picks)
    for value in legal:
        assert value in message, (case, value, message)


def test_g3_origin_enum_refusal_at_parse_names_every_key(wizard, authored):
    from utils.startup_contract import parse_startup_response
    authored["origin"]["background_key"] = "noble"
    with pytest.raises(ValueError) as refused:
        parse_startup_response(json.dumps(authored), latest_user_index=authored["confirmation"]["player_message_index"])
    for key in ("acolyte", "criminal", "sage", "soldier"):
        assert key in str(refused.value)


def test_g3_interview_turns_carry_null_picks(wizard):
    # FF-N6: a continue_interview with origin and starting_equipment null parses; set, it is refused.
    from utils.startup_contract import parse_startup_response
    turn = {"version": 1, "decision": "continue_interview", "narration": "Which background?",
            "confirmation": {"whole_build_approved": False, "player_message_index": None},
            "character": None, "origin": None, "starting_equipment": None}
    assert parse_startup_response(json.dumps(turn), latest_user_index=3) == turn
    with pytest.raises(ValueError, match="origin and starting_equipment null"):
        parse_startup_response(json.dumps(dict(turn, origin={"class_key": "fighter", "background_key": "soldier"})),
                               latest_user_index=3)


def test_g3_finalize_without_picks_is_refused(wizard, authored):
    from utils.startup_contract import parse_startup_response
    authored["starting_equipment"] = None
    with pytest.raises(ValueError, match="Finalization requires origin"):
        parse_startup_response(json.dumps(authored), latest_user_index=authored["confirmation"]["player_message_index"])


def test_f_schema_enums_are_built_at_call_time(wizard, monkeypatch):
    from core.nql import startup_rows
    from utils import startup_prompt_builder
    from utils.startup_contract import startup_response_schema
    origin = startup_response_schema()["properties"]["origin"]["properties"]
    assert origin["class_key"]["enum"] == CLASS_KEYS
    assert origin["background_key"]["enum"] == ["acolyte", "criminal", "sage", "soldier"]
    assert '"acolyte",' in startup_prompt_builder.build_character_creation_system_prompt()
    monkeypatch.setattr(startup_rows, "ORIGINS_PATH", str(Path(os.getcwd()) / "no-such-origins.json"))
    origin = startup_response_schema()["properties"]["origin"]["properties"]
    assert "enum" not in origin["class_key"] and "enum" not in origin["background_key"]
    prompt = startup_prompt_builder.build_character_creation_system_prompt()  # no raise
    assert '"background_key": {' in prompt and '"acolyte",' not in prompt


def test_f_data_unavailable_at_finalize(wizard, monkeypatch):
    from core.nql import startup_rows
    monkeypatch.setattr(startup_rows, "ORIGINS_PATH", str(Path(os.getcwd()) / "no-such-origins.json"))
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    packages = provenance["starting_packages"]
    assert (packages["status"], packages["policy"]) == ("data_unavailable", "D-PKG-1")
    sheet = candidate["character"]
    assert sheet["currency"] == {"gold": 0, "silver": 0, "copper": 0}
    assert sheet["equipment"] == [] and sheet["ammunition"] == []
    assert wizard._starting_gear_notice(sheet, provenance) == (
        "The game's rules data could not be read, so Bram Holloway starts with no gold, no starting gear and no "
        "weapons. Reinstalling the game restores it; reset the campaign and create the character again, or play "
        "on without them.")


# ---- G4b, T124 fed (d)'s candidate offline ---------------------------------------

REVIEWER_LINE = ("When starting_packages.status is engine_unavailable or data_unavailable, missing\n"
                 "gold, starting gear, weapon attack rows and armor from that gear are the game's\n"
                 "disclosed outcome under the owner's ruling, not a lost choice; still check the\npicks.")


class _Ordered(io.StringIO):
    """stdout that also records each print in a shared event list."""

    def __init__(self, events):
        super().__init__()
        self.events = events

    def write(self, text):
        if text.strip():
            self.events.append(("print", text))
        return super().write(text)


def _g4b_disclosed(wizard, monkeypatch, tmp_path):
    from core.nql import apply
    from utils import startup_prompt_builder
    blocked = tmp_path / "not-an-engine"
    blocked.write_text("not an executable", encoding="utf-8")
    monkeypatch.setenv("NQL_APPLY_BINARY", str(blocked))
    reviews = []

    def review(payload):
        reviews.append(payload)
        return {"version": 1, "accepted": True, "feedback": "Disclosed outcome.", "needs_player_clarification": False}

    events = []
    inner = wizard._set_startup_progress

    def progress(conversation, **changes):
        events.append(("progress", changes.get("phase")))
        return inner(conversation, **changes)

    monkeypatch.setattr(wizard, "_set_startup_progress", progress)
    out = _Ordered(events)
    with redirect_stdout(out):
        _, conversation, commits, _, _ = run_interview(wizard, _bram(), monkeypatch, review=review)
    facts = reviews[0]["committed_facts"]
    assert facts["origin"] == {"class_key": "fighter", "background_key": "soldier"}
    assert facts["starting_equipment"] == BRAM_PICKS
    assert facts["starting_packages"] == {"status": "engine_unavailable", "armor_class": "unchecked",
                                          "policy": "D-PKG-1"}
    assert REVIEWER_LINE in startup_prompt_builder.build_startup_review_prompt()
    # The engine-built sheet keeps its unarmored base (10 + Dex 17's +3) when no armor can be projected.
    assert commits[0]["currency"]["gold"] == 0 and commits[0]["armorClass"] == 13
    notice = ("Dungeon Master: The rules engine could not run, so Bram Holloway starts with no gold, no starting "
              f"gear and no weapons. To play with them, make sure {apply.binary_path()} runs on this computer, "
              "reset the campaign, and create the character again; otherwise you can play on without them.")
    assert out.getvalue().count(notice) == 1
    # Shown before the approved checkpoint is written (FF R3 N4).
    shown_at = next(i for i, (kind, text) in enumerate(events) if kind == "print" and notice in "\n" + text)
    approved_at = events.index(("progress", "approved"))
    assert shown_at < approved_at


def test_g4b_reviewer_gets_the_disclosed_outcome(wizard, monkeypatch, tmp_path):
    _g4b_disclosed(wizard, monkeypatch, tmp_path)


def test_mutant_notice_after_the_approved_checkpoint(wizard, monkeypatch, tmp_path):
    real_notice, real_progress = wizard._starting_gear_notice, wizard._set_startup_progress
    held = {}

    def defer(character, provenance):
        held["args"] = (character, provenance)
        return None

    def approved_then_notice(conversation, **changes):
        record = real_progress(conversation, **changes)
        if changes.get("phase") == "approved" and "args" in held:
            print(f"\nDungeon Master: {real_notice(*held['args'])}")
        return record

    monkeypatch.setattr(wizard, "_starting_gear_notice", defer)
    monkeypatch.setattr(wizard, "_set_startup_progress", approved_then_notice)
    with pytest.raises(AssertionError):
        _g4b_disclosed(wizard, monkeypatch, tmp_path)


def test_g4b_reviewer_gets_the_engine_result(wizard, monkeypatch, tmp_path):
    _with_origins(tmp_path)
    reviews = []

    def review(payload):
        reviews.append(payload)
        return {"version": 1, "accepted": True, "feedback": "Ok.", "needs_player_clarification": False}

    with redirect_stdout(io.StringIO()):
        run_interview(wizard, _bram(), monkeypatch, review=review)
    packages = reviews[0]["committed_facts"]["starting_packages"]
    assert packages["status"] == "applied" and packages["armor_class"] == 15
    assert packages["engine_result"] == "gold 61 = Soldier B 50 + Fighter B 11"
    assert "Arrows x20 (ammunition)" in packages["rows"]
    assert sorted(packages["equipped"]) == ["Scimitar", "Shortsword", "Studded Leather Armor"]


# ---- G5, resume ---------------------------------------------------------------

def test_g5_paused_conversation_keeps_its_reference(wizard, monkeypatch):
    # D-CREATE-COST-5 amendment 1c: a paused interview from before the engine-built sheet resumes on the engine
    # path. Its reference stays as it was (same bytes, once), the menu scope is added, a model-written sheet
    # is refused, and the engine builds the approved build from typed intent.
    from test_startup_review_provenance import _engine_finalize
    conversation = copy.deepcopy(_record(F557, 10)["input"]["messages"][:-1])

    def references(messages):
        return [m["content"] for m in messages if m["role"] == "system"
                and (json.loads(m["content"]) if m["content"].startswith("{") else {}).get("task_purpose")
                == "startup_rules_reference"]

    before = references(conversation)
    assert len(before) == 1
    latest = max(i for i, m in enumerate(conversation) if m["role"] == "user")
    old_shape = _picked(_captured(F557, 10), "fighter", "soldier", dict(BRAM_PICKS, background_package="A"))
    missing = _engine_finalize(copy.deepcopy(old_shape))
    valid = copy.deepcopy(missing)
    valid["starting_equipment"]["slot_picks"] = [{"slot": "soldier.A.gaming_set", "display_name": "Dice Set"}]
    for proposal in (old_shape, missing, valid):
        proposal["confirmation"]["player_message_index"] = latest
    # The first engine answer re-scopes once (menu to the build's scope) and is asked again.
    answers = [old_shape, missing, missing, valid]
    authors, commits = [], []
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "_commit_startup_build", lambda c, m, s, **k: commits.append(copy.deepcopy(s)))

    def model(messages, *args, **kwargs):
        if kwargs.get("startup_phase") == "startup_review":
            return json.dumps({"version": 1, "accepted": True, "feedback": "Ok.", "needs_player_clarification": False})
        authors.append(copy.deepcopy(messages))
        return json.dumps(answers[len(authors) - 1])

    monkeypatch.setattr(wizard, "get_ai_response", model)
    with redirect_stdout(io.StringIO()):
        wizard.ai_character_interview(conversation, {"name": "The_Thornwood_Watch"})
    assert references(conversation) == before  # the f2ee68ae-era reference, same bytes, once
    assert len(authors) == 4 and all(references(a) == before for a in authors)
    purposes = [(json.loads(m["content"]) if m["content"].startswith("{") else {}).get("task_purpose")
                for m in conversation if m["role"] == "system"]
    assert "startup_creation_scope" in purposes and "startup_engine_build" in purposes
    assert authors[1][-2]["content"].startswith("Rejected startup proposal")  # the model-written sheet
    refusal = authors[3][-2]["content"]
    assert refusal.startswith("Rejected startup proposal") and "soldier.A.gaming_set" in refusal
    assert len(commits) == 1 and commits[0]["currency"]["gold"] == 25
    assert commits[0]["name"] == old_shape["character"]["name"]


# ---- G6 and G7, the commit and what the player sees ---------------------------------

def _control_event():
    if not F557_EVENTS.exists():
        pytest.skip(f"capture absent: {F557_EVENTS}")
    with open(F557_EVENTS, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if number == 440:
                return json.loads(line)
    pytest.skip(f"{F557_EVENTS} has no line 440")


def _commit_and_read(wizard, monkeypatch, tmp_path, character, *, created=True):
    """D-PKG-3: an approved candidate through the real resume commit, read where the player sees it."""
    from core.effects.effective import effective_sheet
    from core.headless import state_reader
    from updates.update_character_info import normalize_character_name
    from utils.module_path_manager import ModulePathManager
    event = _control_event()
    module = event["party_tracker"]["module"]
    shutil.copytree(ROOT / "modules" / module / "areas", tmp_path / "modules" / module / "areas")
    location = {"areaId": event["location"]["area_id"], "locationId": event["location"]["id"]}
    conversation = ([{"role": "system", "content": json.dumps({"task_purpose": "startup_character_interview"})}]
                    if created else [])
    conversation.append({"role": "system", "content": json.dumps({
        "startup_checkpoint_version": 1, "startup_id": "g7", "phase": "approved", "module": module,
        "latest_user_index": None, "candidate": character, "location": location, "character_path": None})})
    monkeypatch.setattr(wizard, "initialize_startup_conversation", lambda: conversation)
    monkeypatch.setattr(wizard, "select_module", lambda conversation: {"name": module})
    monkeypatch.setattr(wizard, "save_startup_conversation", lambda *a, **k: None)
    monkeypatch.setattr(wizard, "cleanup_startup_conversation", lambda: None)
    out = io.StringIO()
    with redirect_stdout(out):
        assert wizard.run_startup_sequence() is True
    path = tmp_path / "characters" / (normalize_character_name(character["name"]) + ".json")
    sheet = json.loads(path.read_text(encoding="utf-8"))
    state = state_reader.build_snapshot()
    # The inventory view's read (web_interface.py handle_player_data_request, dataType inventory).
    tracker = json.loads((tmp_path / "party_tracker.json").read_text(encoding="utf-8"))
    player_file = ModulePathManager(tracker["module"].replace(" ", "_")).get_character_path(
        normalize_character_name(tracker["partyMembers"][0]))
    inventory = effective_sheet(json.loads(Path(player_file).read_text(encoding="utf-8")))
    welcome = [line for line in out.getvalue().splitlines() if "Welcome, " in line]
    assert state["location"]["id"] == location["locationId"]
    return sheet, state, inventory, welcome, event


def test_g7_player_visible_fix_arm(wizard, monkeypatch, tmp_path):
    _with_origins(tmp_path)
    candidate, _ = wizard._prepare_startup_proposal(_bram())
    sheet, state, inventory, welcome, event = _commit_and_read(wizard, monkeypatch, tmp_path, candidate["character"])
    assert sheet == candidate["character"]
    assert_f1(sheet)
    assert sorted(_names(sheet)) == sorted(FIGHTER_B_ROWS)
    assert [(a["name"], a["quantity"]) for a in sheet["ammunition"]] == [("Arrows", 20)]
    assert state["player"]["currency"]["gold"] == 61
    assert inventory["equipment"] == sheet["equipment"] and inventory["ammunition"] == sheet["ammunition"]
    assert len(welcome) == 1 and welcome[0].endswith("Welcome, Bram Holloway! You start with 61 gold. Armor class 15, hit points 12.")
    assert event["player"]["currency"]["gold"] == 64  # control: what final-557's player saw


def test_g7_player_visible_main_arm_fails(wizard, monkeypatch, tmp_path, main_arm):
    sheet, state, inventory, welcome, _ = _commit_and_read(wizard, monkeypatch, tmp_path, main_arm)
    assert sheet == main_arm and state["player"]["currency"]["gold"] == 64
    assert inventory["equipment"] == sheet["equipment"]
    assert welcome[0].endswith("You start with 64 gold. Armor class 15, hit points 12.")
    with pytest.raises(AssertionError):
        assert_f1(sheet)


def test_g6_pre_upgrade_approved_candidate_commits_unchanged(wizard, monkeypatch, tmp_path, main_arm):
    # (e): a candidate approved before the upgrade (authored gold and gear) commits as stored.
    sheet, state, _, welcome, _ = _commit_and_read(wizard, monkeypatch, tmp_path, copy.deepcopy(main_arm))
    assert sheet == main_arm and sheet["currency"]["gold"] == 64


def test_welcome_line_for_a_character_picked_from_the_list(wizard, monkeypatch, tmp_path, main_arm):
    _, _, _, welcome, _ = _commit_and_read(wizard, monkeypatch, tmp_path, main_arm, created=False)
    assert welcome[0].endswith("Welcome, Bram Holloway! You have 64 gold. Armor class 15, hit points 12.")


# ---- Mutants: each must fail the gate it targets -------------------------------------

def _patch_grant(monkeypatch, change):
    from core.nql import startup_rows
    real = startup_rows.grant_starting_packages
    monkeypatch.setattr(startup_rows, "grant_starting_packages",
                        lambda sheet, origin, picks, faults: change(real, sheet, origin, picks, faults))


def _g1(wizard):
    candidate, provenance = wizard._prepare_startup_proposal(_bram())
    assert_f1_fix(candidate, provenance)


def test_mutant_grant_not_called(wizard, monkeypatch):
    _patch_grant(monkeypatch, lambda real, sheet, origin, picks, faults: (copy.deepcopy(sheet), {}))
    with pytest.raises(AssertionError):
        _g1(wizard)


def test_mutant_gp_term_dropped(wizard, monkeypatch):
    from core.nql import startup_rows
    real = startup_rows.package_records

    def dropped():
        records = copy.deepcopy(real())
        records.backgrounds["soldier"]["equipment_options"]["B"]["coins"]["gp"] = 0
        return records

    monkeypatch.setattr(startup_rows, "package_records", dropped)
    with pytest.raises(AssertionError):
        _g1(wizard)


def test_mutant_wrong_background_option(wizard, monkeypatch):
    _patch_grant(monkeypatch, lambda real, sheet, origin, picks, faults: real(sheet, origin, dict(
        picks, background_package="A", slot_picks=[{"slot": "soldier.A.gaming_set", "display_name": "Dice Set"}]),
        faults))
    with pytest.raises(AssertionError):
        _g1(wizard)


def test_mutant_equipped_ignored(wizard, monkeypatch):
    _patch_grant(monkeypatch, lambda real, sheet, origin, picks, faults: real(
        sheet, origin, dict(picks, equipped=[]), faults))
    with pytest.raises(AssertionError):
        _g1(wizard)


def _overlap_check(wizard, authored):
    candidate, _ = wizard._prepare_startup_proposal(_picked(authored, "fighter", "soldier", {
        "background_package": "A", "class_package": "B", "equipped": [],
        "slot_picks": [{"slot": "soldier.A.gaming_set", "display_name": "Dice Set"}]}))
    sheet = candidate["character"]
    assert [r["quantity"] for r in sheet["equipment"] if r["item_name"] == "Quiver"] == [2]
    assert [(a["name"], a["quantity"]) for a in sheet["ammunition"]] == [("Arrows", 40)]


def test_mutant_no_overlap_merge(wizard, authored, monkeypatch):
    from core.nql import startup_rows
    real = startup_rows._merged
    monkeypatch.setattr(startup_rows, "_merged", lambda items, chosen: [
        merged for item in items for merged in real([item], chosen)])
    with pytest.raises((AssertionError, ValueError)):
        _overlap_check(wizard, authored)


def test_overlap_merge(wizard, authored):
    _overlap_check(wizard, authored)


def _identity_check(wizard, authored):
    authored["character"]["class"] = "Wizard"  # mistyped by the author; the typed key is fighter
    candidate, provenance = wizard._prepare_startup_proposal(_picked(authored, "fighter", "soldier", dict(
        BRAM_PICKS, equipped=[])))
    sheet = candidate["character"]
    assert sheet["class"] == "Fighter"
    assert sheet["maxHitPoints"] == 12  # Fighter d10 + Constitution 2: derived from the written class
    assert "class 'Wizard' -> 'Fighter' (written from origin.class_key)" in provenance["mechanics_notes"]


def test_identity_is_written_from_the_typed_key(wizard, authored):
    _identity_check(wizard, authored)


def test_mutant_identity_written_after_startup_mechanics(wizard, authored, monkeypatch):
    real_write, real_mechanics = wizard._write_origin_identity, wizard.startup_mechanics
    held = {}

    def deferred(character, origin):
        held["origin"] = origin
        return []

    def mechanics_then_identity(character, **kwargs):
        character, notes = real_mechanics(character, **kwargs)
        return character, real_write(character, held["origin"]) + notes

    monkeypatch.setattr(wizard, "_write_origin_identity", deferred)
    monkeypatch.setattr(wizard, "startup_mechanics", mechanics_then_identity)
    with pytest.raises((AssertionError, ValueError)):
        _identity_check(wizard, authored)


def _zero_check(wizard, authored):
    authored["character"]["ammunition"] = [{"name": "Arrows", "quantity": 20, "description": "Authored arrows."}]
    proposal = _picked(authored, "wizard", "sage", {"background_package": "B", "class_package": "B",
                                                    "slot_picks": [], "equipped": []})
    proposal["character"] = _class_sheet(authored, "wizard")
    candidate, _ = wizard._prepare_startup_proposal(proposal)
    sheet = candidate["character"]
    assert sheet["currency"] == {"gold": 105, "silver": 0, "copper": 0}
    assert sheet["equipment"] == [] and sheet["ammunition"] == []


def test_authored_gear_is_set_aside(wizard, authored):
    _zero_check(wizard, authored)


@pytest.mark.parametrize("kept", ["currency", "equipment", "ammunition"])
def test_mutant_authored_gear_kept(wizard, authored, monkeypatch, kept):
    real = wizard._zero_authored_gear

    def keeps(character):
        value = copy.deepcopy(character.get(kept))
        removed = real(character)
        character[kept] = value
        return removed

    monkeypatch.setattr(wizard, "_zero_authored_gear", keeps)
    with pytest.raises((AssertionError, ValueError)):
        _zero_check(wizard, authored)


def test_npc_origin_reference_is_unchanged_by_the_packages(wizard, monkeypatch, tmp_path):
    # task-1: the NPC builder's origins reference drops the startup-only fields; the rest is as before.
    from core.generators import npc_builder
    from core.leveling import tables
    before = subprocess.run(["git", "-C", str(ROOT), "show", "f2ee68ae:data/srd_character_origins.json"],
                            capture_output=True)
    if before.returncode != 0:
        pytest.skip(f"needs commit f2ee68ae in {ROOT}")
    old = tmp_path / "old" / "data"
    (old / "leveling").mkdir(parents=True)
    (old / "srd_character_origins.json").write_bytes(before.stdout)
    current = json.loads((ROOT / "data" / "srd_character_origins.json").read_text(encoding="utf-8"))
    assert all("key" in b and "equipment_options" in b for b in current["backgrounds"])
    for request in (("Human", "Soldier"), ("Hill Dwarf", "Noble"), (None, None)):
        now = npc_builder._srd_origin_reference(*request)
        with monkeypatch.context() as patch:
            patch.setattr(tables, "_DATA", str(old / "leveling" / "progression.json"))
            assert npc_builder._srd_origin_reference(*request) == now
            assert "key" not in npc_builder._srd_origin_reference(*request)["backgrounds"][0]
            (old / "srd_character_origins.json").write_text(json.dumps(dict(
                json.loads(before.stdout), background_ability_scores_rule="read from the old file")), encoding="utf-8")
            assert npc_builder._srd_origin_reference(*request)["background_ability_scores_rule"] == "read from the old file"
            (old / "srd_character_origins.json").write_bytes(before.stdout)
