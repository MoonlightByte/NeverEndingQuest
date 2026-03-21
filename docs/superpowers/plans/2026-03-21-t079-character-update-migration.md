# T079 Character Update Callsite Migration (v2)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **ALL coding changes must be done by hand -- one file at a time. No automated scripts.**

**Goal:** Migrate T079 (player/NPC character updates) to per-provider model configs, with Gemini `response_schema` forcing via runtime-converted existing schema.

**Architecture:** Same config-dict pattern as T067/T065/T082. Gemini calls additionally pass `response_schema` -- the existing `schemas/char_schema.json` converted at runtime to Gemini format. No separate schema file needed. The existing post-response validation chain (`purge_invalid_fields()`) strips any spurious extra fields.

**Tech Stack:** Python, model_config.py, api_client.py, update_character_info.py

---

## Testing Results

**Capture testing (5 variant entries, GPT-5.4 reviewed):**
- gpt-5-mini|low: 3/5 correct
- gpt-4.1-mini baseline: 8/11 correct
- All Gemini models without schema: 1-2/5 (output narration instead of deltas)

**Artificial simulations (6 complex scenarios, auto-converted full schema):**

| Model | Correct | Avg Latency | Spurious Keys |
|---|---|---|---|
| gemini-3.1-flash-lite\|minimal | 4/6 | 2.0s | 8 (fewest) |
| gemini-3-flash\|low | 4/6 | 3.0s | 12 |
| gemini-3-flash\|minimal | 4/6 | 6.7s | 12 |
| gemini-3-pro\|low | 3/6 | 8.8s | 12 |
| gemini-3.1-pro\|low | 3/6 | 10.2s | 12 |

**Key finding:** Passing `response_schema` (auto-converted from `char_schema.json`)
eliminates 100% of narration output. Spurious extra keys are harmless -- stripped by
existing `purge_invalid_fields()` in the post-response validation chain.

**Selected models:**
- **OpenAI:** gpt-5-mini reasoning_effort="low"
- **Gemini:** gemini-3.1-flash-lite thinking_level="minimal" + response_schema (auto-converted)
- **Legacy:** gpt-4.1-mini (no extra params)
- **LM Studio:** local-model (no extra params)

---

## Files Changed

| File | Change |
|---|---|
| `model_config.py` | Add `convert_to_gemini_schema()` + 4 T079 config dicts |
| `core/ai/api_client.py` | Add `response_schema` handling in `_gemini_completion()` |
| `updates/update_character_info.py` | Wire callsite with per-provider config |

---

### Task 1: Add `response_schema` Handling to `_gemini_completion()`

**Why first:** The Gemini config dict will include `response_schema`. The routing
layer needs to pop it from kwargs and forward it to `GenerateContentConfig`.

**Files:**
- Modify: `core/ai/api_client.py`

- [ ] **Step 1: Pop response_schema from kwargs**

After the existing `thinking_level = kwargs.pop("thinking_level", None)` line
(around line 206), add:

```python
    response_schema = kwargs.pop("response_schema", None)
```

- [ ] **Step 2: Forward response_schema to GenerateContentConfig**

After the JSON mode block (around line 238), before `gen_config = types.GenerateContentConfig(...)`, add:

