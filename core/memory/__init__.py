# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Memory Package.
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

from core.memory.memory_db import (
    DEFAULT_MEMORY_DB_PATH,
    DEFAULT_WORLD_NARRATIVE_SEED_DB_PATH,
    bootstrap_memory_db_from_seed,
    create_memory_event,
    create_memory_link,
    init_memory_db,
    run_memory_migrations,
)
from core.memory.memory_ingest import backfill_memory_db_from_histories, ingest_journal_entry, ingest_journal_file
from core.memory.memory_retrieval import (
    get_context_memories,
    get_entity_timeline,
    get_retirement_return_memories,
)
from core.memory.memory_portability import (
    export_memory_db_package,
    import_memory_db_package,
    validate_memory_package,
)
from core.memory.party_transition_memory import (
    build_return_memory_pack,
    record_pc_retirement,
    record_pc_return,
)
from core.memory.session_diary import (
    build_fallback_summary,
    confirm_diary_for_exit,
    compute_world_sort_key,
    confirm_diary_for_save,
    list_diary_entries,
    remediate_diary_entries,
    rebuild_diary_from_journal,
    refresh_draft_if_stale,
)
from core.memory.story_so_far_compiler import (
    build_confirmed_story_text,
    get_or_build_story_pdf,
    render_story_pdf,
)

__all__ = [
    "DEFAULT_MEMORY_DB_PATH",
    "DEFAULT_WORLD_NARRATIVE_SEED_DB_PATH",
    "bootstrap_memory_db_from_seed",
    "init_memory_db",
    "run_memory_migrations",
    "create_memory_event",
    "create_memory_link",
    "ingest_journal_entry",
    "ingest_journal_file",
    "backfill_memory_db_from_histories",
    "get_entity_timeline",
    "get_context_memories",
    "get_retirement_return_memories",
    "export_memory_db_package",
    "validate_memory_package",
    "import_memory_db_package",
    "record_pc_retirement",
    "record_pc_return",
    "build_return_memory_pack",
    "compute_world_sort_key",
    "build_fallback_summary",
    "refresh_draft_if_stale",
    "confirm_diary_for_exit",
    "confirm_diary_for_save",
    "list_diary_entries",
    "remediate_diary_entries",
    "rebuild_diary_from_journal",
    "build_confirmed_story_text",
    "render_story_pdf",
    "get_or_build_story_pdf",
]
