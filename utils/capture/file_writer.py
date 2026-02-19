"""Append-only JSON file writer for multi-model capture records.

Thread-safe: per-file locks prevent concurrent write corruption.
Records are identified by (task_id, timestamp) for background output merging.
"""
import json
import os
import threading
from datetime import datetime, timezone


class CaptureFileWriter:
    """Writes and merges capture records into per-task-id JSON files."""

    def __init__(self, capture_dir="model_captures"):
        self.capture_dir = capture_dir
        self._locks = {}
        self._locks_lock = threading.Lock()
        os.makedirs(capture_dir, exist_ok=True)

    def _get_lock(self, task_id):
        with self._locks_lock:
            if task_id not in self._locks:
                self._locks[task_id] = threading.Lock()
            return self._locks[task_id]

    def _file_path(self, task_id):
        return os.path.join(self.capture_dir, f"{task_id}.json")

    def _read(self, task_id):
        path = self._file_path(task_id)
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except (json.JSONDecodeError, ValueError):
                return []

    def _write(self, task_id, records):
        path = self._file_path(task_id)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)

    def write_primary(self, task_id, file_path, line, tier, input_data,
                      label, content, latency_s, timestamp=None):
        """Write the initial record for a callsite invocation (primary model output)."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        record = {
            "timestamp": timestamp,
            "task_id": task_id,
            "file": file_path,
            "line": line,
            "tier": tier,
            "input": input_data,
            "outputs": {
                label: {"content": content, "latency_s": latency_s}
            },
            "errors": {}
        }

        lock = self._get_lock(task_id)
        with lock:
            records = self._read(task_id)
            records.append(record)
            self._write(task_id, records)

    def merge_background_output(self, task_id, timestamp, label, content, latency_s):
        """Merge a background variant result into an existing record."""
        lock = self._get_lock(task_id)
        with lock:
            records = self._read(task_id)
            for record in reversed(records):
                if record["task_id"] == task_id and record["timestamp"] == timestamp:
                    record["outputs"][label] = {
                        "content": content,
                        "latency_s": latency_s
                    }
                    self._write(task_id, records)
                    return

    def merge_background_error(self, task_id, timestamp, label, error_str):
        """Record an error from a background variant into the errors dict."""
        lock = self._get_lock(task_id)
        with lock:
            records = self._read(task_id)
            for record in reversed(records):
                if record["task_id"] == task_id and record["timestamp"] == timestamp:
                    record["errors"][label] = error_str
                    self._write(task_id, records)
                    return
