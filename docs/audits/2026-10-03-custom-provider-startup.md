# Custom Server live startup transport — issue #557

Public baseline: `222553b8900661d8d9ca869cf515292bf4ebd660`.
Refs https://github.com/MoonlightByte/NeverEndingQuest/issues/557. Do not close
solely on the deterministic tests: the reporter's OS, failure envelopes and
credential-backend behavior were not supplied. No live OpenRouter call was made.

## Proven failure modes

`capture_and_fanout` pins `_request_provider` and resolves the callsite model.
Required T092/T093 requests then use `call_live_provider`, which serializes those
kwargs to a new child for each attempt. On the baseline, the child independently
reads `model_config.get_local_endpoint()` for the client URL/key and again for
the custom model override. Those values are not part of the frozen request.

A deterministic real-child/real-SDK harness reproduces:

- A Custom Server settings change after dispatch redirects the request to the
  new endpoint/model/key. A connection failure becomes `ProviderCallError` with
  `APIConnectionError`, classified `retryable_transport`; the required transport
  reissues. Changing settings between a 503 and its retry reproduces the same
  drift. No inference reaches the originally selected endpoint in the first case.
- A credential resolvable in the parent but unavailable to a fresh child becomes
  the fallback token in the child. The fake endpoint rejects it with HTTP 401
  before inference. This is classified `deterministic` and returned immediately
  as `LiveProviderCompletedError`. The wizard's outer correction loop catches it
  and repeats the request. Tests observe three real children, then explicitly
  supersede the fixture to bound the reproduction.

The latter exercises actual `get_ai_response`, `_review_startup_response` and
`get_ai_starting_location`. Interview and semantic review both use T092; T093 is
starting-location selection. This distinction matters when reading logs.

Stable persisted URL/model/credentials already work on the untouched baseline,
including a 90 KB prompt. Therefore these tests prove a missing request snapshot
and the resulting loops under stated conditions; they do **not** prove which
condition occurred on the reporter's machine, nor a general inability to reach
OpenRouter. A lack of inference records alone cannot distinguish pre-connection
failure, authentication rejection or a stalled child. Credential-backend stalls are not reproduced by this fixture. See the
independent runtime follow-up below for a test deadline/import-latency finding;
that does not establish the cause of the reporter's startup loop.

## Repair

Resolve Local/Custom endpoint, credential and model once in the parent before
starting the live request's retry loop. Pass the detached dictionary through the
existing private stdin payload as `_request_local_endpoint`. The API router
consumes it; the OpenAI-compatible client and model override use the same frozen
values, including reactive local-template repair. Other providers keep their
existing adapter and connection behavior. Non-live local callers continue to
read settings as before.

Keep live-policy precedence. No cancellation, detached status, authority,
correlation, child reaping, retry classification or usage policy is bypassed.
There is no new global lock, throttle, SDK retry or provider switch. Credentials
are not put in subprocess argv/environment, SDK JSON, model captures or usage
records. Only the existing private parent-to-child pipe carries the snapshot.
No startup UI/retry-policy rewrite is included; a genuinely invalid configured
credential can still enter the existing outer wizard correction loop.

## Tests

Initial results at `b38907e1`: **22 passed** (61.87 seconds) with this repair; the identical
suite against public baseline **fails the five cases described above and passes
17 controls** (76.46 seconds). The existing five secure-provider-settings tests
also pass in an isolated installation (0.10 seconds).

Run `python -m pytest -q tests/test_live_custom_provider.py --tb=short`.
The test file isolates source/config/settings/keyring in temporary installations,
uses real subprocesses and installed SDK request/stream parsing, and substitutes
`httpx.MockTransport` for HTTP. Socket connections are forbidden. It inherits
only platform environment plumbing, never operator API keys or cloud settings.
No customer credentials or game saves are read.

