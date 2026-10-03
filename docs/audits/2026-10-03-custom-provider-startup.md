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
failure, authentication rejection or a stalled child. Child-import/credential
backend stalls are not reproduced by this fixture.

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

Final results: **22 passed** (61.87 seconds) with this repair; the identical
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
