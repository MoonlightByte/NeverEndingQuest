"""Fake provider child for tests/test_reissue_limits.py (#1342).

Speaks the live_provider_call child protocol (P phase lines, one E envelope)
without any SDK, network or key. The step it plays comes from the plan file
named by NEQ_FAKE_CHILD_PLAN; NEQ_FAKE_CHILD_COUNT counts generations.
"""
import json
import os
import pickle
import sys


def main():
    request = pickle.loads(sys.stdin.buffer.read())
    count_path = os.environ["NEQ_FAKE_CHILD_COUNT"]
    try:
        index = int(open(count_path).read() or 0)
    except FileNotFoundError:
        index = 0
    open(count_path, "w").write(str(index + 1))
    plan = json.load(open(os.environ["NEQ_FAKE_CHILD_PLAN"]))
    step = plan[min(index, len(plan) - 1)]
    out = sys.stdout.buffer
    for phase in step.get("phases", []):
        out.write(("P " + json.dumps({"phase": phase, "t": 0.0}) + "\n").encode("ascii"))
    if step["kind"] == "success":
        envelope = {"kind": "success", "content": "ok", "response_id": "r", "provider": "openai",
                    "task_id": None, "model": "m", "finish_reason": "stop",
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                              "cached_tokens": 0, "reasoning_tokens": 0}}
    else:
        envelope = {"kind": "error", "error_class": step.get("error_class", "APIConnectionError"),
                    "cause_class": None, "error_code": step.get("error_code"),
                    "disposition": step["disposition"], "provider": "openai", "model": "m",
                    "task_id": None, "http_status": step.get("http_status"), "retry_after": None}
    envelope["correlation"] = request["correlation"]
    body = pickle.dumps(envelope)
    out.write(("E %d\n" % len(body)).encode("ascii"))
    out.write(body)
    out.flush()


if __name__ == "__main__":
    main()
