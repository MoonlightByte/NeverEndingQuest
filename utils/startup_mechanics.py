"""Conservative deterministic checks for ordinary starting armor and equipment.

Unknown/magical armor combinations remain the rules reviewer's responsibility;
these checks never invent choices or modify an approved sheet.
"""
import re

ARMOR = {
    'padded': (11, None), 'leather': (11, None), 'studded leather': (12, None),
    'hide': (12, 2), 'chain shirt': (13, 2), 'scale mail': (14, 2),
    'breastplate': (14, 2), 'half plate': (15, 2),
    'ring mail': (14, 0), 'chain mail': (16, 0), 'splint': (17, 0), 'plate': (18, 0),
}


def ordinary_starting_ac(sheet):
    equipment = sheet.get('equipment', [])
    if not isinstance(equipment, list):
        return None
    # Avoid double-applying magical, feat, racial or temporary AC rules.
    if any(sheet.get(k) for k in ('feats', 'temporaryEffects', 'equipment_effects')):
        return None
    for trait in sheet.get('racialTraits', []) or []:
        text = str(trait).lower()
        if any(word in text for word in ('armor class', 'natural armor', 'carapace')):
            return None
    worn, shields = [], 0
    for item in equipment:
        if not isinstance(item, dict) or item.get('equipped') is not True:
            continue
        name = str(item.get('item_name', '')).lower().strip()
        if item.get('magical') or item.get('effects') or re.search(r'\+\d', name):
            return None
        category = str(item.get('armor_category', '')).lower()
        if name == 'shield':
            shields += 1
        elif name in ARMOR:
            worn.append(ARMOR[name])
        elif category or str(item.get('item_type', '')).lower() == 'armor':
            return None
    if len(worn) != 1 or shields > 1:
        return None
    dex = sheet.get('abilities', {}).get('dexterity')
    if type(dex) is not int:
        return None
    base, cap = worn[0]
    modifier = (dex - 10) // 2
    ac = base + (modifier if cap is None else 0 if cap == 0 else min(modifier, cap)) + 2 * shields
    for feature in sheet.get('classFeatures', []) or []:
        name = str(feature.get('name', '') if isinstance(feature, dict) else feature).lower()
        if name.strip() in ('fighting style: defense', 'defense fighting style'):
            ac += 1
            break
    return ac


def validate_startup_mechanics(sheet):
    expected = ordinary_starting_ac(sheet)
    if expected is not None and sheet.get('armorClass') != expected:
        return False, ('Starting armorClass must be %s for the equipped armor, shield '
                       'and Defense fighting style, not %s. Keep the player choices; '
                       'correct and review the combat total.' % (expected, sheet.get('armorClass')))
    for item in sheet.get('equipment', []) or []:
        if not isinstance(item, dict):
            continue
        if (str(item.get('item_name', '')).strip().lower() in ('land vehicles', 'water vehicles')
                and 'proficien' in str(item.get('description', '')).lower()):
            return False, ('Vehicle proficiency belongs in proficiencies, not as an owned '
                           'inventory item. Preserve the proficiency without inventing a vehicle.')
    return True, None
