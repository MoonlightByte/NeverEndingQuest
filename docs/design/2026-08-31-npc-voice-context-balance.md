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

## 10. Phase-A implementation boundary

E3 is the first request-local reuse seam for the future memory-offload direction:
one attributed T112 selection may feed both the focal T105 packet and the later DM
context rebuild. It adds no model call and does not yet remove canonical memory from
the DM. T105/T112 provider lifetimes are individually registered beneath the exact
live-turn operation and beat, are sealed at the semantic consumer boundary, and are
reaped by their task-owned monitors. Late results are rejected rather than carried
into another beat.

## 11. Direct combat no-limits train (GL-1)

The combat request and narration context now preserve every selected record and its
complete strings. This retires character budgets; it does not remove semantic
selection. T096 still selects exact actor-window facts, owned capability records, and
at most the established number of whole SRD references. Narration still receives the
typed dossier and authoritative committed events.

| Retired guard | Preserved protection |
|---|---|
| T096 candidate, encounter, capability, and spell-index character budgets | exact actor ownership, complete-record selection, canonical capability matching, and the existing SRD reference-count selection |
| T097 dossier string/list truncation | private-key filtering plus the typed dossier fields and committed-event authority |
| T097 retry-candidate truncation | the existing completed-invalid attempt count and full violation-code records |
| `900 + 650 * events` prose rejection | event coverage/order, mechanics-invention, hidden-information, perspective, and exact event-ID checks |
| player action, clarification, and DM-request character slices | the existing last-eight complete exchange retention and exact pending-turn ownership |
| `historyInput` and `displayPrefix` character slices | stable delivery IDs, committed-event receipts, durable history acknowledgement, and replay identity |
| persisted narration-candidate character slices | the existing at-most-twelve complete attempt receipts and typed violation/warning codes |

This train does not alter the compression, episodic-storage, or web-TTS caps owned by
#262.
