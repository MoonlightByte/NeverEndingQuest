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
import os
import threading
import time
from typing import Any, Dict, Tuple

from flask import current_app, jsonify, send_file

from utils.character_creation_audit import (
    AUDIT_RESULT_SUCCESS,
    READINESS_REPAIR_WRITABLE_FIELDS,
    apply_readiness_repair_patch,
    audit_character_creation,
    audit_character_readiness,
    build_readiness_repair_proposal,
    diff_mechanical_snapshot,
    get_mechanical_snapshot,
    sanitize_readiness_repair_patch,
)
from utils.enhanced_logger import error, info, warning
from utils.saving_throw_utils import get_effective_saving_throw_proficiencies


READINESS_REPAIR_COOLDOWN_SECONDS = 15
_repair_cooldown_state: Dict[str, float] = {}
_repair_cooldown_lock = threading.Lock()


# TABLETOP MODE: Character appearance portrait target on page index 1.
CHARACTER_APPEARANCE_PAGE_INDEX = 1
DEFAULT_CHARACTER_IMAGE_RECT = (36.4791, 443.398, 199.172, 661.497)
PDF_EXPORT_TEXT_FONT_SIZE = 8
PDF_EXPORT_FONT10_FIELDS = (
    "PersonalityTraits ",  # NOTE: trailing space is intentional (PDF field name)
    "Ideals",
    "Bonds",
    "Flaws",
    "AttacksSpellcasting",
    "Wpn Name",
    "Wpn1 AtkBonus",
    "Wpn1 Damage",
    "Wpn Name 2",
    "Wpn2 AtkBonus ",  # NOTE: trailing space is intentional
    "Wpn2 Damage ",  # NOTE: trailing space is intentional
    "Wpn Name 3",
    "Wpn3 AtkBonus  ",  # NOTE: two trailing spaces are intentional
    "Wpn3 Damage ",  # NOTE: trailing space is intentional
    "Equipment",
    "Features and Traits",
    "ProficienciesLang",
    "Feat+Traits",  # Additional Features and Traits (page index 1)
    "Allies",  # Allies and Organizations (page index 1)
    "Backstory",
    "Treasure",
)


def _normalize_requested_character(request: Any) -> Tuple[str, str]:
    """Resolve raw and normalized character names from request payload."""
    from updates.update_character_info import normalize_character_name

    request_data = request.get_json(silent=True) or {}
    raw_name = str(
        request_data.get("character")
        or request_data.get("character_name")
        or request.args.get("character")
        or ""
    ).strip()
    return raw_name, normalize_character_name(raw_name) if raw_name else ""


def _load_character_payload(normalized_name: str) -> Tuple[Dict[str, Any], str]:
    """Load character JSON and its path by normalized name."""
    import os
    from utils.file_operations import safe_read_json
    from utils.module_path_manager import ModulePathManager

    path_manager = ModulePathManager()
    character_path = path_manager.get_character_path(normalized_name)
    if not os.path.exists(character_path):
        return {}, character_path

    data = safe_read_json(character_path)
    if not isinstance(data, dict):
        return {}, character_path
    return data, character_path


def _check_repair_cooldown(action: str, normalized_name: str) -> Tuple[bool, int]:
    """Return (is_limited, retry_after_seconds)."""
    now = time.time()
    cooldown_key = f"{action}:{normalized_name}"
    with _repair_cooldown_lock:
        last_at = _repair_cooldown_state.get(cooldown_key, 0.0)
        elapsed = now - last_at
        if elapsed < READINESS_REPAIR_COOLDOWN_SECONDS:
            retry_after = int(READINESS_REPAIR_COOLDOWN_SECONDS - elapsed) + 1
            return True, retry_after

        _repair_cooldown_state[cooldown_key] = now
        return False, 0


