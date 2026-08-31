# Issue #210 — Startup fail-forward on an un-appliable interrupted transition

**Branch:** `travel-recovery-clean` (off `origin/main` 691b5a2f) · **Governing doctrine:** issue #193 v1.7
(fetched live 2026-08-24) · **Fixes:** #210 · **Author:** Claude (OpenAI/WSL arm)

> Status: **CONVERGED (6/6 reviewers) -> owner-approved (D-210-1 fail-forward; D-210-2 narration
> register) -> IMPLEMENTED -> ACCEPTANCE ALL PASS.** See §13 Execution & acceptance results.
> Not yet committed/pushed (awaiting owner go).

---

## 1. The observed failure (OBSERVED, #210)

At startup, when `recover_pending_location_transition` returns `status: "blocked"` (the party's
authoritative location matches **neither** the interrupted transition's origin **nor** its staged
destination), the startup handler fail-**closes by stopping**:

`main.py:6354` (current):
```python
if pending_transition_recovery.get("status") == "blocked":
    error("FAILURE: Startup stopped because an interrupted location "
          "transition does not match authoritative party state",
          category="location_transitions")
    return          # -> main_game_loop returns -> engine_stop
```

Result: the engine exits cleanly (no crash), but:
1. The game **does not boot into a playable state** — it stops.
2. The reason is written **only to the log**, never to the player-facing stream.
3. **No recovery / Load path** is offered.

