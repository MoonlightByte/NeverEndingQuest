# Startup provider configuration recovery

Source baseline: public main `331ec9929a8c157b39b4de19c57a45e4c38f8ffe`.
This is separate from PR558's request-owned connection snapshot and the
startup provenance fix. No character mechanics, saved heroes or worlds change.

## Reproduced failure and ownership

The real provider child classifies completed 401/403/402 errors as deterministic
and hands them back after reaping. `get_ai_response` (T092 interview/reviewer)
and `get_ai_starting_location` (T093) instead append a model correction and retry.
`api_client._local_template_repair` previously accepted any completed status,
so a trailing system correction caused an extra physical authentication attempt.

Current-main plus PR558 baseline replay of each of the actual interview,
review and location functions returned three deterministic 401 envelopes,
five HTTP attempts, three reaped children and zero usage receipts. The fixture
superseded after three envelopes to contain the broken baseline; production
has no such bound. The same caller/repair code is unchanged from the originally
reproduced public main `6f7825ba` to `331ec992`.

This uses the actual installed OpenAI SDK and provider subprocess with synthetic
HTTP responses and socket connections forbidden. It does not establish that
the reporter of #557 used invalid credentials or reproduce their no-request
symptom. The original fenced-JSON probe is a strict-format failure compatible
with the real startup parser, not evidence of connectivity failure.

## Resulting behavior

- 401 requests key/endpoint correction; 403 requests access/permissions
  correction; 402 requests credits/billing correction. Only structured HTTP
  status determines this branch. Provider prose is never classified.
- Neither template repair nor model correction retries these refusals.
- Web startup remains in progress in the same live scope, with actionable busy
  status and retained choices. The existing Settings controls remain available.
  The production output marker recognizes `startup_configuration_required`;
  it never emits `game_started` or falsely reports startup failure/ready.
- A successful Local/Custom Settings Save deliberately retries, including a
  same-value save after a remote credit or access change. A failed save or
  another provider's credential save cannot release the wait. Provider
  selection resumes with the newly selected provider profile. A save during
  the failed request is observed using a revision captured before dispatch.
- Console input owns an explicit retry/cancel prompt. Cancellation propagates
  to the existing startup owner; it is not caught as another model failure.
- Load, Reset and Exit supersede the existing scope; accepted saves use the
  existing game-thread drain. Status delivery failure cannot kill the wait.
  There is no global provider lock, new retry cap or transient-policy change.
- 400 caller correction, reactive local 400/5xx message repair, transient 429
  and connection retry retain their existing policy. Model output review and
  ordinary schema/location validation remain in place.

PR558 is an integration prerequisite for request-owned endpoint/key/model
pinning: each resumed logical request must capture fresh connection settings,
while retries within that request keep its pinned snapshot. This narrow patch
does not copy or replace PR558 and does not read changed credentials into an
active attempt.

## Offline validation

Commands from this branch (the new tests have their own reusable subprocess
fixture; they are runnable without PR558):

```
python -m pytest -q tests/test_startup_provider_recovery.py tests/test_startup_configuration_wait.py --tb=short
python -m pytest -q web/frontend/e2e/provider_contract_test.py --tb=short
```

Native Windows Python 3.12.3, pytest 9.1.1, OpenAI 2.36.0, HTTPX 0.28.1:
30 subprocess cases passed (27 in 128.73s plus three owned-scope/repeated-refusal
controls in 18.30s); 13 wait/console/web-marker checks passed in 0.25s;
25 existing Settings handler/SDK/Socket.IO contract tests passed in 6.80s.
Each fixture worker retains the existing 25-second deadline. Tests copy only
public source into temporary installations, synthesize credentials, prohibit
operator keyring/network access and check child reaping and secret redaction.

The subprocess matrix covers all three startup paths for each of 401/403/402,
corrected credentials, same-value save, failed save, unrelated provider save,
provider switch, repeated refusal, restore/reset/exit, owned-scope handback,
400 template repair, 400 model correction, 429/503 and connection recovery.
Rejected attempts record no accepted usage; recovery records exactly one.

Current-main plus PR558 provider regression: all 24 passed in 70.62s using
Python 3.10.19/OpenAI 2.36.0 on WSL with Linux-native `/dev/shm` temp space
(47 GB available checked first), unchanged 25-second worker deadline.
Native Windows comparison had 21 passes, two Linux-only skips and one parallel
fixture PID-record assertion failure. That Windows run is not a clean pass.
The prior mounted-filesystem timeouts and historical passes remain separate.

Final integration at `9a3d436a2aa86080559f9517128b94a419393c23` (public
`331ec992` + PR558 commits `b38907e1`/`dcf91ea5` + auth fix `516f701d`):
all **67 passed in 180.78s** on Linux using `/dev/shm`, including the original
24 provider regressions, all 30 real subprocess recovery cases and 13 focused
wait/terminal/production-web-marker checks. The 25-second deadline is unchanged.

No paid requests, main merge, deployment, browser visual acceptance or new
successful-projection live replay are performed by this patch. Desktop owns
the remaining live replay and complete current-main integration acceptance.
