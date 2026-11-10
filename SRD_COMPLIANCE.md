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

The following monster files contain data derived from SRD 5.2.1. Each carries the `_srd_attribution` line shown under Attribution Implementation below.

#### The Thornwood Watch (`modules/The_Thornwood_Watch/monsters/`)
- `awakened_shrub.json` - Awakened Shrub (SRD p. 260)
- `bandit.json` - Bandit (SRD p. 261)
- `corrupted_wolf.json` - Wolf, named "Corrupted Wolf" (SRD p. 364)
- `wolf.json` - Wolf (SRD p. 364)

#### Keep of Doom (`modules/Keep_of_Doom/monsters/`)
- `animated_armor.json` - Animated Armor (SRD p. 259)
- `awakened_shrub.json` - Awakened Shrub (SRD p. 260)
- `gargoyle.json` - Gargoyle (SRD p. 286)
- `gelatinous_cube.json` - Gelatinous Cube (SRD pp. 286-287)
- `ghoul.json` - Ghoul (SRD p. 288)
- `giant_rat.json` - Giant Rat (SRD p. 353)
- `giant_spider.json` - Giant Spider (SRD pp. 353-354)
- `gibbering_mouther.json` - Gibbering Mouther (SRD p. 288)
- `mimic.json` - Mimic (SRD pp. 308-309)
- `shadow.json` - Shadow (SRD pp. 322-323)
- `shambling_mound.json` - Shambling Mound (SRD p. 323)
- `skeleton.json` - Skeleton (SRD pp. 325-326)
- `specter.json` - Specter (SRD p. 327)
- `swarm_of_spiders.json` - Swarm of Insects, named "Swarm of Spiders" (SRD p. 361)
- `will_o_wisp.json` - Will-o'-Wisp (SRD pp. 341-342)
- `zombie.json` - Zombie (SRD pp. 343-344)

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