def _format_repair_preview(character_data: Dict[str, Any], updates: Dict[str, str]) -> Dict[str, Any]:
    """Build field-by-field preview object for UI modal."""
    def get_nested_value(data: Dict[str, Any], path: str) -> Any:
        current: Any = data
        for key in path.split("."):
            if not isinstance(current, dict) or key not in current:
                return None
            current = current[key]
        return current

    preview_rows = []
    for field_path in READINESS_REPAIR_WRITABLE_FIELDS:
        if field_path not in updates:
            continue
        before_value = get_nested_value(character_data, field_path)
        preview_rows.append(
            {
                "field": field_path,
                "before": str(before_value or "").strip(),
                "after": updates[field_path],
            }
        )

    return {
        "proposed_updates": preview_rows,
        "updates": updates,
    }


def _resolve_character_portrait_path(normalized_name: str, party_tracker: Dict[str, Any]) -> str:
    """Resolve the best available portrait image path for a character."""
    candidate_paths = []
    image_exts = ("png", "jpg", "jpeg", "webp")

    # Primary static portrait location.
    for ext in image_exts:
        candidate_paths.append(os.path.join("web", "static", "portraits", f"{normalized_name}.{ext}"))

    # Module portrait location for save portability.
    module_name = str((party_tracker or {}).get("module", "")).replace(" ", "_").strip()
    if module_name:
        module_portraits_dir = os.path.join("modules", module_name, "portraits")
        for ext in image_exts:
            candidate_paths.append(os.path.join(module_portraits_dir, f"{normalized_name}.{ext}"))

        # TABLETOP MODE: NPC media fallback for promoted NPC->PC characters.
        # Module media should win over static media.
        module_npc_media_dir = os.path.join("modules", module_name, "media", "npcs")
        candidate_paths.append(os.path.join(module_npc_media_dir, f"{normalized_name}_thumb.jpg"))
        for ext in image_exts:
            candidate_paths.append(os.path.join(module_npc_media_dir, f"{normalized_name}.{ext}"))

    # Static NPC media fallback (for pack/global media).
    static_npc_media_dir = os.path.join("web", "static", "media", "npcs")
    candidate_paths.append(os.path.join(static_npc_media_dir, f"{normalized_name}_thumb.jpg"))
    for ext in image_exts:
        candidate_paths.append(os.path.join(static_npc_media_dir, f"{normalized_name}.{ext}"))

    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return ""


def _get_character_image_rect(reader: Any) -> Tuple[float, float, float, float]:
    """Read the CHARACTER IMAGE widget rectangle from PDF template fields."""
    try:
        fields = reader.get_fields() or {}
        image_field = fields.get("CHARACTER IMAGE", {})

        kids = image_field.get("/Kids", []) if isinstance(image_field, dict) else []
        if kids:
            first_kid = kids[0].get_object() if hasattr(kids[0], "get_object") else kids[0]
            rect = first_kid.get("/Rect") if isinstance(first_kid, dict) else None
            if isinstance(rect, (list, tuple)) and len(rect) == 4:
                return float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])

        rect = image_field.get("/Rect") if isinstance(image_field, dict) else None
        if isinstance(rect, (list, tuple)) and len(rect) == 4:
            return float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
    except Exception:
        pass

    return DEFAULT_CHARACTER_IMAGE_RECT


def _embed_character_portrait(
    writer: Any,
    portrait_path: str,
    page_index: int,
    image_rect: Tuple[float, float, float, float],
) -> bool:
    """Embed a portrait image into the specified rectangle on a PDF page."""
    if not portrait_path or page_index < 0 or page_index >= len(writer.pages):
        return False

    try:
        from PIL import Image, ImageOps
        from pypdf import PdfReader, Transformation

        x0, y0, x1, y1 = image_rect
        width = max(1, int(round(abs(x1 - x0))))
        height = max(1, int(round(abs(y1 - y0))))
        min_x = min(float(x0), float(x1))
        min_y = min(float(y0), float(y1))

        with Image.open(portrait_path) as source_image:
            fitted_image = ImageOps.fit(
                source_image.convert("RGB"),
                (width, height),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )

            overlay_stream = io.BytesIO()
            fitted_image.save(overlay_stream, format="PDF", resolution=72.0)

        overlay_stream.seek(0)
        overlay_reader = PdfReader(overlay_stream)
        overlay_page = overlay_reader.pages[0]

        target_page = writer.pages[page_index]
        transform = Transformation().translate(tx=min_x, ty=min_y)
        target_page.merge_transformed_page(overlay_page, transform, over=True)
        return True
    except Exception:
        return False


