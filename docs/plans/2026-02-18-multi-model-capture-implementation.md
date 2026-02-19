# Multi-Model Capture System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a fire-and-forget parallel telemetry capture system that fires all model variants in
background threads whenever a game API callsite executes, recording input/output pairs per callsite
for later comparison - without changing game behavior.

**Architecture:** `capture_and_fanout()` wraps individual callsites. Primary gpt-4.1 call runs
synchronously and returns immediately. A shared `ThreadPoolExecutor` fires all other variants
(gpt-5.2, gpt-5-mini, Gemini 3) in background threads. Results append to per-task-id JSON files
in a gitignored `model_captures/` folder.

**Tech Stack:** Python stdlib (`threading`, `concurrent.futures`, `json`, `time`), `openai` SDK
(already installed), `google-genai` SDK (check/install), `model_config.py` toggle.

**Design doc:** `docs/plans/2026-02-18-capture-system-design.md`
**Callsite inventory:** `docs/audit/2026-02-12-openai-api-call-inventory.json`

---

### Task 1: Setup - toggle, package skeleton, gitignore

**Files:**
- Modify: `model_config.py`
- Modify: `.gitignore`
- Create: `utils/capture/__init__.py`
- Create: `model_captures/.gitkeep_readme.txt` (documents the folder purpose locally)

**Step 1: Add capture toggle to model_config.py**

Open `model_config.py` and add at the end:

```python
# --- Multi-Model Capture Settings ---
MULTI_MODEL_CAPTURE = False  # Set True to enable parallel telemetry capture
```

**Step 2: Verify model_captures/ is in .gitignore**

Check `.gitignore` already has `model_captures/` (added in design commit). If not, add it under
the "Reference documents" block:

```
# Multi-model capture data (local telemetry only)
model_captures/
```

**Step 3: Create the utils/capture package**

```bash
mkdir -p utils/capture
touch utils/capture/__init__.py
```

**Step 4: Create model_captures/ folder with a local readme**

```bash
mkdir -p model_captures
```

Create `model_captures/.gitkeep_readme.txt` with content:
```
This folder is gitignored. It contains per-callsite telemetry JSON files from
the multi-model capture system. See docs/plans/2026-02-18-capture-system-design.md.

Files: T012.json through T095.json (one per runtime API callsite)
Config: capture_config.json
Errors: errors.log
Test: test_all_models.py
```

**Step 5: Check google-genai is installed**

```bash
pip show google-genai 2>/dev/null || echo "NOT INSTALLED"
```

If not installed:
```bash
pip install google-genai
```

Then add to `requirements.txt` if it exists:
```bash
grep -q "google-genai" requirements.txt || echo "google-genai" >> requirements.txt
```

**Step 6: Commit**

```bash
git add model_config.py .gitignore utils/capture/__init__.py requirements.txt
git commit -m "feat(capture): add package skeleton, toggle, and gitignore for model_captures/"
```

---

### Task 2: OpenAI caller module

**Files:**
- Create: `utils/capture/openai_caller.py`
- Create: `tests/capture/openai_caller_tests.py`

**Step 1: Write the failing tests**

Create `tests/capture/openai_caller_tests.py`:

