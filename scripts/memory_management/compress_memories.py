#!/usr/bin/env python3
"""
Companion Memory Compression Script
Compresses memory JSON files to minimal token format for AI DM usage
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any

# Action abbreviation mapping
ACTION_MAP = {
    "shared camaraderie": "sc",
    "resolve determination": "rg",
    "showed generosity": "sg",
    "admitted vulnerability": "vr",
    "banter exchange": "bx",
    "provided comfort": "pc",
    "kept watch": "kr",
    "unified united": "uk",
    "shared kiss": "sk",
    "coordinated attack": "ct",
    "shared laughter": "sl",
    "last stand": "ls",
    "offered reassurance": "sr",
    "s hope": "sh",
    "showed cruelty": "cr",
    "deceived ally": "da",
    "made threats": "mt",
    "mentored ally": "ma",
    "understood empathized": "ue",
    "s lead": "ld",
    "s point": "pt",
    "s moments": "sm",
    "s mood": "md",
    "s wounds": "tw",
    "s to": "st",
    "stories experiences": "se",
    "deepened bond": "db",
    "whispered softly": "ws",
    "patiently carefully": "pp",
    "with against": "wa",
    "shared embrace": "em",
    "shared experiences": "ex",
    "faced abandonment": "fa",
    "experienced betrayal": "eb",
    "tended wounds": "tw",
    "held captive": "hc",
    "made last stand": "ls",
    "fled or retreated": "fr",
    "renewed hope": "rh"
}

def compress_memory(memory: Dict) -> Dict:
    """Compress a single memory to minimal format"""
    compressed = {
        "i": memory['id'].split('_')[-1],  # Just keep the number part
        "t": memory['timestamp'],
        "l": memory['location'],
        "a": [],  # Compressed actions
        "e": [  # Emotional vector as array
            round(memory['emotional_vector'].get('trust', 0), 2),
            round(memory['emotional_vector'].get('power', 0), 2),
            round(memory['emotional_vector'].get('intimacy', 0), 2),
            round(memory['emotional_vector'].get('fear', 0), 2),
            round(memory['emotional_vector'].get('respect', 0), 2)
        ],
        "v": memory['emotional_velocity'],
        "j": memory['journal_excerpt'][:80] + "..." if len(memory['journal_excerpt']) > 80 else memory['journal_excerpt'],
        "c": memory['context'].replace("Positive interaction at ", "Pos@").replace("Negative encounter at ", "Neg@").replace("Mixed interactions at ", "Mix@"),
        "m": memory.get('mass', memory['emotional_velocity']),
        "x": memory.get('interaction_number', 0)
    }

    # Compress action names
    for action in memory['trigger_actions']:
        action_lower = action.lower()

        # Try exact match first
        if action_lower in ACTION_MAP:
            compressed_action = ACTION_MAP[action_lower]
        # Try partial matches for common patterns
        elif "kiss" in action_lower:
            compressed_action = "sk"  # shared kiss
        elif "dance" in action_lower:
            compressed_action = "sc"  # shared camaraderie
        elif "embrace" in action_lower or "hug" in action_lower:
            compressed_action = "em"  # shared embrace
        else:
            # Unknown action - keep full text with marker
            compressed_action = f"?{action[:10]}"  # Mark unknown with ? prefix

        compressed["a"].append(compressed_action)

    # Add cascade type only if present
    if memory.get('cascade_type'):
        compressed["ct"] = memory['cascade_type']

    # Add decay resistance only if not 1.0
    if memory.get('decay_resistance', 1.0) != 1.0:
        compressed["dr"] = round(memory['decay_resistance'], 1)

    return compressed

def compress_npc_data(npc_data: Dict) -> Dict:
    """Compress full NPC memory data"""
    compressed = {
        "n": npc_data['npc_name'],
        "ti": npc_data['total_interactions'],
        "es": [  # Current emotional state as array
            round(npc_data['current_emotional_state'].get('trust', 0), 2),
            round(npc_data['current_emotional_state'].get('power', 0), 2),
            round(npc_data['current_emotional_state'].get('intimacy', 0), 2),
            round(npc_data['current_emotional_state'].get('fear', 0), 2),
            round(npc_data['current_emotional_state'].get('respect', 0), 2)
        ],
        "bm": [  # Behavioral model as array
            round(npc_data['behavioral_model'].get('protector_vs_exploiter', 0), 1),
            round(npc_data['behavioral_model'].get('consistent_vs_chaotic', 0), 1),
            round(npc_data['behavioral_model'].get('generous_vs_greedy', 0), 1),
            round(npc_data['behavioral_model'].get('truthful_vs_deceptive', 0), 1),
            round(npc_data['behavioral_model'].get('violent_vs_peaceful', 0), 1)
        ],
        "mem": [compress_memory(m) for m in npc_data['core_memories']]
    }

    return compressed

def create_compressed_file():
    """Create the main compressed memory file"""
    memory_dir = Path("data/companion_memories")

    # Build the specification
    spec = {
        "spec": {
            "es": ["trust", "power", "intimacy", "fear", "respect"],
            "es_rng": "-1..+1 (float)",
            "bm": ["protector", "consistent", "generous", "truthful", "peaceful"],
            "bm_rng": "-1..+1 (float)",
            "m": "memory salience (0..2+)",
            "dr": "decay_resistance (0..1, omit=1)",
            "v": "emotion_velocity magnitude (0..~2)",
            "x": "interaction index (int)",
            "ct": ["CONFIRMATION", "REVERSAL", "COMPLEXITY", None],
            "tone_map": {
                "trust": "+warm,+cooperative; -guarded",
                "power": "+assertive/leader; -deferential",
                "intimacy": "+personal/vulnerable; -distant",
                "fear": "+cautious/anxious; -bold",
                "respect": "+formal/honor; -irreverent"
            },
            "act": ACTION_MAP
        },
        "guide": {
            "use": "When narrating, bias tone and choices using current es; blend with most recent mem.e and bm.",
            "rules": [
                "Tone: map es to style via spec.tone_map; stronger |es| = stronger tone.",
                "Actions: treat mem.a codes (spec.act) as hints for verbs/phrases.",
                "Stability: bm tilts choices (e.g., generous>greedy); do not contradict bm without REVERSAL.",
                "Momentum: higher v => more emotional intensity in wording/pacing.",
                "Salience: higher m => memory should be referenced/echoed in narration.",
                "Decay: low dr fades quickly; prefer recent/high-m items.",
                "Cascade: ct tags signal beats (CONFIRMATION=reinforce trait, REVERSAL=flip, COMPLEXITY=mixed)."
            ]
        }
    }

    # Load memory config
    config_path = memory_dir / "memory_config.json"
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = json.load(f)
            spec["cfg"] = {
                "c": config.get("crystallization_threshold", 0.35),
                "m": config.get("max_memories_per_npc", 5),
                "r": config.get("retrieval_pull_threshold", 0.1),
                "T": config.get("total_memories_created", 0),
                "ic": config.get("npc_interaction_counts", {})
            }

    # Process each NPC's memories
    npcs = []
    for file_path in memory_dir.glob("*_memories.json"):
        if file_path.stem != "memory_config":
            with open(file_path, 'r') as f:
                npc_data = json.load(f)
                compressed_npc = compress_npc_data(npc_data)
                npcs.append(compressed_npc)

    # Determine what legend/spec elements are actually needed
    used_actions = set()
    has_cascade_types = False
    has_decay_resistance = False

    # Scan through all NPCs to see what's actually used
    for npc in npcs:
        for mem in npc.get('mem', []):
            # Collect used action codes
            for action_code in mem.get('a', []):
                if not action_code.startswith('?'):  # Skip unknown actions
                    used_actions.add(action_code)
            # Check for optional fields
            if 'ct' in mem:
                has_cascade_types = True
            if 'dr' in mem:
                has_decay_resistance = True

    # Build minimal spec with only what's needed
    minimal_spec = {}

    # Only include action map for actions actually used
    if used_actions:
        # Reverse lookup to get only needed action definitions
        action_subset = {}
        for action, code in ACTION_MAP.items():
            if code in used_actions:
                action_subset[action] = code

        if action_subset:
            minimal_spec["act"] = action_subset

    # Only include field definitions if we have complex memories
    total_memories = sum(len(npc.get('mem', [])) for npc in npcs)

    if total_memories > 5:  # Include basic legend for larger datasets
        minimal_spec["es"] = ["trust", "power", "intimacy", "fear", "respect"]

    if total_memories > 10:  # Include behavioral model for very large datasets
        minimal_spec["bm"] = ["protector", "consistent", "generous", "truthful", "peaceful"]

    if has_cascade_types:
        minimal_spec["ct"] = ["CONFIRMATION", "REVERSAL", "COMPLEXITY", None]

    # Build final compressed structure based on size
    original_size = sum(os.path.getsize(f) for f in memory_dir.glob("*_memories.json") if f.stem != "memories_compressed")

    if minimal_spec:  # Only include spec if we have something to include
        compressed = {
            "spec": minimal_spec,
            "npcs": npcs
        }
    else:  # Ultra-minimal for tiny datasets
        compressed = {"npcs": npcs}

    # Save compressed version
    output_path = memory_dir / "memories_compressed.json"
    with open(output_path, 'w') as f:
        json.dump(compressed, f, separators=(',', ':'), ensure_ascii=True)

    # Recalculate after saving
    compressed_size = os.path.getsize(output_path)
    ratio = (1 - compressed_size / original_size) * 100

    print(f"Compression complete!")
    print(f"Original size: {original_size:,} bytes")
    print(f"Compressed size: {compressed_size:,} bytes")
    print(f"Compression ratio: {ratio:.1f}%")
    print(f"Saved to: {output_path}")

    return compressed

def decompress_memories(compressed_path: str = "data/companion_memories/memories_compressed.json"):
    """Decompress memories back to original format (for verification)"""
    with open(compressed_path, 'r') as f:
        compressed = json.load(f)

    # Reverse action map
    action_reverse = {v: k for k, v in compressed['spec']['act'].items()}

    for npc in compressed['npcs']:
        decompressed = {
            "npc_name": npc['n'],
            "core_memories": [],
            "current_emotional_state": {
                "trust": npc['es'][0],
                "power": npc['es'][1],
                "intimacy": npc['es'][2],
                "fear": npc['es'][3],
                "respect": npc['es'][4]
            },
            "behavioral_model": {
                "protector_vs_exploiter": npc['bm'][0],
                "consistent_vs_chaotic": npc['bm'][1],
                "generous_vs_greedy": npc['bm'][2],
                "truthful_vs_deceptive": npc['bm'][3],
                "violent_vs_peaceful": npc['bm'][4]
            },
            "total_interactions": npc['ti']
        }

        # Decompress memories
        for mem in npc['mem']:
            memory = {
                "id": f"{npc['n'].lower()}_mem_{mem['i']}",
                "timestamp": mem['t'],
                "location": mem['l'],
                "npc_name": npc['n'],
                "trigger_actions": [action_reverse.get(a, a) for a in mem['a']],
                "emotional_vector": {
                    "trust": mem['e'][0],
                    "power": mem['e'][1],
                    "intimacy": mem['e'][2],
                    "fear": mem['e'][3],
                    "respect": mem['e'][4]
                },
                "emotional_velocity": mem['v'],
                "journal_excerpt": mem['j'],
                "context": mem['c'].replace("Pos@", "Positive interaction at ").replace("Neg@", "Negative encounter at ").replace("Mix@", "Mixed interactions at "),
                "mass": mem['m'],
                "decay_resistance": mem.get('dr', 1.0),
                "cascade_type": mem.get('ct', None),
                "interaction_number": mem['x']
            }
            decompressed["core_memories"].append(memory)

        print(f"Decompressed {npc['n']}: {len(decompressed['core_memories'])} memories")

    return compressed

if __name__ == "__main__":
    # Run compression
    compressed_data = create_compressed_file()

    # Show sample of compressed output
    print("\nSample compressed NPC (first 500 chars):")
    sample = json.dumps(compressed_data['npcs'][0] if compressed_data.get('npcs') else {}, separators=(',', ':'))
    print(sample[:500] + "..." if len(sample) > 500 else sample)