```python
    # Gemini response_schema: constrains JSON output to a specific structure.
    # Auto-converted at runtime from the callsite's existing JSON schema file.
    if response_schema is not None:
        config_kwargs["response_schema"] = response_schema
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 4: Commit**

```bash
git add core/ai/api_client.py
git commit -m "feat: add response_schema support to _gemini_completion"
```

---

### Task 2: Add Schema Converter and T079 Configs to model_config.py

**Why:** T079 needs config dicts per provider. The Gemini config includes
`response_schema` loaded from `char_schema.json` via a runtime converter.
The converter is reusable for other callsites that need schema forcing.

**Files:**
- Modify: `model_config.py`

- [ ] **Step 1: Add the convert_to_gemini_schema() function**

Add before the T067 config section (around line 40):

```python
def convert_to_gemini_schema(json_schema):
    """Convert JSON Schema Draft-07 to Gemini API response_schema format.

    Strips $schema, required, oneOf (takes first option), uppercases types.
    Handles union types like ["integer", "null"] by taking the non-null type.
    Reusable for any callsite that needs Gemini response_schema forcing.
    """
    _TYPE_MAP = {
        "string": "STRING", "integer": "INTEGER", "number": "NUMBER",
        "boolean": "BOOLEAN", "array": "ARRAY", "object": "OBJECT",
    }

    def _convert_prop(prop):
        result = {}
        prop_type = prop.get("type")
        if isinstance(prop_type, list):
            non_null = [t for t in prop_type if t != "null"]
            prop_type = non_null[0] if non_null else "string"
        if prop_type:
            result["type"] = _TYPE_MAP.get(prop_type, "STRING")
        if "oneOf" in prop and "type" not in result:
            first = prop["oneOf"][0]
            if "type" in first:
                result["type"] = _TYPE_MAP.get(first["type"], "STRING")
            if "items" in first:
                result["type"] = "ARRAY"
                result["items"] = _convert_prop(first["items"])
        if "properties" in prop:
            result["type"] = "OBJECT"
            result["properties"] = {
                k: _convert_prop(v) for k, v in prop["properties"].items()
            }
        if "items" in prop:
            result["type"] = "ARRAY"
            result["items"] = _convert_prop(prop["items"])
        return result

    return {
        "type": "OBJECT",
        "properties": {
            k: _convert_prop(v) for k, v in json_schema.get("properties", {}).items()
        },
    }


# Load and convert char_schema.json for Gemini response_schema
_char_schema_path = os.path.join(os.path.dirname(__file__), "schemas", "char_schema.json")
if os.path.exists(_char_schema_path):
    with open(_char_schema_path, "r") as _f:
        _CHAR_SCHEMA_GEMINI = convert_to_gemini_schema(json.load(_f))
else:
    _CHAR_SCHEMA_GEMINI = None
    import logging as _logging
    _logging.warning(
        "schemas/char_schema.json not found -- Gemini response_schema "
        "forcing disabled. Gemini may output narration instead of deltas."
    )
```

- [ ] **Step 2: Add 4 T079 config dicts**

Add after the T082 config section:

```python
# --- T079 Character Update Model Configs (from capture + simulation testing) ---
# Gemini requires response_schema to prevent narration output. Schema is
# auto-converted from schemas/char_schema.json at runtime -- no separate file.
# Existing purge_invalid_fields() strips spurious extra keys from output.
# Temperature is 0.7 at callsite.

# OpenAI (mini model with low reasoning)
CHAR_UPDATE_GPT5MINI_LOW = {"model": "gpt-5-mini", "reasoning_effort": "low"}

# Gemini (3.1 flash-lite with minimal thinking + auto-converted schema)
CHAR_UPDATE_GEMINI_FLASHLITE_MINIMAL = {
    "model": "gemini-3.1-flash-lite-preview",
    "thinking_level": "minimal",
    "response_schema": _CHAR_SCHEMA_GEMINI,
}

# Legacy (no extra params -- matches current PLAYER_INFO_UPDATE_MODEL)
CHAR_UPDATE_LEGACY = {"model": "gpt-4.1-mini-2025-04-14"}

# LM Studio (local passthrough)
CHAR_UPDATE_LMSTUDIO = {"model": "local-model"}
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 4: Commit**

```bash
git add model_config.py
git commit -m "feat: add schema converter and T079 per-provider model configs

convert_to_gemini_schema() converts JSON Schema Draft-07 to Gemini
format at runtime. No separate schema file needed -- changes to
char_schema.json automatically propagate to Gemini calls."
```

---

### Task 3: Migrate T079 Callsite and Clean Dead Code in update_character_info.py

**Why:** Wire T079 to use per-provider config and remove all dead code that only
served the old direct-client call path.

**Dead code after migration (all in this file, all only used by T079):**
- Line 122: `OPENAI_API_KEY, PLAYER_INFO_UPDATE_MODEL, NPC_INFO_UPDATE_MODEL` imports
- Line 133: `client = OpenAI(api_key=OPENAI_API_KEY)`
- Lines 488-493: `get_model_for_character()` function
- Line 1449: `model = get_model_for_character(character_role)`

There is only ONE API callsite in this file (T079 at line 1455). All the above
code exists solely to feed that call.

**Files:**
- Modify: `updates/update_character_info.py`

- [ ] **Step 1: Update imports**