def _should_emit_pdf_debug_headers() -> bool:
    """Return True when running in debug/testing mode."""
    try:
        return bool(current_app.debug or current_app.testing)
    except Exception:
        return False


def _set_pdf_widget_font_size(
    writer: Any,
    target_field_names: Tuple[str, ...],
    font_size: int = PDF_EXPORT_TEXT_FONT_SIZE,
) -> int:
    """Set widget /DA font size for selected text fields (fail-open)."""
    try:
        from pypdf.generic import NameObject, TextStringObject
    except Exception:
        return 0

    updated_count = 0
    target_names = set(target_field_names)
    da_value = TextStringObject(f"/Helvetica {int(font_size)} Tf 0 g")

    for page in writer.pages:
        annotations = page.get("/Annots") or []
        for annotation_ref in annotations:
            try:
                annotation = (
                    annotation_ref.get_object()
                    if hasattr(annotation_ref, "get_object")
                    else annotation_ref
                )
                if not isinstance(annotation, dict):
                    continue
                if annotation.get("/Subtype") != "/Widget":
                    continue

                parent = None
                parent_ref = annotation.get("/Parent")
                if parent_ref and hasattr(parent_ref, "get_object"):
                    parent_obj = parent_ref.get_object()
                    if isinstance(parent_obj, dict):
                        parent = parent_obj

                field_name = annotation.get("/T")
                if field_name is None and parent is not None:
                    field_name = parent.get("/T")
                if field_name not in target_names:
                    continue

                field_type = annotation.get("/FT")
                if field_type is None and parent is not None:
                    field_type = parent.get("/FT")
                if field_type != "/Tx":
                    continue

                annotation[NameObject("/DA")] = da_value
                if parent is not None:
                    parent[NameObject("/DA")] = da_value
                updated_count += 1
            except Exception:
                continue

    return updated_count


