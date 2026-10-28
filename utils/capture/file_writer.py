"""Append-only JSON file writer for multi-model capture records.

Thread-safe: per-file locks prevent concurrent write corruption.
Records are identified by (task_id, timestamp) for background output merging.
"""
import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4


_PROCESS_LOCKS = {}
_PROCESS_LOCKS_GUARD = threading.Lock()

_REPR_LIMIT = 300
# A value _json_safe left out; never written.
_LEFT_OUT = object()


def _described(value):
    try:
        shown = repr(value)
    except Exception:
        shown = "<repr failed>"
    return "%s: %s" % (type(value).__name__, shown[:_REPR_LIMIT])


def _json_safe(value, path, found, active=None):
    """A copy of ``value`` that json.dump writes as it writes the original, with
    each value it cannot write left out (#1621).

    Values are kept by json's own isinstance tests, in its order, so a str or
    int subclass, an OrderedDict or a NaN is written exactly as before. A value
    json would refuse, a dict key it would refuse, or a reference back to an
    enclosing container is left out of its dict (None in a list, so later
    indexes stay true); ``found`` maps its dotted path to its type and repr.
    """
    if isinstance(value, str) or value is None or value is True or value is False:
        return value
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, (list, tuple, dict)):
        found[path] = _described(value)
        return _LEFT_OUT
    active = set() if active is None else active
    if id(value) in active:
        found[path] = "cycle: a reference back to an enclosing %s" % type(value).__name__
        return _LEFT_OUT
    active.add(id(value))
    try:
        if isinstance(value, dict):
            copied = {}
            for key, item in value.items():
                if not (isinstance(key, (str, int, float)) or key is None):
                    found["%s.<key %s>" % (path, type(key).__name__) if path
                          else "<key %s>" % type(key).__name__] = _described(key)
                    continue
                child = _json_safe(item, "%s.%s" % (path, key) if path else str(key), found, active)
                if child is not _LEFT_OUT:
                    copied[key] = child
            return copied
        copied = []
        for index, item in enumerate(value):
            child = _json_safe(item, "%s[%d]" % (path, index), found, active)
            copied.append(None if child is _LEFT_OUT else child)
        return copied
    finally:
        active.discard(id(value))


def _process_lock(path):
    """Return one in-process lock shared by every writer instance for a file."""
    with _PROCESS_LOCKS_GUARD:
        if path not in _PROCESS_LOCKS:
            _PROCESS_LOCKS[path] = threading.Lock()
        return _PROCESS_LOCKS[path]


class CaptureFileWriter:
    """Writes and merges capture records into per-task-id JSON files."""

    def __init__(self, capture_dir="model_captures", error_logger=None):
        self.capture_dir = capture_dir
        # The capture error log (model_captures/errors.log), for values left out.
        self.error_logger = error_logger
        os.makedirs(capture_dir, exist_ok=True)

    def _report(self, task_id, invocation_id, found):
        """One error-log line per value left out of a record (#1621)."""
        if self.error_logger is None:
            return
        for path, described in found.items():
            try:
                self.error_logger.error(
                    "[%s] capture record %s: left out non-JSON value at %s (%s)"
                    % (task_id, invocation_id, path, described.split(":", 1)[0])
                )
            except Exception:
                pass

    def _get_lock(self, task_id):
        return _process_lock(os.path.abspath(self._file_path(task_id)))

    @contextmanager
    def _locked_file(self, task_id):
        """Serialize read-modify-write across threads, instances, and processes."""
        process_lock = self._get_lock(task_id)
        lock_path = self._file_path(task_id) + ".lock"
        with process_lock:
            with open(lock_path, "a+b") as lock_file:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0, os.SEEK_END)
                    if lock_file.tell() == 0:
                        lock_file.write(b"\0")
                        lock_file.flush()
                    from utils.path_transaction_lock import wait_for_windows_lock
                    wait_for_windows_lock(lock_file)  # no ten-try cap (#944)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        lock_file.seek(0)
                        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

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
                # Preserve the damaged evidence instead of treating it as an
                # empty list and erasing it on the next successful write.
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                quarantine = os.path.join(
                    self.capture_dir,
                    f"{task_id}.corrupt-{stamp}-{uuid4().hex}.json",
                )
                os.replace(path, quarantine)
                return []

    def _write(self, task_id, records):
        path = self._file_path(task_id)
        # HIGH-13: atomic write -- serialize to a temp file then os.replace, so a
        # crash mid-write can't leave a truncated/empty capture JSON. os.replace
        # is atomic on the same filesystem.
        tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.{uuid4().hex}.tmp"
        try:
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def write_primary(self, task_id, file_path, line, tier, input_data,
                      label, content, latency_s, timestamp=None,
                      token_usage=None, cost_usd=None, invocation_id=None):
        """Write the initial record for a callsite invocation (primary model output)."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()
        if invocation_id is None:
            invocation_id = str(uuid4())

        output_entry = {"content": content, "latency_s": latency_s}
        if token_usage:
            output_entry["tokens"] = token_usage
        if cost_usd is not None:
            output_entry["cost_usd"] = cost_usd

        record = {
            "timestamp": timestamp,
            "invocation_id": invocation_id,
            "task_id": task_id,
            "file": file_path,
            "line": line,
            "tier": tier,
            "input": input_data,
            "outputs": {
                label: output_entry
            },
            "errors": {}
        }
        found = {}
        record = _json_safe(record, "", found)
        if found:
            record["unserializable"] = found

        with self._locked_file(task_id):
            records = self._read(task_id)
            records.append(record)
            self._write(task_id, records)
        if found:
            self._report(task_id, invocation_id, found)
        return invocation_id

    def merge_background_output(self, task_id, invocation_id, label, content, latency_s,
                                token_usage=None, cost_usd=None):
        """Merge a background variant result into its exact invocation record."""
        with self._locked_file(task_id):
            records = self._read(task_id)
            record = self._find_record(records, task_id, invocation_id)
            if record is None:
                return False
            output_entry = {"content": content, "latency_s": latency_s}
            if token_usage:
                output_entry["tokens"] = token_usage
            if cost_usd is not None:
                output_entry["cost_usd"] = cost_usd
            found = {}
            record["outputs"][label] = _json_safe(output_entry, "outputs.%s" % label, found)
            if found:
                record.setdefault("unserializable", {}).update(found)
            self._write(task_id, records)
        if found:
            self._report(task_id, invocation_id, found)
        return True

    def merge_background_error(self, task_id, invocation_id, label, error_str):
        """Record an error from a background variant into the errors dict."""
        with self._locked_file(task_id):
            records = self._read(task_id)
            record = self._find_record(records, task_id, invocation_id)
            if record is None:
                return False
            found = {}
            safe = _json_safe(error_str, "errors.%s" % label, found)
            record["errors"][label] = None if safe is _LEFT_OUT else safe
            if found:
                record.setdefault("unserializable", {}).update(found)
            self._write(task_id, records)
        if found:
            self._report(task_id, invocation_id, found)
        return True

    @staticmethod
    def _find_record(records, task_id, invocation_id):
        for record in reversed(records):
            if (
                record.get("task_id") == task_id
                and record.get("invocation_id") == invocation_id
            ):
                return record

        # Compatibility for pre-invocation-ID callers/captures: timestamp
        # matching is permitted only when it identifies exactly one record.
        timestamp_matches = [
            record
            for record in records
            if record.get("task_id") == task_id
            and record.get("timestamp") == invocation_id
        ]
        return timestamp_matches[0] if len(timestamp_matches) == 1 else None
