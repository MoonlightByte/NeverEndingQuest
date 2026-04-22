# GUI Builder Semantic Remediation Reporting

## Builder Review Draft

Purpose: implement the next bounded GUI-builder slice so semantic publishability blockers surface as a distinct remediation lane for any module, instead of appearing primarily as raw JSON failure dumps.

This is implementation work, but it is still bounded and review-safe. It is not approval to add autonomous semantic repair.

## Intent

The deterministic GUI-builder chain is already complete:

1. media-only handoff semantics
2. workflow UI ordering
3. gameplay/readiness payload normalization
4. mixed-failure classification

The next gap is operator-facing reporting. The backend already knows when a module has semantic blockers; the toolkit UI does not yet render that clearly.

## MUST Contract

- The builder SHALL keep this slice limited to toolkit reporting/rendering and targeted tests.
- The builder SHALL treat semantic remediation as a generalized lane for any module with semantic publishability blockers.
- The builder SHALL consume existing structured output (`remediation_categories`, `blocking_findings`, `blocking_errors`) rather than inventing a parallel source of truth.
- The builder SHALL preserve Python authority over `ready_status` and `publishable_status`.
- The builder SHALL preserve pure media-only handoff behavior unchanged.
- The builder SHALL preserve failed semantics for mixed media-plus-semantic cases.
- The builder SHALL NOT add autonomous semantic repair, auto-aliasing, or LLM proposal generation in this slice.

## SHOULD Guidance

- Prefer additive formatting helpers in toolkit UI code.
- Prefer `blocking_findings` first, with fallback to `blocking_errors` when structured findings are absent.
- Keep raw payload visibility available for debugging after the formatted summary.

## Proposed Step Sequence

### Step 1 - Lock the reporting contract

Define the operator-visible states for:
- semantic-only blockers
- mixed semantic + media blockers
- media-only handoff

### Step 2 - Implement bounded toolkit rendering

Add a semantic remediation rendering path to toolkit build/upload surfaces so semantic blockers are presented as structured guidance instead of raw JSON only.

### Step 3 - Prove no status-policy regressions

Add targeted tests for semantic-only and mixed cases, confirming media-only handoff still behaves exactly as before.

## Full Builder Prompt

Implement OpenSpec change `gui-builder-semantic-remediation-reporting` as a bounded toolkit reporting/rendering slice.

Goal: for any module with semantic publishability blockers, surface a distinct semantic remediation section in toolkit result flows using existing structured audit output, while preserving current media-only handoff and mixed-failure status semantics.

Allowed files:
- `web/templates/module_toolkit.html`
- `web/web_interface.py`
- targeted toolkit/reporting test files
- this change's artifacts if you need to refine wording after implementation evidence

Forbidden:
- changing semantic extraction logic
- changing publishability decision rules
- adding LLM remediation or auto-edit behavior
- weakening mixed-failure blocking semantics

Required:
- semantic-only cases render a semantic remediation lane
- mixed media + semantic cases remain failed and show both classes distinctly
- pure media-only cases preserve `success_with_media_handoff`
- raw JSON is no longer the only operator-facing output for semantic blocker cases
- targeted verification evidence is captured

Edit Strategy: Apply one anchored patch at a time, then re-run `py_compile` before the next patch.
