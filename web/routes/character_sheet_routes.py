# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Web Routes - Character sheet endpoints
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import io

from flask import jsonify, send_file

from utils.enhanced_logger import error, warning


def export_character_pdf_impl(request):
    """Fill the official 5E Character Sheet PDF with active character data."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import BooleanObject, NameObject
        from utils.file_operations import safe_read_json
        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name
        import glob
        import os

        # 1. Determine character
        character_name = request.args.get('character')
        party_tracker = safe_read_json("party_tracker.json") or {}

        if not character_name:
            character_name = party_tracker.get('active_character')

        if not character_name and party_tracker.get('partyMembers') and len(party_tracker['partyMembers']) > 0:
            character_name = party_tracker['partyMembers'][0]

        if not character_name:
            return jsonify({'error': 'No character specified or active'}), 400

        normalized_name = normalize_character_name(character_name)

        # 2. Load character data
        path_manager = ModulePathManager()
        player_file = path_manager.get_character_path(normalized_name)

        if not os.path.exists(player_file):
            return jsonify({'error': f'Character file not found: {normalized_name}'}), 404

        char_data = safe_read_json(player_file)
        if not char_data:
            return jsonify({'error': 'Failed to read character data'}), 500

        # 3. Load template PDF
        template_path = "templates/pdf/5E_CharacterSheet_Fillable.pdf"
        if not os.path.exists(template_path):
            return jsonify({'error': 'Template PDF not found'}), 404

        reader = PdfReader(template_path)
        writer = PdfWriter()
        writer.append(reader)

        # 4. Map NEQ data to PDF field names (MVP: Text fields only)
        def get_mod(score):
            mod = (score - 10) // 2
            return f"+{mod}" if mod >= 0 else str(mod)

        def get_hit_die_type(class_name):
            """Return hit die type based on class (5e standard)."""
            class_lower = class_name.lower() if class_name else ""
            # d6 classes
            if class_lower in ["wizard", "sorcerer"]:
                return 6
            # d8 classes
            elif class_lower in ["bard", "cleric", "druid", "monk", "rogue", "warlock", "thief"]:
                return 8
            # d10 classes
            elif class_lower in ["fighter", "paladin", "ranger"]:
                return 10
            # d12 classes
            elif class_lower in ["barbarian"]:
                return 12
            # Default to d8 for unknown classes
            else:
                return 8

        fields = {
            "CharacterName": char_data.get("name", ""),
            "ClassLevel": f"{char_data.get('class', '')} {char_data.get('level', 1)}",
            "Background": char_data.get("background", "Adventurer"),
            "PlayerName": "",
            "Race ": char_data.get("race", ""),
            "Alignment": char_data.get("alignment", "Neutral").capitalize(),
            "XP": str(char_data.get("experience_points", 0)),

            # Ability Scores
            "STR": str(char_data.get("abilities", {}).get("strength", 10)),
            "DEX": str(char_data.get("abilities", {}).get("dexterity", 10)),
            "CON": str(char_data.get("abilities", {}).get("constitution", 10)),
            "INT": str(char_data.get("abilities", {}).get("intelligence", 10)),
            "WIS": str(char_data.get("abilities", {}).get("wisdom", 10)),
            "CHA": str(char_data.get("abilities", {}).get("charisma", 10)),

            # Ability Modifiers
            "STRmod": get_mod(char_data.get("abilities", {}).get("strength", 10)),
            "DEXmod ": get_mod(char_data.get("abilities", {}).get("dexterity", 10)),
            "CONmod": get_mod(char_data.get("abilities", {}).get("constitution", 10)),
            "INTmod": get_mod(char_data.get("abilities", {}).get("intelligence", 10)),
            "WISmod": get_mod(char_data.get("abilities", {}).get("wisdom", 10)),
            "CHamod": get_mod(char_data.get("abilities", {}).get("charisma", 10)),

            # Combat Stats
            "AC": str(char_data.get("armorClass", 10)),
            "Initiative": f"+{char_data.get('initiative', 0)}" if char_data.get('initiative', 0) >= 0 else str(char_data.get('initiative', 0)),
            "Speed": str(char_data.get("speed", 30)),
            "ProfBonus": f"+{char_data.get('proficiencyBonus', 2)}",
            "HPMax": str(char_data.get("maxHitPoints", 10)),
            "HPCurrent": str(char_data.get("hitPoints", 10)),

            # Hit Dice - determine die type by class (5e standard)
            "HD": str(char_data.get("level", 1)),
            "HDTotal": f"{char_data.get('level', 1)}d{get_hit_die_type(char_data.get('class', ''))}",

            # Currency
            "CP": str(char_data.get("currency", {}).get("copper", 0)),
            "SP": str(char_data.get("currency", {}).get("silver", 0)),
            "GP": str(char_data.get("currency", {}).get("gold", 0)),

            # Text Area Fields
            "PersonalityTraits ": char_data.get("personality_traits", ""),
            "Ideals": char_data.get("ideals", ""),
            "Bonds": char_data.get("bonds", ""),
            "Flaws": char_data.get("flaws", ""),
            "Features and Traits": "\n".join([f"{f['name']}: {f['description']}" for f in char_data.get("classFeatures", [])]),
            "ProficienciesLang": f"LANGUAGES:\n{', '.join(char_data.get('languages', ['Common']))}\n\nARMOR:\n{', '.join(char_data.get('proficiencies', {}).get('armor', []))}\n\nWEAPONS:\n{', '.join(char_data.get('proficiencies', {}).get('weapons', []))}",
        }

        # Split equipment into regular equipment and treasure/miscellaneous
        equipment_items = char_data.get("equipment", [])
        regular_equipment = []
        treasure_items = []

        for item in equipment_items:
            item_type = item.get("item_type", "").lower()

            # Check if it's a miscellaneous item (goes to Treasure)
            is_miscellaneous = (item_type == "miscellaneous")

            item_text = f"{item['item_name']} (x{item.get('quantity', 1)})"

            if is_miscellaneous:
                # Miscellaneous items go to Treasure field
                treasure_items.append(item_text)
            else:
                # All other items (weapon, armor, equipment, consumable, etc.) go to Equipment
                regular_equipment.append(item_text)

        fields["Equipment"] = "\n".join(regular_equipment)
        # Treasure items will be added to page2_fields below

        # Skills
        prof_bonus = char_data.get("proficiencyBonus", 2)
        proficient_skills = char_data.get("skills", [])
        if not isinstance(proficient_skills, list):
            proficient_skills = []

        skill_map = {
            "Acrobatics": "dexterity", "Animal": "wisdom", "Arcana": "intelligence",
            "Athletics": "strength", "Deception ": "charisma", "History ": "intelligence",
            "Insight": "wisdom", "Intimidation": "charisma", "Investigation ": "intelligence",
            "Medicine": "wisdom", "Nature": "intelligence", "Perception ": "wisdom",
            "Performance": "charisma", "Persuasion": "charisma", "Religion": "intelligence",
            "SleightofHand": "dexterity", "Stealth ": "dexterity", "Survival": "wisdom"
        }

        for pdf_field, ability in skill_map.items():
            base_score = char_data.get("abilities", {}).get(ability, 10)
            bonus = (base_score - 10) // 2
            clean_pdf_name = pdf_field.strip()
            neq_name = clean_pdf_name
            if clean_pdf_name == "Animal":
                neq_name = "Animal Handling"
            if clean_pdf_name == "SleightofHand":
                neq_name = "Sleight of Hand"
            if neq_name in proficient_skills:
                bonus += prof_bonus
            fields[pdf_field] = f"+{bonus}" if bonus >= 0 else str(bonus)

        pp_bonus = (char_data.get("abilities", {}).get("wisdom", 10) - 10) // 2
        if "Perception" in proficient_skills:
            pp_bonus += prof_bonus
        fields["Passive"] = str(10 + pp_bonus)

        # Saving Throws
        saving_throw_proficiencies = char_data.get("savingThrows", [])
        if not isinstance(saving_throw_proficiencies, list):
            saving_throw_proficiencies = []

        st_fields = {
            "ST Strength": "strength",
            "ST Dexterity": "dexterity",
            "ST Constitution": "constitution",
            "ST Intelligence": "intelligence",
            "ST Wisdom": "wisdom",
            "ST Charisma": "charisma"
        }

        # Checkbox mapping for saving throw proficiency (Check Box 11-16)
        st_checkbox_map = {
            "strength": "Check Box 11",
            "dexterity": "Check Box 12",
            "constitution": "Check Box 13",
            "intelligence": "Check Box 14",
            "wisdom": "Check Box 15",
            "charisma": "Check Box 16"
        }

        for pdf_field, ability in st_fields.items():
            base_score = char_data.get("abilities", {}).get(ability, 10)
            bonus = (base_score - 10) // 2

            # Check if proficient in this save
            is_proficient = ability in saving_throw_proficiencies
            if is_proficient:
                bonus += prof_bonus
                # Mark proficiency checkbox
                if ability in st_checkbox_map:
                    fields[st_checkbox_map[ability]] = "Yes"

            fields[pdf_field] = f"+{bonus}" if bonus >= 0 else str(bonus)

        # Weapons & Attacks (3 slots)
        attacks = char_data.get("attacksAndSpellcasting", [])
        if isinstance(attacks, list) and len(attacks) > 0:
            # Weapon 1
            if len(attacks) >= 1:
                wpn1 = attacks[0]
                fields["Wpn Name"] = wpn1.get("name", "")
                fields["Wpn1 AtkBonus"] = wpn1.get("attackBonus", "")
                damage_dice = wpn1.get("damageDice", "")
                damage_bonus = wpn1.get("damageBonus", 0)
                if damage_dice:
                    if damage_bonus != 0:
                        fields["Wpn1 Damage"] = f"{damage_dice}+{damage_bonus}"
                    else:
                        fields["Wpn1 Damage"] = damage_dice

            # Weapon 2
            if len(attacks) >= 2:
                wpn2 = attacks[1]
                fields["Wpn Name 2"] = wpn2.get("name", "")
                fields["Wpn2 AtkBonus "] = wpn2.get("attackBonus", "")
                damage_dice = wpn2.get("damageDice", "")
                damage_bonus = wpn2.get("damageBonus", 0)
                if damage_dice:
                    if damage_bonus != 0:
                        fields["Wpn2 Damage "] = f"{damage_dice}+{damage_bonus}"
                    else:
                        fields["Wpn2 Damage "] = damage_dice

            # Weapon 3
            if len(attacks) >= 3:
                wpn3 = attacks[2]
                fields["Wpn Name 3"] = wpn3.get("name", "")
                fields["Wpn3 AtkBonus  "] = wpn3.get("attackBonus", "")
                damage_dice = wpn3.get("damageDice", "")
                damage_bonus = wpn3.get("damageBonus", 0)
                if damage_dice:
                    if damage_bonus != 0:
                        fields["Wpn3 Damage "] = f"{damage_dice}+{damage_bonus}"
                    else:
                        fields["Wpn3 Damage "] = damage_dice

        # AttacksSpellcasting text area
        attacks_spellcasting_lines = []
        spellcasting = char_data.get("spellcasting", {})

        if spellcasting and spellcasting.get("spells"):
            # Character is a spellcaster - list cantrips and prepared spells
            spells_data = spellcasting.get("spells", {})
            prepared_spells = spellcasting.get("preparedSpells", [])

            # Cantrips
            cantrips = spells_data.get("cantrips", [])
            if cantrips:
                attacks_spellcasting_lines.append(f"Cantrips: {', '.join(cantrips)}")

            # Prepared spells by level
            for level in range(1, 10):
                level_key = f"level{level}"
                level_spells = spells_data.get(level_key, [])
                if level_spells:
                    prepared = [spell for spell in level_spells if spell in prepared_spells]
                    if prepared:
                        attacks_spellcasting_lines.append(f"L{level}: {', '.join(prepared)}")

        if attacks and isinstance(attacks, list):
            # Add special attacks for all characters (including non-casters)
            special_attacks = []
            for attack in attacks:
                if isinstance(attack, dict):
                    name = attack.get("name", "")
                    desc = attack.get("description", "")
                    if desc:
                        special_attacks.append(f"- {name}: {desc}")
                    elif attack.get("damageDice"):
                        dmg = attack.get("damageDice")
                        bonus = attack.get("damageBonus", 0)
                        if bonus != 0:
                            special_attacks.append(f"- {name}: {dmg}+{bonus}")
                        else:
                            special_attacks.append(f"- {name}: {dmg}")

            if special_attacks:
                if attacks_spellcasting_lines:
                    attacks_spellcasting_lines.append("")
                attacks_spellcasting_lines.append("Special Attacks:")
                attacks_spellcasting_lines.extend(special_attacks)

        if attacks_spellcasting_lines:
            fields["AttacksSpellcasting"] = "\n".join(attacks_spellcasting_lines)

        # 5. Fill the form
        try:
            if "/AcroForm" in writer.root_object:
                acroform = writer.root_object["/AcroForm"]
                if hasattr(acroform, "get_object"):
                    acroform = acroform.get_object()
                acroform.update({
                    NameObject("/NeedAppearances"): BooleanObject(True)
                })
        except Exception as na_err:
            warning(f"PDF_EXPORT: Could not set NeedAppearances: {na_err}")

        writer.update_page_form_field_values(writer.pages[0], fields)

        # Page 2: Character Description & Features
        if len(writer.pages) > 1:
            page2_fields = {
                "CharacterName 2": char_data.get("name", "")
            }

            # Feat+Traits: Combine racial traits, class features, and feats
            features_list = []

            for trait in char_data.get("racialTraits", []):
                if isinstance(trait, dict):
                    trait_text = f"{trait.get('name', '')}: {trait.get('description', '')}"
                    features_list.append(trait_text)

            for feature in char_data.get("classFeatures", []):
                if isinstance(feature, dict):
                    feature_text = f"{feature.get('name', '')}: {feature.get('description', '')}"
                    features_list.append(feature_text)

            for feat in char_data.get("feats", []):
                if isinstance(feat, dict):
                    feat_text = f"{feat.get('name', '')}: {feat.get('description', '')}"
                    features_list.append(feat_text)

            if features_list:
                page2_fields["Feat+Traits"] = "\n\n".join(features_list)

            # Backstory from background feature + narrative chronicles
            backstory_parts = []

            background_feature = char_data.get("backgroundFeature", {})
            if isinstance(background_feature, dict):
                bg_name = background_feature.get('name', '')
                bg_desc = background_feature.get('description', '')
                if bg_name or bg_desc:
                    backstory_parts.append(f"{bg_name}\n{bg_desc}")

            try:
                summary_files = glob.glob("modules/campaign_summaries/*.json")
                character_name = char_data.get('name', '')

                if summary_files and character_name:
                    summary_files.sort(key=os.path.getmtime, reverse=True)

                    for summary_file in summary_files[:3]:
                        try:
                            summary_data = safe_read_json(summary_file)
                            if summary_data and isinstance(summary_data, dict):
                                summary_text = summary_data.get('summary', '')
                                if character_name.lower() in summary_text.lower():
                                    paragraphs = summary_text.split('\n\n')
                                    for para in paragraphs:
                                        if character_name.lower() in para.lower():
                                            backstory_parts.append(f"\nRecent Adventures:\n{para}")
                                            break
                                    break
                        except Exception:
                            continue
            except Exception:
                pass

            if backstory_parts:
                page2_fields["Backstory"] = "\n\n".join(backstory_parts)

            if treasure_items:
                page2_fields["Treasure"] = "\n".join(treasure_items)

            writer.update_page_form_field_values(writer.pages[1], page2_fields)

        # Page 3: Spellcasting
        if len(writer.pages) > 2:
            page3_fields = {}
            spellcasting = char_data.get("spellcasting", {})

            if spellcasting:
                page3_fields["Spellcasting Class 2"] = char_data.get("class", "")
                page3_fields["SpellcastingAbility 2"] = spellcasting.get("ability", "").capitalize()
                page3_fields["SpellSaveDC  2"] = str(spellcasting.get("spellSaveDC", ""))
                page3_fields["SpellAtkBonus 2"] = f"+{spellcasting.get('spellAttackBonus', 0)}" if spellcasting.get('spellAttackBonus', 0) >= 0 else str(spellcasting.get('spellAttackBonus', 0))

                spell_slots = spellcasting.get("spellSlots", {})
                for level in range(1, 10):
                    slot_key = f"level{level}"
                    if slot_key in spell_slots:
                        slot_data = spell_slots[slot_key]
                        field_num = 18 + level
                        page3_fields[f"SlotsTotal {field_num}"] = str(slot_data.get("max", 0))
                        page3_fields[f"SlotsRemaining {field_num}"] = str(slot_data.get("current", 0))

                spells_data = spellcasting.get("spells", {})
                prepared_spells = spellcasting.get("preparedSpells", [])

                spell_field_mapping = {
                    "cantrips": {
                        "fields": [1014, 1016, 1017, 1018, 1019, 1020, 1021, 1022],
                        "checkboxes": []
                    },
                    "level1": {
                        "fields": [1015, 1023, 1024, 1025, 1026, 1027, 1028, 1029, 1030, 1031, 1032, 1033],
                        "checkboxes": list(range(251, 263))
                    },
                    "level2": {
                        "fields": list(range(1034, 1047)),
                        "checkboxes": list(range(263, 276))
                    },
                    "level3": {
                        "fields": list(range(1047, 1060)),
                        "checkboxes": list(range(276, 289))
                    },
                    "level4": {
                        "fields": list(range(1060, 1073)),
                        "checkboxes": list(range(289, 302))
                    },
                    "level5": {
                        "fields": list(range(1073, 1082)),
                        "checkboxes": list(range(302, 311))
                    },
                    "level6": {
                        "fields": list(range(1082, 1091)),
                        "checkboxes": list(range(311, 320))
                    },
                    "level7": {
                        "fields": list(range(1091, 1100)),
                        "checkboxes": list(range(320, 329))
                    },
                    "level8": {
                        "fields": list(range(10100, 10107)),
                        "checkboxes": list(range(329, 336))
                    },
                    "level9": {
                        "fields": [10107, 10108, 10109, 101010, 101011, 101012, 101013],
                        "checkboxes": list(range(336, 343))
                    }
                }

                if "cantrips" in spells_data:
                    cantrip_fields = spell_field_mapping["cantrips"]["fields"]
                    for i, spell_name in enumerate(spells_data["cantrips"]):
                        if i < len(cantrip_fields):
                            page3_fields[f"Spells {cantrip_fields[i]}"] = spell_name

                for level in range(1, 10):
                    level_key = f"level{level}"
                    mapping_key = f"level{level}"

                    if level_key in spells_data and mapping_key in spell_field_mapping:
                        level_info = spell_field_mapping[mapping_key]
                        spell_fields = level_info["fields"]
                        checkboxes = level_info["checkboxes"]

                        for i, spell_name in enumerate(spells_data[level_key]):
                            if i < len(spell_fields):
                                page3_fields[f"Spells {spell_fields[i]}"] = spell_name
                                if spell_name in prepared_spells and i < len(checkboxes):
                                    page3_fields[f"Check Box {checkboxes[i]}"] = "Yes"

            writer.update_page_form_field_values(writer.pages[2], page3_fields)

        # 6. Stream back the PDF
        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        filename = f"{normalized_name}_CharacterSheet.pdf"
        return send_file(
            output_stream,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )

    except Exception as route_error:
        error(f"PDF_EXPORT: Failed to generate character sheet PDF: {route_error}")
        import traceback

        traceback.print_exc()
        return jsonify({'error': str(route_error)}), 500
