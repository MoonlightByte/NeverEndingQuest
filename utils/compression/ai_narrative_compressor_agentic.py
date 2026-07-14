#!/usr/bin/python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
AI-powered narrative compressor using GPT-4.1-mini (Agentic approach)
Converts fantasy narrative to ultra-compact EVT notation format
"""

import hashlib
import json
import sys
import re
from typing import Dict, Any, List
from pathlib import Path
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T084", "utils/compression/ai_narrative_compressor_agentic.py", 267)

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass  # No-op fallback

# System prompt for GPT-4.1-mini (Agentic approach)
SYSTEM_PROMPT = """# SYSTEM PROMPT — Agentic Slimline Compressor (for GPT-4.1-mini)

You are an **agentic compressor**. Your job is to read a fantasy narrative passage and produce a compact, readable **slimline** representation that we can store and later expand. You must **think through the task internally**, run a **self-check**, repair your own draft if needed, and then return **only the final JSON** described below (no notes, no explanations).

## Operating principles

* **Agentic autonomy**: You choose beat boundaries, which details to retain, and how to condense — as long as the final output conforms to the schema.
* **Low friction**: Prefer minimal constraints. When in doubt, pick the simplest representation that preserves who/where/what happened.
* **Self-critique & repair**: Internally draft → validate against the schema & rubric → fix → output final JSON. Do not show draft or reasoning.
* **Determinism**: Behave as if `temperature=0` and `top_p=1.0` even if the caller forgets to set them.
* **Prose preservation**: Beats may combine a marker, an action, and a short natural-language summary. You may include character names, items, or events directly in the beat text if it helps preserve story context.

## Input (user message payload)

You will receive JSON like:

```json
{
  "CANON": {
    "codebook": { "C": {}, "L": {}, "S": {} },
    "blocks": [],
    "next_seq_by_location": {}
  },
  "PASSAGE": "…raw narrative text…",
  "CONFIG": {
    "mode": "agentic",              // "agentic" | "strict"
    "max_chars": 12,
    "max_locs": 12,
    "min_party_size": 3,
    "min_party_occurrences": 2
  }
}
```

Notes:

* `CANON` may be empty; otherwise reuse IDs for exact name matches.
* `mode=agentic` lets you keep multiple adjacent beats if they add meaning; `mode=strict` pushes you to merge near-duplicates.

## Output (final JSON only)

```jsonc
{
  "version": "1.0",
  "ops": [
    { "action": "match_update" | "create", "block_id": "LOC-###", "reason": "short rationale" }
  ],
  "codebook": {
    "C": { "1":"Name", "2":"Name", ... },
    "L": { "1":"Location", "2":"Location", ... },
    "S": { "1":"Spell", ... }
  },
  "blocks": [
    {
      "block_id": "LOC-###",
      "signature": { "L":[...], "C":[...] },
      "text": "@C={id:Name,...}\\n@L={id:Loc,...}\\n@S={id:Spell,...}\\n@I={token,token,...}\\n@R={r1:(A relation B), r2:(A,B,C party)}\\n\\nEVT[\\n1) <marker> <action> [with:ID,ID].\\n...]\\n"
    }
  ],
  "validation": { "errors": [], "warnings": [] }
}
```

## Slimline format (light rules)

* **Tables**:
  * `@C` people only; reuse existing IDs where names match exactly.
  * `@L` reuse existing canon location names EXACTLY as written in CANON.codebook.L. Do NOT rename, paraphrase, or expand them. Only create new @L entries for locations not in the canon. For new locations, use the longest canonical name from the passage.
  * `@S` small known list (Aid, Bless, Shield, Mage Armor, Cure Wounds, Guidance, Light, Detect Magic).
  * `@I` compact tokens (lowercase): `armor, boots, ssword×2, sbow, cloak, weapons, gear, stew, ale, porridge`.

* **Relations `@R`**:
  * Use shorthand keys for relations:
    Example: @R={romance:(1,2), party:(1,2,3,4)}
  * `romance`: choose **the** closest/frequent pair across the passage; at most one.
  * `prevOwnedBy`: detect "under Y's ownership/control/…", or "owned/enslaved/kept by Y"; victim = nearest other character.
  * `party`: largest recurring group (≥3) that co-occurs in multiple paragraphs (threshold from CONFIG).