```python
"""Tests for OpenAI variant caller parameter building."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.capture.openai_caller import build_openai_params


def test_baseline_with_temperature():
    """gpt-4.1 baseline: passes temperature, no reasoning_effort."""
    variant = {
        "provider": "openai",
        "model": "gpt-4.1-2025-04-14",
        "reasoning_effort": None,
        "use_caller_temp": True,
        "label": "gpt-4.1|baseline"
    }
    messages = [{"role": "user", "content": "hello"}]
    params = build_openai_params(variant, messages, caller_temperature=0.7)

    assert params["model"] == "gpt-4.1-2025-04-14"
    assert params["messages"] == messages
    assert params["temperature"] == 0.7
    assert "reasoning_effort" not in params
    assert "max_tokens" not in params
    assert "max_completion_tokens" not in params


def test_gpt52_effort_none_with_temperature():
    """gpt-5.2 effort=none: passes temperature alongside reasoning_effort."""
    variant = {
        "provider": "openai",
        "model": "gpt-5.2",
        "reasoning_effort": "none",
        "use_caller_temp": True,
        "label": "gpt-5.2|effort=none"
    }
    params = build_openai_params(variant, [], caller_temperature=0.8)

    assert params["model"] == "gpt-5.2"
    assert params["reasoning_effort"] == "none"
    assert params["temperature"] == 0.8
    assert "max_tokens" not in params


def test_gpt52_effort_low_no_temperature():
    """gpt-5.2 effort=low: omits temperature (incompatible with reasoning > none)."""
    variant = {
        "provider": "openai",
        "model": "gpt-5.2",
        "reasoning_effort": "low",
        "use_caller_temp": False,
        "label": "gpt-5.2|effort=low"
    }
    params = build_openai_params(variant, [], caller_temperature=0.7)

    assert params["reasoning_effort"] == "low"
    assert "temperature" not in params
    assert "max_tokens" not in params


def test_no_token_limits_ever():
    """Confirm max_tokens and max_completion_tokens are never present."""
    variant = {
        "provider": "openai",
        "model": "gpt-5-mini",
        "reasoning_effort": None,
        "use_caller_temp": False,
        "label": "gpt-5-mini"
    }
    params = build_openai_params(variant, [], caller_temperature=None)

    assert "max_tokens" not in params
    assert "max_completion_tokens" not in params


def test_caller_temp_none_skips_temperature():
    """If caller did not pass temperature, it is not included even with use_caller_temp."""
    variant = {
        "provider": "openai",
        "model": "gpt-4.1-2025-04-14",
        "reasoning_effort": None,
        "use_caller_temp": True,
        "label": "gpt-4.1|baseline"
    }
    params = build_openai_params(variant, [], caller_temperature=None)

    assert "temperature" not in params
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/capture/openai_caller_tests.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` - `openai_caller` does not exist yet.

**Step 3: Implement `utils/capture/openai_caller.py`**

```python
"""OpenAI variant caller for multi-model capture system.

Builds call parameters and executes a single OpenAI variant call.
Never sets max_tokens or max_completion_tokens.
"""
import time
from openai import OpenAI

_client = None


def _get_client():
    global _client
    if _client is None:
        import config
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def build_openai_params(variant, messages, caller_temperature=None):
    """Build the kwargs dict for client.chat.completions.create.

    Args:
        variant: dict from capture_config full_tier_variants or mini_tier_variants
        messages: the original messages list from the callsite
        caller_temperature: the temperature value the callsite passed, or None

    Returns:
        dict of kwargs - never includes max_tokens or max_completion_tokens
    """
    params = {
        "model": variant["model"],
        "messages": messages,
    }

    if variant.get("reasoning_effort") is not None:
        params["reasoning_effort"] = variant["reasoning_effort"]

    if variant.get("use_caller_temp") and caller_temperature is not None:
        params["temperature"] = caller_temperature

    # Never add max_tokens or max_completion_tokens - ever
    return params


def call_openai_variant(variant, messages, caller_temperature=None, caller_kwargs=None):
    """Execute one OpenAI variant call and return (content, latency_s).

    Args:
        variant: variant config dict
        messages: original messages list
        caller_temperature: temperature the original callsite used, or None
        caller_kwargs: other kwargs from original call (response_format etc)

    Returns:
        tuple of (content_str, latency_seconds)

    Raises:
        Exception: any API error - caller should catch
    """
    params = build_openai_params(variant, messages, caller_temperature)

    # Pass through response_format if original call used it
    if caller_kwargs and "response_format" in caller_kwargs:
        params["response_format"] = caller_kwargs["response_format"]

    client = _get_client()
    start = time.time()
    response = client.chat.completions.create(**params)
    latency_s = round(time.time() - start, 3)

    content = response.choices[0].message.content
    return content, latency_s
```

**Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/capture/openai_caller_tests.py -v
```

Expected: All 5 tests `PASSED`.

**Step 5: Commit**

```bash
git add utils/capture/openai_caller.py tests/capture/openai_caller_tests.py
git commit -m "feat(capture): add OpenAI variant caller with parameter building"
```

---

### Task 3: Gemini caller module

**Files:**
- Create: `utils/capture/gemini_caller.py`
- Create: `tests/capture/gemini_caller_tests.py`

**Step 1: Write the failing tests**

Create `tests/capture/gemini_caller_tests.py`:

```python
"""Tests for Gemini message format conversion."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from utils.capture.gemini_caller import convert_messages_to_gemini, build_gemini_config


def test_system_message_extracted():
    """System message becomes system_instruction, not part of contents."""
    messages = [
        {"role": "system", "content": "You are a dungeon master."},
        {"role": "user", "content": "What do I see?"}
    ]
    system_instruction, contents = convert_messages_to_gemini(messages)

    assert system_instruction == "You are a dungeon master."
    assert len(contents) == 1
    assert contents[0]["role"] == "user"
    assert "What do I see?" in str(contents[0]["parts"])


def test_no_system_message():
    """Messages without a system role: system_instruction is None."""
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello back"}
    ]
    system_instruction, contents = convert_messages_to_gemini(messages)

    assert system_instruction is None
    assert len(contents) == 2


def test_assistant_role_mapped_to_model():
    """OpenAI 'assistant' role maps to Gemini 'model' role."""
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello"}
    ]
    _, contents = convert_messages_to_gemini(messages)

    roles = [c["role"] for c in contents]
    assert "model" in roles
    assert "assistant" not in roles


def test_build_config_low_thinking_with_temp():
    """Low thinking with temperature included."""
    variant = {
        "model": "gemini-3-pro-preview",
        "thinking_level": "low",
        "use_caller_temp": True,
        "label": "gemini-3-pro|thinking=low"
    }
    config = build_gemini_config(variant, caller_temperature=0.7, use_json=False)

    assert config["thinking_level"] == "low"
    assert config.get("temperature") == 0.7


def test_build_config_high_thinking_no_temp():
    """High thinking: temperature omitted (use_caller_temp=False)."""
    variant = {
        "model": "gemini-3-pro-preview",
        "thinking_level": "high",
        "use_caller_temp": False,
        "label": "gemini-3-pro|thinking=high"
    }
    config = build_gemini_config(variant, caller_temperature=0.7, use_json=False)

    assert config["thinking_level"] == "high"
    assert "temperature" not in config


def test_build_config_json_output():
    """JSON response_mime_type set when use_json=True."""
    variant = {
        "model": "gemini-3-flash-preview",
        "thinking_level": "low",
        "use_caller_temp": False,
        "label": "gemini-3-flash|thinking=low"
    }
    config = build_gemini_config(variant, caller_temperature=None, use_json=True)

    assert config.get("response_mime_type") == "application/json"
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/capture/gemini_caller_tests.py -v
```

Expected: `ImportError` - `gemini_caller` does not exist yet.

**Step 3: Implement `utils/capture/gemini_caller.py`**

```python
"""Gemini variant caller for multi-model capture system.

