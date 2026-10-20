#!/usr/bin/env python3
"""
character_sheet_compressor.py
Compresses D&D 5e character JSON to dense key-value format for AI token optimization.

Features:
- 88% size reduction (33KB JSON -> 4KB flatlist)
- Preserves ability usage counters (e.g., ChannelDivinity:2/rest(2/2))
- Maintains weapon/armor bonuses (+1, +2, etc.)
- Deduplicates data already in DM Note (HP, XP, spell slots)
- Normalizes spell/feature names for consistency
- Schema-tolerant: handles various character JSON formats

Usage:
  python3 core/ai/character_sheet_compressor.py --char path/to/character.json
"""

import json, re, argparse
from typing import Any, Dict, List

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')

def compact(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s)).strip()

def describe_text(s) -> str:
    """Whole description text, single line: whitespace collapsed and ';' -> ','.

    No slice, no cap (D-242-D). Non-string or missing values render empty.
    """
    if s is None or isinstance(s, (bool, list, dict)):
        return ''
    return compact(str(s)).replace(';', ',')

def squeeze_name(name: str) -> str:
    """Blessing of the Silent King -> BlessingSilentKing"""
    n = re.sub(r'\bof the\b', '', name, flags=re.IGNORECASE)
    n = re.sub(r'\bof\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+', '', n).strip()
    return n

def normalize_feat(name: str) -> str:
    """A feature's name squeezed, with what its parentheses hold kept as written
    (spaces removed): "Divine Order (Protector)" -> "DivineOrder:Protector".
    No word in the name decides what is shown."""
    inner = [x.strip().replace(' ', '') for x in re.findall(r'\(([^)]*)\)', name)]
    inner = [x for x in inner if x]
    if inner:
        base = squeeze_name(re.sub(r'\s*\([^)]*\)', '', name).strip())
        return f"{base}:{','.join(inner)}"
    return squeeze_name(name)

def normalize_attack(name: str, kind: str, dmg_die: str, dmg_type: str, atk_bonus: int = None, dmg_bonus: int = None) -> str:
    # Remove apostrophes and special chars, then StudlyCaps
    nm = re.sub(r"[''']s?", '', name)  # Remove apostrophes and possessives
    nm = re.sub(r'[^A-Za-z0-9]+', ' ', nm)
    # StudlyCaps: capitalize each word
    nm = ''.join(w.capitalize() for w in nm.split())
    kind = kind.lower()
    dmg = (dmg_die or '').lower().replace(' ', '')
    dtype = (dmg_type or '').lower().replace(' ', '')
    
    # Add bonuses if present
    result = f"{nm}:{kind}:{dmg}{dtype}"
    if atk_bonus is not None and atk_bonus != 0:
        result += f":+{atk_bonus}" if atk_bonus > 0 else f":{atk_bonus}"
    if dmg_bonus is not None and dmg_bonus != 0:
        result += f"/+{dmg_bonus}" if dmg_bonus > 0 else f"/{dmg_bonus}"
    return result

def get_list(d: Dict[str, Any], *keys) -> List[Any]:
    for k in keys:
        if isinstance(d.get(k), list):
            return d[k]
    return []

def get_dict(d: Dict[str, Any], *keys) -> Dict[str, Any]:
    for k in keys:
        if isinstance(d.get(k), dict):
            return d[k]
    return {}