* **Beats `EVT[...]`**:
  * Each beat starts with a location **marker** then action(s), optionally followed by a short natural-language summary.
  * Format: "n) <marker> <action> [with:IDs]. [Optional prose description.]"
  * Allowed markers: `@Lk` (present), `->Lk` (move to), `<-Lk` (return from).
  * Actions can include: meet, trade, rest, prep, cast, tension, romance, bond.
  * You may include character names, items, spells, or events directly in the beat prose to preserve context.
  * Example: "1) @L1 meet with:1,2,3,4,7. Adventurers gather at the Hearth; Cira serves stew and ale."
  * Example: "3) @L2 prep with:1,2,3,4. Eirik arranges gear; casts Aid spell twice; party readies for journey."
  * `with:` uses **IDs only**, up to 6.
  * End every beat with a period. Number beats `1)..N)`.
  * **Game-mechanical values**: When the passage states specific numeric outcomes (damage dealt, HP healed, spell slots recovered, DC checks, dice rolls), preserve these numbers in the beat text. They are load-bearing game state, not expendable flavor. Example: "Aldric casts Cure Wounds on Tarin, healing 8 HP" NOT "Aldric heals Tarin".
  * If a known spell appears in the passage (e.g., Aid), include it in @S and reference it in at least one beat.

## Agentic freedoms (what you can decide)

* **Beat granularity**: You may keep multiple adjacent beats (e.g., separate `tension` then `bond`) **if they add meaning**. If two beats are semantically redundant (same action with near-identical `with:`), merge them.
* **Action choice**: If a beat could be `rest` **and** `trade`, pick the one that best characterizes the paragraph. In `strict` mode, prefer merging/one action; in `agentic` mode, you can keep both as **separate** beats if they illuminate different moments.
* **No forced minimalism**: If a second `bond` beat meaningfully signals a later scene of camaraderie at a different location, you may keep it.

## Block matching / creation

* Compute `signature.L` (primary locations referenced) and `signature.C` (3–6 central characters by frequency).
* Match an existing block if: share ≥1 primary location AND ≥50% of signature characters.
* If matched: `action="match_update"`; replace `text`.
* Else: `action="create"`, `block_id=<PrimaryLocSlug>-<seq>`; slug = initial letters of words (e.g., Black Lantern Hearth → **BLH**). Sequence from `next_seq_by_location` or start `001`.

## Self-check rubric (run internally; don't output)

1. **Schema**: Output is valid JSON; exactly one `EVT[...]` block; numbered beats with periods.
2. **Referential integrity**: Any `Lk`/`ID` used in beats exists in `@L`/`@C`; `with:` is IDs only.
3. **Coverage**: Tables include all entities referenced in beats (no missing Brother Lintar/locations/spells if used).
4. **Conciseness**: Target high compression (≥85% reduction). Prose in beats is allowed if it preserves important context.
5. **Relations**: At most one `romance`; `party` reflects the recurring group; avoid nickname/possessive artifacts as characters.
6. **Items & Spells**: Canonical tokens in `@I`; spells present in passage → present in `@S` and referenced in beats.
7. **Beat quality**: Each beat should be meaningful. Prose descriptions help preserve narrative flow.

