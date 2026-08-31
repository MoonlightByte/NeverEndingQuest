# NPC Voice Context Balance - owner direction record (2026-08-31)

Branch: integration/npc-voice-episodic. Status: DESIGN RECORD + probe scope. This
captures the owner's balance direction so it is not lost; implementation follows the
probe-first cycle and the #193 v1.8 loop (No-Limits + Single-Path sentinels standing).

## 1. Model facts (verified in model_config.py:951,988-996)
- T105 voice + T107 profile both call **gpt-5.6-luna, reasoning_effort="none"**
  (NPC_VOICE_T105_OPENAI_LUNA_NONE / NPC_PROFILE_T107_OPENAI_LUNA_NONE).
- Luna = cheapest tier (~$0.20 in / $1.20 out per 1M). At effort "none" it is a fast
  pattern-follower, not a deep reasoner: packets must be STRUCTURED and selective, and
  the probe should A/B effort none vs low once packets are enriched to find the floor
  that holds voice quality.

## 2. What the T105 packet contains today (validated 2026-08-31)
Identity/personality/relationship-with-player are solid: full T107 profile, NPC<->player
relationship state + top-3 evidence, own working memory, utilities/items/goals, location.

## 3. The isolation gaps (owner-confirmed direction: close them, balanced)
1. NO recent conversation window - scene.recentEvents is hardcoded []; the NPC hears
   only the current input + one prior accepted beat. It cannot hear what the DM just
   narrated.
2. Companions are names only - no NPC<->NPC relationship state, no awareness of what
   other present companions just said/did.
3. Episodic recall does NOT reach T105 - recalled episodes (already computed per-NPC)
   feed only the DM context block, so the speaking NPC is blind to its own ledger.
4. The player is thin - name + relationship only; no visible condition.

## 4. The four probe-scoped enrichments (owner: "fold those four in")
All selection-based (ranked/top-N picks); NO character truncation (banned, #193 v1.8):
- E1 recent-scene window: last few accepted DM/player beats.
- E2 companion visible acts: what other present companions just visibly said/did.
- E3 recalled episodes routed INTO the T105 packet (reuse the per-NPC recall already
  computed for the DM block - no new calls).
- E4 NPC<->NPC relationship state for present companions.
Probes A/B enriched vs current packets on real luna and show the narration difference
BEFORE anything ships. "We'll need to find the right balance" - the probe is the
balancing instrument.

## 5. DM authority line (owner-required, goes in the DM system prompt / advisory block)
The DM must be told explicitly: the NPC voice comes from a LIMITED-CONTEXT micro call;
the DM has AUTHORITY to take it as input but override and change it consistent with the
actual story, using the DM's full contextual history and memory. This balances the
NPC's unique micro-call voice against the DM's complete view. (Extends the existing
"you own final narration, mechanics, and actions" wording with the limited-context
rationale.)

## 6. Future direction (owner's thinking, NEEDS MORE DEVELOPMENT - do not build yet)
Once the balance above is proven: STOP passing the NPC memory system + affinity data
into the DM context each pass (the canonical companion-context block), and offload
that knowledge to the luna micro calls instead - the DM would then receive it distilled
through each NPC's voice rather than raw. Goal: save main-DM context tokens per turn
while keeping companion fidelity in the micro layer. This inverts today's flow (today:
memory -> DM block + thin voice packet; future: memory -> rich voice packet only, DM
gets the voices). Requires the E1-E4 balance to land first and its own #193 loop.

## 7. Standing constraints
No char/token caps anywhere (No-Limits Sentinel); one live path (Single-Path Sentinel);
agentic-first; probes are development aids - acceptance stays real headless play judged
on DM narration fidelity of the fed voice data.
