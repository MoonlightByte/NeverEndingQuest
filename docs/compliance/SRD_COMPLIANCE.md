# SRD 5.2.1 Compliance Documentation

## Overview

This document tracks compliance with the System Reference Document 5.2.1 (SRD 5.2.1) published by Wizards of the Coast LLC under the Creative Commons Attribution 4.0 International License.

## License Information

- **SRD Version**: 5.2.1
- **License**: Creative Commons Attribution 4.0 International License (CC BY 4.0)
- **Source**: https://dnd.wizards.com/resources/systems-reference-document
- **Attribution Required**: Yes

## SRD-Derived Content

### Monsters

The following monster files contain data derived from SRD 5.2.1:

#### Core SRD Monsters (Verified)
- `shadow.json` - Shadow (SRD pg. XXX)
- `skeleton.json` - Skeleton (SRD pg. XXX)
- `giant_spider.json` - Giant Spider (SRD pg. XXX)

#### Additional Monsters (Requires Verification)
- `animated_armor.json` - Animated Armor
- `ghoul.json` - Ghoul
- `giant_rat.json` - Giant Rat
- `mimic.json` - Mimic
- `specter.json` - Specter
- `swarm_of_spiders.json` - Swarm of Insects (Spiders)
- `twig_blight.json` - Twig Blight
- `wight.json` - Wight
- `will-o'-wisp.json` - Will-o'-Wisp
- `gibbering_mouther.json` - Gibbering Mouther

#### Custom/Homebrew Monsters (Original Content)
- `shadow_manifestations.json` - Original creation
- `shadow_mastiff.json` - Needs verification (may be SRD)
- `shadow_of_sir_garran.json` - Custom variant
- `shadow_relic.json` - Original creation
- `skeletal_archer.json` - Custom variant
- `animated_weapon.json` - Custom variant

### Game Mechanics

SRD-derived game mechanics include:
- Ability scores (STR, DEX, CON, INT, WIS, CHA)
- Armor Class calculations
- Hit Points and damage systems
- Saving throws and skill checks
- Combat turn structure
- Spellcasting mechanics

### Character Data

Character schemas follow SRD 5.2.1 structure for:
- Class features (Fighter, etc.)
- Racial traits (Human, etc.)
- Equipment and weapons
- Spell lists and descriptions

## Compliance Status

### ✅ Completed
- [x] Added CC BY 4.0 LICENSE file
- [x] Updated README with SRD attribution
- [x] Replaced trademarked terms in code
- [x] Added attribution to core monster files
- [x] Created compliance documentation

### 🔍 Requires Verification
- [ ] Cross-reference all monsters against SRD 5.2.1
- [ ] Verify spell lists in character files
- [ ] Check class features for SRD compliance
- [ ] Audit equipment lists

### ⚠️ Potential Issues
- Some monster variants may be homebrew content
- Custom campaign content needs clear attribution
- System prompts may reference non-SRD content

## Attribution Implementation

### Monster Files
All SRD-derived monster files include:
```json
{
  "_srd_attribution": "Portions of this monster data derived from SRD 5.2.1, licensed under CC BY 4.0",
  ...
}
```

### Code Files
Files using SRD content include headers:
```python
# Portions of this work derived from SRD 5.2.1, licensed under CC BY 4.0
```

## Trademark Compliance

### Avoided Terms
- "D&D" replaced with "5th edition" or "5e"
- "Dungeons & Dragons" replaced with "fifth edition"
- No references to proprietary settings (Forgotten Realms, etc.)

### Campaign Content
- "Keep of Doom" campaign uses generic fantasy setting
- Location names are original or generic
- NPCs are original creations

## Ongoing Compliance

### For Developers
1. Always check SRD 5.2.1 before adding new monsters
2. Mark all SRD-derived content with attribution
3. Use generic terms instead of trademarked names
4. Document original vs. SRD content clearly

### For Content Creators
1. Campaign content should be original or SRD-derived
2. Avoid proprietary setting references
3. Clearly mark homebrew vs. SRD content
4. Maintain attribution in all derived files

## References

- **SRD 5.2.1 Document**: `/SRD/SRD_CC_v5.2.1.pdf`
- **Conversion Guide**: `/SRD/converting-to-srd-5.2.1.pdf`
- **CC BY 4.0 License**: https://creativecommons.org/licenses/by/4.0/
- **WotC SRD Page**: https://dnd.wizards.com/resources/systems-reference-document

---

*Last Updated: 2024-06-14*
*Next Review: Before public release*