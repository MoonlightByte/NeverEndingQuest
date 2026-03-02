# Developer Homebrew Ingest Media Handles and Portrait Prewarm - Executor Prompts

## Prompt 1: Media Extraction (warn-only)

**Task:** Build `scripts/homebrew_media_extract.py`.

**Scope:**
- Parse markdown image directives and direct image URLs.
- Download/copy assets into module media folders.
- Classify title vs map images.
- Emit warnings, never block ingest.

**MUST:**
- Fail-open for all media fetch/copy failures.
- Produce structured JSON report with extracted and failed counts.
- Keep deterministic naming and atomic writes.

**SHOULD:**
- Use heading context for classification.
- Prefer stable filenames derived from URL basename.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_media_extract.py
python scripts/homebrew_media_extract.py --source "Docs/modules/hombrew/The Secrets of Mangrove Keep.md" --module-slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 2: Media Handle Manifest

**Task:** Build `scripts/homebrew_media_handles.py`.

**Scope:**
- Generate `modules/<slug>/media/media_handles.json`.
- Emit deterministic handle IDs.
- Preserve entries for failed downloads.

**MUST:**
- Include future-use flags for `chat_title_candidate` and `map_tab_candidate`.
- Include source refs and storage relpaths.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_media_handles.py
python scripts/homebrew_media_handles.py --slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 3: Portrait Prewarm (NPC + Monster)

**Task:** Build `scripts/homebrew_prewarm_portraits.py`.

**Scope:**
- Discover entities in generated module.
- Prewarm missing NPC and monster portraits.
- Skip existing files.

**MUST:**
- Fail-open on provider errors.
- Emit counters: planned/done/failed/skipped for each entity type.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_prewarm_portraits.py
python scripts/homebrew_prewarm_portraits.py --slug The_Secrets_of_Mangrove_Keep --json
```

## Prompt 4: Orchestrator Integration

**Task:** Update `scripts/homebrew_ingest_dev.py` and `scripts/homebrew_sidecar_audit.py`.

**Scope:**
- Add media extraction, handle generation, and prewarm stages.
- Extend sidecar with media/prewarm blocks.
- Keep strict ingest fail-closed behavior unchanged.

**MUST:**
- Media/prewarm failures are warnings/degraded, not pipeline hard-fail.

**Verification:**
```bash
python3 -m py_compile scripts/homebrew_ingest_dev.py scripts/homebrew_sidecar_audit.py
python scripts/homebrew_ingest_dev.py --source "Docs/modules/hombrew/The Secrets of Mangrove Keep.md" --strict --json
```

## Prompt 5: Skill Update

**Task:** Update `.opencode/skills/dev-homebrew-ingest/SKILL.md` to match new pipeline.

**Scope:**
- Add media extraction and handles stages.
- Add portrait prewarm stage.
- Add report format fields for degraded media outcomes.

**Verification:**
- Confirm workflow and stop conditions match new OpenSpec tasks.