def export_character_pdf_impl(request):
    """Fill the official 5E Character Sheet PDF with active character data."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import BooleanObject, NameObject
        from utils.file_operations import safe_read_json
        from utils.module_path_manager import ModulePathManager
        from updates.update_character_info import normalize_character_name
        import glob

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

        # TABLETOP MODE: Non-fatal readiness audit visibility for legacy sheets.
        readiness = audit_character_readiness(char_data)
        readiness_warnings = readiness.get("warnings", []) if isinstance(readiness, dict) else []
        if readiness_warnings:
            warning(
                f"PDF_EXPORT: Readiness audit warnings for {normalized_name}: {'; '.join(readiness_warnings[:5])}",
                category="character_creation",
            )

        # 3. Load template PDF
        template_path = "templates/pdf/5E_CharacterSheet_Fillable.pdf"
        if not os.path.exists(template_path):
            return jsonify({'error': 'Template PDF not found'}), 404

        reader = PdfReader(template_path)
        writer = PdfWriter()
        writer.append(reader)

        # TABLETOP MODE: Reduce selected text field font size to prevent clipping.
        font_updates = _set_pdf_widget_font_size(
            writer=writer,
            target_field_names=PDF_EXPORT_FONT10_FIELDS,
            font_size=PDF_EXPORT_TEXT_FONT_SIZE,
        )
        info(
            f"PDF_EXPORT: Applied {PDF_EXPORT_TEXT_FONT_SIZE}pt font to {font_updates} targeted fields",
            category="character_creation",
        )

        portrait_path = _resolve_character_portrait_path(normalized_name, party_tracker)
        portrait_embed_status = "not_attempted"
        image_rect = _get_character_image_rect(reader)

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
        saving_throw_proficiencies = get_effective_saving_throw_proficiencies(
            char_data.get("savingThrows", []),
            char_data.get("class", ""),
        )

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
                if isinstance(acroform, dict):
                    acroform[NameObject("/NeedAppearances")] = BooleanObject(True)
        except Exception as na_err:
            warning(f"PDF_EXPORT: Could not set NeedAppearances: {na_err}")

        writer.update_page_form_field_values(writer.pages[0], fields)

        # Page 2: Character Description & Features
        if len(writer.pages) > 1:
            page2_fields = {
                "CharacterName 2": char_data.get("name", "")
            }

            # Physical traits (page 2 appearance box fields)
            page2_fields["Age"] = str(char_data.get("age", "") or "").strip()
            page2_fields["Height"] = str(char_data.get("height", "") or "").strip()
            page2_fields["Weight"] = str(char_data.get("weight", "") or "").strip()
            page2_fields["Eyes"] = str(char_data.get("eyes", "") or "").strip()
            page2_fields["Skin"] = str(char_data.get("skin", "") or "").strip()
            page2_fields["Hair"] = str(char_data.get("hair", "") or "").strip()

            # Feat+Traits: Combine background feature, racial traits, class features, and feats
            features_list = []

            # Background feature first
            background_feature = char_data.get("backgroundFeature", {})
            if isinstance(background_feature, dict):
                bg_name = background_feature.get('name', '')
                bg_desc = background_feature.get('description', '')
                if bg_name or bg_desc:
                    features_list.append(f"{bg_name}: {bg_desc}")

            # Racial traits
            for trait in char_data.get("racialTraits", []):
                if isinstance(trait, dict):
                    trait_text = f"{trait.get('name', '')}: {trait.get('description', '')}"
                    features_list.append(trait_text)

            # Class features
            for feature in char_data.get("classFeatures", []):
                if isinstance(feature, dict):
                    feature_text = f"{feature.get('name', '')}: {feature.get('description', '')}"
                    features_list.append(feature_text)

            # Feats
            for feat in char_data.get("feats", []):
                if isinstance(feat, dict):
                    feat_text = f"{feat.get('name', '')}: {feat.get('description', '')}"
                    features_list.append(feat_text)

            if features_list:
                page2_fields["Feat+Traits"] = "\n\n".join(features_list)

            # Backstory from authored backstory + optional narrative chronicles
            backstory_parts = []
            
            # Primary: authored backstory
            authored_backstory = char_data.get('backstory', '')
            if authored_backstory and isinstance(authored_backstory, str):
                backstory_parts.append(authored_backstory)
            
            # Optional: recent adventures from campaign summaries
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
                                            backstory_parts.append(f"Recent Adventures:\n{para}")
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

            # TABLETOP MODE: Embed PC portrait in appearance box on page index 1.
            if portrait_path:
                embedded = _embed_character_portrait(
                    writer=writer,
                    portrait_path=portrait_path,
                    page_index=CHARACTER_APPEARANCE_PAGE_INDEX,
                    image_rect=image_rect,
                )
                if embedded:
                    portrait_embed_status = "embedded"
                    info(
                        f"PDF_EXPORT: Embedded portrait for {normalized_name} from {portrait_path}",
                        category="character_creation",
                    )
                else:
                    portrait_embed_status = "embed_failed"
                    warning(
                        f"PDF_EXPORT: Portrait embedding failed for {normalized_name} ({portrait_path})",
                        category="character_creation",
                    )
            else:
                portrait_embed_status = "missing_source"
        else:
            portrait_embed_status = "missing_page"

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
        response = send_file(
            output_stream,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename,
        )
        if _should_emit_pdf_debug_headers():
            response.headers["X-Debug-Portrait-Source"] = portrait_path or "none"
            response.headers["X-Debug-Portrait-Status"] = portrait_embed_status
        if readiness_warnings:
            response.headers["X-Character-Readiness-Warnings"] = " | ".join(readiness_warnings[:3])
        return response

    except Exception as route_error:
        error(f"PDF_EXPORT: Failed to generate character sheet PDF: {route_error}")
        import traceback

        traceback.print_exc()
        return jsonify({'error': str(route_error)}), 500


def readiness_repair_preview_impl(request):
    """Preview narrative-only character readiness repairs without saving."""
    try:
        raw_name, normalized_name = _normalize_requested_character(request)
        if not normalized_name:
            return jsonify({"success": False, "error": "Missing character name"}), 400

        is_limited, retry_after = _check_repair_cooldown("preview", normalized_name)
        if is_limited:
            info(
                f"READINESS_REPAIR action=preview character={normalized_name} outcome=cooldown retry_after={retry_after}",
                category="character_creation",
            )
            return jsonify(
                {
                    "success": False,
                    "rate_limited": True,
                    "retry_after_seconds": retry_after,
                    "error": "Repair preview is on cooldown for this character",
                }
            ), 429

        character_data, character_path = _load_character_payload(normalized_name)
        if not character_data:
            return jsonify({"success": False, "error": f"Character not found: {normalized_name}"}), 404

        audit_result = audit_character_creation(
            character_data,
            source="readiness_repair_preview",
            enable_enrichment=False,
        )
        if audit_result.result_type == AUDIT_RESULT_SUCCESS:
            info(
                f"READINESS_REPAIR action=preview character={normalized_name} outcome=already_ready warnings=0",
                category="character_creation",
            )
            return jsonify(
                {
                    "success": True,
                    "ready": True,
                    "character": raw_name or normalized_name,
                    "warnings": [],
                    "missing_fields": [],
                    "proposed_updates": [],
                    "updates": {},
                    "character_path": character_path,
                }
            )

        missing_fields = [path for path in audit_result.missing_paths if path in READINESS_REPAIR_WRITABLE_FIELDS]
        proposal = build_readiness_repair_proposal(character_data, missing_fields)
        updates = sanitize_readiness_repair_patch(proposal)
        preview = _format_repair_preview(character_data, updates)

        info(
            (
                f"READINESS_REPAIR action=preview character={normalized_name} "
                f"outcome=ok warnings={len(audit_result.errors)} updates={len(updates)} source={proposal.get('source', 'unknown')}"
            ),
            category="character_creation",
        )
        return jsonify(
            {
                "success": True,
                "ready": False,
                "character": raw_name or normalized_name,
                "result_type": audit_result.result_type,
                "warnings": [f"{entry['path']}: {entry['message']}" for entry in audit_result.errors],
                "missing_fields": missing_fields,
                "proposal_source": proposal.get("source", "fallback"),
                **preview,
                "character_path": character_path,
            }
        )
    except Exception as route_error:
        error(
            f"READINESS_REPAIR action=preview outcome=error detail={route_error}",
            exception=route_error,
            category="character_creation",
        )
        return jsonify({"success": False, "error": "Failed to generate repair preview"}), 500


def readiness_repair_apply_impl(request):
    """Apply narrative-only character readiness repairs after explicit confirm."""
    try:
        from utils.file_operations import safe_write_json

        raw_name, normalized_name = _normalize_requested_character(request)
        if not normalized_name:
            return jsonify({"success": False, "error": "Missing character name"}), 400

        is_limited, retry_after = _check_repair_cooldown("apply", normalized_name)
        if is_limited:
            info(
                f"READINESS_REPAIR action=apply character={normalized_name} outcome=cooldown retry_after={retry_after}",
                category="character_creation",
            )
            return jsonify(
                {
                    "success": False,
                    "rate_limited": True,
                    "retry_after_seconds": retry_after,
                    "error": "Repair apply is on cooldown for this character",
                }
            ), 429

        character_data, character_path = _load_character_payload(normalized_name)
        if not character_data:
            return jsonify({"success": False, "error": f"Character not found: {normalized_name}"}), 404

        request_data = request.get_json(silent=True) or {}
        request_updates = request_data.get("updates", {})
        sanitized_request_updates = sanitize_readiness_repair_patch({"updates": request_updates})

        before_snapshot = get_mechanical_snapshot(character_data)

        audit_before = audit_character_creation(
            character_data,
            source="readiness_repair_apply_pre",
            enable_enrichment=False,
        )
        missing_fields = [path for path in audit_before.missing_paths if path in READINESS_REPAIR_WRITABLE_FIELDS]

        if audit_before.result_type == AUDIT_RESULT_SUCCESS and not sanitized_request_updates:
            return jsonify(
                {
                    "success": True,
                    "ready": True,
                    "character": raw_name or normalized_name,
                    "warnings": [],
                    "updated_fields": [],
                }
            )

        if sanitized_request_updates:
            updates = sanitized_request_updates
            proposal_source = "client"
        else:
            proposal = build_readiness_repair_proposal(character_data, missing_fields)
            updates = sanitize_readiness_repair_patch(proposal)
            proposal_source = proposal.get("source", "fallback")

        if not updates:
            return jsonify(
                {
                    "success": False,
                    "error": "No valid repair updates were produced",
                    "missing_fields": missing_fields,
                }
            ), 400

        patched_data = apply_readiness_repair_patch(character_data, updates)
        after_snapshot = get_mechanical_snapshot(patched_data)
        changed_mechanics = diff_mechanical_snapshot(before_snapshot, after_snapshot)
        if changed_mechanics:
            warning(
                (
                    f"READINESS_REPAIR action=apply character={normalized_name} outcome=blocked "
                    f"mechanical_changes={','.join(changed_mechanics)}"
                ),
                category="character_creation",
            )
            return jsonify(
                {
                    "success": False,
                    "error": "Repair was blocked because mechanical fields changed",
                    "changed_mechanical_fields": changed_mechanics,
                }
            ), 400

        audit_after = audit_character_creation(
            patched_data,
            source="readiness_repair_apply_post",
            enable_enrichment=False,
        )
        if audit_after.result_type != AUDIT_RESULT_SUCCESS:
            warning(
                (
                    f"READINESS_REPAIR action=apply character={normalized_name} outcome=audit_block "
                    f"errors={len(audit_after.errors)}"
                ),
                category="character_creation",
            )
            return jsonify(
                {
                    "success": False,
                    "error": "Patched character failed readiness audit",
                    "result_type": audit_after.result_type,
                    "errors": audit_after.errors,
                }
            ), 400

        if not safe_write_json(character_path, patched_data):
            return jsonify({"success": False, "error": "Failed to save repaired character"}), 500

        readiness = audit_character_readiness(patched_data)
        info(
            (
                f"READINESS_REPAIR action=apply character={normalized_name} outcome=saved "
                f"updated={len(updates)} source={proposal_source} warnings_after={len(readiness.get('warnings', []))}"
            ),
            category="character_creation",
        )
        return jsonify(
            {
                "success": True,
                "character": raw_name or normalized_name,
                "updated_fields": sorted(list(updates.keys())),
                "proposal_source": proposal_source,
                "readiness": readiness,
            }
        )
    except Exception as route_error:
        error(
            f"READINESS_REPAIR action=apply outcome=error detail={route_error}",
            exception=route_error,
            category="character_creation",
        )
        return jsonify({"success": False, "error": "Failed to apply repair"}), 500
