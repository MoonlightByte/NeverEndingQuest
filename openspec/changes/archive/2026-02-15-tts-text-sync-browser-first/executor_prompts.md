## Kimi/GLM Executor Prompts

Use these prompts to implement `tts-text-sync-browser-first` in tightly controlled slices.

Execution policy:
- Run one slice at a time (`C1` -> `C6`, optional `C7`).
- Do not edit files outside each slice scope.
- Run required verification before reporting completion.
- Stop after each slice and wait for human approval.

---

## 0) Session Bootstrap Prompt (Run First)

```text
You are implementing OpenSpec change: tts-text-sync-browser-first.

Rules you MUST follow:
1) Read these files first:
   - openspec/changes/tts-text-sync-browser-first/proposal.md
   - openspec/changes/tts-text-sync-browser-first/design.md
   - openspec/changes/tts-text-sync-browser-first/tasks.md
   - openspec/changes/tts-text-sync-browser-first/specs/tts-browser-word-sync/spec.md
   - openspec/changes/tts-text-sync-browser-first/specs/tts-sync-engine-abstraction/spec.md
   - openspec/changes/tts-text-sync-browser-first/specs/tts-block-narration-only/spec.md
2) Keep canonical block narration output as the only source path.
3) Do NOT re-enable player-facing server stream events.
4) Keep changes merge-safe and minimal.
5) Execute one slice at a time and stop for review.

Output format:
- Slice: <C1|C2|...>
- Files changed:
- What changed:
- Verification run:
- Risks/notes:
- Ready for next slice: <yes/no>

Acknowledge and wait for: "Run C1".
```

---

## 1) C1 Prompt - Config and Toggle Wiring

```text
Run C1 only for OpenSpec change tts-text-sync-browser-first.

Scope lock (allowed files):
- model_config.py
- web/web_interface.py
- web/templates/game_interface.html

Required C1 tasks:
- Add sync feature defaults (OFF by default).
- Wire any required template flags without changing canonical output payload semantics.
- Add/adjust UI toggle controls for sync mode.

Acceptance focus:
- Sync feature can be enabled/disabled.
- Legacy behavior remains default.

Required verification:
- python3 -m py_compile model_config.py web/web_interface.py

Stop after C1 report. Do NOT run C2.
```

---

## 2) C2 Prompt - Reveal Rendering Layer

```text
Run C2 only for OpenSpec change tts-text-sync-browser-first.

Precondition:
- C1 approved.

Scope lock (allowed files):
- web/templates/game_interface.html

Required C2 tasks:
- Add CSS classes for reveal mode.
- Add reveal helper functions (init/update/finalize).
- Integrate optional reveal DOM wrapping in narration addMessage path.

Acceptance focus:
- Sync OFF path renders exactly like before.
- Reveal mode structure is isolated to narration messages.

Stop after C2 report. Do NOT run C3.
```

---

## 3) C3 Prompt - Browser Boundary Playback Sync

```text
Run C3 only for OpenSpec change tts-text-sync-browser-first.

Precondition:
- C2 approved.

Scope lock (allowed files):
- web/templates/game_interface.html

Required C3 tasks:
- Implement Browser TTS boundary-driven reveal updates via onboundary.
- Ensure stop/error/end lifecycle clears speaking state safely.
- Keep manual and autoplay controls working.

Acceptance focus:
- Reveal progression tracks spoken words.
- No frozen cursor or unreadable partial state on interruption.

Stop after C3 report. Do NOT run C4.
```

---

## 4) C4 Prompt - Queue Strategy Integration

```text
Run C4 only for OpenSpec change tts-text-sync-browser-first.

Precondition:
- C3 approved.

Scope lock (allowed files):
- web/static/js/tts_queue_manager.js
- web/templates/game_interface.html

Required C4 tasks:
- Add per-item sync strategy metadata.
- Preserve single active playback invariant.
- Ensure queue handoff resolves strategy per message.

Acceptance focus:
- Mixed queue items do not leak sync state.
- Browser sync item and non-sync item can run back-to-back safely.

Stop after C4 report. Do NOT run C5.
```

---

## 5) C5 Prompt - Canonical Path Regression Guard

```text
Run C5 only for OpenSpec change tts-text-sync-browser-first.

Precondition:
- C4 approved.

Scope lock (allowed files):
- web/templates/game_interface.html
- web/web_interface.py (only if needed for guard/fallback wiring)

Required C5 tasks:
- Confirm no server stream delta events are introduced.
- Confirm canonical narration remains single-visible-path.
- Confirm OpenAI TTS remains unchanged block behavior.
- Confirm skipTTS/system/mechanical message handling is unchanged.

Acceptance focus:
- No duplicate narration renders.
- No JSON/token leakage in user-visible narration.

Stop after C5 report. Do NOT run C6.
```

---

## 6) C6 Prompt - Verification and Evidence

```text
Run C6 only for OpenSpec change tts-text-sync-browser-first.

Precondition:
- C5 approved.

Scope lock (allowed files):
- No new runtime files unless fixing a blocker discovered in verification.

Required C6 tasks:
- Run compile checks for touched Python files.
- Execute manual smoke: intro + one non-combat turn + one combat turn with sync ON/OFF.
- Produce requirement-to-code traceability summary.

Required verification commands:
- python3 -m py_compile model_config.py web/web_interface.py

Manual checklist:
- Browser sync ON: reveal follows speech.
- Browser sync OFF: legacy block behavior.
- OpenAI TTS path unchanged.
- Stop mid-playback leaves readable state.
- skipTTS/system outputs unaffected.

Stop and provide final report. Do not archive change.
```

---

## 7) Optional Future Slice - C7 Dual-Engine Estimation Scaffold

```text
Run C7 only if explicitly approved after C6.

Scope lock (allowed files):
- plans/tts-txt-sync.md
- web/templates/game_interface.html
- web/static/js/tts_queue_manager.js

Required C7 tasks:
- Add placeholder strategy hook for `estimated_timeline` without enabling runtime behavior.
- Document timing estimation inputs, drift thresholds, and fallback policy.

Acceptance focus:
- No user-visible behavior change from C6 output.
- Future implementation path is explicit and testable.
```
