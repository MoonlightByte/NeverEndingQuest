#!/usr/bin/env python3
"""
Module Gameplay Audit Script

Validates monster reference parity for NeverEndingQuest modules.
Checks that all referenced monsters have JSON definitions and media assets.

Usage:
    python audit_module_gameplay.py --module <module_name>
    python audit_module_gameplay.py --module <module_name> --baseline <baseline_module>
    python audit_module_gameplay.py --module <module_name> --strict-instructions

Exit codes:
    0 - No blocking errors
    1 - Blocking errors found
"""

import argparse
import json
import glob
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


MEDIA_OUTCOME_REUSED_OR_GENERATED = "reused_or_generated"
MEDIA_OUTCOME_PROVIDER_DISABLED_MISSING = "provider_disabled_missing"
MEDIA_OUTCOME_ATTEMPTED_BUT_UNRESOLVED = "attempted_but_unresolved"


@dataclass
class MonsterRef:
    """A monster reference with source attribution."""
    slug: str
    source_file: str
    source_path: str
    confidence: str = "structural"  # "structural" or "heuristic"
    original_text: str = ""


# Common words that are unlikely to be monster names; used to filter heuristic matches.
HEURISTIC_STOP_WORDS = {
    # Articles, conjunctions, prepositions, pronouns, common verbs, genre-specific noise
    "the", "a", "an", "and", "or", "but", "if", "when", "while", "however", "therefore",
    "thus", "unless", "until", "before", "after", "during", "because", "since", "although",
    "though", "even", "nor", "from", "with", "to", "by", "for", "in", "on", "at", "near",
    "far", "here", "there", "this", "that", "these", "those", "what", "which", "who",
    "whom", "whose", "where", "why", "how", "be", "is", "are", "was", "were", "do",
    "does", "did", "can", "could", "should", "would", "will", "shall", "may", "might",
    "must", "has", "have", "had", "having", "encounter", "attack", "battle", "combat",
    "scene", "area", "location", "party", "adventurers", "heroes", "player", "character",
    "dm", "gm", "narrator", "story", "plot", "hook", "clue", "treasure", "loot",
    "reward", "challenge", "skill", "check", "save", "roll", "initiative", "turn",
    "round", "phase", "action", "bonus", "reaction", "movement", "speed", "damage",
    "heal", "rest", "spell", "ability", "feature", "trait", "feat", "power", "level",
    "xp", "experience", "hit", "miss", "critical", "success", "failure", "pass", "fail"
}


def is_likely_monster_name(name: str) -> bool:
    """
    Heuristic guard: determine if a captured phrase is likely an actual monster name.
    Rejects generic prose and common false positives.
    """
    if not name:
        return False
    # Require first character to be uppercase (title case)
    if not name[0].isupper():
        return False
    # Stop-word filter on the first word
    first_word = name.split()[0].lower()
    if first_word in HEURISTIC_STOP_WORDS:
        return False
    return True