Handles OpenAI->Gemini message format conversion and executes Gemini variant calls.
"""
import os
import time

_gemini_client = None


def _get_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        api_key_file = "google_api.pi"
        if os.path.exists(api_key_file):
            with open(api_key_file, 'r') as f:
                content = f.read().strip()
                if 'api_key=' in content:
                    api_key = content.split('api_key=')[1].strip()
                else:
                    api_key = content
        else:
            raise FileNotFoundError(
                "google_api.pi not found - Gemini API key required for capture"
            )
        os.environ['GEMINI_API_KEY'] = api_key
        _gemini_client = genai.Client()
    return _gemini_client


def convert_messages_to_gemini(messages):
    """Convert OpenAI messages format to Gemini contents format.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": "..."}

    Returns:
        tuple of (system_instruction_str_or_None, contents_list)
        where contents_list items are {"role": "user"|"model", "parts": [{"text": "..."}]}
    """
    system_instruction = None
    contents = []

    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")

        if role == "system":
            system_instruction = content
            continue

        # Map OpenAI roles to Gemini roles
        gemini_role = "model" if role == "assistant" else "user"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": content}]
        })

    return system_instruction, contents


def build_gemini_config(variant, caller_temperature=None, use_json=False):
    """Build the config dict for generate_content call.

    Args:
        variant: variant config dict with thinking_level and use_caller_temp
        caller_temperature: temperature from original callsite, or None
        use_json: True if original call used response_format json_object

    Returns:
        dict of config values (not yet a types.GenerateContentConfig object)
    """
    config = {
        "thinking_level": variant.get("thinking_level", "low")
    }

    if variant.get("use_caller_temp") and caller_temperature is not None:
        config["temperature"] = caller_temperature

    if use_json:
        config["response_mime_type"] = "application/json"

    return config


def call_gemini_variant(variant, messages, caller_temperature=None, caller_kwargs=None):
    """Execute one Gemini variant call and return (content, latency_s).

    Args:
        variant: variant config dict
        messages: original OpenAI-format messages list
        caller_temperature: temperature from original callsite, or None
        caller_kwargs: other kwargs from original call (response_format etc)

    Returns:
        tuple of (content_str, latency_seconds)

    Raises:
        Exception: any API error - caller should catch
    """
    from google.genai import types

    use_json = (
        caller_kwargs is not None
        and caller_kwargs.get("response_format", {}).get("type") == "json_object"
    )

    system_instruction, contents = convert_messages_to_gemini(messages)
    cfg = build_gemini_config(variant, caller_temperature, use_json)

    # Build GenerateContentConfig
    config_kwargs = {
        "thinking_config": types.ThinkingConfig(thinking_level=cfg["thinking_level"])
    }
    if "temperature" in cfg:
        config_kwargs["temperature"] = cfg["temperature"]
    if "response_mime_type" in cfg:
        config_kwargs["response_mime_type"] = cfg["response_mime_type"]
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    gen_config = types.GenerateContentConfig(**config_kwargs)

    # Convert contents to types.Content objects
    gemini_contents = [
        types.Content(
            role=c["role"],
            parts=[types.Part(text=p["text"]) for p in c["parts"]]
        )
        for c in contents
    ]

    client = _get_client()
    start = time.time()
    response = client.models.generate_content(
        model=variant["model"],
        contents=gemini_contents,
        config=gen_config,
    )
    latency_s = round(time.time() - start, 3)

    return response.text, latency_s
```

**Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/capture/gemini_caller_tests.py -v
```

Expected: All 6 tests `PASSED`. (These are pure unit tests - no API calls made.)

**Step 5: Commit**

```bash
git add utils/capture/gemini_caller.py tests/capture/gemini_caller_tests.py
git commit -m "feat(capture): add Gemini variant caller with message format conversion"
```

---

### Task 4: File writer

**Files:**
- Create: `utils/capture/file_writer.py`
- Create: `tests/capture/file_writer_tests.py`

**Step 1: Write the failing tests**

Create `tests/capture/file_writer_tests.py`:

```python
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
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/capture/file_writer_tests.py -v
```

Expected: `ImportError` - `file_writer` does not exist yet.

**Step 3: Implement `utils/capture/file_writer.py`**

```python
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
        """Write the initial record for a callsite invocation (primary model output).

        Args:
            task_id: e.g. "T013"
            file_path: source file e.g. "core/ai/action_handler.py"
            line: line number
            tier: "full" or "mini"
            input_data: dict with messages, temperature, etc.
            label: e.g. "gpt-4.1|baseline"
            content: response string
            latency_s: float seconds
            timestamp: ISO timestamp string, defaults to now UTC
        """
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
        """Merge a background variant result into an existing record.

        Finds the record matching (task_id, timestamp) and adds the output.
        If no matching record found, logs silently and skips.
        """
        lock = self._get_lock(task_id)
        with lock:
            records = self._read(task_id)
            for record in reversed(records):  # most recent first
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
```

**Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/capture/file_writer_tests.py -v
```

Expected: All 5 tests `PASSED`.

**Step 5: Commit**

```bash
git add utils/capture/file_writer.py tests/capture/file_writer_tests.py
git commit -m "feat(capture): add thread-safe file writer with record merging"
```

---

### Task 5: `capture_and_fanout()` main function

**Files:**
- Create: `utils/capture/multi_model_capture.py`
- Create: `tests/capture/multi_model_capture_tests.py`

**Step 1: Write the failing tests**

Create `tests/capture/multi_model_capture_tests.py`:

```python
"""Tests for capture_and_fanout wrapper."""
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock, call
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


def _make_mock_response(content="mock response"):
    mock = MagicMock()
    mock.choices = [MagicMock()]
    mock.choices[0].message.content = content
    return mock


def test_returns_primary_response_when_capture_disabled(tmp_path):
    """With capture disabled, returns primary call result transparently."""
    mock_create = MagicMock(return_value=_make_mock_response("primary"))

    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        from utils.capture.multi_model_capture import capture_and_fanout
        result = capture_and_fanout(
            "T013", mock_create,
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4.1-2025-04-14",
        )

    assert result.choices[0].message.content == "primary"
    mock_create.assert_called_once()


def test_passes_original_kwargs_to_primary(tmp_path):
    """All original kwargs reach the primary call unchanged."""
    mock_create = MagicMock(return_value=_make_mock_response())

    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        from utils.capture.multi_model_capture import capture_and_fanout
        capture_and_fanout(
            "T013", mock_create,
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-4.1-2025-04-14",
            temperature=0.7,
            reasoning_effort="none",
        )

    _, kwargs = mock_create.call_args
    assert kwargs["temperature"] == 0.7
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["model"] == "gpt-4.1-2025-04-14"


def test_determines_tier_full():
    """Full model config variables map to 'full' tier."""
    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        from utils.capture.multi_model_capture import _determine_tier
        import model_config as mc
        assert _determine_tier(mc.DM_MAIN_MODEL) == "full"


def test_determines_tier_mini():
    """Mini model config variables map to 'mini' tier."""
    with patch("model_config.MULTI_MODEL_CAPTURE", False):
        from utils.capture.multi_model_capture import _determine_tier
        import model_config as mc
        assert _determine_tier(mc.DM_MINI_MODEL) == "mini"
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/capture/multi_model_capture_tests.py -v
```

Expected: `ImportError` - module does not exist yet.

**Step 3: Implement `utils/capture/multi_model_capture.py`**

```python
"""Multi-model capture and fanout wrapper.

