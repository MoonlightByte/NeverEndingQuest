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

Optional flags:
  --keep-paren-info   Keep parenthetical info in EQUIP item names (default: removed).
"""

import json, re, argparse
from typing import Any, Dict, List, Tuple, Optional

def slug(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(s).lower()).strip('_')

def compact(s: str) -> str:
    return re.sub(r'\s+', ' ', str(s)).strip()

def strip_parens(text: str) -> Tuple[str, Optional[str]]:
    # Don't strip +N modifiers for weapons/armor
    if re.search(r'\+\d+', text):
        return text, None
    infos = re.findall(r'\(([^()]*)\)', text)
    base = re.sub(r'\s*\([^)]*\)', '', text).strip()
    return base, ('; '.join(compact(x) for x in infos) if infos else None)

def squeeze_name(name: str) -> str:
    """Blessing of the Silent King -> BlessingSilentKing"""
    n = re.sub(r'\bof the\b', '', name, flags=re.IGNORECASE)
    n = re.sub(r'\bof\b', '', n, flags=re.IGNORECASE)
    n = re.sub(r'\s+', '', n).strip()
    return n

def normalize_feat(name: str, ability_uses: dict = None) -> str:
    """Normalize features with ability counters if available"""
    m = re.search(r'\(([^)]*)\)', name)
    base_name = re.sub(r'\s*\([^)]*\)', '', name).strip() if m else name
    
    # Check if this ability has usage tracking
    if ability_uses:
        for ability_key in ability_uses:
            if ability_key.lower() in base_name.lower():
                uses = ability_uses[ability_key]
                current = uses.get('current', uses.get('uses', 0))
                max_uses = uses.get('max', uses.get('max_uses', 0))
                base = squeeze_name(base_name)
                if max_uses > 0:
                    return f"{base}({current}/{max_uses})"
    
    if m:
        inner = m.group(1).strip()
        base = squeeze_name(base_name)
        # Replace spaces in CR values
        inner = re.sub(r'CR\s+', 'CR', inner)
        if re.search(r'\d|cr|rest', inner, flags=re.IGNORECASE):
            return f"{base}:{inner.replace(' ', '')}"
        return base
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

def format_flatlist(character: Dict[str, Any], keep_paren_info: bool=False) -> str:
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
    affected  = character.get('affected') or ''

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

    # Skills
    skills = get_dict(character, 'skills', 'SKILLS')
    skills_out = ','.join(f"{k[:3]}:{v}" for k,v in skills.items())

    # Proficiency bonus / Senses
    prof_bonus = character.get('proficiencyBonus') or 3
    senses = get_dict(character, 'senses', 'SENSES')
    darkv = senses.get('darkvision') or 0
    pp = senses.get('passivePerception') or 10

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
    # Deduplicate and format resistances
    res_clean = set()
    for r in res:
        r_lower = r.lower().replace(' from ', '_from_').replace(' ', '_')
        # Handle "poison_from_giant_spider" -> "spider_poison"
        if 'poison_from_giant_spider' in r_lower:
            res_clean.add('spider_poison')
        elif 'poison' in r_lower and 'poison' not in res_clean:
            res_clean.add('poison')
        else:
            res_clean.add(r_lower)
    res_out = ','.join(sorted(res_clean))
    cimm= character.get('conditionImmunities') or []
    cimm_out = ','.join(c.lower() for c in cimm)

    # Features - now with usage tracking
    class_feats = get_list(character, 'classFeatures')
    cf_norm = []
    for feat in class_feats:
        if isinstance(feat, dict):
            feat_name = feat.get('name', '')
            usage = feat.get('usage', {})
            current = usage.get('current')
            max_uses = usage.get('max')
            
            # For abilities with usage, add (current/max) after the name
            if current is not None and max_uses is not None:
                # First normalize the base name (keeping things like 2/rest)
                base_norm = normalize_feat(feat_name, None)
                # Then add the usage counter
                cf_norm.append(f"{base_norm}({current}/{max_uses})")
            else:
                cf_norm.append(normalize_feat(feat_name, None))
        else:
            cf_norm.append(normalize_feat(feat, None))
    classfeat_out = ','.join(cf_norm)

    # Equipment
    equip = get_list(character, 'equipment')
    equip_names: List[str] = []
    for it in equip:
        if isinstance(it, dict):
            raw = it.get('item_name') or it.get('name') or ''
            qty = it.get('quantity', 1)
        else:
            raw, qty = str(it), 1
        base, _ = strip_parens(raw) if not keep_paren_info else (raw, None)
        nm = compact(base)
        nm_qty = f"{nm} x{qty}" if qty and qty > 1 else nm
        equip_names.append(nm_qty)
    equip_out = '[' + ','.join(equip_names) + ']'

    # Attacks
    attacks = get_list(character, 'attacksAndSpellcasting')
    atk_parts = []
    for atk in attacks:
        an = atk.get('name','')
        dmg = atk.get('damageDice','') or ''
        dtype = atk.get('damageType','') or ''
        atk_bonus = atk.get('attackBonus')
        dmg_bonus = atk.get('damageBonus')
        desc = (atk.get('description') or '').lower()
        if 'spell' in desc or an.lower().strip() == 'sacred flame':
            kind = 'spell'
        elif 'ranged' in desc or 'crossbow' in an.lower():
            kind = 'ranged'
        else:
            kind = 'melee'
        atk_parts.append(normalize_attack(an, kind, dmg, dtype, atk_bonus, dmg_bonus))
    atk_out = '[' + ','.join(atk_parts) + ']'

    # Spellcasting
    sc = get_dict(character, 'spellcasting')
    ability = sc.get('ability') or 'wisdom'
    # Shorten ability names
    ability_short = {'strength':'str', 'dexterity':'dex', 'constitution':'con',
                     'intelligence':'int', 'wisdom':'wis', 'charisma':'cha'}
    ability = ability_short.get(ability.lower(), ability[:3].lower())
    dc = sc.get('spellSaveDC') or 0
    atk_bonus = sc.get('spellAttackBonus') or 0
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
    # XP removed - already in DM Note

    # Personality
    traits = character.get('personality_traits') or ''
    ideals = character.get('ideals') or ''
    bonds  = character.get('bonds') or ''
    flaws  = character.get('flaws') or ''
    backstory_raw = character.get('backstory') or ''
    backstory = backstory_raw[:100] if backstory_raw else ''  # Bounded for flat output

    out = []
    out.append(f"CHAR={name}; LVL={lvl}; RACE={race}; CLASS={cls}; ALIGN={align}; BG={bg}; AC={ac}; SPD={spd}; STATUS={status}; CONDITION={condition}; AFFECTED={affected};")
    out.append(f"STATS={{STR:{STR},DEX:{DEX},CON:{CON},INT:{INT},WIS:{WIS},CHA:{CHA}}}; SAVES={saves_out}; SKILLS={{{skills_out}}}; PROF+{prof_bonus};")
    out.append(f"SENSES={{darkvision:{darkv},PP:{pp}}}; LANG={langs_out};")
    out.append(f"PROF={{{prof_out}}};")
    out.append(f"VULN={vuln}; RES={res_out}; IMM=; COND_IMM={cimm_out};")
    out.append(f"CLASSFEAT={classfeat_out};")
    out.append(f"EQUIP={equip_out};")
    out.append(f"ATK={atk_out};")
    out.append(f"SPELLCAST={spellcast_out};")
    out.append(f"SPELLS={spells_out};")
    out.append(f"CURRENCY={currency_out};")
    out.append(f"TRAITS={traits}; IDEALS={ideals}; BONDS={bonds}; FLAWS={flaws}; BACKSTORY={backstory};")
    return '\n'.join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', required=True, help='Path to character JSON')
    ap.add_argument('--keep-paren-info', action='store_true', help='Keep parenthetical info in EQUIP item names')
    args = ap.parse_args()
    with open(args.char, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(format_flatlist(data, keep_paren_info=args.keep_paren_info))

if __name__ == '__main__':
    main()