If any check fails, **repair your block** and re-run the rubric. Return only the final JSON."""


def resolve_agentic_compression_runtime(
    mode: str = "agentic", provider: str = None
) -> Dict[str, Any]:
    """Snapshot the provider/config/prompt identity used by one T084 call.

    The snapshot is shared with the outer cache so a provider switch cannot
    cause a response from one provider to be stored under another provider's
    cache key.
    """
    if provider is None:
        from model_config import get_provider

        provider = get_provider()

    configs = {
        "openai": config.AGENTIC_COMPRESS_GPT54MINI_NONE,
        "gemini": config.AGENTIC_COMPRESS_GEMINI_PRO_LOW,
        "lmstudio": config.AGENTIC_COMPRESS_LMSTUDIO,
        "legacy": config.AGENTIC_COMPRESS_LEGACY,
    }
    provider_config = dict(configs.get(provider, configs["legacy"]))
    return {
        "callsite": "T084",
        "provider": provider,
        "config": provider_config,
        "mode": mode,
        "temperature": 0.1,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
    }

def validate_block_text_minimal(t: str) -> List[str]:
    """Minimal validation - relaxed for prose-enhanced beats"""
    errs = []
    
    # Check for exactly one EVT block
    if t.count("EVT[") != 1:
        errs.append("NOT_ONE_EVT_BLOCK")
    
    # Basic format check - tables present
    if "@C=" not in t or "@L=" not in t:
        errs.append("MISSING_REQUIRED_TABLES")
    
    # Allow prose in beats - just check basic structure
    evt = re.search(r"EVT\[(.*)\]", t, flags=re.S)
    if evt:
        for line in [x.strip() for x in evt.group(1).splitlines() if x.strip()]:
            # Must start with "n) <marker>" and end with period
            # Allow any content between marker and period (including prose)
            if not re.match(r"^\d+\)\s+(?:@L\d+|->L\d+|<-L\d+)\s+.*\.$", line):
                errs.append("BEAT_MALFORMED")
                break
    
    # Relations can use shorthand format - no validation needed
    # Allow both shorthand (romance:(1,2)) and canonical (r1:(1 romance 2))
    
    # Spell checking is relaxed - just ensure if @S exists, spell is mentioned somewhere
    
    return errs

def compress_with_ai(
    narrative: str,
    canon: Dict[str, Any] = None,
    mode: str = "agentic",
    *,
    provider_snapshot: str = None,
    provider_config: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Compress narrative text using GPT-4.1-mini with agentic approach
    
    Args:
        narrative: The raw narrative text to compress
        canon: Optional existing canon with codebook and blocks
        mode: "agentic" for flexible beats, "strict" for minimal beats
        
    Returns:
        The AI's compression response as a dictionary
    """
    
    # Prepare the payload
    if canon is None:
        canon = {
            "codebook": {"C": {}, "L": {}, "S": {}},
            "blocks": [],
            "next_seq_by_location": {}
        }
    
    payload = {
        "CANON": canon,
        "PASSAGE": narrative,
        "CONFIG": {
            "mode": mode,
            "max_chars": 12,
            "max_locs": 12,
            "min_party_size": 3,
            "min_party_occurrences": 2
        }
    }
    
    runtime = resolve_agentic_compression_runtime(mode, provider_snapshot)
    provider_snapshot = runtime["provider"]
    compress_config = dict(provider_config or runtime["config"])

    max_retries = 1  # Keep retries minimal for agentic approach
    
    for attempt in range(max_retries + 1):
        try:
            # Build messages
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)}
            ]
            
            # If this is a retry, add minimal feedback
            if attempt > 0:
                messages.append({"role": "user", "content": json.dumps({
                    "instruction": "Re-emit fixing the format issue. Ensure exactly one EVT block."
                })})
            
            response = capture_and_fanout("T084", api_client.create_completion,
                _request_provider=provider_snapshot,
                messages=messages,
                model=compress_config["model"],
                temperature=runtime["temperature"],
                **{k: v for k, v in compress_config.items() if k != "model"})
            
            # Track token usage
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass  # Silently ignore tracking errors
            
            # Extract and parse the response
            ai_output = response.choices[0].message.content
            
            # Strip markdown formatting if present
            if ai_output.startswith("```json"):
                ai_output = ai_output[7:]  # Remove ```json
            elif ai_output.startswith("```"):
                ai_output = ai_output[3:]  # Remove ```
            if ai_output.endswith("```"):
                ai_output = ai_output[:-3]  # Remove trailing ```
            
            result = json.loads(ai_output.strip())
            
            # Minimal validation - just check structure
            if result and "blocks" in result and result["blocks"]:
                block_text = result["blocks"][0].get("text", "")
                violations = validate_block_text_minimal(block_text)
                
                if violations:
                    if attempt < max_retries:
                        print(f"Format issue detected: {violations}, retrying...")
                        continue
                    print(f"ERROR: Compression remained invalid: {violations}")
                    return None
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse AI response as JSON: {e}")
            if attempt < max_retries:
                continue
            return None
        except Exception as e:
            print(f"ERROR: API call failed: {e}")
            return None
    
    return None

def extract_compressed_text(ai_response: Dict[str, Any]) -> str:
    """Extract just the compressed text from the AI response"""
    if not ai_response or "blocks" not in ai_response:
        return ""
    
    blocks = ai_response.get("blocks", [])
    if not blocks:
        return ""
    
    # Return the text from the first (and likely only) block
    return blocks[0].get("text", "")