def normalize_slug(name: str) -> str:
    """
    Normalize monster name to runtime slug format.
    Matches normalize_character_name() used by ModulePathManager.
    """
    s = name.lower().strip()
    s = s.replace(' ', '_').replace("'", '_')
    s = re.sub(r'[^a-z0-9_]', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return s


def extract_name_from_entry(entry) -> Optional[str]:
    """Extract monster name from various entry formats."""
    if isinstance(entry, str):
        return entry.strip() if entry.strip() else None
    elif isinstance(entry, dict):
        name = entry.get('name') or entry.get('monsterType') or entry.get('type') or entry.get('monster')
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def extract_from_structure(data, path: str = "root") -> List[Tuple[str, str, str]]:
    """
    Recursively extract monster refs from nested structures.
    Returns list of (slug, source_path, confidence) tuples.
    """
    refs = []
    
    if isinstance(data, dict):
        # Check for monster-related keys
        for key, value in data.items():
            lower_key = key.lower()
            current_path = f"{path}.{key}"
            
            # Direct monster arrays
            if lower_key in ['monsters', 'creatures', 'enemies'] and isinstance(value, list):
                for i, entry in enumerate(value):
                    name = extract_name_from_entry(entry)
                    if name:
                        refs.append((normalize_slug(name), f"{current_path}[{i}]", "structural"))
            
            # CreateEncounter payload detection
            elif lower_key == 'action' and value == 'createEncounter':
                # Look for monsters in parameters
                params = data.get('parameters', {})
                if isinstance(params, dict):
                    monsters = params.get('monsters', [])
                    if isinstance(monsters, list):
                        for i, entry in enumerate(monsters):
                            name = extract_name_from_entry(entry)
                            if name:
                                refs.append((normalize_slug(name), f"{path}.parameters.monsters[{i}]", "structural"))
            
            # Recurse into nested structures
            elif isinstance(value, (dict, list)):
                refs.extend(extract_from_structure(value, current_path))
                
    elif isinstance(data, list):
        for i, item in enumerate(data):
            refs.extend(extract_from_structure(item, f"{path}[{i}]"))
    
    return refs


def extract_monster_refs_from_text(text: str, source_path: str) -> List[Tuple[str, str, str, str]]:
    """
    Heuristic extraction of monster names from instruction text.
    Returns list of (slug, source_path, confidence, original_text) tuples.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    
    refs = []
    
    # Pattern 1: "X monster" or "monsters like X"
    pattern1 = re.compile(
        r'(?:encounter|fight|battle|spawn|summon|appear|create|generate)s?\s+(?:with\s+)?(?:a\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        re.IGNORECASE
    )
    for match in pattern1.finditer(text):
        name = match.group(1).strip()
        if len(name) > 2 and name.lower() not in ['the', 'and', 'with', 'from', 'they', 'them', 'their']:
            # Guard: first char uppercase and not a stop-word phrase
            if is_likely_monster_name(name):
                refs.append((normalize_slug(name), source_path, "heuristic", name))
    
    # Pattern 2: Monster names in quotes
    pattern2 = re.compile(r'["\']([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)["\']')
    for match in pattern2.finditer(text):
        name = match.group(1).strip()
        if len(name) > 2 and is_likely_monster_name(name):
            refs.append((normalize_slug(name), source_path, "heuristic", name))
    
    # Pattern 3: Capitalized multi-word phrases that look like monster names
    # (more conservative - only in combat/narrative contexts)
    combat_contexts = ['combat', 'encounter', 'attack', 'enemy', 'foe', 'hostile', 'threat', 'monster']
    if any(ctx in text.lower() for ctx in combat_contexts):
        pattern3 = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b')
        for match in pattern3.finditer(text):
            name = match.group(1).strip()
            # Filter out common false positives
            if name.lower() not in ['the party', 'player characters', 'dungeon master', 'next turn', 'saving throw', 'attack roll', 'hit points', 'armor class']:
                if is_likely_monster_name(name):
                    refs.append((normalize_slug(name), source_path, "heuristic", name))
    
    return refs


def extract_monster_refs(module_path: str, strict_instructions: bool = False) -> List[MonsterRef]:
    """
    Extract all monster references from active area files with source attribution.
    """
    refs = []
    area_pattern = os.path.join(module_path, 'areas', '*.json')
    
    for area_file in glob.glob(area_pattern):
        # Skip backup files
        if area_file.endswith('_BU.json'):
            continue
            
        try:
            with open(area_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        
        filename = os.path.basename(area_file)
        
        # 1. Extract from structural locations[].monsters
        for loc_idx, location in enumerate(data.get('locations', [])):
            loc_id = location.get('locationId', f'loc_{loc_idx}')
            
            # monsters array
            for m_idx, monster in enumerate(location.get('monsters', [])):
                name = extract_name_from_entry(monster)
                if name:
                    refs.append(MonsterRef(
                        slug=normalize_slug(name),
                        source_file=filename,
                        source_path=f"locations[{loc_idx}].monsters[{m_idx}]",
                        confidence="structural",
                        original_text=name
                    ))
            
            # 2. Extract from randomEncounters in locations
            for re_idx, encounter in enumerate(location.get('randomEncounters', [])):
                # Check encounter structure
                if isinstance(encounter, dict):
                    # Direct monsters array
                    for m_idx, monster in enumerate(encounter.get('monsters', [])):
                        name = extract_name_from_entry(monster)
                        if name:
                            refs.append(MonsterRef(
                                slug=normalize_slug(name),
                                source_file=filename,
                                source_path=f"locations[{loc_idx}].randomEncounters[{re_idx}].monsters[{m_idx}]",
                                confidence="structural",
                                original_text=name
                            ))
                    
                    # createEncounter in action/dmInstruction
                    for key in ['action', 'dmAction', 'dmInstruction']:
                        if encounter.get(key) == 'createEncounter':
                            monsters = encounter.get('monsters', [])
                            if isinstance(monsters, list):
                                for m_idx, m in enumerate(monsters):
                                    name = extract_name_from_entry(m)
                                    if name:
                                        refs.append(MonsterRef(
                                            slug=normalize_slug(name),
                                            source_file=filename,
                                            source_path=f"locations[{loc_idx}].randomEncounters[{re_idx}].{key}.monsters[{m_idx}]",
                                            confidence="structural",
                                            original_text=name
                                        ))
                    
                    # Nested structure scan
                    nested_refs = extract_from_structure(encounter, f"locations[{loc_idx}].randomEncounters[{re_idx}]")
                    for slug, path, confidence in nested_refs:
                        refs.append(MonsterRef(
                            slug=slug,
                            source_file=filename,
                            source_path=path,
                            confidence=confidence,
                            original_text=""
                        ))
                    
                    # Heuristic scan of text fields
                    text_fields = ['description', 'dmInstruction', 'dmNote', 'instruction', 'narrative']
                    for field in text_fields:
                        if field in encounter:
                            text = encounter[field]
                            if isinstance(text, str):
                                for slug, path, confidence, original in extract_monster_refs_from_text(
                                    text, f"locations[{loc_idx}].randomEncounters[{re_idx}].{field}"
                                ):
                                    refs.append(MonsterRef(
                                        slug=slug,
                                        source_file=filename,
                                        source_path=path,
                                        confidence=confidence,
                                        original_text=original
                                    ))
        
        # 3. Extract from top-level randomEncounters
        for re_idx, encounter in enumerate(data.get('randomEncounters', [])):
            if isinstance(encounter, dict):
                for m_idx, monster in enumerate(encounter.get('monsters', [])):
                    name = extract_name_from_entry(monster)
                    if name:
                        refs.append(MonsterRef(
                            slug=normalize_slug(name),
                            source_file=filename,
                            source_path=f"randomEncounters[{re_idx}].monsters[{m_idx}]",
                            confidence="structural",
                            original_text=name
                        ))
                
                # Nested structure scan
                nested_refs = extract_from_structure(encounter, f"randomEncounters[{re_idx}]")
                for slug, path, confidence in nested_refs:
                    refs.append(MonsterRef(
                        slug=slug,
                        source_file=filename,
                        source_path=path,
                        confidence=confidence,
                        original_text=""
                    ))
                
                # Heuristic scan of text fields
                text_fields = ['description', 'dmInstruction', 'dmNote', 'instruction', 'narrative']
                for field in text_fields:
                    if field in encounter:
                        text = encounter[field]
                        if isinstance(text, str):
                            for slug, path, confidence, original in extract_monster_refs_from_text(
                                text, f"randomEncounters[{re_idx}].{field}"
                            ):
                                refs.append(MonsterRef(
                                    slug=slug,
                                    source_file=filename,
                                    source_path=path,
                                    confidence=confidence,
                                    original_text=original
                                ))
        
        # 4. Heuristic scan of plot hooks and DC checks (if strict mode)
        if strict_instructions:
            for field in ['plotHooks', 'dcChecks', 'dmNotes', 'storyHooks']:
                items = data.get(field, [])
                if isinstance(items, list):
                    for i, item in enumerate(items):
                        if isinstance(item, str):
                            for slug, path, confidence, original in extract_monster_refs_from_text(
                                item, f"{field}[{i}]"
                            ):
                                refs.append(MonsterRef(
                                    slug=slug,
                                    source_file=filename,
                                    source_path=path,
                                    confidence=confidence,
                                    original_text=original
                                ))
                        elif isinstance(item, dict) and 'description' in item:
                            text = item['description']
                            if isinstance(text, str):
                                for slug, path, confidence, original in extract_monster_refs_from_text(
                                    text, f"{field}[{i}].description"
                                ):
                                    refs.append(MonsterRef(
                                        slug=slug,
                                        source_file=filename,
                                        source_path=path,
                                        confidence=confidence,
                                        original_text=original
                                    ))
    
    return refs


def check_monster_json(module_path: str, slug: str) -> Tuple[bool, List[str]]:
    """
    Check if monster JSON exists and is valid.
    Returns (is_valid, missing_keys).
    """
    json_path = os.path.join(module_path, 'monsters', f'{slug}.json')
    
    if not os.path.exists(json_path):
        return False, ['FILE_NOT_FOUND']
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        return False, ['PARSE_ERROR']
    
    # Load schema to check required keys
    schema_path = 'schemas/mon_schema.json'
    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        required_keys = set(schema.get('required', []))
        present_keys = set(data.keys())
        missing_keys = sorted(required_keys - present_keys)
        return len(missing_keys) == 0, missing_keys
    except (IOError, json.JSONDecodeError):
        # If schema unavailable, just check basic structure
        basic_required = ['name', 'size', 'type', 'alignment', 'armorClass', 
                         'hitPoints', 'speed', 'abilities', 'challengeRating']
        missing = [k for k in basic_required if k not in data]
        return len(missing) == 0, missing


def check_monster_media(module_path: str, slug: str) -> Dict[str, bool]:
    """
    Check media asset availability for a monster slug.
    """
    media_dir = os.path.join(module_path, 'media', 'monsters')
    
    # Check base media
    base_extensions = ['.jpg', '.jpeg', '.png', '.webp']
    base_found = any(
        os.path.exists(os.path.join(media_dir, f'{slug}{ext}'))
        for ext in base_extensions
    )
    
    # Check thumb
    thumb_found = any(
        os.path.exists(os.path.join(media_dir, f'{slug}_thumb{ext}'))
        for ext in base_extensions
    )
    
    # Check video
    video_found = os.path.exists(os.path.join(media_dir, f'{slug}_video.mp4'))
    
    return {
        'base': base_found,
        'thumb': thumb_found,
        'video': video_found
    }


def classify_monster_media_outcome(media_status: Dict[str, bool]) -> str:
    """Classify deterministic media outcome for reporting surfaces."""
    base_present = bool(media_status.get('base'))
    thumb_present = bool(media_status.get('thumb'))
    video_present = bool(media_status.get('video'))

    if base_present:
        return MEDIA_OUTCOME_REUSED_OR_GENERATED
    if thumb_present or video_present:
        return MEDIA_OUTCOME_ATTEMPTED_BUT_UNRESOLVED
    return MEDIA_OUTCOME_PROVIDER_DISABLED_MISSING


def audit_module(module_name: str, strict_instructions: bool = False) -> Dict:
    """
    Perform full gameplay audit on a module.
    """
    module_path = os.path.join('modules', module_name)
    
    if not os.path.exists(module_path):
        return {
            'blocking_errors': [f"Module not found: {module_name}"],
            'warnings': [],
            'coverage_stats': {'module': module_name},
            'fix_list': [],
            'references': []
        }
    
    # Extract references with source attribution
    refs = extract_monster_refs(module_path, strict_instructions)
    
    # Deduplicate by slug
    seen_slugs = set()
    unique_refs = []
    for ref in refs:
        if ref.slug not in seen_slugs:
            seen_slugs.add(ref.slug)
            unique_refs.append(ref)
    
    blocking_errors = []
    warnings = []
    fix_list = []
    
    json_valid_count = 0
    json_invalid_count = 0
    json_missing_count = 0
    media_base_count = 0
    media_thumb_count = 0
    media_video_count = 0
    monster_media_findings = []
    
    structural_refs = [r for r in unique_refs if r.confidence == "structural"]
    heuristic_refs = [r for r in unique_refs if r.confidence == "heuristic"]
    
    # Process structural refs (always blockers if broken)
    for ref in sorted(structural_refs, key=lambda x: x.slug):
        slug = ref.slug
        
        # Check JSON
        is_valid, missing_keys = check_monster_json(module_path, slug)
        
        if not is_valid:
            if 'FILE_NOT_FOUND' in missing_keys:
                blocking_errors.append(f"Missing monster JSON: {slug} (from {ref.source_file}:{ref.source_path})")
                json_missing_count += 1
                fix_list.append(f"Create: modules/{module_name}/monsters/{slug}.json")
            elif 'PARSE_ERROR' in missing_keys:
                blocking_errors.append(f"Invalid JSON: monsters/{slug}.json")
                json_invalid_count += 1
                fix_list.append(f"Fix JSON syntax: monsters/{slug}.json")
            else:
                warnings.append(f"Monster {slug} missing keys: {', '.join(missing_keys)}")
                json_invalid_count += 1
        else:
            json_valid_count += 1
        
        # Check media
        media_status = check_monster_media(module_path, slug)
        media_outcome = classify_monster_media_outcome(media_status)
        monster_media_findings.append(
            {
                'slug': slug,
                'confidence': ref.confidence,
                'source_file': ref.source_file,
                'source_path': ref.source_path,
                'outcome': media_outcome,
                'base': bool(media_status.get('base')),
                'thumb': bool(media_status.get('thumb')),
                'video': bool(media_status.get('video')),
            }
        )
        
        if not media_status['base']:
            # Base media missing is a blocker for tabletop mode
            blocking_errors.append(f"Missing base media for: {slug} (from {ref.source_file}:{ref.source_path})")
            fix_list.append(f"Add media: modules/{module_name}/media/monsters/{slug}.jpg")
        else:
            media_base_count += 1
        
        if media_status['thumb']:
            media_thumb_count += 1
        else:
            warnings.append(f"Missing thumb for: {slug}")
        
        if media_status['video']:
            media_video_count += 1
        else:
            warnings.append(f"Missing video for: {slug}")
    
    # Process heuristic refs
    for ref in sorted(heuristic_refs, key=lambda x: x.slug):
        slug = ref.slug
        
        # Check JSON
        is_valid, missing_keys = check_monster_json(module_path, slug)
        
        if not is_valid:
            if 'FILE_NOT_FOUND' in missing_keys:
                msg = f"Heuristic monster reference unresolved: '{ref.original_text}' -> {slug} (from {ref.source_file}:{ref.source_path})"
                if strict_instructions:
                    blocking_errors.append(msg)
                else:
                    warnings.append(msg)
                fix_list.append(f"Create (if valid): modules/{module_name}/monsters/{slug}.json")
        
        # Media check for heuristics is warning only
        media_status = check_monster_media(module_path, slug)
        media_outcome = classify_monster_media_outcome(media_status)
        monster_media_findings.append(
            {
                'slug': slug,
                'confidence': ref.confidence,
                'source_file': ref.source_file,
                'source_path': ref.source_path,
                'outcome': media_outcome,
                'base': bool(media_status.get('base')),
                'thumb': bool(media_status.get('thumb')),
                'video': bool(media_status.get('video')),
            }
        )
        if not media_status['base']:
            if strict_instructions:
                blocking_errors.append(f"Missing base media (heuristic): {slug} (from {ref.source_file}:{ref.source_path})")
            else:
                warnings.append(f"Missing base media (heuristic): {slug}")
    
    total_structural = len(structural_refs)
    total_heuristic = len(heuristic_refs)
    total_refs = len(seen_slugs)
    
    coverage_stats = {
        'module': module_name,
        'referenced_monsters': total_refs,
        'structural_refs': total_structural,
        'heuristic_refs': total_heuristic,
        'json_valid': json_valid_count,
        'json_invalid': json_invalid_count,
        'json_missing': json_missing_count,
        'json_coverage_pct': round((json_valid_count / total_structural * 100), 1) if total_structural > 0 else 0,
        'media_base_coverage': media_base_count,
        'media_thumb_coverage': media_thumb_count,
        'media_video_coverage': media_video_count,
        'media_base_coverage_pct': round((media_base_count / total_structural * 100), 1) if total_structural > 0 else 0,
        'media_policy': {
            'provider_generation_mode': 'opt_in_manual_only',
            'manual_toolkit_workflow': [
                'Monster Management & Generator -> Generate Monster Images',
                'Module Media Generator -> one-click monster media generation',
            ],
            'outcome_vocabulary': [
                MEDIA_OUTCOME_REUSED_OR_GENERATED,
                MEDIA_OUTCOME_PROVIDER_DISABLED_MISSING,
                MEDIA_OUTCOME_ATTEMPTED_BUT_UNRESOLVED,
            ],
        },
    }
    
    return {
        'blocking_errors': blocking_errors,
        'warnings': warnings,
        'coverage_stats': coverage_stats,
        'fix_list': fix_list,
        'monster_media_findings': monster_media_findings,
        'references': [
            {
                'slug': r.slug,
                'file': r.source_file,
                'path': r.source_path,
                'confidence': r.confidence,
                'original': r.original_text
            }
            for r in unique_refs
        ]
    }


def format_report(result: Dict, baseline_result: Optional[Dict] = None) -> str:
    """
    Format audit results for display.
    """
    lines = []
    lines.append("=" * 70)
    lines.append("MODULE GAMEPLAY AUDIT REPORT")
    lines.append("=" * 70)
    
    stats = result['coverage_stats']
    lines.append(f"\nModule: {stats['module']}")
    lines.append(f"Referenced monsters: {stats['referenced_monsters']}")
    lines.append(f"  - Structural refs: {stats['structural_refs']}")
    lines.append(f"  - Heuristic refs: {stats['heuristic_refs']}")
    lines.append(f"\nJSON Coverage: {stats['json_valid']}/{stats['structural_refs']} ({stats['json_coverage_pct']}%)")
    lines.append(f"  - Valid: {stats['json_valid']}")
    lines.append(f"  - Invalid: {stats['json_invalid']}")
    lines.append(f"  - Missing: {stats['json_missing']}")
    
    lines.append(f"\nMedia Coverage:")
    lines.append(f"  - Base: {stats['media_base_coverage']}/{stats['structural_refs']} ({stats['media_base_coverage_pct']}%)")
    lines.append(f"  - Thumb: {stats['media_thumb_coverage']}/{stats['structural_refs']}")
    lines.append(f"  - Video: {stats['media_video_coverage']}/{stats['structural_refs']}")
    
    # Baseline comparison
    if baseline_result:
        base_stats = baseline_result['coverage_stats']
        lines.append(f"\nBaseline ({base_stats['module']}) Comparison:")
        lines.append(f"  JSON coverage: {base_stats['json_coverage_pct']}% -> {stats['json_coverage_pct']}%")
        lines.append(f"  Media coverage: {base_stats['media_base_coverage_pct']}% -> {stats['media_base_coverage_pct']}%")
    
    # Blocking errors
    if result['blocking_errors']:
        lines.append(f"\n❌ BLOCKING ERRORS ({len(result['blocking_errors'])}) [strict mode: {result.get('strict_mode', False)}]:")
        lines.append("-" * 70)
        for error in result['blocking_errors'][:20]:  # Limit display
            lines.append(f"  • {error}")
        if len(result['blocking_errors']) > 20:
            lines.append(f"  ... and {len(result['blocking_errors']) - 20} more")
        
        # TABLETOP MODE WARNING
        lines.append("\n⚠️  TABLETOP MODE RISK:")
        lines.append("   Missing monster JSON files will cause combat_builder to fail-closed,")
        lines.append("   resulting in narration/combat desync for affected monsters.")
    else:
        lines.append("\n✅ No blocking errors found!")
    
    # Warnings
    if result['warnings']:
        lines.append(f"\n⚠️  WARNINGS ({len(result['warnings'])}):")
        lines.append("-" * 70)
        for warning in result['warnings'][:15]:
            lines.append(f"  • {warning}")
        if len(result['warnings']) > 15:
            lines.append(f"  ... and {len(result['warnings']) - 15} more")
    
    # Fix list
    if result['fix_list']:
        lines.append(f"\n🔧 FIX LIST ({len(result['fix_list'])} items):")
        lines.append("-" * 70)
        for fix in result['fix_list'][:15]:
            lines.append(f"  • {fix}")
        if len(result['fix_list']) > 15:
            lines.append(f"  ... and {len(result['fix_list']) - 15} more")
    
    lines.append("\n" + "=" * 70)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Audit module gameplay integrity (monster parity)'
    )
    parser.add_argument(
        '--module', 
        required=True,
        help='Module name to audit (e.g., The_Pumpkin_Kings_Curse)'
    )
    parser.add_argument(
        '--baseline',
        help='Optional baseline module for comparison (e.g., The_Thornwood_Watch)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output raw JSON instead of formatted report'
    )
    parser.add_argument(
        '--strict-instructions',
        action='store_true',
        help='Treat heuristic instruction-derived unresolved refs as blockers'
    )
    
    args = parser.parse_args()
    
    # Run audit
    result = audit_module(args.module, args.strict_instructions)
    result['strict_mode'] = args.strict_instructions
    
    # Run baseline comparison if requested
    baseline_result = None
    if args.baseline:
        baseline_result = audit_module(args.baseline, args.strict_instructions)
    
    # Output
    if args.json:
        output = {
            'target': result,
            'baseline': baseline_result
        }
        print(json.dumps(output, indent=2))
    else:
        print(format_report(result, baseline_result))
    
    # Exit code based on blocking errors
    sys.exit(1 if result['blocking_errors'] else 0)


if __name__ == '__main__':
    main()
