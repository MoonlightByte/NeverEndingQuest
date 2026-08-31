# Issue #210 follow-up — two player-stream defects (wrong-location resume; notice absorbs a diagnostic line)

**Branch:** `travel-recovery-clean` · **Governing doctrine:** issue #193 v1.7 (live) · **Relates:** #210
· **Author:** Claude (OpenAI/WSL arm) · **Found by:** Codex native-Windows acceptance
(`docs/audits/2026-08-24-travel-recovery-windows-210-acceptance.md`, #210 comment)

> Status: **CONVERGED 5/5** (Architecture Custodian, Fail-Forward DA, Acceptance DA,
> Player-Experience DA, Legacy-Contract DA — zero blocking findings; FYIs folded below). Awaiting
> owner execution approval. Convergence completes review only (#193 Part 3).

---

## 1. The two OBSERVED defects (Codex native-Windows; both confirmed in code on my arm)

**Defect A — resume welcome-back narration states the STALE location.** After a #210 discard-boot
(party authoritatively at E05/Storage Vaults), the first DM turn's narration told the player they
were in **E03/Torture Chamber**. This directly contradicts the deterministic #210 notice (which
correctly says E05) — a jarring, player-visible falsehood. (The following ordinary turn rebuilt
correct E05 context; the defect is the resume narration.)

**Defect B — the #210 recovery notice absorbs a diagnostic line.** The headless `narration` event
for the notice included the trailing text `[SaveGameManager] INITIALIZATION: Validation prompt
loaded for both paths`. The notice reaches the right channel but is not a clean player message.

## 2. Root causes (CODE-PROVEN, my arm)

**Defect A.** On resume, boot injects a fixed DM note and T067 generates a "welcome back"
narration. The note (`main.py:613`, `check_and_inject_return_message`) tells the model to recap
"the immediate situation and surroundings" and that "the party is already at their current
location" — but **never states WHAT that location is** (no name/id/area). So T067 must *infer* the
current location from conversation history. On a discard-boot the history's operative location
context is the **stale interrupted-turn E03** (the discard path retires the checkpoint but does not
reconcile conversation history — `recover_pending_location_transition` only calls
`_remove_location_transition_checkpoint()`; the normal *resume* path completes the transition and
reconciles context, which is why untampered resume narrates correctly). Codex's T067 capture
confirms: authoritative E05 present as an early system projection, stale "Current location: Torture
Chamber (E03)" later in a retained user message, and the resume instruction did not restate the
authoritative location — so the model followed the later stale line.
- Injection: `main.py:557-617` `check_and_inject_return_message` (note body at `:613`).
- Call site: `main.py:6573` — `party_tracker_data` / `location_data` are in scope (authoritative
  location is available to inject).
- Per-turn location context IS embedded in the normal player-turn `dm_note` (`main.py:7183-7226`),
  but the **resume welcome-back note has no equivalent**.

**Defect B.** A single `print("Dungeon Master: …")` (`main.py:6378-6383`) OPENS a narration section
in both output routers (`web/web_interface.py:637`; `core/headless/classifier.py:142`); the section
is only flushed on the NEXT non-DM line or on `stdout.flush()`. The next startup line
(`[SaveGameManager] INITIALIZATION: …`) is not in either router's debug-marker list, so it is
appended into the open DM buffer and emitted as part of the narration. Both routers' `flush()`
(`web_interface.py:774`; `classifier.py:169`) call `_flush_dm_buffer()` and close the section.

## 3. The fix (minimal, additive — no history deletion, no new mechanism)

**Fix A — state the authoritative location in the resume note (input-boundary fix, AP-6 spirit).**
`check_and_inject_return_message` receives the authoritative current location (name + id + area,
sourced **only** from `party_tracker_data["worldConditions"]` via `.get()` — reuse
`get_location_data_from_party_tracker`, `main.py:620`, which returns `None` gracefully) and includes
it in the injected note, instructing the model to recap **THIS** location and treat it as current:

> "Dungeon Master Note: Resume the game, the player has returned. The party is currently at
> `{name} ({id})` in the `{area}` area — recap and narrate THIS location and situation; refer to the
> location by name in the narration; do not treat any earlier location in the history as current.
> Welcome the player back warmly. … (rest unchanged, incl. the party-acknowledgment, atmospheric
> recap, prompt-for-next-action, and the existing 'Do NOT use transitionLocation' guard)."

Requirements (reviewer-pinned):
- **Idempotency:** the phrase `"Resume the game, the player has returned"` MUST remain the leading
  substring (the re-injection guard at `main.py:587` matches it) — the authoritative sentence is
  inserted AFTER it, never before.
- **Authoritative snapshot:** build the location from the **post-recovery** party_tracker (the same
  authoritative worldConditions the #210 notice reads at `main.py:6361-6366`); the #210 discard does
  not mutate party_tracker, so the in-scope `party_tracker_data` reflects E05 — read it, not a stale
  pre-recovery copy.
- **Fall-forward:** use `.get()` throughout; if a location field is absent, OMIT the location clause
  and fall back to the current note verbatim — never index (`[...]`) / raise at boot.
- **`{name} ({id})` format is proven safe** (the per-turn `dm_note` at `main.py:7183-7205` already
  uses the identical construction and the id does not leak into player prose).

Rationale: give the model the authoritative fact as the LAST/operative statement (the note is
appended last, `main.py:615`) rather than letting it infer from contradictory history. Additive;
**preserves all accepted history** (no deletion — satisfies Codex's constraint + GL-1); **no-op on
already-correct resumes** (a correct resume already narrates the current location; naming it restates
a fact it was already going to narrate); reactive to the observed #210 discard defect (AP-5 citation
= #210 / Codex acceptance). Hardens ALL resumes against stale-history inference, not just discard.

**Fix B — flush the notice as a clean block (guarded).** After the #210 notice `print(...)`
(`main.py:6383`), flush so the DM section is emitted and closed before the next diagnostic line —
using the tree's existing guarded-flush pattern (`main.py:288`) so a broken/closed terminal pipe
cannot abort boot:
```python
try:
    sys.stdout.flush()
except (BrokenPipeError, OSError, ValueError):
    pass
```
Reuses the routers' existing `flush()` -> `_flush_dm_buffer()` path; no new mechanism. (Bare
`sys.stdout.flush()` was rejected: in terminal mode a closed downstream pipe would raise
`BrokenPipeError`, be caught by the boot `except` at `main.py:6398`, and `return` — aborting boot,
contradicting this handler's own "never engine_stop" B1 promise.)

**Explicitly NOT doing:** deleting/rewriting the stale interrupted-turn messages from
conversation history. That is higher-risk (GL-1: preserve accepted history) and unnecessary once the
authoritative location is the operative statement. Recorded as considered-and-rejected in §7.

## 4. Spec-pin

| Datum | Source of truth | Note |
|---|---|---|
| Authoritative current location | `party_tracker.json` worldConditions (name/id/area) | `party_tracker_data` in scope at `main.py:6573` (loaded `:6277`). NOTE: `location_data` is NOT in scope there — source location from `party_tracker_data["worldConditions"]` only (via `get_location_data_from_party_tracker`, `main.py:620`). |
| Resume welcome-back note | `main.py:613` (`check_and_inject_return_message`) | Fix A site. |
| Per-turn location context (working reference) | `main.py:7183-7226` `dm_note` | The pattern Fix A mirrors for the resume note. |
| Player narration channel | `Dungeon Master:` section -> `game_output`/`narration` (web `:637/:774`) / `narration` event (headless `:142/:169`) | Fix B relies on `flush()`. |
| Single-turn travel + T013->T063->T064 chain | #193 D-TRAVEL-2 / CLAUDE.md | Fix A must NOT alter the travel narration chain — it only names the current location in the resume note. |

**Player-experience promise:** Part 2 p9 — "a resumed game shows the player where they were";
resume narration must be truthful to disk (Player-Experience DA contract #7, truth-to-disk).

## 5. GL-1 (behavioral contract)

Both fixes are **additive** (insertions only; no deletion/replacement of branches/guards/ordering):
- Fix A: adds the authoritative location to an existing note string + threads the location value
  into `check_and_inject_return_message`. The existing note guidance (welcome, recap, no
  transitionLocation) is **PRESERVED verbatim**. Working-path prompt change -> AP-5 citation = #210
  observed defect; no-op on correct resumes (byte-behavior of correct resumes unchanged in outcome).
- Fix B: adds one `sys.stdout.flush()`. Removes nothing.
No deletions -> no GL-1 disposition table required beyond this statement; nothing RETIRED.

## 6. FS-1

Diff adds no `timeout`/`deadline`/`max_*`/`retries`/`sleep`/`wait_for`/bound of any spelling.
FS-1 = zero hits (reviewer re-greps the diff).

## 7. Acceptance (defined pre-code; MUST assert narration CONTENT — the gap that let this ship)

Real headless play, configured OpenAI, on a **clean official save** (Keep_of_Doom / Thornwood /
Pumpkin King — NOT Shadows_of_Frostmere), one operation at a time. My prior #210 acceptance passed
because it only checked on-disk location, NOT narration content — this plan fixes that.

**Gate (Defect A):** reproduce the discard-boot (kill@`movement_committed` E03->E01, tamper party
to E05, relaunch). **Assert on the resume welcome-back narration TEXT:**
- names the authoritative location (Storage Vaults / E05);
- does NOT claim the party is at the stale location (no "Torture Chamber"/E03 as current);
- consistent with the deterministic #210 notice (both say E05);
- verify against the captured request that the injected resume note now contains the authoritative
  "Current location" line (CODE + OBSERVED). **Capture selector:** the player-turn call is logged
  under `endpoint: "main_dm"` in `debug/api_captures/api_calls_master.jsonl` (NOT a literal `"T067"`
  key) — select the last `main_dm` record whose messages contain the resume note.

**Gate (Defect B):** assert the notice `narration` event content equals the notice sentence in its
**emitted form** (router strips the leading `Dungeon Master:` and `.strip()`s; `% here` is
interpolated) — and, stronger, that the trailing diagnostic line (`[SaveGameManager] INITIALIZATION:
…`) now appears on the **debug** stream and is ABSENT from the narration event (direct proof the
buffer closed). Assert in headless; spot in web (game pane).

**No-regression:** normal (untampered) resume still narrates the correct current location and
converges (kill@`movement_committed`, no tamper -> welcome-back names the real destination), and the
captured untampered request ALSO carries the new authoritative note line (confirms the general
hardening fired no-op). Clean boot with no interruption still welcomes correctly.

Evidence: commands + raw narration events + the captured T067 request messages, per claim.

## 8. Triage

**FULL** — touches a play-path prompt (resume narration) and the #210 startup handler; Player-
Experience DA standing (narration truthfulness). Panel: Architecture Custodian, Fail-Forward DA,
Acceptance DA, Legacy-Contract DA (GL-1, though additive), Player-Experience DA. Consumer/Compat
only if `check_and_inject_return_message`'s signature change affects other callers (single caller at
`main.py:6573` — verify).

## 9. Tracked follow-ups (Zero-Deferral)

- **F-B -> filed as #213 (CONFIRMED, OBSERVED on OpenAI):** boot runs a synchronous
  chronicle-compression backlog (11 sections, several `BEAT_MALFORMED` failures/retries) BEFORE the
  first prompt / leased-kickoff welcome-back, delaying reaching playable by minutes. Confirmed on a
  freshly-restored save (not test pollution). Orthogonal to #210; its own plan + review. During #210
  acceptance this only required a longer boot window; the game did reach the prompt once compression
  finished.
- **Gemma local-model compression output-parsing** (3/7 chunks `Failed to compress` with thinking
  off) — Codex's local-model matrix domain; separate from this fix.
- **Resume-note hotspot (Legacy-Contract DA):** `check_and_inject_return_message`'s note has now
  been content-edited across several commits for resume-narration symptoms (the `transitionLocation`
  guard `87c5f9d0`, and now this stale-location fix — distinct symptoms, so two-strikes is NOT
  tripped). A THIRD symptom-patch to this note would trip GL-1 two-strikes and demand a layer-down
  bisect (the resume-context assembly) rather than another sentence. Logged as a watch item.

## 10. Owner decisions

- **D-PS-1:** Fix A hardens ALL resumes (not just discard) by naming the authoritative location in
  the resume note. Confirm this general hardening is acceptable (it is reactive to #210 and no-op on
  correct resumes). Author recommends YES.

## 11. Resolution ledger

| # | Finding | Round | Resolution |
|---|---|---|---|
| (seed A) | Resume welcome-back narrates stale E03 vs authoritative E05 (Codex) | 0 | Fix A: authoritative location in resume note. |
| (seed B) | #210 notice absorbs `[SaveGameManager] INITIALIZATION` line (Codex + my own under-asserted run) | 0 | Fix B: `sys.stdout.flush()` after notice. |
| (seed) | Prior #210 acceptance checked on-disk only, not narration content | 0 | §7 now asserts narration TEXT + captured request. |
| R1-1 (Fail-Forward, FYI) | Bare `sys.stdout.flush()` could raise `BrokenPipeError` in terminal mode -> caught by boot `except` -> aborts boot (violates handler's "never engine_stop"). | 1 | FIXED. §3 Fix B pins the guarded `try/except (BrokenPipeError, OSError, ValueError): pass` form (`main.py:288` pattern). |
| R1-2 (Custodian + Fail-Forward, FYI) | Plan cited `location_data` as in-scope at `main.py:6573`; it is not. | 1 | FIXED. §3/§4 source location from `party_tracker_data["worldConditions"]` only (via `get_location_data_from_party_tracker`), `.get()`/degrade-to-omit. |
| R1-3 (Acceptance, FYI) | Capture is labeled `endpoint:"main_dm"`, not `"T067"`; selector ambiguous. | 1 | FIXED. §7 selects the last `main_dm` record containing the resume note. |
| R1-4 (Acceptance, FYI) | Defect-B exact-match must use emitted (stripped/interpolated) form; add diagnostic-routes-to-debug assertion. | 1 | FIXED. §7 asserts emitted form + diagnostic on debug/absent from narration. |
| R1-5 (Legacy-Contract, FYI) | Idempotency guard (`main.py:587`) needs the leading substring preserved. | 1 | FIXED. §3 requires `"Resume the game, the player has returned"` stays the leading substring. |
| R1-6 (Player-Experience, FYI/taste) | Insulate against id-in-prose on the contradict-stale case. | 1 | Applied: §3 note adds "refer to the location by name in the narration." |
| R1-7 (Player-Experience, FYI) | Note must be built from post-recovery authoritative party_tracker snapshot. | 1 | FIXED. §3 pins the post-recovery snapshot requirement. |
| R1-8 (Legacy-Contract, FYI) | Resume note is a hotspot; a 3rd symptom-patch trips two-strikes. | 1 | Logged as §9 watch item. |

**Round-1 result:** all 5 required reviewers CONVERGED with zero blocking findings; the 8 FYIs
above are folded in (wording precision + the guarded-flush hardening). No fix-substance change that
warrants re-dispatch (the guarded flush is the Fail-Forward DA's own prescribed one-line remedy).
Plan is converged and ready for owner execution approval.

## 12. Execution & acceptance results (OBSERVED — real headless play, OpenAI/WSL)

**Implemented** on `travel-recovery-clean` (uncommitted): `main.py` only (+47/-6). Fix A
(`check_and_inject_return_message` gains `location_note`; call site builds the authoritative clause
from `party_tracker["worldConditions"]` via `.get()`, degrade-to-omit) + Fix B (guarded
`sys.stdout.flush()` after the #210 notice). Empty `location_note` reproduces the original note
byte-for-byte; compiles; idempotency substring preserved.

### Acceptance — ALL PASS (Keep_of_Doom, configured OpenAI)
- **Fix A, deterministic (party=E05, E03-centric history, clean boot):** welcome-back narrated
  *"You find yourself once more in the Storage Vaults, deep within the Cursed Dungeons"* — authoritative
  E05, not the stale Torture Chamber. Captured resume note carried
  *"The party is currently at Storage Vaults (E05) … refer to the location by name …"*.
- **Full constructed discard-boot (party=E05 + v2 checkpoint origin=E03/dest=E01 phase=movement_committed
  -> blocked):** blocked breadcrumb fired; checkpoint retired; reached the playable prompt; produced
  BOTH the clean #210 notice ("… you remain where the party actually stands - Storage Vaults …") AND
  the welcome-back ("Welcome back. You find yourself once more in the Storage Vaults …"). Gate A
  (welcome-back names Storage Vaults / avoids Torture Chamber) and Gate B (notice clean; no
  `[SaveGameManager]` absorbed; diagnostic routed to the debug stream) both PASS.
- **Fix B independently:** the #210 notice `narration` event is exactly the notice sentence; the
  trailing `[SaveGameManager] INITIALIZATION` line appears on the debug stream, absent from narration.

### Observation carried out of acceptance -> filed
Reaching the prompt on the discard-boot required a long window because boot ran a **synchronous
chronicle-compression backlog** ("Processing 11 sections … Active compression is required", several
`Failed to compress … BEAT_MALFORMED, retrying`) BEFORE the leased-kickoff welcome-back. This is the
§11 F-B item, now CONFIRMED on OpenAI (not test pollution — it is the save's accumulated history with
compressor failures) and orthogonal to the #210 fix. Filed as a separate issue (see §11).

**Status: IMPLEMENTED + ACCEPTANCE ALL PASS. Not committed/pushed (awaiting owner go).**
