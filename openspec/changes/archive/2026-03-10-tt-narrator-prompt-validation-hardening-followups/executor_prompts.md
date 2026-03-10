# Builder Prompts - tt-narrator-prompt-validation-hardening-followups

## Step 1.1 Builder Prompt (Kimi K2.5 - Lite)

Step: 1.1 - Sync skipped narrator-validation specs to main OpenSpec specs.
Edit: `openspec/specs/tt-narrator-validation-contract/spec.md`, `openspec/specs/tt-validation-retry-hygiene/spec.md`, `openspec/specs/tt-npc-move-hint-fallback/spec.md`.
Scope: Do not modify runtime code, prompts, tests, or archived change contents.
Do: Copy capability contracts from `openspec/changes/archive/2026-03-10-tt-narrator-prompt-validation-refactor/specs/*/spec.md` into the three main spec paths; keep MUST/SHALL wording and scenarios intact; ASCII only.
Checks: `openspec validate tt-narrator-prompt-validation-hardening-followups`.
Report: List created files and whether validation passed; include any blockers.

Edit Strategy: Apply one anchored patch at a time, then re-run validation before next patch.