Coverage: custom OpenRouter-compatible URL/model/auth; settings drift at dispatch
and retry; actual interview/review/location calls; LM Studio default/custom model
and JSON behavior; explicit JSON schema; OpenAI Responses, Legacy Chat Completions
and Gemini routing; detached scopes/status; pre-spawn, in-flight and completed-
response supersession; authority loss; child reaping; transient versus completed
HTTP errors; one usage record even with a second tracking attempt; diagnostic
redaction; capture exclusion; and two provider children overlapping at a barrier.

For baseline comparison, set `NEQ_PROVIDER_TEST_ROOT` to an untouched export of
that public revision and run the same test file from this branch. Only five
cases should fail: the two settings-race cases and three wizard credential cases.
All other cases should pass. The same five cases pass with the repair.

Localhost socket creation is denied by the audit sandbox, so these are HTTP
transport doubles rather than listening-server/TLS tests. Model responses are
scripted and no model quality, native Windows keyring behavior, browser UI or
paid OpenRouter acceptance is claimed. Reporter confirmation remains necessary
before declaring #557 resolved.

## Independent runtime follow-up

The original 22-case run used Python 3.10.19, pytest 9.0.2, OpenAI 2.36.0 and
HTTPX 0.28.1. An independent run with Python 3.11.16, pytest 9.1.1, OpenAI 3.11.0
and HTTPX 0.28.1, installed on WSL's Windows-mounted `/mnt/c`, timed out in the
T092/T093 stable controls. The deadline was the **test harness's 25 seconds**,
not a production live-provider timeout. Both independent controls had already
reached fake HTTP with matching authentication.

The T092 timeout reproduced using that exact interpreter and committed test.
Bounded `faulthandler` traces then showed the parent and real child still
importing OpenAI types/resources from `/mnt/c`, including lazy chat resources.
There was no observed missing dependency or evidence of a transport deadlock.
Copying only the unchanged installed OpenAI package (1,568 Python files) onto
`/tmp` made the same interpreter/control finish in **7.58 seconds**, with one
request, one usage receipt and the child reaped. The deadline remained 25 seconds.
A subsequent mounted-SDK control again timed out at 25 seconds during resource
imports. The child reached its endpoint phase at 9.37 seconds with mounted SDK
imports versus 1.73 seconds with the staged package.

The test fixture now stages that installed package once per pytest session,
outside the per-case deadline. It keeps the same interpreter, SDK version,
dependencies, real provider subprocess and SDK response parser. No production
imports, routing, retries or timeout values changed. Use a Linux-filesystem
pytest temp directory for WSL runs, e.g. `--basetemp=/tmp/neq-provider-tests`.
This is a deterministic contract test, not a cold-start performance benchmark.

The old harness also killed only its worker on `TimeoutExpired` and could leave
the worker's provider child behind. Each fixture now owns a separate POSIX
process group and terminates that group in `finally`, including interruption;
the direct worker is waited for and pipes closed. Two Linux regression cases
exercise timeout and `KeyboardInterrupt` with a real descendant process and
verify no owned process remains running. Normal successful cases still assert
the production code reaped its own provider children. The Windows tree-cleanup
branch has not been exercised; native Windows acceptance remains outstanding.

Historical desktop processes cannot be inspected from the diagnostic tool's
separate PID namespace. No claim is made that those original processes were
reaped. All new diagnostic runs used dedicated groups and bounded cleanup.

With SDK staging and the two cleanup cases, the repaired engine passes **24/24**
in both environments: Python 3.10/OpenAI 2.36.0 in **66.09 seconds**, and the
exact independent Python 3.11/OpenAI 3.11.0 interpreter in **222.97 seconds**.
A final cleanup-assertion refinement was also checked separately: **2 passed**.

The revised suite against untouched public `222553b8`, using that same desktop
interpreter/SDK, reports **5 expected failures and 19 passes in 266.42 seconds**.
Only the two settings-drift cases and three parent-only credential wizard cases
fail; there are no harness timeouts. This independently preserves the original
before/after result with both newer SDKs and the cleanup tests included.
