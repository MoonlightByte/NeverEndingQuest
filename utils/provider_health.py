"""Provider health check: one real, tiny call through the live child transport.

Developer tool, off the play path (#409 Task 5). It answers "is the
configured provider actually working right now, and how long does each
transport phase take?" with the same code path the game uses, and prints the
phase timeline the child reported. Exit code 0 when the answer arrived.

Usage (from the repository root):
    python utils/provider_health.py [--provider openai|legacy|lmstudio]
"""
import argparse
import os
import sys
import time


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", default=None,
                        help="provider to check (default: the configured one)")
    args = parser.parse_args(argv)

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    os.chdir(repo_root)
    import model_config
    from utils.capture.live_provider_call import call_live_provider

    provider = args.provider or model_config.get_provider()
    request_kwargs = model_config.resolve_callsite_config("T107", provider, 0)
    request_kwargs["_request_provider"] = provider
    request_kwargs["task_id"] = "T107"
    request_kwargs["response_format"] = None
    messages = [
        {"role": "system", "content": "You are a connectivity check. Answer in one word."},
        {"role": "user", "content": "Reply with the single word OK."},
    ]
    started = time.monotonic()
    print("provider=%s model=%s" % (provider, request_kwargs.get("model")))
    try:
        response = call_live_provider(
            "T107", messages, request_kwargs, policy="advisory",
            status_emit=lambda message: print("  status: %s" % message),
        )
    except Exception as exc:
        print("FAILED after %.1f s: %s: %s" % (
            time.monotonic() - started, type(exc).__name__, str(exc)[:300]))
        return 1
    phases = (response.raw_response or {}).get("liveProviderPhases", {})
    print("answer: %r in %.1f s" % (
        (response.choices[0].message.content or "").strip()[:40],
        time.monotonic() - started))
    usage = response.usage.model_dump()
    print("usage: prompt=%d completion=%d cached=%d reasoning=%d" % (
        usage["prompt_tokens"], usage["completion_tokens"],
        usage["cached_tokens"], usage["reasoning_tokens"]))
    print("phases (seconds from generation start):")
    for name, offset in sorted(phases.items(), key=lambda item: item[1]):
        print("  %-14s %7.3f" % (name, offset))
    return 0


if __name__ == "__main__":
    sys.exit(main())