def format_flatlist(character: Dict[str, Any]) -> str:
    try:
        from core.effects.effective import effective_sheet
        character = effective_sheet(character)
    except Exception:
        pass
    # Basic header
    name = character.get('name') or 'Unknown'
    lvl  = character.get('level') or 1
    race = character.get('race') or 'Unknown'
    cls  = character.get('class') or 'Unknown'
    align= character.get('alignment') or 'NE'
    # Convert alignment to shorthand
    align_map = {
        'lawful good': 'LG', 'neutral good': 'NG', 'chaotic good': 'CG',
        'lawful neutral': 'LN', 'true neutral': 'N', 'chaotic neutral': 'CN', 
        'lawful evil': 'LE', 'neutral evil': 'NE', 'chaotic evil': 'CE'
    }
    align = align_map.get(align.lower(), align.upper()[:2] if len(align) > 2 else align)
    bg   = character.get('background') or 'Unknown'
    ac   = character.get('armorClass') or 10
    spd  = character.get('speed') or 30
    status = character.get('status') or 'alive'
    condition = character.get('condition') or 'none'
    affected  = ','.join(str(c) for c in character.get('condition_affected') or []) if isinstance(character.get('condition_affected'), list) else ''

    # Stats
    abilities = get_dict(character, 'abilities', 'STATS', 'stats')
    STR = abilities.get('strength') or abilities.get('STR') or 10
    DEX = abilities.get('dexterity') or abilities.get('DEX') or 10
    CON = abilities.get('constitution') or abilities.get('CON') or 10
    INT = abilities.get('intelligence') or abilities.get('INT') or 10
    WIS = abilities.get('wisdom') or abilities.get('WIS') or 10
    CHA = abilities.get('charisma') or abilities.get('CHA') or 10

    # Saves
    saves = character.get('savingThrows') or []
    m = {'strength':'str','dexterity':'dex','constitution':'con',
         'intelligence':'int','wisdom':'wis','charisma':'cha'}
    saves_out = ','.join(m.get(x.lower(), x[:3].lower()) for x in saves)
    save_totals = character.get('savingThrowBonuses')
    if isinstance(save_totals, dict) and save_totals:  # engine totals; proficient abilities stay listed
        saves_out = ','.join(f"{m.get(a, a[:3])}:{v:+d}" for a, v in save_totals.items()) + (f"(prof:{saves_out})" if saves_out else '')
    roll_modes = character.get('rollModes')
    modes_out = (' MODES(engine applies at the roll prompt; never pass as mode)={' + ','.join(f'{k}:{v}' for k, v in roll_modes.items()) + '};') if isinstance(roll_modes, dict) and roll_modes else ''

    # Skills: the engine's bonuses from a dict; a legacy list names the
    # proficient skills with no number. No arithmetic and no defaults here:
    # proficiency, initiative and passive perception are engine-written
    # (core/nql/stats) and print as stored.
    # Full skill names: a three-letter cut folded Perception, Persuasion and
    # Performance into one 'per' key (#553).
    skills_field = character.get('skills')
    if isinstance(skills_field, dict):
        skills_out = ','.join(f"{k}:{v}" for k,v in skills_field.items())
    elif isinstance(skills_field, list):
        skills_out = ','.join(str(k).lower() for k in skills_field)
    else:
        skills_out = ''

    # Proficiency bonus / Senses
    prof_bonus = character.get('proficiencyBonus')
    initiative = character.get('initiative')
    senses = get_dict(character, 'senses', 'SENSES')
    darkv = senses.get('darkvision') or 0
    pp = senses.get('passivePerception')
    expertise = character.get('expertise')
    expertise_out = ','.join(str(k).lower() for k in expertise) if isinstance(expertise, list) else ''

    langs = character.get('languages') or []
    langs_out = ','.join(langs) if isinstance(langs, list) else str(langs)

    # Proficiencies
    profs = get_dict(character, 'proficiencies', 'PROF')
    armor = profs.get('armor') or []
    weapons = profs.get('weapons') or []
    tools = profs.get('tools') or []
    # Normalize tool names  
    tools_norm = []
    for t in tools:
        t = t.replace('gaming set', 'gaming-set')
        t = re.sub(r'vehicles\s*\(([^)]*)\)', r'vehicles:\1', t)
        tools_norm.append(t)
    prof_out = f"armor:{','.join(armor)}; weapons:{','.join(weapons)}; tools:{','.join(tools_norm)}"

    # VULN/RES/IMM/COND_IMM
    vuln = character.get('vulnerabilities') or ''
    res  = character.get('damageResistances') or []
    # Each resistance as the sheet holds it (deduplicated), never merged or reworded
    res_clean = set()
    for r in res:
        value = compact(r).lower().replace(' ', '_')
        if value:
            res_clean.add(value)
    res_out = ','.join(sorted(res_clean))
    cimm= character.get('conditionImmunities') or []
    cimm_out = ','.join(c.lower() for c in cimm)

    # Features - now with usage tracking
    class_feats = get_list(character, 'classFeatures')
    cf_norm = []
    for feat in class_feats:
        if isinstance(feat, dict):
            feat_name = feat.get('name', '')
            usage = feat.get('usage') or {}
            current = usage.get('current')
            max_uses = usage.get('max')
            
            # For abilities with usage, add (current/max) after the name
            if current is not None and max_uses is not None:
                # First normalize the base name (keeping things like 2/rest)
                base_norm = normalize_feat(feat_name)
                # Then add the usage counter
                cf_norm.append(f"{base_norm}({current}/{max_uses})")
            else:
                cf_norm.append(normalize_feat(feat_name))
        else:
            cf_norm.append(normalize_feat(feat))
    classfeat_out = ','.join(cf_norm)

    # Feats (D-242-D, ruling 5): every feat with its whole description, so the
    # DM can choose a rescue from what the sheet actually holds. Complete list,
    # no cap, no filtering; whitespace collapsed and ';' -> ',' only so the
    # one-line-per-key shape survives. Never normalize_feat (it strips text).
    feats_out_parts: List[str] = []
    for feat in get_list(character, 'feats'):
        if isinstance(feat, dict):
            feat_name = compact(feat.get('name') or '')
            feat_desc = describe_text(feat.get('description'))
            if feat.get('grantedSpells'):
                feat_desc += ' grantedSpells=' + json.dumps(feat['grantedSpells'], ensure_ascii=True)
            # A feat's own use pool (#891), shown as class features show theirs (#937)
            usage = feat.get('usage') if isinstance(feat.get('usage'), dict) else {}
            if type(usage.get('current')) is int and type(usage.get('max')) is int:
                feat_name = f"{feat_name}({usage['current']}/{usage['max']})"
        else:
            feat_name, feat_desc = compact(str(feat)), ''
        feats_out_parts.append(f"{feat_name}: {feat_desc}" if feat_desc else feat_name)
    feats_out = ','.join(feats_out_parts)

    # Equipment
    equip = get_list(character, 'equipment')
    equip_names: List[str] = []
    for it in equip:
        if isinstance(it, dict):
            raw = it.get('item_name') or it.get('name') or ''
            qty = it.get('quantity', 1)
            desc = describe_text(it.get('description'))
        else:
            raw, qty, desc = str(it), 1, ''
        # The item's name as the sheet writes it, parentheses included.
        nm = compact(raw)
        nm_qty = f"{nm} x{qty}" if qty and qty > 1 else nm
        if isinstance(it, dict) and it.get('equipped') is True:
            nm_qty = f"{nm_qty} [equipped]"
        # D-242-D: the item's whole description after a colon.
        equip_names.append(f"{nm_qty}: {desc}" if desc else nm_qty)
    equip_out = '[' + ','.join(equip_names) + ']'

    # #359: the typed ammunition rows. The full sheet prints them (AMMO) and the
    # DM Note does not, so the compressed sheet must; an empty list is printed
    # so "none" is a fact, not a gap.
    ammo_parts = []
    for row in get_list(character, 'ammunition'):
        if isinstance(row, dict) and row.get('name'):
            part = f"{describe_text(row['name'])} x{row.get('quantity', 0)}"
            if type(row.get('recoverable')) is int and row['recoverable'] > 0:
                part += f"(recoverable {row['recoverable']})"
            ammo_parts.append(part)
    ammo_out = '[' + ','.join(ammo_parts) + ']'

    # Attacks
    attacks = get_list(character, 'attacksAndSpellcasting')
    atk_parts = []
    for atk in attacks:
        an = atk.get('name','')
        dmg = atk.get('damageDice','') or ''
        dtype = atk.get('damageType','') or ''
        atk_bonus = atk.get('attackBonus')
        dmg_bonus = atk.get('damageBonus')
        # The row's typed kind (char_schema: melee, ranged or spell); a row
        # without one is shown as untyped, never guessed from its words.
        kind = atk.get('type') if atk.get('type') in ('melee', 'ranged', 'spell') else 'untyped'
        atk_parts.append(normalize_attack(an, kind, dmg, dtype, atk_bonus, dmg_bonus))
    atk_out = '[' + ','.join(atk_parts) + ']'

    # Spellcasting
    sc = get_dict(character, 'spellcasting')
    ability = sc.get('ability') or 'wisdom'
    # Shorten ability names
    ability_short = {'strength':'str', 'dexterity':'dex', 'constitution':'con',
                     'intelligence':'int', 'wisdom':'wis', 'charisma':'cha'}
    ability = ability_short.get(ability.lower(), ability[:3].lower())
    dc = sc.get('spellSaveDC')
    atk_bonus = sc.get('spellAttackBonus')
    spellcast_out = f"{{ability:{ability},DC:{dc},ATK:+{atk_bonus}}}"

    spells = sc.get('spells') or {}
    spells_parts = []
    for spell_lvl, lst in spells.items():
        if not lst:  # Skip empty spell levels
            continue
        key = '0' if spell_lvl.lower() in ('cantrips','0') else re.sub(r'level','',spell_lvl.lower())
        # Fix spell name casing - remove spaces but keep capitalization
        spell_names = []
        for spell in lst:
            # Remove "the" and "of" then squish together
            spell_norm = re.sub(r'\bthe\b|\bof\b', '', spell, flags=re.IGNORECASE)
            spell_norm = ''.join(word.capitalize() for word in spell_norm.split())
            spell_names.append(spell_norm)
        spells_parts.append(f"{key}:[{','.join(spell_names)}]")
    spells_out = '{' + ','.join(spells_parts) + '}'

    # Currency / XP
    cur = get_dict(character, 'currency')
    gp = cur.get('gold') or 0
    sp = cur.get('silver') or 0
    cp = cur.get('copper') or 0
    currency_out = f"{{gp:{gp},sp:{sp},cp:{cp}}}"
    # --- Fields removed from flatlist (already in DM Note party stats) ---
    # XP: Level, XP current/next in DM Note
    # HP: HP current/max in DM Note
    # SPELL SLOTS: L1:current/max etc. in DM Note
    # LVL: removed from header line below
    # STATS: STR/DEX/CON/INT/WIS/CHA removed from stats line below
    # CURRENCY: GP/SP/CP removed from currency line below

    # Personality
    traits = character.get('personality_traits') or ''
    ideals = character.get('ideals') or ''
    bonds  = character.get('bonds') or ''
    flaws  = character.get('flaws') or ''
    temporary_effects = []
    for effect in character.get('temporaryEffects', []) or []:
        if not isinstance(effect, dict) or not effect.get('name'):
            continue
        duration = effect.get('duration')
        if effect.get('roundsRemaining') is not None:
            duration = f"{effect['roundsRemaining']}r"
        elif effect.get('expiration'):
            duration = f"until:{effect['expiration']}"
        temporary_effects.append(
            f"{effect['name']}({duration})" if duration else str(effect['name'])
        )

    exhaustion = character.get('exhaustion')
    exhaustion_out = f" EXH={exhaustion}(-{2 * exhaustion}d20; long rest -1);" if type(exhaustion) is int and exhaustion > 0 else ""
    if type(exhaustion) is int and exhaustion > 0 and type(spd) is int:
        spd = f"{max(0, spd - 5 * exhaustion)}now(base{spd},exh-{5 * exhaustion})"
    out = []
    # LVL removed - already in DM Note party stats
    out.append(f"CHAR={name}; RACE={race}; CLASS={cls}; ALIGN={align}; BG={bg}; AC={ac}; SPD={spd}; STATUS={status}; CONDITION={condition}; AFFECTED={affected};")
    # STATS removed - already in DM Note party stats (STR:X DEX:X etc.)
    out.append(f"SAVES={saves_out}; SKILLS={{{skills_out}}}; EXPERTISE={expertise_out}; PROF+{prof_bonus}; INIT={initiative}(final,prof+feats incl);{exhaustion_out}{modes_out}")
    out.append(f"SENSES={{darkvision:{darkv},PP:{pp}}}; LANG={langs_out};")
    out.append(f"PROF={{{prof_out}}};")
    out.append(f"VULN={vuln}; RES={res_out}; IMM=; COND_IMM={cimm_out};")
    out.append(f"CLASSFEAT={classfeat_out};")
    if feats_out:
        out.append(f"FEATS={feats_out};")
    if temporary_effects:
        out.append(f"TEMP_FX=[{','.join(temporary_effects)}];")
    focus = character.get('concentration')
    if isinstance(focus, dict) and focus.get('name'):
        out.append(f"CONC={focus['name']}({','.join(focus.get('targets') or []) or 'self'}; engine saves on damage, one spell at a time);")
    out.append(f"EQUIP={equip_out};")
    out.append(f"AMMO={ammo_out};")
    out.append(f"ATK={atk_out};")
    out.append(f"SPELLCAST={spellcast_out};")
    out.append(f"SPELLS={spells_out};")
    # CURRENCY removed - already in DM Note party stats
    out.append(f"TRAITS={traits}; IDEALS={ideals}; BONDS={bonds}; FLAWS={flaws};")
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', required=True, help='Path to character JSON')
    args = ap.parse_args()
    with open(args.char, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(format_flatlist(data))

if __name__ == '__main__':
    main()
