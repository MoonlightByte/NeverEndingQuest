"""Tests for capture file writer."""
import sys
import os
import json
import tempfile
import threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.capture.file_writer import CaptureFileWriter


def test_creates_file_on_first_write(tmp_path):
    """Writer creates T013.json if it does not exist."""
    writer = CaptureFileWriter(str(tmp_path))
    writer.write_primary("T013", "core/ai/action_handler.py", 1003, "full",
                         {"messages": [], "temperature": 0.7},
                         "gpt-4.1|baseline", "response text", 0.85,
                         timestamp="2026-02-18T14:00:00Z")

    target = tmp_path / "T013.json"
    assert target.exists()
    data = json.loads(target.read_text())
    assert len(data) == 1
    assert data[0]["task_id"] == "T013"
    assert "gpt-4.1|baseline" in data[0]["outputs"]


def test_merge_background_output(tmp_path):
    """Background output merges into existing record by timestamp+task_id."""
    writer = CaptureFileWriter(str(tmp_path))
    ts = "2026-02-18T14:00:00Z"

    writer.write_primary("T013", "core/ai/action_handler.py", 1003, "full",
                         {"messages": []}, "gpt-4.1|baseline", "primary", 0.8, ts)

    writer.merge_background_output("T013", ts, "gpt-5.2|effort=none", "alt response", 0.6)

    data = json.loads((tmp_path / "T013.json").read_text())
    assert len(data) == 1  # still one record
    assert "gpt-5.2|effort=none" in data[0]["outputs"]
    assert data[0]["outputs"]["gpt-5.2|effort=none"]["content"] == "alt response"
    assert data[0]["outputs"]["gpt-5.2|effort=none"]["latency_s"] == 0.6


def test_merge_error(tmp_path):
    """Errors from background variants recorded in errors dict."""
    writer = CaptureFileWriter(str(tmp_path))
    ts = "2026-02-18T14:00:00Z"

    writer.write_primary("T013", "core/ai/action_handler.py", 1003, "full",
                         {"messages": []}, "gpt-4.1|baseline", "primary", 0.8, ts)

    writer.merge_background_error("T013", ts, "gemini-3-pro|thinking=high", "RateLimitError")

    data = json.loads((tmp_path / "T013.json").read_text())
    assert "gemini-3-pro|thinking=high" in data[0]["errors"]


def test_multiple_records_accumulate(tmp_path):
    """Each invocation appends a new record to the array."""
    writer = CaptureFileWriter(str(tmp_path))

    writer.write_primary("T013", "f.py", 1, "full", {}, "gpt-4.1|baseline",
                         "r1", 0.8, "2026-02-18T14:00:00Z")
    writer.write_primary("T013", "f.py", 1, "full", {}, "gpt-4.1|baseline",
                         "r2", 0.9, "2026-02-18T14:01:00Z")

    data = json.loads((tmp_path / "T013.json").read_text())
    assert len(data) == 2


def test_thread_safe_concurrent_writes(tmp_path):
    """Concurrent writes from multiple threads do not corrupt the file."""
    writer = CaptureFileWriter(str(tmp_path))
    ts = "2026-02-18T14:00:00Z"

    writer.write_primary("T013", "f.py", 1, "full", {}, "gpt-4.1|baseline",
                         "primary", 0.8, ts)

    labels = [f"variant-{i}" for i in range(20)]
    threads = [
        threading.Thread(
            target=writer.merge_background_output,
            args=("T013", ts, label, f"content-{label}", 0.5)
        )
        for label in labels
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    data = json.loads((tmp_path / "T013.json").read_text())
    assert len(data) == 1
    assert len(data[0]["outputs"]) == 21  # primary + 20 variants
