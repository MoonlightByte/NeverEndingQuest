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
relationship state + complete relevant evidence, own working memory, utilities/items/goals,
and location.

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
All are code-selected by relevance and authority, with NO character truncation:
- E1 recent-scene window: accepted DM/player beats available to the current scene.
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

## 8. Fork rulings (owner, 2026-08-31 - after the first panel round hard-stop)
- FORK 1 = (a): RETIRE the legacy (T045) combat pipeline as a runtime. Typed/agentic
  combat is the ONLY combat runtime; old saves/legacy-provenance encounters adapt
  FORWARD via data migration on the live path. Now a #193 Part 5 ratified ruling
  (v1.9). Retirement is its own #193-planned change; the voice wave must not build
  new behavior on the legacy path.
- FORK 2: persist the immutable combat voice map inside the EXISTING combat
  transaction record so crash recovery replays the same advice (no new store).
- FORK 3: voice-call failure policy - never block the game; a failed T105/T112 call
  degrades AT MOST that one beat, is logged loudly + surfaced in telemetry, and the
  next beat retries fresh. Silent permanent degradation is a defect. Now a #193
  Part 5 ratified ruling (v1.9).
- FORK 4: this wave stays scoped to the voice path + directly-touched combat files.
  The additional caps found (episodic storage, combat compression/prompts, web TTS)
  are tracked on issue #262 for a separate systematic retirement.

## 9. Second-panel rulings (owner, 2026-08-31: "b / yes / bless")
- D-VR-13 = (b): NO legacy freeze fiction. Phase A upgrades the ONE shared T105 stack
  and legacy T045 legally INHERITS the improvements through its existing seams until
  retirement (Phase B). Pinning/copying an old voice stack for legacy stays banned.
  Recorded as amendment D-VR-13b on the #193 v2.0 legacy-retirement ruling.
- D-VR-14 = YES, in-wave: minimal structural worker-lifecycle fix - causal fencing
  (every voice/recall result stamped with its beat/Load authority id; stale rejected -
  closes the voice half of #256) + reap-and-reissue so a stuck provider call can never
  permanently occupy a worker (B2-iii structural liveness; no deadlines, no new store).
- D-VR-15 = BLESSED: T097 completed-invalid bounded-retry-then-generic-fallback is now
  a ratified B2-iv class in #193 v2.0 Part 5 (post-commit narration only; mechanics
  already committed; failure surfaces via Fork-3 telemetry).

## 10. Round-batch combat ruling (owner GO, 2026-09-01)
Owner corrected the combat architecture and ruled GO on the round-batch design after
the latency facts (C:\vra-evidence\voice_repair_latency\C6_LATENCY_FACTS_AND_ROUND_
BATCH_SKETCH.md): combat is ONE round-loop - all NPC voices fire in PARALLEL after
the accepted player input (so voices SEE the fresh order - the prefetch/responsiveness
fork is dead), collected completion-bounded under #193 v2.1 B2(vi) (new clause:
waiting for completion is not a timeout), then ONE T096 round adjudication with
explicit adjust-if-stale authority, resolve, persist map in the transaction, one T097.
Measured cost: +3.2-3.5s median (2-4 parallel voices) on a 9.6s median round.
Side rulings: empty/whitespace submit lock RESTORED at UI+engine source; resumed
combat may omit voices in its first round; luna|none confirmed (p50 2.9s across all
29 recorded behavior calls).