Primary call runs synchronously and returns immediately.
All other variants fire in background threads via ThreadPoolExecutor.
"""
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import model_config
from utils.capture.file_writer import CaptureFileWriter
from utils.capture.openai_caller import call_openai_variant
from utils.capture.gemini_caller import call_gemini_variant

# Shared thread pool - initialized once
_executor = ThreadPoolExecutor(max_workers=8)
_writer = None
_config = None
_config_lock = threading.Lock()

# Error logger
_error_logger = None


def _get_error_logger():
    global _error_logger
    if _error_logger is None:
        os.makedirs("model_captures", exist_ok=True)
        _error_logger = logging.getLogger("capture_errors")
        if not _error_logger.handlers:
            handler = logging.FileHandler("model_captures/errors.log")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            _error_logger.addHandler(handler)
            _error_logger.setLevel(logging.ERROR)
    return _error_logger


def _get_writer():
    global _writer
    if _writer is None:
        _writer = CaptureFileWriter("model_captures")
    return _writer


def _load_config():
    global _config
    with _config_lock:
        if _config is not None:
            return _config
        config_path = "model_captures/capture_config.json"
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                _config = json.load(f)
        else:
            _config = {"capture_enabled": False, "full_tier_variants": [], "mini_tier_variants": []}
        return _config


def _determine_tier(model_string):
    """Determine if a model string is full or mini tier.

    Checks against known mini model config variables. Everything else is full.
    """
    mini_models = {
        model_config.DM_MINI_MODEL,
        model_config.DM_SUMMARIZATION_MODEL,
        model_config.NARRATIVE_COMPRESSION_MODEL,
        model_config.COMBAT_DIALOGUE_SUMMARY_MODEL,
        model_config.ADVENTURE_SUMMARY_MODEL,
        model_config.PLOT_UPDATE_MODEL,
        model_config.NPC_INFO_UPDATE_MODEL,
        model_config.ENCOUNTER_UPDATE_MODEL,
        model_config.TRANSITION_VALIDATOR_MODEL,
    }
    # Also catch by string fragment for safety
    if model_string in mini_models or "mini" in model_string.lower():
        return "mini"
    return "full"


def _fire_background_variant(variant, task_id, messages, timestamp,
                              caller_temperature, caller_kwargs):
    """Execute one variant call and write result. Runs in thread pool."""
    label = variant["label"]
    writer = _get_writer()
    try:
        if variant["provider"] == "openai":
            content, latency_s = call_openai_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        else:
            content, latency_s = call_gemini_variant(
                variant, messages, caller_temperature, caller_kwargs
            )
        writer.merge_background_output(task_id, timestamp, label, content, latency_s)
    except Exception as e:
        error_str = f"{type(e).__name__}: {e}"
        writer.merge_background_error(task_id, timestamp, label, error_str)
        _get_error_logger().error(f"[{task_id}][{label}] {error_str}")


def capture_and_fanout(task_id, primary_fn, messages, **kwargs):
    """Drop-in wrapper around client.chat.completions.create.

    Fires the primary gpt-4.1 call synchronously, returns immediately.
    Submits all other variants to background thread pool.

    Usage:
        # Before:
        response = client.chat.completions.create(model=..., messages=messages, temperature=0.7)

        # After:
        response = capture_and_fanout("T013", client.chat.completions.create,
                                      messages=messages, model=..., temperature=0.7)

    Args:
        task_id: task ID string from inventory e.g. "T013"
        primary_fn: the original client.chat.completions.create callable
        messages: the messages list (also passed as kwarg for the primary call)
        **kwargs: all original kwargs (model, temperature, reasoning_effort, etc.)

    Returns:
        The primary gpt-4.1 response object, unmodified.
    """
    # Always fire primary call synchronously
    import time
    start = time.time()
    response = primary_fn(messages=messages, **kwargs)
    primary_latency = round(time.time() - start, 3)

    # If capture disabled, return immediately
    if not getattr(model_config, "MULTI_MODEL_CAPTURE", False):
        return response

    cfg = _load_config()
    if not cfg.get("capture_enabled", False):
        return response

    # Gather call metadata
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model = kwargs.get("model", "unknown")
    tier = _determine_tier(model)
    caller_temperature = kwargs.get("temperature")
    caller_kwargs = {k: v for k, v in kwargs.items() if k not in ("model", "messages")}

    # Build input record (snapshot of what was passed)
    input_data = {"messages": messages}
    if caller_temperature is not None:
        input_data["temperature"] = caller_temperature
    if "reasoning_effort" in kwargs:
        input_data["reasoning_effort"] = kwargs["reasoning_effort"]

    # Write primary output synchronously (already have the response)
    primary_content = response.choices[0].message.content
    primary_label = f"{model}|baseline"

    # Check task_overrides for custom variant list
    variants = cfg.get("task_overrides", {}).get(task_id)
    if variants is None:
        variants = cfg.get(f"{tier}_tier_variants", [])

    # Find the file/line info from inventory if available (best effort)
    # These are embedded at callsite wiring time via the task_id lookup
    writer = _get_writer()

    # Get source location from CALLSITE_META if registered
    meta = _CALLSITE_META.get(task_id, {})
    writer.write_primary(
        task_id=task_id,
        file_path=meta.get("file", "unknown"),
        line=meta.get("line", 0),
        tier=tier,
        input_data=input_data,
        label=primary_label,
        content=primary_content,
        latency_s=primary_latency,
        timestamp=timestamp,
    )

    # Fire all non-baseline variants in background
    for variant in variants:
        if variant.get("model") == model and variant.get("reasoning_effort") is None:
            continue  # skip the baseline variant (already captured above)
        _executor.submit(
            _fire_background_variant,
            variant, task_id, messages, timestamp, caller_temperature, caller_kwargs
        )

    return response


# Callsite metadata registry - populated at wiring time
# Maps task_id -> {"file": "...", "line": N}
_CALLSITE_META = {}


def register_callsite(task_id, file_path, line):
    """Register file/line metadata for a task_id. Called at module import."""
    _CALLSITE_META[task_id] = {"file": file_path, "line": line}
```

**Step 4: Run tests to confirm they pass**

```bash
python -m pytest tests/capture/multi_model_capture_tests.py -v
```

Expected: All 4 tests `PASSED`.

**Step 5: Commit**

```bash
git add utils/capture/multi_model_capture.py tests/capture/multi_model_capture_tests.py
git commit -m "feat(capture): add capture_and_fanout() with thread pool and background fanout"
```

---

### Task 6: Create `capture_config.json`

**Files:**
- Create: `model_captures/capture_config.json` (gitignored - local only)

**Step 1: Create the model_captures directory if not present**

```bash
mkdir -p model_captures
```

**Step 2: Write `model_captures/capture_config.json`**

```json
{
  "capture_enabled": true,
  "full_tier_variants": [
    { "provider": "openai", "model": "gpt-4.1-2025-04-14",     "reasoning_effort": null,    "use_caller_temp": true,  "label": "gpt-4.1|baseline" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "none",  "use_caller_temp": true,  "label": "gpt-5.2|effort=none" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5.2|effort=low" },
    { "provider": "openai", "model": "gpt-5.2",                "reasoning_effort": "medium","use_caller_temp": false, "label": "gpt-5.2|effort=medium" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-5-mini" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5-mini|effort=low" },
    { "provider": "gemini", "model": "gemini-3-pro-preview",   "thinking_level": "low",     "use_caller_temp": true,  "label": "gemini-3-pro|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-pro-preview",   "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-pro|thinking=high" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "low",     "use_caller_temp": true,  "label": "gemini-3-flash|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-flash|thinking=high" }
  ],
  "mini_tier_variants": [
    { "provider": "openai", "model": "gpt-4.1-mini-2025-04-14","reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-4.1-mini|baseline" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": null,    "use_caller_temp": false, "label": "gpt-5-mini" },
    { "provider": "openai", "model": "gpt-5-mini",             "reasoning_effort": "low",   "use_caller_temp": false, "label": "gpt-5-mini|effort=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "low",     "use_caller_temp": false, "label": "gemini-3-flash|thinking=low" },
    { "provider": "gemini", "model": "gemini-3-flash-preview", "thinking_level": "high",    "use_caller_temp": false, "label": "gemini-3-flash|thinking=high" }
  ],
  "task_overrides": {}
}
```

Note: This file is gitignored. It must be created locally on each machine that runs capture.
Do NOT commit it.

**Step 3: Verify it is gitignored**

```bash
git check-ignore -v model_captures/capture_config.json
```

Expected output: `.gitignore:NNN:model_captures/  model_captures/capture_config.json`

---

### Task 7: Test script

**Files:**
- Create: `model_captures/test_all_models.py` (gitignored - local only)

**Step 1: Write `model_captures/test_all_models.py`**

```python
"""Smoke test: verify all model variants return a response.

