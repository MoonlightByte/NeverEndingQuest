# Startup review: authored proposal and engine provenance

Public baseline: `388de319b4dc0a7fa14d5c54b4c9587c3153f631`, freshly fetched
2026-10-03. Branch: `fix/startup-review-provenance`. No applicable AGENTS.md
was present in the workspace ancestors, repository or new worktree. Existing
repository guidance was inspected. Tests are explicitly committed despite the
repository's general test ignore rule; that ignore policy is unchanged.

## Observed failure

The desktop-owned synthetic OpenRouter run selected Thornwood and created an
Alden Human Fighter proposal. All 24 physical requests completed HTTP 200 with
finish_reason `stop`, but startup did not commit a hero or party. The test guard
stopped the run after 504.96 seconds. Recorded key usage delta was $0.042842176;
provider receipt reconciliation may lag. This work made no provider requests.

Early author errors included an incorrect latest-player index and null
spellcasting ability against the existing string schema. HP 13 was subsequently
corrected to 12. The persistent semantic-review loop remained after those fixes:
the raw author supplied empty equipment effects and omitted saving-throw totals,
the engine projection inserted AC effects and saving totals, and the reviewer
rejected those additions as author-supplied data. Scalar AC/HP were unchanged,
so the old scalar-change notes did not identify the successful projection.

The committed fixture is only the fictional authored response at
2026-10-03 17:21:20.595263 from `desktop-game-001`. It contains no raw capture,
provider metadata, credentials, operator settings or existing hero data.

## Change

The wizard retains an untouched authored wire object and normalizes a private
copy through the existing repairs, schema checks and real NQL projection. Review
receives both objects. Successful projection provenance includes its actual
matching character status, armor class and AC-target effect entries, even when
the scalar values are unchanged. Other authored effects are not certified by
that AC selector. An unavailable or incomplete projection has no success
certificate. HP derivation records its existing policy; a retained higher
maximum is explicitly not certified as rules-correct.

Reviewer instructions apply author-only restrictions to the authored object,
check canonical narration/mechanics against the normalized candidate, and keep
player consent and independent rejection authority. Repair context returns the
raw rejected proposal alongside its separate canonical candidate/provenance;
it does not ask the author to erase engine output that normalization restores.

Retry, transport, cancellation, persistence and existing-hero paths are unchanged.
Canonical effects/totals are retained. This is separate from PR558's connection
snapshot fix. Open issues/PRs were checked: #407 is the analogous but distinct
level-up normalization/review conflict, #394 concerns startup model adherence,
and #395 tracks finalized armor/feature consistency. No duplicate issue/PR was
opened. No Defense feature alias repair is included.

## Offline validation

Run on native Windows from the new worktree, with installed requirements and
pytest:

```powershell
python -B -m pytest -q tests/test_startup_review_provenance.py --tb=short -p no:cacheprovider
```

For WSL when Linux disk space is unavailable, set TMPDIR to a new writable test
directory on E: and use `--capture=sys` (pytest fd capture's anonymous temporary
files failed on this mounted filesystem before any test ran). The production
game, provider or runner configuration is unchanged.

The suite replays the captured proposal through actual normalization/schema/NQL
on Windows and Linux. It checks immutable authorship, repeated unchanged scalar
projection, actual engine status, unavailable/incomplete projection, AC-only
effect provenance, actual wizard reviewer/repair payloads, canonical publication,
negative consent/index/schema gates, rejected narration/identity/mechanics and
authored totals/effects, clarification handling, cancellation, interview-only
flow, malformed-review repair and fenced JSON parsing. Socket connections and
DNS are forbidden; provider calls and OS credential access are blocked. Model
replies/verdicts are scripted and publication is intercepted in disposable
test directories. These are offline boundary regressions, not AI acceptance.

For a matched public-baseline check, extract the baseline source into an isolated
directory and set `NEQ_STARTUP_TEST_ROOT` to it. Run the same committed test with
`-k actual_interview_reviews_both_sources`. Untouched public main fails at the
real review payload with `KeyError: authored_proposal`; the patched case passes.

## Integration and remaining acceptance

Cherry-pick only this branch's new commit onto the desktop integration candidate;
retain PR558 separately where needed. The transfer bundle and machine-readable
handoff outside the repository record the exact commit, baseline, commands and
results. No push, merge, deployment or hosted files were changed.

Desktop still owns genuine live acceptance through character creation, T093,
first scene, turns, save, clean exit, restart and Continue. The strict small
probe result stays false: its response was code-fenced JSON, accepted by the real
startup parser. That result is a strict formatting failure, not a connectivity
failure or completed game acceptance. Original evidence, synthetic worlds,
candidate worktrees and runner files are preserved.
