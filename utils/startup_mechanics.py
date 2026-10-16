"""Deterministic startup equipment checks.

Starting armorClass is the engine's (utils.startup_wizard.startup_mechanics ->
nql.armor_class.project, #531); this module does not derive it a second time
(#855). It refuses a sheet whose equipped armor the engine cannot model, so the
engine sets every starting armorClass. These checks never invent choices or
modify an approved sheet.
"""
from core.nql.armor_class import unmodelled_armor

VEHICLE_PROFICIENCIES = ('land vehicles', 'water vehicles')


def validate_startup_mechanics(sheet):
    unmodelled = unmodelled_armor(sheet)
    if unmodelled:
        return False, ('Equipped armor %s is not armor the rules engine can model, so it cannot set '
                       'armorClass. Name each exactly as its catalog armor (for example Studded Leather '
                       'Armor or Plate Armor), or give the row its ac_base and armor_category. Keep the '
                       'player choices.' % ', '.join(unmodelled))
    for item in sheet.get('equipment', []) or []:
        if not isinstance(item, dict):
            continue
        # A proficiency category is never an owned item, whatever its description.
        if str(item.get('item_name', '')).strip().lower() in VEHICLE_PROFICIENCIES:
            return False, ('Vehicle proficiency belongs in proficiencies, not as an owned '
                           'inventory item. Preserve the proficiency without inventing a vehicle.')
    return True, None