Run this before wiring any callsites to confirm API keys work
and all models are accessible.

Usage:
    python model_captures/test_all_models.py
"""
import sys
import os
import json
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.capture.openai_caller import call_openai_variant
from utils.capture.gemini_caller import call_gemini_variant

TEST_PROMPT = "Respond with the word OK and nothing else."
TEST_MESSAGES = [{"role": "user", "content": TEST_PROMPT}]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "capture_config.json")


def run_variant(variant):
    """Run one variant, return (label, passed, latency_s, error)."""
    label = variant["label"]
    try:
        if variant["provider"] == "openai":
            content, latency_s = call_openai_variant(
                variant, TEST_MESSAGES, caller_temperature=None
            )
        else:
            content, latency_s = call_gemini_variant(
                variant, TEST_MESSAGES, caller_temperature=None
            )
        return label, True, latency_s, None
    except Exception as e:
        return label, False, 0.0, f"{type(e).__name__}: {e}"


def main():
    if not os.path.exists(CONFIG_PATH):
        print(f"[ERROR] capture_config.json not found at {CONFIG_PATH}")
        print("  Run Task 6 to create it first.")
        sys.exit(1)

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)

    all_results = []

    for tier_name in ("full_tier_variants", "mini_tier_variants"):
        variants = cfg.get(tier_name, [])
        if not variants:
            continue
        print(f"\nTesting {tier_name.replace('_', ' ')} ({len(variants)} variants)...")
        for variant in variants:
            label, passed, latency_s, error = run_variant(variant)
            status = "[PASS]" if passed else "[FAIL]"
            if passed:
                print(f"  {label:<45} {status}  {latency_s:.2f}s")
            else:
                print(f"  {label:<45} {status}  {error}")
            all_results.append(passed)

    total = len(all_results)
    passed = sum(all_results)
    print(f"\nResult: {passed}/{total} passed")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
```

**Step 2: Run the test script**

```bash
python model_captures/test_all_models.py
```

Expected: All variants show `[PASS]` with latency times. Any `[FAIL]` entries show the specific
error (auth failure, model not found, rate limit). Fix before proceeding to callsite wiring.

Common failures and fixes:
- `AuthenticationError` on OpenAI: check `config.py` has valid `OPENAI_API_KEY`
- `FileNotFoundError: google_api.pi`: create `google_api.pi` with `api_key=AIza...`
- `404 model not found` on gpt-5.2: model name may differ - check OpenAI dashboard for exact ID
- `429 RateLimitError` on Gemini: expected on free tier if hammered too fast, acceptable

---

### Task 8: Wire first callsite (T013 - proof of concept)

**File:** `core/ai/action_handler.py` line 1003

This is the main DM action handler - the most important callsite and best proof of concept.
**Get explicit approval before touching this file.**

**Step 1: Read the callsite context**

```bash
python -c "
import linecache
for i in range(995, 1015):
    print(f'{i}: {linecache.getline(\"core/ai/action_handler.py\", i)}', end='')
"
```

Verify line 1003 is the `chat.completions.create` call matching T013 in the inventory.

**Step 2: Add the import at the top of `core/ai/action_handler.py`**

Find the existing OpenAI imports section and add after it:

```python
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T013", "core/ai/action_handler.py", 1003)
```

**Step 3: Wrap the callsite**

Change (line ~1003):
```python
response = client.chat.completions.create(
    model=...,
    messages=messages,
    temperature=...,
    reasoning_effort=...,
)
```

To:
```python
response = capture_and_fanout(
    "T013",
    client.chat.completions.create,
    messages=messages,
    model=...,
    temperature=...,
    reasoning_effort=...,
)
```

**Step 4: Enable capture toggle temporarily for testing**

In `model_config.py`, set:
```python
MULTI_MODEL_CAPTURE = True
```

**Step 5: Run the game briefly and trigger a DM action**

```bash
python run_web.py
```

Enter one player action in the game. Then check:

```bash
python -c "
import json
with open('model_captures/T013.json') as f:
    data = json.load(f)
print(f'Records: {len(data)}')
if data:
    print(f'Outputs: {list(data[-1][\"outputs\"].keys())}')
    print(f'Errors: {data[-1][\"errors\"]}')
"
```

Expected: 1 record with all variant labels present in outputs, errors dict empty or showing only
expected rate limit entries.

**Step 6: Set capture back to False**

```python
MULTI_MODEL_CAPTURE = False
```

The wiring stays in place permanently. Capture only fires when the toggle is on.

**Step 7: Commit**

```bash
git add core/ai/action_handler.py utils/capture/multi_model_capture.py
git commit -m "feat(capture): wire T013 action_handler.py:1003 as first capture callsite"
```

---

## Running All Tests

```bash
python -m pytest tests/capture/ -v
```

Expected: All tests pass. This covers openai_caller, gemini_caller, file_writer, and
capture_and_fanout unit tests. The test_all_models.py script is a live integration test,
run separately.

---

## After This Plan

Once T013 is verified working, the remaining 58 runtime callsites follow the identical pattern
(Tasks equivalent to Task 8). Each one requires:
1. Explicit user approval
2. Read the callsite to understand context
3. Add import + `register_callsite()` at module level
4. Wrap the call with `capture_and_fanout()`
5. Test with toggle on
6. Commit individually

Callsite order recommendation: start with the most-used game paths first
(action_handler, combat_manager, main.py) to gather the richest telemetry fastest.