Change line 122 from:
```python
from config import OPENAI_API_KEY, PLAYER_INFO_UPDATE_MODEL, NPC_INFO_UPDATE_MODEL
```

To:
```python
import config
from core.ai import api_client
```

- [ ] **Step 2: Remove dead client initialization**

Remove line 133:
```python
client = OpenAI(api_key=OPENAI_API_KEY)
```

Also remove `from openai import OpenAI` if it exists in the imports and is no
longer used anywhere in the file.

- [ ] **Step 3: Remove dead get_model_for_character() function**

Remove lines 488-493:
```python
def get_model_for_character(character_role):
    """Get the appropriate model based on character role"""
    if character_role == 'player':
        return PLAYER_INFO_UPDATE_MODEL
    else:
        return NPC_INFO_UPDATE_MODEL
```

- [ ] **Step 4: Remove dead model assignment and add provider config selection**

Remove line 1449:
```python
    model = get_model_for_character(character_role)
```

Replace with provider config selection:
```python
    # T079 MIGRATION NOTE: Gemini requires response_schema forcing on this callsite.
    # The schema is auto-converted from schemas/char_schema.json at runtime and
    # passed via the config dict. purge_invalid_fields() strips spurious extra keys.
    from model_config import MODEL_PROVIDER
    if MODEL_PROVIDER == "openai":
        char_update_config = config.CHAR_UPDATE_GPT5MINI_LOW
    elif MODEL_PROVIDER == "gemini":
        char_update_config = config.CHAR_UPDATE_GEMINI_FLASHLITE_MINIMAL
    elif MODEL_PROVIDER == "lmstudio":
        char_update_config = config.CHAR_UPDATE_LMSTUDIO
    else:  # legacy
        char_update_config = config.CHAR_UPDATE_LEGACY
```

- [ ] **Step 5: Update the API call**

Change the call from:
```python
            response = capture_and_fanout("T079", client.chat.completions.create,
                messages=messages,
                model=model,
                temperature=TEMPERATURE
            )
```

To:
```python
            response = capture_and_fanout("T079", api_client.create_completion,
                messages=messages,
                model=char_update_config["model"],
                temperature=TEMPERATURE,
                **{k: v for k, v in char_update_config.items() if k != "model"})
```

For Gemini, this unpacks `thinking_level` and `response_schema`. Task 1 added
`response_schema` handling to `_gemini_completion()`. For OpenAI, only
`reasoning_effort` is unpacked. For Legacy/LM Studio, nothing extra.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_create_completion_integration.py -v
```

- [ ] **Step 7: Commit**

```bash
git add updates/update_character_info.py
git commit -m "feat: migrate T079 to per-provider model configs

Character updates now use gpt-5-mini reasoning=low (OpenAI),
gemini-3.1-flash-lite thinking=minimal with auto-converted
response_schema (Gemini). Schema prevents narration output.
Removed dead OpenAI client, model imports, get_model_for_character."
```

---

### Task 4: Update Migration Tracking

**Files:**
- Modify: `tests/model_validation/README.md`
- Modify: `docs/reference/legacy-model-variable-map.md`

- [ ] **Step 1: Add T079 to migration status table**

```
| T079 | Character data updates | gpt-5-mini low | gemini-3.1-flash-lite minimal + schema | Done |
```

- [ ] **Step 2: Mark T079 task IDs as done in legacy map**

- [ ] **Step 3: Commit**

```bash
git add tests/model_validation/README.md docs/reference/legacy-model-variable-map.md
git commit -m "docs: mark T079 as migrated in tracking docs"
```

---

## Summary

| Task | File | Change |
|---|---|---|
| 1 | `core/ai/api_client.py` | Add response_schema pop + forward in _gemini_completion |
| 2 | `model_config.py` | Add convert_to_gemini_schema() + 4 T079 config dicts |
| 3 | `updates/update_character_info.py` | Wire callsite with per-provider config |
| 4 | Tracking docs | Update migration status |

## What This Does NOT Change

- T079 temperature (0.7) -- stays at callsite
- T079 retry logic (max 3 attempts) -- unchanged
- T079 system prompt -- frozen
- T079 post-response validation chain -- unchanged (purge_invalid_fields handles extra keys)
- schemas/char_schema.json -- unchanged (read-only, auto-converted at runtime)
- No separate Gemini schema file created