Reproduced (artificial tamper, per #210) on `travel-recovery-clean` @ `d42ebdf8`, Keep_of_Doom:
kill at `movement_committed`, set `party_tracker.currentLocationId` to differ from the checkpoint's
`destination_location_id`, relaunch -> `engine_stop`.

## 2. Why this is out of policy (CODE-PROVEN against #193)

- **B1 (fail-forward / fail-closed boundary).** "Fail-forward everywhere the player can feel it
  (play, save, LOAD — never refused —, build, reset). Fail-closed is legal ONLY at an un-committed
  mutation boundary, its result is a NO-OP that leaves the game playable ... Refusal is delivered
  as narration, never a system error or frozen session." Startup-boot is **not a mutation
  boundary**, and `engine_stop` is a **frozen session**, not a playable NO-OP. Both halves of B1
  are violated.
- **Part 2 p11 (Provider routing & startup).** "Startup/char-creation is a play path under B1."
- **Part 2 p9 (Save/restore).** "Loading a save is NEVER refused (B1's hardest guarantee)"; a
  resumed game "shows the player where they were ... never a blank screen (#79, #116)." Current
  behavior offers no Load and shows nothing.
- **AP-3 (refusal gates on play paths).** Grep trigger names `return`/refuse inside `recover*`/load
  paths bricking play on residue. This is that pattern exactly.
- **Leanness test #3 (net-negative recovery) / scar #167.** The canonical over-engineering
  breakage in this repo is *a recovery gate that bricks player startup*. Leaving the un-appliable
  checkpoint on disk means it re-blocks **every** subsequent boot — a permanent brick, strictly
  worse than the unrecovered failure. This is #167 in miniature.

**There is no corruption to protect against.** `party_tracker.json` is the authoritative record of
movement (recover()'s own docstring: "Movement itself is authoritative in party_tracker.json";
Part 2 p2 "disk is truth"). The party is at a real, valid location; the checkpoint is un-appliable
**residue**. Booting at the authoritative location is playing from truth, not from corruption. The
"stop" buys nothing (the double-move it prevents is already prevented — the checkpoint is never
applied) and costs the entire session. Textbook AP-3.

## 3. Doctrine disposition of the "owner design decision"

#210 framed stop-vs-boot as an owner design decision. My position (for owner ratification):
**B1 already decides it** — a play path may not stop or freeze; it fails forward. The owner's role
is to **approve the fix**, not to re-open whether a play path may brick. The one genuinely adjacent
OPEN item is **Part 5 D-7** (should *detected corruption* fail-closed *before mutation*). D-7 does
**not** rescue "stop at startup": (a) startup-boot is not a mutation, and (b) even a maximal D-7
reading requires fail-closed to be "a NO-OP that leaves the game playable" (B1), i.e. a *scene*,
never `engine_stop`. Recorded as **D-210-1** below so the owner may veto; a veto still cannot
restore silent engine_stop — at minimum the surface must be player-facing and offer Load.

## 4. Spec-pin (canonical definitions)

| Datum | Source of truth | Note |
|---|---|---|
| Party location (authoritative) | `party_tracker.json` `worldConditions.currentLocationId` | Movement is committed here atomically before any narration (recover() docstring). |
| Interrupted-transition checkpoint | `modules/conversation_history/pending_location_transition.json` | Residue only; never authority over movement. |
| Checkpoint lifecycle owner | `core/ai/action_handler.py::recover_pending_location_transition` + `_remove_location_transition_checkpoint` | Already auto-retires `completed`, `planned@origin` (replan). |
| `blocked` semantics (CODE-PROVEN) | recover() returns `blocked` **only** when party matches neither origin nor destination (v1 `main.py`-analog `1715`; v2 `1668`; v2 cross-module `1634`). | **Always terminal / un-appliable** — waiting/retrying cannot help; party_tracker will not spontaneously realign. |
| Startup blocked handler | `main.py:6354` | The defect. |
| Pre-action drain blocked handler | `main.py:4149` -> `transition_context_pending`, `retryable:True` | Non-fatal; self-heals once checkpoint is retired. |
| Turn-loop blocked handling | `main.py:7230` handles `resume_required` only; `blocked` falls through to a normal turn | Non-fatal; self-heals once checkpoint is retired. |

**Commit point / end states after fix:** startup on `blocked` -> checkpoint retired (by recover())
-> player-facing surface -> **fall through to the live playable loop** at the authoritative party
location. End states: `completed`/`replan_required`/`resume_required` unchanged; `blocked` -> boot
playable (never engine_stop).

**Player-experience promise advanced (Part 2 p9/p11, README resume/startup):** "a resumed game
shows the player where they were"; startup is a play path that never dead-ends a player.

## 5. The fix (minimal, root-cause, reactive)

Two edits. No new persisted format, no new public symbol, no new flag, no timeout/bound/retry.
Uses the existing retire helper the function already calls for other terminal states.

### Edit A — `core/ai/action_handler.py::recover_pending_location_transition`
At each of the **three** terminal `blocked` returns (v2 cross-module ~`1634`; v2 ~`1668`; v1
~`1715`), **retire the un-appliable checkpoint before returning**, and log a forensic breadcrumb
(operation_id / phase / reason) at `warning`. This makes the lifecycle owner retire a terminal
checkpoint exactly as it already does for `completed`/`replan_required` — closing the #167 re-block
trap at the source, so **all three** call sites self-heal.

```python
# before each `return {"status": "blocked", ...}`:
warning("Discarding un-appliable interrupted transition (<site-appropriate "
        "fields>); authoritative party state matches neither the staged "
        "origin/destination nor a staged module projection.",
        category="location_transitions")
_remove_location_transition_checkpoint()
return {"status": "blocked", "discarded": True, "reason": <existing reason>}
```
`"discarded": True` lets callers surface accurately; the `"blocked"` key is preserved so the
existing `main.py:4149` drain branch keeps compiling and behaving (one retryable turn, then the
checkpoint is gone -> proceeds).

> **Per-site log fields (R1, reviewer-flagged).** The breadcrumb must use only locals **in scope at
> each site**. The v1 site (~`1715`) and v2 within-module site (~`1668`) have `origin_id` /
> `destination_id` / `current_id`. The **v2 cross-module site (~`1634`) does NOT** — those locals
> are assigned later (~`1654-1660`); it has `checkpoint` / `party_projection` / the `module_handoff`
> projections. Emitting the `*_id` template verbatim at `1634` would `NameError`. Each of the three
> sites logs its own in-scope fields; the retire call + return shape are identical across all three.

### Edit B — `main.py:6354` startup handler  *(revised R1 — delivery channel corrected)*
Replace `error(...) + return` with a **player-visible surface + fall-through** (no return). The
surface **must reach the player stream in every mode**, not the log/Debug tab.

**Delivery-channel constraint (CODE-PROVEN — the round-1 blocking finding).** In all three run
modes the *only* player-facing output surface that exists without new machinery is a
`Dungeon Master:` narration block:
- **Web:** `WebOutputCapture` routes a line to the player pane (`game_output_queue`,
  `type:'narration'`) **only** inside a `Dungeon Master:` section (trigger `web/web_interface.py:637`;
  flush -> `:521/782`). Any other line — including a bare `[SYSTEM] ...` or a `WARNING:` line — goes
  to `debug_output_queue` -> the **Debug tab** (`:758-764`), which the player does not watch.
- **Headless:** `core/headless/classifier.py` mirrors this exactly — narration only inside a
  `Dungeon Master:` section (`:142`); `[`-prefixed banners and `DEBUG:/INFO:/WARNING:/ERROR:` lines
  emit as `debug` (`:126-139`).
- **Terminal:** raw stdout prints everything.

So a bare `print("[SYSTEM] ...")` at startup (the original Edit B) is **invisible to the web and
headless player** — it reproduces the exact #210 defect ("reason written only to the log"). The
notice is therefore delivered **through the player narration channel** (reusing existing plumbing —
no new mechanism, AP-4 clean):

```python
if pending_transition_recovery.get("status") == "blocked":
    world = (party_tracker_data or {}).get("worldConditions", {}) or {}
    here = world.get("currentLocation") or world.get("currentLocationId") or "where you are"
    warning("Interrupted location transition could not be auto-completed; "
            "discarded the un-appliable record and continuing from the "
            "authoritative party location. reason=%s"
            % pending_transition_recovery.get("reason"),
            category="location_transitions")
    # Player-visible in web + headless + terminal: the narration channel is the
    # only existing cross-mode player surface (see delivery-channel constraint).
    print("Dungeon Master: A prior travel action didn't finish cleanly, so "
          "you remain where the party actually stands - %s. You can continue "
          "from here, or load an earlier save to redo that journey." % here)
    # fall through: boot into the normal playable loop (no return / no engine_stop)
```
Register (in-fiction DM narration vs an explicit out-of-fiction "[SYSTEM]" notice) is an owner
taste call — **D-210-2**. Note the hard constraint: an out-of-fiction register that is *still
player-visible in web/headless* does **not exist today** and would require a NEW player-facing
system-message channel (new mechanism -> owner mandate) — tracked as **F-210-c**. Absent that, a
player-visible notice must be rendered as narration. Wording content (names where they are; offers
Continue + Load) was reviewer-approved; only the channel/register changed.

### Why the drain (`4149`) and turn-loop (`7230`) need **no** edit (R4 — verified round 1)
Startup runs **before** any turn, and Edit A retires the checkpoint on the `blocked` return, so by
the time the drain/turn-loop run, `recover()` returns `none` and they proceed normally.
CODE-PROVEN by the panel for the (artificial, mid-session-only) case where a `blocked` checkpoint
arises during play: the drain (`4149`) returns `transition_context_pending, retryable:True`
**once**; `resolve_retryable_ai_result` (`main.py:5582-5586`) does **not** auto-retry that status,
so the turn-loop prints its state-changed notice and re-prompts — i.e. it costs **one deferred
player turn, not an automatic regeneration**. On that next turn the checkpoint is already gone
(Edit A retired it), `recover()` returns `none`, and the action applies. The turn-loop's `blocked`
simply falls through to a normal turn. No brick, no refused-forever loop. (Confirmed by the
Fail-Forward, Architecture, and Consumer/Compat reviewers.)

## 6. GL-1 Behavioral Contract (deletions/replacements)

| Deleted/changed behavior | Origin | Goal it served | Disposition |
|---|---|---|---|
| Startup `error()+return` on `blocked` (stop the game) | `main.py` startup handler, commit **`60a7e776`** "fix(travel): harden contextual location transitions" (2026-08-06) — original introduction, never re-fixed since (`git log -S` = one commit; two-strikes CLEAR) | Prevent playing from a mismatched staged transition (avoid double-move) | **RETIRED** under B1/#210. CODE-PROVEN by GL-1 reviewer: `recover()` never writes `party_tracker.json` on any path, so the double-move is *already* prevented (checkpoint never applied); the stop bought zero corruption protection and cost the whole session. Replaced by fail-forward surface + continue. |
| recover() leaving the `blocked` checkpoint on disk for callers | v1 site (~`1715`) = `60a7e776`; v2 sites (~`1634`/`1668`) = **`b7f7a863`** "fix(travel): make agentic transitions recoverable" (2026-08-24) | Let caller decide policy | **RETIRED**. Leaving it = #167 re-block-every-boot trap. Retirement centralized in the lifecycle owner, consistent with its existing `completed`/`replan` retirement. No caller reads data OUT of the persisted checkpoint (3 callers enumerated in §4; CODE-PROVEN by Consumer/Compat + Legacy-Contract reviewers). |
| **PRESERVED** | | | Conflict **detection** (three comparisons byte-untouched); **non-application** of the un-appliable movement (structural — recover() mutates only the checkpoint file); the safety property that we never play from a fabricated projection. |

Byte-behavior A/B: `completed`, `replan_required`, `resume_required`, `none` return paths are
untouched (verify by diff — only the `blocked` branches change).

**Highest-risk GL-1 question — v2 `blocked` discard — CODE-PROVEN SAFE (round 1).** A v2 `blocked`
checkpoint is un-completable *by construction*: movement commits `currentLocationId = destination`
to `party_tracker.json` **before** the checkpoint advances past `movement_committed`, and the
work-preserving `resume_required` path (~`1695`) is reached **only when `current_id == destination_id`**;
`blocked` fires only when the party is at *neither* origin nor destination — the state that
falsifies resume's precondition. So the accepted summary/enrichment/sibling work a `blocked`
checkpoint might carry is unresumable regardless; retiring it strands no recoverable player-visible
work. Edit A does not touch the party-at-destination resume path.

## 7. FS-1 (smuggled fail-stop) — diff grep

The diff adds **no** `timeout`/`deadline`/`max_*`/`retries`/`sleep`/`wait_for`/`range(`-around-
provider/`shutdown(wait`. The token `retryable` already exists at `main.py:4149` and is **not**
edited by this plan. No numeric bound of any spelling is introduced. FS-1 = **zero hits**
(reviewer re-greps the actual diff).

## 8. Acceptance (defined pre-code, at the player-experience + on-disk layers)  *(revised round 1)*

Configured OpenAI provider, **Keep_of_Doom** (official module; per #193 p13 + owner ruling — NOT
Shadows_of_Frostmere), one operation at a time (no fan-out on probes). Because the fix is a
**player-visible startup surface**, acceptance is judged at the **experience layer in the real
player surface**, not only on-disk — and must be run in **both** headless serve AND web mode
(the routing that broke round 1 is mode-specific).

**GATE-POLARITY control (required — exercise the FIRING path, #193 p13):**
1. Launch a travel turn; poll `pending_location_transition.json` for `movement_committed`; hard
   `kill -9` the process group (party now authoritatively at destination).
2. Tamper `party_tracker.currentLocationId` to a third location (matches neither origin nor
   staged destination) -> forces `blocked`.
3. Relaunch. **Assert (all):**
   - **(prove-firing, BLOCKING-2)** recover() actually returned `status:"blocked"` this boot —
     capture Edit A's forensic `warning` breadcrumb ("Discarding un-appliable interrupted
     transition …") in the run log. Without this the gate-polarity control proves nothing (the
     tamper could have landed on `resume_required`/`completed`/`replan_required` instead).
   - engine **boots into the playable loop** (reaches a prompt); no crash/traceback.
   - the recovery notice naming the authoritative location + Load option renders **in the player
     surface** — in **headless** as a `narration` protocol event (NOT a `debug` event); in **web**
     as a `game_output`/`narration` payload in the **game pane** (NOT `debug_output`/the Debug tab).
     This is the round-1 blocking assertion — pin the exact stream, not "appears somewhere."
   - `pending_location_transition.json` is **removed**.
   - a subsequent ordinary turn (e.g. "I look around") completes normally; no duplicate
     movement/time/journal.
4. **Load control (B1 p9):** from the booted state, `restore` an earlier save; assert it succeeds
   **and** the resumed session shows player-visible location/recent history (not a blank screen,
   #79/#116) — not merely a no-error return.

**Firing-path coverage (R4).** The kill-at-`movement_committed` repro exercises the **v2
within-module** `blocked` site (~`1668`). The **v1** site (~`1715`) and **v2 cross-module** site
(~`1634`) are accepted **by construction**: identical `_remove_location_transition_checkpoint()` +
identical return contract, verified by the Architecture + Legacy-Contract reviewers. A dedicated
cross-module `blocked` probe is not run (heavy setup); this coverage boundary is stated, not hidden.

**Negative / no-regression controls:**
- Normal `completed`/`resume_required` recovery still converges (the kill-at-`movement_committed`
  headline from the extraction acceptance still passes — journal +1 not +2, arrival once).
- A clean boot with no checkpoint is unaffected.

Evidence: exact commands + raw player-surface output (NDJSON events for headless; `game_output`
vs `debug_output` capture for web) + before/after on-disk `party_tracker` and checkpoint state, per
claim (artifact-or-HYPOTHESIS). Driver harnesses are local dev aids, untracked (D-9) — adapt the
existing `blocked_conflict.py`; add a web-mode leg.

## 9. Triage

**FULL** — touches the shared `recover_pending_location_transition` primitive (return-side-effect
change) and a play path (startup), and trips GL-1 (retires two behaviors). Required panel:
Architecture Custodian, Fail-Forward DA, Acceptance DA; conditional Consumer/Compat DA (shared fn
+ its 3 call sites), Legacy-Contract DA (GL-1), Player-Experience DA (player-facing startup
surface). Escalation is one-way; no downgrade.

## 10. Tracked follow-ups (Zero-Deferral — number required before merge)

- **F-210-a -> filed as #211:** The startup handler's **exception** branch (`main.py:6374`) also
  `return`s (stops) on *any* exception raised inside recovery. Different failure class (a genuine
  raised exception, not a detected conflict), out of scope here. Includes the Fail-Forward
  reviewer's edge: Edit A's `_remove_location_transition_checkpoint()` only swallows
  `FileNotFoundError`; a different `os.remove` error (e.g. a Windows lock, `WinError`) would raise
  into this branch and stop the engine.
- **F-210-c -> filed as #212:** There is **no out-of-fiction, player-visible system-message
  channel** in web or headless mode: any line not in a `Dungeon Master:` section routes to the
  Debug tab / `debug` event. The existing turn-loop `[SYSTEM]` notice (`main.py:7246`) — which the
  original draft cited as a "consistency precedent" — is therefore itself invisible to web/headless
  players. A proper OOC player channel is a NEW mechanism requiring an owner mandate (AP-4), and
  gates the register option in D-210-2. Not required for #210 (Edit B uses the narration channel).

## 11. Owner decisions

- **D-210-1:** Ratify that startup on an un-appliable interrupted transition **fails forward**
  (boot playable + player-facing surface + Load offered), per B1 — closing the #210 "owner design
  decision." Author recommends **YES** (B1 is dispositive). A veto to keep fail-closed still may
  not use silent `engine_stop`: the minimum acceptable fail-closed is a player-facing scene that
  offers Load (never a frozen session).
- **D-210-2 (register — R7 taste escalation):** Should the recovery notice read as **in-fiction DM
  narration** (Edit B as written — the only channel player-visible today) or as an **explicit
  out-of-fiction "[SYSTEM]" notice**? The latter is NOT player-visible in web/headless without the
  new channel in **F-210-c**. Author recommends: ship the narration-channel notice now (unblocks
  #210); decide OOC-channel separately under F-210-c. Owner-only.

## 12. Resolution ledger

| # | Finding | Round | Resolution |
|---|---|---|---|
| (seed) | Startup stops (engine_stop) on `blocked`; log-only; no recovery offered (#210) | 0 | Fix §5 Edit A+B; acceptance §8. |
| (seed) | Un-appliable checkpoint left on disk -> re-block every boot (#167 class) | 0 | Edit A retires it in the lifecycle owner. |
| (seed) | Three call sites handle `blocked` three different ways (coherence, Part 4) | 0 | Edit A makes `blocked` self-healing everywhere; drain/turn-loop need no edit. |
| **R1-B1** (Acceptance + Player-Experience, **BLOCKING**) | Bare `print("[SYSTEM] …")` at startup routes to the **Debug tab / `debug` event** in web+headless — invisible to the player; reproduces the #210 defect in the primary product mode. | 1 | **FIXED.** §5 Edit B now delivers via the player **narration channel** (only cross-mode player surface, no new mechanism). Register escalated D-210-2; OOC-channel gap filed F-210-c. |
| **R1-B2** (Acceptance, **BLOCKING**) | Gate-polarity control asserted continuation but never proved recover() actually returned `blocked` (tamper could hit another status). | 1 | **FIXED.** §8 step 3 now requires capturing Edit A's forensic breadcrumb proving `blocked` fired this boot. |
| **R1-B3** (Acceptance + Player-Experience, **BLOCKING**) | Acceptance ran headless only; the routing defect is web-specific and would pass. | 1 | **FIXED.** §8 now mandates **both** headless + web legs, pinning the exact player stream (game_output/narration, not debug). |
| R1-F1 (Fail-Forward + Legacy-Contract + Custodian, FYI) | Edit A warning template references `origin_id/destination_id/current_id` not in scope at the cross-module site (`1634`) -> NameError. | 1 | FIXED. §5 Edit A now mandates site-appropriate in-scope fields. |
| R1-F2 (Fail-Forward, FYI) | Retire's `os.remove` non-`FileNotFoundError` could raise into the `6374` exception branch (stop). | 1 | Folded into F-210-a (issue filed this turn). |
| R1-F3 (Custodian + Fail-Forward, FYI) | §5 drain wording overstated automaticity (`transition_context_pending` not in auto-retry set). | 1 | FIXED. §5 now says "one deferred player turn, not automatic regeneration." |
| R1-F4 (Custodian, FYI) | Doc-reconciliation missing; dangling path ref; wrong blame hash. | 1 | FIXED. §6 blame origins corrected (`60a7e776`/`b7f7a863`); doc-reconciliation note below; this plan supersedes no docs. |
| R1-F5 (Player-Experience, FYI) | Location label may show a raw ID if `currentLocation` absent. | 1 | Acknowledged. `here` prefers `currentLocation` name; `currentLocationId`/"where you are" are graceful fallbacks. Non-blocking. |
| R1-F6 (Acceptance + Legacy-Contract, FYI) | Firing-path coverage exercises only the v2 within-module `blocked` site. | 1 | FIXED. §8 "Firing-path coverage" states v1 + cross-module sites are accepted by construction (identical helper + contract). |
| R1-F7 (Consumer/Compat, FYI, cosmetic) | Drain `blocked` branch becomes effectively dead in normal boot ordering. | 1 | Acknowledged; harmless (self-heals the artificial mid-session case). No change. |

**Doc reconciliation (R1-F4):** this plan **supersedes no existing docs**. It references the sibling
artifact `docs/audits/2026-08-24-travel-recovery-CODEX-HANDOFF.md` (on this branch); the earlier
draft's `docs/plans/2026-08-24-travel-recovery-extraction-plan.md` path was a dangling reference and
is dropped. The retired "stop" behavior originated in code (commit `60a7e776`), not in any design
doc, so nothing needs a SUPERSEDED header.

**Round-1 result:** 4 reviewers CONVERGED (Architecture Custodian, Fail-Forward DA, Consumer/Compat
DA, Legacy-Contract DA); 2 CHANGES-REQUIRED (Acceptance DA, Player-Experience DA) — both on the
single delivery-channel defect, now fixed. Re-dispatch Acceptance DA + Player-Experience DA on this
revision for the confirmation pass; the 4 converged reviewers re-verify the revised §5/§6/§8 touch
their lanes (Edit A shape unchanged; Edit B channel change is player-surface only).

## 13. Execution & acceptance results (OBSERVED — real headless play, OpenAI/WSL)

**Convergence (round 2 / confirmation pass):** all six reviewers CONVERGED. Acceptance DA + Player-
Experience DA confirmed the delivery-channel fix (notice reaches the player via the narration
channel; the round-1 blocker is resolved). Architecture Custodian + Fail-Forward DA re-verified the
Edit B channel change introduces no new mechanism (AP-4) and no new fail-stop (B1/FS-1). Consumer/
Compat DA + Legacy-Contract DA held converged (their lanes — caller shapes, GL-1 deletions — are
byte-unchanged by the round-1 edits).

**Implemented** on `travel-recovery-clean` (uncommitted): `main.py` startup handler (Edit B) +
`core/ai/action_handler.py` recover() three `blocked` sites (Edit A). Diff: +63/-4 across 2 files.
`party_tracker.json` is gitignored; no tracked runtime/save state altered by acceptance.

### 13.1 GATE-POLARITY (headless serve --debug, real OpenAI, Keep_of_Doom) — ALL 9 PASS
Repro: party E03 -> travel to E01; poll checkpoint, hard `kill -9` at `phase=movement_committed`
(party at E01, moved once); tamper `party_tracker.currentLocationId` -> E05 (matches neither origin
E03 nor destination E01); relaunch.
- PASS movement committed once (party at E01 after kill).
- PASS boot playable (reached prompt; no engine_stop).
- PASS `blocked` fired — forensic breadcrumb captured (debug event):
  `[WARNING] [SaveGameManager] Discarding un-appliable interrupted transition (v2 origin=E03 dest=E01 current=E05): party location matches neither.`
- PASS notice on the PLAYER stream — arrived as a `narration` event (1), zero debug copies:
  `"A prior travel action didn't finish cleanly, so you remain where the party actually stands - Storage Vaults. You can continue from here, or load an earlier save to redo that journey."`
- PASS notice names the authoritative location (Storage Vaults / E05).
- PASS checkpoint retired after boot (`pending_location_transition.json` removed).
- PASS next ordinary turn works (reached prompt, narration produced).
- PASS no crash (zero error events).
- PASS no duplicate movement (party stays E05 authoritative; staged E03->E01 never re-applied).

### 13.2 WEB routing (real `WebOutputCapture` production router, exact notice string) — PASS
The notice line + a following prompt line fed through the actual `web/web_interface.py`
`WebOutputCapture` enqueued the notice to `game_output_queue` as `{'type':'narration'}` (the game
pane). The only debug-stream echo is the internal `[OUTPUT_TRACE] Started DM section:` diagnostic,
not a player-facing copy. Confirms the round-1 web-specific defect (bare `[SYSTEM]` -> Debug tab)
is fixed; web routing matches the headless result.

### 13.3 NO-REGRESSION: normal resume still converges (headless, real OpenAI) — ALL PASS
Same kill@`movement_committed` but **no tamper** (party at destination E01): relaunch takes the
**resume** path (NO discard breadcrumb), boots playable, converges (checkpoint removed), party at
E01 (moved once), no crash, narration produced. Confirms Edit A did not disturb the
`resume_required`/`completed` paths.

### 13.4 LOAD control (B1 p9) — PASS
`run_headless.py saves restore` of an earlier save succeeded (`ok:true`, 136 files, backup created);
`party_tracker` -> the saved location (E03); relaunch reached a prompt and the `state` event showed
`location {id:E03, name:"Torture Chamber", ...}` (not a blank screen); no spurious blocked
breadcrumb. Load is available and not refused from the fail-forward flow.

### 13.5 Coverage boundary (stated, not hidden)
The live repro exercised the **v2 within-module** `blocked` site. The **v1** (`~1740`) and **v2
cross-module** (`~1634`) sites use the identical `_remove_location_transition_checkpoint()` + return
contract (verified by the Architecture + Legacy-Contract reviewers) and are accepted by
construction; no dedicated cross-module live probe was run.

### 13.6 Authoritative-arm follow-up
Native-Windows (cp1252/O_BINARY) + Gemma/local-model re-run of this same matrix belongs to Codex,
per the travel-recovery handoff. Filed follow-ups: **#211** (exception-branch stop + os.remove
edge), **#212** (no OOC player-visible channel).
