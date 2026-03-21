"""T079 character updates: Test Gemini models with auto-converted response_schema.

Tests whether passing the full char_schema.json (auto-converted to Gemini format)
as response_schema prevents Gemini from outputting narration instead of character
update deltas.

Results (6 artificial scenarios, auto-converted full schema):
    gemini-3.1-flash-lite|minimal: 4/6 correct, 2.0s avg, fewest spurious keys
    gemini-3-flash|low:            4/6 correct, 3.0s avg
    gemini-3-flash|minimal:        4/6 correct, 6.7s avg
    gemini-3-pro|low:              3/6 correct, 8.8s avg

Without schema: Gemini flash models output {"narration": "..."} (wrong format).
With schema: Zero narration output, correct delta structure.

Usage:
    python tests/model_validation/test_t079_gemini_schema.py
"""
import json
import time
import sys
import os
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load Gemini API key
api_key_file = "google_api.pi"
if os.path.exists(api_key_file):
    with open(api_key_file, "r") as f:
        content = f.read().strip()
        if "api_key=" in content:
            api_key = content.split("api_key=")[1].strip()
        else:
            api_key = content
    os.environ["GEMINI_API_KEY"] = api_key

from google import genai
from google.genai import types
from model_config import convert_to_gemini_schema

client = genai.Client()

# Load and convert schema
with open("schemas/char_schema.json") as f:
    gemini_schema = convert_to_gemini_schema(json.load(f))

# Load system prompt from capture
d = json.load(open("model_captures/T079.json"))
entry = d[1]
system_prompt = ""
for m in entry["input"]["messages"]:
    if m.get("role") == "system":
        system_prompt += m["content"] + "\n\n"

# Test character data
char_data = {
    "name": "Tarin Underbough", "level": 3, "race": "Lightfoot Halfling",
    "class": "Rogue", "hitPoints": 22, "maxHitPoints": 22, "armorClass": 14,
    "status": "alive", "condition": "none",
    "currency": {"gold": 45, "silver": 12, "copper": 3},
    "equipment": [
        {"item_name": "Shortsword", "item_type": "weapon", "description": "Finesse", "quantity": 1},
        {"item_name": "Dagger", "item_type": "weapon", "description": "Thrown", "quantity": 2},
        {"item_name": "Shield", "item_type": "armor", "description": "+2 AC", "quantity": 1},
        {"item_name": "Healing Potion", "item_type": "potion", "description": "2d4+2 HP", "quantity": 3},
    ],
    "ammunition": [{"name": "Arrows", "quantity": 40}],
    "attacksAndSpellcasting": [
        {"name": "Shortsword", "attackBonus": 5, "damageDice": "1d6", "damageBonus": 3,
         "damageType": "piercing", "type": "melee", "reach": "5 ft"},
    ],
    "equipment_effects": [
        {"name": "Shield AC Bonus", "type": "ac_bonus", "value": 2, "target": "armorClass",
         "description": "+2 AC", "source": "Shield"},
    ],
    "temporaryEffects": [], "deathSaves": {"successes": 0, "failures": 0},
}

scenarios = [
    ("S1: Multi-item trade", "Traded 2 Daggers+10g for Enchanted Cloak of Shadows (magical equipment).",
     lambda p: "currency" in p and "equipment" in p),
    ("S2: Combat+potion+ammo", "Took 8 dmg (HP 22->14). Used 1 Healing Potion (7hp, HP->21). Fired 3 arrows.",
     lambda p: "hitPoints" in p and "ammunition" in p),
    ("S3: Shield destroyed", "Shield destroyed by acid. Remove shield, AC 14->12, remove Shield AC Bonus effect.",
     lambda p: "equipment" in p and "armorClass" in p),
    ("S4: Weapon swap", "Swapped Shortsword for Longsword (1d8 slash, +5 atk, +3 dmg, melee 5ft).",
     lambda p: "equipment" in p and "attacksAndSpellcasting" in p),
    ("S5: Poisoned+death", "Poisoned (1hr), HP->0, unconscious, first death save failed.",
     lambda p: "condition" in p and "hitPoints" in p and "status" in p),
    ("S6: Spell slot", "Cast Charm Person (lvl1). Spell slot level1 current 3->2.",
     lambda p: "spellcasting" in p),
]

models = [
    ("gemini-3-flash-preview", "minimal"),
    ("gemini-3-flash-preview", "low"),
    ("gemini-3-flash-preview", "medium"),
    ("gemini-3-pro-preview", "low"),
    ("gemini-3.1-flash-lite-preview", "minimal"),
    ("gemini-3.1-flash-lite-preview", "low"),
    ("gemini-3.1-pro-preview", "low"),
]


def run_one(model_name, thinking, s_name, changes, validate_fn):
    contents = [
        types.Content(role="user", parts=[types.Part(text=f"Current character data:\n{json.dumps(char_data, indent=2)}")]),
        types.Content(role="user", parts=[types.Part(text=f"Changes to make: {changes}")]),
    ]
    start = time.time()
    try:
        response = client.models.generate_content(
            model=model_name, contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                thinking_config=types.ThinkingConfig(thinking_level=thinking),
                response_mime_type="application/json",
                response_schema=gemini_schema,
            ),
        )
        latency = round(time.time() - start, 2)
        parsed = json.loads(response.text)
        has_narration = "narration" in parsed
        ok = validate_fn(parsed) and not has_narration
        spurious = len([k for k in parsed if k in ("personality_traits", "ideals", "bonds", "flaws", "background", "name", "race", "class")])
        return (f"{model_name}|{thinking}", s_name, ok, latency, spurious)
    except Exception as e:
        return (f"{model_name}|{thinking}", s_name, False, round(time.time() - start, 2), 0)


if __name__ == "__main__":
    from collections import defaultdict

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        for model_name, thinking in models:
            for s_name, changes, validate in scenarios:
                tasks.append(executor.submit(run_one, model_name, thinking, s_name, changes, validate))
        all_results = [t.result() for t in tasks]

    agg = defaultdict(lambda: {"passed": 0, "total": 0, "latency": 0, "spurious": 0})
    for label, s_name, ok, lat, sp in all_results:
        a = agg[label]
        a["total"] += 1
        a["latency"] += lat
        a["spurious"] += sp
        if ok:
            a["passed"] += 1

    print(f'{"Model":<45} {"Correct":>8} {"Avg Lat":>8} {"Spurious":>9}')
    print("-" * 75)
    for label in sorted(agg, key=lambda l: (-agg[l]["passed"], agg[l]["latency"] / max(agg[l]["total"], 1))):
        a = agg[label]
        avg_lat = round(a["latency"] / a["total"], 1)
        print(f'{label:<45} {a["passed"]}/{a["total"]:>5}   {avg_lat:>6.1f}s   {a["spurious"]:>7}')
