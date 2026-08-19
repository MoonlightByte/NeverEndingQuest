# Plan — Episodic Memory: Close Capture Gaps + Summary Backfill + Seamless Upgrade

**Status:** proposed v2 (re-scoped after independent review + a compression-cycle audit).
**Supersedes:** the v1 "backfill from raw archives" premise, which review proved false.
**Relates to:** `docs/design/companion-episodic-memory.md`.

## Why v1 was wrong (established by review + audit)

- The permanent archives (`modules/campaign_archives/*`) store **compressed** per-location summaries,
  not raw turns; the `Party NPCs:` presence stamp survives in ~**4% of segments (12/267 measured)**.
  Backfilling raw memory from archives is not possible — the raw journey isn't there at rest.
- Worse, a **rolling/incremental compressor destroys raw turns DURING live play, before the current
  location even closes** — so the shipped Phase-1 location-close hook already misses beats. Details:
  - `core/ai/incremental_compression.py` (`IncrementalLocationCompressor`), triggered ~every 15
    turn-pairs via `save_conversation_history` (`main.py:4536-4544`, ~27 callsites): collapses all but
    the last 5 raw pairs of the **still-open** location into `[SUMMARY OF EVENTS...]`. Long locations
    lose their early raw beats before `compress_conversation_history_on_transition` runs.
  - **Combat** raw turns live only in `combat_conversation_history.json`; at combat exit
    (`combat_manager.py:1811 summarize_dialogue`, T041) they become a single `[COMBAT CONCLUDED]` prose
    summary in main history. Near-death / heroism (the highest-salience beats, and the "you almost
    died" acceptance beat) are never seen by the location-close capture.
- So the fix is not "backfill harder from archives" — it is **capture at the true last-raw moment
  going forward**, and **seed old games from the summaries we do have** (lossy).

## Part 1 — Close the forward capture gaps (highest value; fixes a real miss + R8)

Hook episodic capture at every point that is about to destroy raw turns, so nothing is lost:

1a. **Rolling incremental compression.** In `core/ai/incremental_compression.py`, BEFORE
`apply_compression_to_list` replaces the current location's raw pairs, run per-companion capture on the
raw pairs being compressed. Gated, offloaded, fail-open, non-mutating. Coordinate: the SAME location
(`currentLocationId`) + a within-location sub-position (e.g. `close-{N}.roll-{k}`) so multiple rolls at
one location, and the final location-close, all yield distinct-but-stable episodeIds, idempotent.
1b. **Combat.** At combat exit (`combat_manager._finalize_combat_exit`), run capture over the raw
`combat_conversation_history.json` (present companions from the combat roster `creatures[]` — an
authoritative presence source, better than the stamp). This captures near-death/heroism directly and
**delivers the deferred R8 near-death** (HP-threshold beats become `near_death` salient facts).
1c. Keep the existing location-close hook (it still catches the final/last-5 raw pairs + short
locations). All three feed the same idempotent `capture_location_episode`/`commit_episode`.

Net: forward play now captures long-location beats + combat beats, not just short locations. This is a
correctness fix to the shipped feature, independent of any backfill.

## Part 2 — Summary-derived backfill for old games ("from what we have")

For a game with existing history but no episodes, recover the big beats from the compressed record:
- New `core/npc/episode_summary_backfill.py`: read each `modules/campaign_archives/*` LOCATION SUMMARY
  block + the per-module `modules/campaign_summaries/*_summary_*.json` saga prose.
- A dedicated agentic extractor (new callsite, luna) reads the SUMMARY prose and returns attributed
  core memories, INFERRING presence from the prose (which companions are named as present) — NOT the
  absent stamp. Reconcile-by-code: keep a fact only if its named companion resolves to a party
  identity; drop otherwise.
- Distinct provenance + coordinate: `derived_from="summary_backfill"`, boundary
  `summary-{module}-{seq}-{loc}` so summary episodes NEVER collide with live raw-captured episodes
  (different coordinate space) — no dedup fight with Part 1.
- Honestly lossy: no raw dialogue, mechanical combat flattened, presence inferred not stamped. Recovers
  "the party defeated X; Kira nearly died; Eirik gave Kira the charm" — the journey's peaks, not every
  micro-moment. Surface this to the player honestly in the UX.

## Part 3 — Seamless upgrade UX (progress-screened, resumable, 100% backward compatible)

- **First-run detect** (once per load, at the single seam `main.py:~5533` in `main_game_loop`, which
  covers BOTH web + terminal since web runs the same loop): if `NPC_VOICE_ENABLED` and the game has
  history and the upgrade marker is not `complete`, run the upgrade. Store the marker + resume state
  **inside the ledger** (or add it to the save `state_manifest`) so save/restore stays consistent
  (review gap B1).
- **Progress screen:** reuse the existing full-screen progress-bar widget — `combat_compressor.py`
  emits `compression_progress {completed,total}`, forwarded by `web_interface.py:480`, rendered as a
  filling bar (`game_interface.html:5715`). Emit a **distinct** event trio (not `compression_*`, to
  avoid the compaction widget collision) with a real `completed/total` fraction. Terminal path: a text
  progress line. Gameplay is paused with LIVE progress (SocketIO threading mode) — call it that, not
  "non-blocking."
- **Steps:** migrate sidecar (on-load, additive) → create ledger → run summary-backfill (Part 2) with
  the bar → mark complete. Allow **Skip** (resume next load). Honest final note if little was recovered.
- **Fail-open decision (resolve the review contradiction A1/B3):** do NOT hard-block the game if the
  store is read-only. On a genuinely unmigratable sidecar, log LOUD (record_store_health) and DISABLE
  the episodic feature for the session (fail-open, game still plays) rather than `assert_store_writable`
  aborting startup. `assert_store_writable` stays a diagnostic/dev tool, not a player-facing gate.

## 100% backward-compatibility guarantees (assert in tests)
- Upgrade/backfill/capture write ONLY under `data/companion_memories/` (verified). Never touch
  conversation_history, party_tracker, character sheets, module files, campaign summaries, or archives
  (read-only). Byte-for-byte assertion on all pre-existing game files after a full upgrade.
- Flag off → nothing runs. Any failure → fail-open, game proceeds.
- Save/restore: new files manifest-fingerprinted; old saves without them still validate.

## Phases (sequence-only; each headless-validated on real data)
- **U1 — combat capture (Part 1b).** Highest value: near-death/heroism + R8. Gate: a real fight →
  near_death salient facts land for the near-dying companion; idempotent; existing files untouched.
- **U2 — rolling-compression capture (Part 1a).** Gate: a long location (>15 pairs) → early beats
  captured before incremental compression eats them; distinct idempotent sub-position ids.
- **U3 — summary backfill (Part 2).** Gate: run on real Keep_of_Doom summaries → core memories with
  prose-inferred presence; distinct coordinate; no collision with live episodes; files untouched.
- **U4 — upgrade UX (Part 3).** First-run detect + progress bar + resumable + fail-open store decision.
- **U5 — end-to-end on a real existing game.** Load → progress → backfill → companions remember the
  peaks → 100% compat (files untouched, save/restore valid, flag-off no-op, interrupt resumes).

## Risks
1. **Part 1 touches the hot path** (save_conversation_history, combat exit) — must be offloaded,
   fail-open, non-mutating, like the location-close hook. Careful placement + headless proof.
2. **Summary backfill fidelity** is inherently lower; set player expectations honestly.
3. **Coordinate discipline:** rolling/combat/location/summary captures must use distinct-but-stable
   sub-coordinates so they neither collide nor duplicate. Prove idempotency per source with a test.