def post_merge_duplicates(text: str) -> str:
    """Optional: Post-process to merge exact duplicate beats"""
    lines = text.split('\n')
    result = []
    seen = set()
    
    for line in lines:
        # Skip if exact duplicate beat (same marker, action, with:)
        if line.startswith(tuple('0123456789')) and line in seen:
            continue
        seen.add(line)
        result.append(line)
    
    return '\n'.join(result)

def main():
    # Built-in test narrative (same as before)
    NARRATIVE = """Beneath the somber skies that perpetually shrouded Marrow's Rest, the Black Lantern Hearth flickered like a solitary beacon against the encroaching gloom. Here, the adventurers--Eirik, known among close friends as Trouble Magnet for his uncanny knack for calamity, the lithe scout Kira whose spirit flickered like the black flame of the lighthouse itself, the ever-watchful Elen with her hawk's gaze, and the steady, unyielding Thane--began and returned repeatedly, their lives entwined with the village's fate and each other's.

Their first emergence from the Hearth was a passage marked by foreboding and quiet determination. The salty air clung to their cloaks as they ventured toward the Shroudwatch Garrison, the fortress rising grim and resolute amidst the fog. There, Brother Lintar, the quartermaster whose stoic demeanor belied a heart worn tender by years of war and watchfulness, greeted them with cautious warmth. He offered the battered remnants of the garrison's stores: studded leather armor that bore the faint scent of oiled leather and sweat, boots softened by countless marches, and weapons worn yet reliable. Kira, brushing a rebellious strand of hair from her face, chose gear that balanced protection with her nimble agility--a dark woolen cloak that whispered secrets with every movement, shortswords that gleamed faintly beneath the flickering torchlight, and a shortbow strung taut with hope. Elen's choices mirrored grace and precision, while Thane's quiet nod affirmed the trust growing between them.

The exchange was more than a transaction; it was a weaving of trust. Thane's steady voice advocated for Kira, insisting she be armed fairly after the indignities suffered under Grimjaw's cruel ownership. The quartermaster's acceptance of their modest gold, a token rather than payment, sealed an unspoken pact--this band of misfits would carry the village's hopes.

Returning to the Hearth, the tavern's smoky warmth enveloped them like a balm. Cira, the innkeeper with hands as deft at mending hearts as at pouring ale, offered steaming bowls of stew and mugs frothing with peat-scented ale. Kira exhaled a breath she had unknowingly held, the simple comfort of food and friendship rekindling her strength. Elen allowed herself a rare smile, the tension easing from her slender shoulders, while Thane's subtle grin hinted at cautious optimism. Here, among whispered laughter and flickering shadows, the party's bonds deepened--not merely comrades in arms but a family forged in shared trials.

Yet the Hearth was also witness to more intimate moments. Eirik settled beside Kira near the hearth's dying embers, his rough fingers entwining with hers in a silent vow to protect the fragile ember of her freedom. Their eyes met--no words needed--before a kiss, tentative and trembling, blossomed into a promise. Later, in the sanctuary of Eirik's chamber, armor clattering softly onto stone, passion ignited like a wildfire, their bodies speaking truths too deep for daylight. Kira's laughter, light and mischievous, chased away the shadows that clung to her like a second skin, while Eirik's whispered assurances wove a cocoon of safety around them both.

At dawn, the tavern's hearth glowed anew, and over porridge fragrant with peat and honey, laughter rippled among the four. The fragile peace was a shimmering thread amid the island's darkness, yet it steeled their resolve. Kira's gentle reassurances, Elen's sharp insights, Thane's quiet strength, and Eirik's daring leadership coalesced into a force ready to confront the cursed abbey ruins and the black-flamed lighthouse whose spectral light haunted the marshes.

Their path led once more to the Shroudwatch Garrison, where the clang of armor and murmur of vigilant soldiers greeted them like an old song. Here, Eirik's hands, calloused and sure, arranged the party's gear with methodical care. His ritual--a triple check of every blade and bowstring--was met with affectionate eye-rolls from Elen and a smirk from Kira, who nicknamed him "Gear Warden" in jest. Before stepping into the mist, Eirik wove the Aid spell twice, a radiant glow suffusing their forms, bolstering flesh and spirit alike. Thane, usually stoic as a mountain, allowed himself a rare, grateful smile that warmed the chill settling over them.

The garrison's stone walls offered a brief sanctuary where each found moments of quiet reprieve. Kira sharpened her shortswords with a practiced hand, her brows knitting in concentration; Elen slipped into her elven trance, eyes half-closed as she communed silently with the spirits of the forest; Thane tested his bowstring with measured precision, muscles taut but calm. In these hushed intervals, the silent language of glances and shared breaths spoke volumes--fears unspoken, hopes nurtured, and the faintest stirrings of something tender and unyielding.

Yet the island's shadow was relentless. Back at the Black Lantern Hearth, Grimjaw's one-eyed gaze bore into them like a sharpened blade, a reminder of debts unpaid and chains yet to be broken. The tavern's smoky air thickened with tension, but the party's unity was a shield against despair. Cloaks pulled tight, weapons readied, they slipped once more toward the garrison's embrace, the cold stone fortress standing as a bulwark against the unknown.

Within the garrison's austere walls, the familiar presence of Brother Lintar and the quiet hum of readiness grounded them. The flickering torchlight cast long shadows that danced along the stacked weapons and polished armor, a testament to vigilance and sacrifice. Here, the party found strength not only in steel and spell but in each other. Kira's hand brushed briefly against Eirik's as they passed, a spark igniting beneath the surface of shared danger. Elen's keen eyes softened when she caught Thane's steady gaze, a silent promise that no darkness would sever their bond.

Their final passage through the village streets, veiled in mist and silence, was a procession of resolve. The Black Lantern Hearth's hearthfire glowed faintly behind them, a last flicker of warmth before the unknown. As they crossed once more into the garrison's guarded walls, the weight of the island's curse settled upon their shoulders--but so too did the unbreakable strength of their fellowship.

In the stillness of those stone halls, amid the whispered prayers and the faint scent of burning pine, the adventurers braced themselves. Ahead lay the haunted abbey ruins, the cursed lighthouse whose black flame licked at the edges of sanity, and the spectral horrors that prowled the marshes. Yet within their hearts burned a fiercer light--love forged in stolen kisses by firelight, trust born of shared hardship, and a fierce hope that even in the deepest shadow, dawn would come.

Thus, the tale of Marrow's Rest unfolds--a saga not merely of monsters and magic but of human frailty and fierce devotion, of whispered promises and desperate embraces. The black flame may flicker ominously, but the bonds forged in the Black Lantern Hearth and tempered in the Shroudwatch Garrison will light the way through darkness yet to come."""
    
    # Prefer stdin if it has content
    try:
        data = sys.stdin.read()
    except Exception:
        data = ""
    
    text = data if data and data.strip() else NARRATIVE
    
    print("Calling GPT-4.1-mini with agentic approach...")
    print("-" * 60)
    
    # Call the AI with agentic mode
    result = compress_with_ai(text, mode="agentic")
    
    if result:
        # Extract the compressed text
        compressed_text = extract_compressed_text(result)
        
        # Optional: post-merge exact duplicates
        compressed_text = post_merge_duplicates(compressed_text)
        
        # Print the compressed output
        print(compressed_text)
        
        # Save full response for analysis
        with open("ai_compression_agentic_response.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        
        # Save just the compressed text for comparison
        with open("ai_compression_agentic_output.txt", "w", encoding="utf-8") as f:
            f.write("AI NARRATIVE COMPRESSION OUTPUT (GPT-4.1-mini Agentic)\n")
            f.write("=" * 60 + "\n\n")
            f.write(compressed_text)
            f.write("\n\n" + "=" * 60 + "\n")
            f.write(f"Original length: {len(text)} chars\n")
            f.write(f"Compressed length: {len(compressed_text)} chars\n")
            if len(text) > 0:
                f.write(f"Reduction: {(1 - len(compressed_text)/len(text))*100:.1f}%\n")
        
        print("\n" + "-" * 60)
        print(f"Saved AI response to: ai_compression_agentic_response.json")
        print(f"Saved compressed text to: ai_compression_agentic_output.txt")
        
        if len(text) > 0:
            print(f"Original: {len(text)} chars -> Compressed: {len(compressed_text)} chars")
            print(f"Reduction: {(1 - len(compressed_text)/len(text))*100:.1f}%")
        
        # Print validation info if present
        validation = result.get("validation", {})
        if validation.get("errors"):
            print("\nValidation errors:", validation["errors"])
        if validation.get("warnings"):
            print("Validation warnings:", validation["warnings"])
    else:
        print("ERROR: Failed to get compression from AI")

if __name__ == "__main__":
    main()