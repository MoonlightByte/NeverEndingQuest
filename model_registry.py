"""Immutable model catalog and canonical per-callsite binding declarations.

This module deliberately contains no API client and imports no game modules.  It is
safe to import from configuration, capture tooling, and offline evaluation scripts.
Provider-specific schemas remain in :mod:`model_config`; bindings refer to those
profiles by compatibility name and the resolver returns a detached deep copy.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Tuple


SUPPORTED_PROVIDERS = ("openai", "gemini", "legacy", "lmstudio")
SUPPORTED_GPT56_EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")
EVALUATION_EFFORTS = ("none", "low", "medium", "high")


@dataclass(frozen=True)
class ModelCatalogEntry:
    model_id: str
    family: str
    supported_efforts: Tuple[str, ...]
    input_usd_per_million: float
    cached_input_usd_per_million: float
    output_usd_per_million: float
    pricing_source_date: str
    pricing_source_url: str
    available: bool
    availability_checked_at: str
    created_at: Optional[str]
    shutdown_at: Optional[str]
    owned_by: Optional[str]


# Pricing snapshot from the model pages fetched directly on 2026-08-16.
# Sol and the unsuffixed gpt-5.6 alias are intentionally
# absent; discovery never makes a model eligible automatically.
MODEL_CATALOG: Mapping[str, ModelCatalogEntry] = MappingProxyType(
    {
        "gpt-5.6-luna": ModelCatalogEntry(
            model_id="gpt-5.6-luna",
            family="gpt-5.6-luna",
            supported_efforts=SUPPORTED_GPT56_EFFORTS,
            input_usd_per_million=0.20,
            cached_input_usd_per_million=0.02,
            output_usd_per_million=1.20,
            pricing_source_date="2026-08-16",
            pricing_source_url="https://developers.openai.com/api/docs/models/gpt-5.6-luna",
            available=True,
            availability_checked_at="2026-08-16",
            created_at="2026-06-23T15:30:58+00:00",
            shutdown_at=None,
            owned_by="system",
        ),
        "gpt-5.6-terra": ModelCatalogEntry(
            model_id="gpt-5.6-terra",
            family="gpt-5.6-terra",
            supported_efforts=SUPPORTED_GPT56_EFFORTS,
            input_usd_per_million=2.00,
            cached_input_usd_per_million=0.20,
            output_usd_per_million=12.00,
            pricing_source_date="2026-08-16",
            pricing_source_url="https://developers.openai.com/api/docs/models/gpt-5.6-terra",
            available=True,
            availability_checked_at="2026-08-16",
            created_at="2026-06-23T15:27:39+00:00",
            shutdown_at=None,
            owned_by="system",
        ),
    }
)


@dataclass(frozen=True)
class CallsiteBinding:
    task_id: str
    status: str
    openai: Tuple[str, ...]
    gemini: Tuple[str, ...]
    legacy: Tuple[str, ...]
    lmstudio: Tuple[str, ...]
    note: str = ""

    def profiles_for(self, provider: str) -> Tuple[str, ...]:
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError("Unknown provider %r" % provider)
        return getattr(self, provider)


def _profiles(openai, gemini, legacy, lmstudio):
    return {
        "openai": (openai,) if isinstance(openai, str) else tuple(openai),
        "gemini": (gemini,) if isinstance(gemini, str) else tuple(gemini),
        "legacy": (legacy,) if isinstance(legacy, str) else tuple(legacy),
        "lmstudio": (lmstudio,) if isinstance(lmstudio, str) else tuple(lmstudio),
    }


_DECLARATIONS = []


def _declare(task_ids, profiles, *, status="active", note=""):
    for task_id in task_ids.split():
        _DECLARATIONS.append(
            CallsiteBinding(
                task_id=task_id,
                status=status,
                note=note,
                **profiles,
            )
        )


_declare(
    "T022 T023 T025 T028 T029 T031 T036 T037 T059 T092",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
)
_declare(
    "T024",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
    status="dormant",
    note="Direct comparison only; helper is currently unreferenced.",
)
_declare(
    "T026",
    _profiles(
        "OPENAI_GPT56_LUNA_HIGH",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
    note="Selected by the 2026-08-15 blind quality/cost evaluation.",
)
_declare(
    "T027 T030 T032 T033 T038",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_SUMM_GEMINI_FLASH_LOW",
        "DM_SUMM_LEGACY",
        "DM_SUMM_LMSTUDIO",
    ),
)
_declare(
    "T066",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_SUMM_GEMINI_FLASH_LOW",
        "DM_SUMM_LEGACY",
        "DM_SUMM_LMSTUDIO",
    ),
)
_declare(
    "T042 T087 T088 T089 T090 T093",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "MINI_UTIL_GEMINI_FLASH_LOW",
        "MINI_UTIL_LEGACY",
        "MINI_UTIL_LMSTUDIO",
    ),
)
_declare(
    "T083",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "MINI_UTIL_GEMINI_FLASH_LOW",
        "MINI_UTIL_LEGACY",
        "MINI_UTIL_LMSTUDIO",
    ),
    note="Luna-none changed an explicit beast to monstrosity; Luna-low passed all taxonomy cases.",
)
_declare(
    "T063 T064 T094 T095",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "MINI_UTIL_GEMINI_FLASH_LOW",
        "MINI_UTIL_LEGACY",
        "MINI_UTIL_LMSTUDIO",
    ),
)
_declare(
    "T012",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_LOCSTART_T012_GEMINI_FLASHLITE_LOW",
        "DM_LOCSTART_T012_LEGACY",
        "DM_LOCSTART_T012_LMSTUDIO",
    ),
)
_declare(
    "T013",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_MINI_MODEL_GEMINI_FLASH_LOW",
        "DM_MINI_MODEL_LEGACY",
        "DM_MINI_MODEL_LMSTUDIO",
    ),
)
_declare(
    "T015 T016 T018 T019",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "ADV_SUMM_GEMINI_FLASH_LOW",
        "ADV_SUMM_LEGACY",
        "ADV_SUMM_LMSTUDIO",
    ),
)
_declare(
    "T017",
    _profiles(
        "OPENAI_GPT56_LUNA_MEDIUM",
        "COMBAT_COMPRESS_GEMINI_FLASH_LOW",
        "COMBAT_COMPRESS_LEGACY",
        "COMBAT_COMPRESS_LMSTUDIO",
    ),
    note="Luna-medium passed 6/6 source-aware compression cases versus 5/6 for the incumbent and 1/6 for Luna-none.",
)
_declare(
    "T020",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "NARR_COMPRESS_GEMINI_FLASH_LOW",
        "NARR_COMPRESS_LEGACY",
        "NARR_COMPRESS_LMSTUDIO",
    ),
)
_declare(
    "T021",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "TRANSITION_VAL_GEMINI_FLASH_LOW",
        "TRANSITION_VAL_LEGACY",
        "TRANSITION_VAL_LMSTUDIO",
    ),
)
_declare(
    "T034",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "MONSTER_BUILD_GEMINI_FLASH_LOW",
        "MONSTER_BUILD_LEGACY",
        "MONSTER_BUILD_LMSTUDIO",
    ),
)
_declare(
    "T035",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "NPC_BUILD_GEMINI_FLASH_LOW",
        "NPC_BUILD_LEGACY",
        "NPC_BUILD_LMSTUDIO",
    ),
)
_declare(
    "T039",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_SUMM_T039_GEMINI_FLASHLITE_LOW",
        "DM_SUMM_T039_LEGACY",
        "DM_SUMM_T039_LMSTUDIO",
    ),
)
_declare(
    "T040",
    _profiles(
        "COMBAT_VALID_TERRA_LOW",
        "COMBAT_VALID_GEMINI_FLASH_LOW",
        "COMBAT_VALID_LEGACY",
        "COMBAT_VALID_LMSTUDIO",
    ),
    note="OpenAI=terra|low. Replaced gpt-5.4 after adversarial + broad referee testing: "
         "on a poisoned player-pause case (DM plan hallucinates a 3-actor window vs the "
         "authoritative player-only state window) gpt-5.4 AND luna|low false-positive "
         "rejected legitimate play (jamming combat in a retry loop) while terra was "
         "correct; on a 45-case randomized battery terra|low caught 33/33 violation "
         "types (0 false negatives) and passed all valid cases. Chosen over sol|none on "
         "cost (terra $2/$12 vs sol $5/$30 per 1M) at equal correctness; terra|medium/high "
         "add no accuracy. Paired with a combat_validation prompt clause: plan/narration "
         "text does not define the turn window (only game state does).",
)
_declare(
    "T041",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "COMBAT_SUMMARY_GEMINI_FLASH_LOW",
        "COMBAT_SUMMARY_LEGACY",
        "COMBAT_SUMMARY_LMSTUDIO",
    ),
)
_declare(
    "T043 T044 T045",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "COMBAT_MAIN_GEMINI_PRO_LOW",
        "COMBAT_MAIN_LEGACY",
        "COMBAT_MAIN_LMSTUDIO",
    ),
)
_declare(
    "T046",
    _profiles(
        "INIT_TRACKER_GPT52_NONE",
        "INIT_TRACKER_GEMINI_FLASH_LOW",
        "INIT_TRACKER_LEGACY",
        "INIT_TRACKER_LMSTUDIO",
    ),
    note="Retain incumbent: Terra-none was only 0.12s faster over four cases and offered no material accepted-result efficiency gain.",
)
_declare(
    "T121",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_CONV_GEMINI_FLASH_LOW",
        "LEVELUP_CONV_LEGACY",
        "LEVELUP_CONV_LMSTUDIO",
    ),
    note="L1 level-up agent (2026-09-29): the one conversational callsite of the table-driven level-up; "
         "same Luna low binding as the T047 interview it replaces.",
)
_declare(
    "T047",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_CONV_GEMINI_FLASH_LOW",
        "LEVELUP_CONV_LEGACY",
        "LEVELUP_CONV_LMSTUDIO",
    ),
    note="#323 level-up interview on Luna low (owner ruling 2026-09-14: the whole level-up path runs on "
         "Luna; replays showed reasoning=none re-emits rejected answers while low converges in 1-2 rounds).",
)
_declare(
    "T086",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "LEVELUP_CONV_GEMINI_FLASH_LOW",
        "LEVELUP_CONV_LEGACY",
        "LEVELUP_CONV_LMSTUDIO",
    ),
)
_declare(
    "T048",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_VAL_GEMINI_PRO_LOW",
        "LEVELUP_VAL_LEGACY",
        "LEVELUP_VAL_LMSTUDIO",
    ),
    note="#323 owner-selected Terra low for the level-up full validator. "
         "Narrow interview controls passed; full saved-level-up acceptance remains pending.",
)
_declare(
    "T049",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "STORAGE_PROCESSOR_T049_GEMINI_FLASHLITE_LOW",
        "STORAGE_PROCESSOR_T049_LEGACY",
        "STORAGE_PROCESSOR_T049_LMSTUDIO",
    ),
)
_declare(
    "T050",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_VALIDATOR_GEMINI_FLASH_LOW",
        "CHAR_VALIDATOR_LEGACY",
        "CHAR_VALIDATOR_LMSTUDIO",
    ),
)
_declare(
    "T051",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_VALIDATOR_T051_GEMINI_FLASH_LOW",
        "CHAR_VALIDATOR_LEGACY",
        "CHAR_VALIDATOR_LMSTUDIO",
    ),
)
_declare(
    "T052",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_VALIDATOR_T052_GEMINI_FLASH_LOW",
        "CHAR_VALIDATOR_LEGACY",
        "CHAR_VALIDATOR_LMSTUDIO",
    ),
)
_declare(
    "T053",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_VALIDATOR_T053_GEMINI_FLASH_LOW",
        "CHAR_VALIDATOR_LEGACY",
        "CHAR_VALIDATOR_LMSTUDIO",
    ),
)
_declare(
    "T054",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_VALIDATOR_T054_GEMINI_FLASH_LOW",
        "CHAR_VALIDATOR_LEGACY",
        "CHAR_VALIDATOR_LMSTUDIO",
    ),
)
_declare(
    "T065",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "DM_VALIDATION_GEMINI_FLASH_LOW",
        "DM_VALIDATION_LEGACY",
        "DM_VALIDATION_LMSTUDIO",
    ),
    note="Luna-low passed 11/13 full validator cases versus 7/13 for Luna-none and the incumbent.",
)
_declare(
    "T067",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_FULL_MODEL_GEMINI_PRO_LOW",
        "DM_FULL_MODEL_LEGACY",
        "DM_FULL_MODEL_LMSTUDIO",
    ),
    note=(
        "Single rung by evidence: a five-arm live matrix (2026-09-04) had "
        "luna|none, luna|low, luna|medium, terra|none and terra|low ALL pass "
        "the same action turn on one attempt. The earlier reasoning-off "
        "failures were a stale-prompt fixture, not the effort setting, so no "
        "measurement justifies paying for a higher rung here."
    ),
)
_declare(
    "T078",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_EFFECTS_GEMINI_FLASH_HIGH",
        "CHAR_EFFECTS_LEGACY",
        "CHAR_EFFECTS_LMSTUDIO",
    ),
    note="One binding serves both live implementations sharing this ID.",
)
_declare(
    "T079",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "CHAR_UPDATE_GEMINI_FLASHLITE_LOW",
        "CHAR_UPDATE_LEGACY",
        "CHAR_UPDATE_LMSTUDIO",
    ),
)
_declare(
    "T081",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "ENCOUNTER_UPD_GEMINI_FLASH_LOW",
        "ENCOUNTER_UPD_LEGACY",
        "ENCOUNTER_UPD_LMSTUDIO",
    ),
)
_declare(
    "T082",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "ACTION_PRED_GEMINI_FLASH_LOW",
        "ACTION_PRED_LEGACY",
        "ACTION_PRED_LMSTUDIO",
    ),
)
_declare(
    "T084",
    _profiles(
        "OPENAI_GPT56_TERRA_LOW",
        "AGENTIC_COMPRESS_GEMINI_PRO_LOW",
        "AGENTIC_COMPRESS_LEGACY",
        "AGENTIC_COMPRESS_LMSTUDIO",
    ),
)
_declare(
    "T085",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "LOC_COMPRESS_GEMINI_PRO_LOW",
        "LOC_COMPRESS_LEGACY",
        "LOC_COMPRESS_LMSTUDIO",
    ),
)
_declare(
    "T096",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "COMBAT_INTENT_GEMINI_FLASH_LOW",
        "COMBAT_INTENT_LEGACY",
        "COMBAT_INTENT_LMSTUDIO",
    ),
)
_declare(
    "T097",
    _profiles(
        (
            "OPENAI_GPT56_LUNA_NONE",
            "OPENAI_GPT56_LUNA_LOW",
            "OPENAI_GPT56_LUNA_MEDIUM",
        ),
        (
            "COMBAT_NARRATE_GEMINI_FLASH_LOW",
            "COMBAT_NARRATE_GEMINI_FLASH_MEDIUM",
            "COMBAT_NARRATE_GEMINI_FLASH_MEDIUM",
        ),
        ("COMBAT_NARRATE_LEGACY",) * 3,
        ("COMBAT_NARRATE_LMSTUDIO",) * 3,
    ),
    note="Intent -> commit -> narration sequence; retry ladder is explicit.",
)
_declare(
    "T098 T100 T102",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
)
_declare(
    "T101",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
    note="Luna-none required two NPC-repair attempts in the complete build.",
)
_declare(
    "T103",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
    note="Luna-none compiled each generated creature successfully; telemetry attempts are per-creature calls.",
)
_declare(
    "T099",
    _profiles(
        "OPENAI_GPT56_TERRA_LOW",
        "DM_MAIN_GEMINI_PRO_LOW",
        "DM_MAIN_LEGACY",
        "DM_MAIN_LMSTUDIO",
    ),
    note="Luna none/low exhausted the stage; Terra-none passed but showed one- and two-attempt runs.",
)
_declare(
    "T104",
    _profiles(
        "OPENAI_GPT56_LUNA_NONE",
        "NPC_COHERENCE_T104_GEMINI_PRO_LOW",
        "NPC_COHERENCE_T104_LEGACY",
        "NPC_COHERENCE_T104_LMSTUDIO",
    ),
    note="Classic-build NPC coherence repair is enabled at the reviewed tip default.",
)
_declare(
    "T122",
    _profiles(
        "NPC_TYPING_T122_GPT56LUNA_NONE",
        "NPC_TYPING_T122_GEMINI_PRO_LOW",
        "NPC_TYPING_T122_LEGACY",
        "NPC_TYPING_T122_LMSTUDIO",
    ),
    note="Typing a module that joins without a module declaration (N4), once per "
         "module at its integration. Bound like T104.",
)
_declare(
    "T123",
    _profiles(
        "ROUTE_TIMING_T123_GPT56LUNA_NONE",
        "ROUTE_TIMING_T123_GEMINI_PRO_LOW",
        "ROUTE_TIMING_T123_LEGACY",
        "ROUTE_TIMING_T123_LMSTUDIO",
    ),
    note="Timing a built module's links (N5), once per build in the declaration "
         "emitter. Bound like T122.",
)
_declare(
    "T105",
    _profiles(
        "NPC_VOICE_T105_OPENAI_LUNA_NONE",
        "NPC_VOICE_T105_GEMINI_FLASHLITE_LOW",
        "NPC_VOICE_T105_LEGACY",
        "NPC_VOICE_T105_LMSTUDIO",
    ),
    note="Per-NPC voice (+ isolated affinity classifier, same config) micro call, "
         "always on. OpenAI on cheapest luna|none (per-NPC per-turn "
         "micro tier). Distinct from T104 (NPC cross-area coherence). The Gemini "
         "response_schema is supplied by the service (core/npc/voice_service.py).",
)
_declare(
    "T107",
    _profiles(
        "NPC_PROFILE_T107_OPENAI_LUNA_NONE",
        "NPC_PROFILE_T107_GEMINI_FLASHLITE_LOW",
        "NPC_PROFILE_T107_LEGACY",
        "NPC_PROFILE_T107_LMSTUDIO",
    ),
    note="One-time per-NPC profile seed (structured behavior profile) for the NPC "
         "voice system, always on. OpenAI on cheapest luna|none.",
)
_declare(
    "T108",
    _profiles(
        "NPC_EPISODE_T108_OPENAI_LUNA_LOW",
        "NPC_EPISODE_T108_GEMINI_FLASH_LOW",
        "NPC_EPISODE_T108_LEGACY",
        "NPC_EPISODE_T108_LMSTUDIO",
    ),
    note="Companion EPISODE extraction: attributed salient facts from full-fidelity "
         "encounter text into the canonical episode ledger, at per-location close and "
         "module-leave consolidation. Always on. OpenAI on luna|low "
         "(designated on a real-archive sample). The Gemini response_schema is supplied "
         "by the service (core/npc/episode_extraction.py).",
)
_declare(
    "T112",
    _profiles(
        "NPC_RECALL_T112_OPENAI_LUNA_LOW",
        "NPC_RECALL_T112_GEMINI_FLASHLITE_LOW",
        "NPC_RECALL_T112_LEGACY",
        "NPC_RECALL_T112_LMSTUDIO",
    ),
    note="Episodic RECALL anchor-parse: parses a player's 'remember when...' line into "
         "structured anchors; CODE selects the matching episodeIds from the NPC's own "
         "index (model never selects episodes -> cannot fabricate). Always "
         "on. OpenAI luna|low. Service: core/npc/episode_recall.py.",
)
_declare(
    "T113",
    _profiles(
        "NPC_BACKFILL_T113_OPENAI_LUNA_LOW",
        "NPC_BACKFILL_T113_GEMINI_FLASH_LOW",
        "NPC_BACKFILL_T113_LEGACY",
        "NPC_BACKFILL_T113_LMSTUDIO",
    ),
    note="Episodic BACKFILL extraction: one-time upgrade of an existing game. Reads "
         "compressed journal/campaign-summary prose and SELECTS present companions from "
         "a CLOSED module roster (agentic presence, reconciled by code -> a name not in "
         "the roster is dropped), producing attributed backfilled episodes. Always "
         "on, behind the upgrade progress UI. OpenAI luna|low (same tier "
         "as T108). Service: core/npc/episode_backfill.py.",
)


_declare(
    "T114",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "NPC_RECALL_T112_GEMINI_FLASHLITE_LOW",
        "NPC_RECALL_T112_LEGACY",
        "NPC_RECALL_T112_LMSTUDIO",
    ),
    note="Required, action-triggered party-membership guardian before T065. "
         "Reviews consent and accepted-story grounding without writing state "
         "(#193 D-NPC-PARTY-2..4). Service: core/npc/party_guardian.py.",
)


_declare(
    "T115 T117",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_CONV_GEMINI_FLASH_LOW",
        "LEVELUP_CONV_LEGACY",
        "LEVELUP_CONV_LMSTUDIO",
    ),
    note="Required private level-up domain authors: features, spells, numbers (#323).",
)
_declare(
    "T119",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_CONV_GEMINI_FLASH_LOW",
        "LEVELUP_CONV_LEGACY",
        "LEVELUP_CONV_LMSTUDIO",
    ),
    note="Required private level-up numbers author (#323); Luna low with the rest of the level-up path (2026-09-14).",
)
_declare(
    "T116 T118 T120",
    _profiles(
        "OPENAI_GPT56_LUNA_LOW",
        "LEVELUP_VAL_GEMINI_PRO_LOW",
        "LEVELUP_VAL_LEGACY",
        "LEVELUP_VAL_LMSTUDIO",
    ),
    note="Required focused reviews of level-up domain proposals (#323).",
)


def _build_bindings():
    bindings = {}
    for binding in _DECLARATIONS:
        if binding.task_id in bindings:
            raise RuntimeError("Duplicate callsite binding: %s" % binding.task_id)
        bindings[binding.task_id] = binding
    return MappingProxyType(bindings)


CALLSITE_BINDINGS: Mapping[str, CallsiteBinding] = _build_bindings()

# Per-callsite output ceilings for OpenAI answers, in characters of streamed
# output: four times the 95th percentile of that callsite's captured answers
# (owner rule, 2026-09-29; measured over the kit captures, see the table's
# source note). A streamed answer that passes its ceiling is aberrant by
# measurement (the observed runaway was 55 times the largest real T067
# answer), so the stream is closed and the identical request is reissued.
# Callsites without an entry have no ceiling. Never sent to a provider.
OPENAI_OUTPUT_CEILING_CHARS: Mapping[str, int] = {
    # Source: kit captures scanned 2026-09-29 (OpenAI answers only; callsites with
    # fewer than 30 answers are not listed). T067 max excludes the 170,922-char runaway.
    "T013": 3560,  # n=55 p95=890 max=1003
    "T015": 35244,  # n=43 p95=8811 max=9749
    "T016": 6652,  # n=43 p95=1663 max=2129
    "T034": 5540,  # n=32 p95=1385 max=1386
    "T040": 3344,  # n=31 p95=836 max=949
    "T042": 13512,  # n=90 p95=3378 max=3798
    "T044": 5416,  # n=31 p95=1354 max=1535
    "T047": 12060,  # n=58 p95=3015 max=3348
    "T048": 4252,  # n=42 p95=1063 max=2558
    "T049": 1168,  # n=60 p95=292 max=309
    "T051": 14628,  # n=117 p95=3657 max=3906
    "T052": 4204,  # n=38 p95=1051 max=1518
    "T053": 10568,  # n=39 p95=2642 max=2690
    "T063": 4680,  # n=55 p95=1170 max=1226
    "T064": 7960,  # n=56 p95=1990 max=2012
    "T065": 1564,  # n=706 p95=391 max=584
    "T067": 5528,  # n=1368 p95=1382 max=3099
    "T078": 1800,  # n=85 p95=44 max=44 were all "none" answers; a real add is 390-450 chars (E12a probe), 4x that
    "T079": 3576,  # n=100 p95=894 max=2415
    "T082": 960,  # n=356 p95=240 max=276
    "T084": 18448,  # n=3830 p95=4612 max=7811
    "T090": 5892,  # n=73 p95=1473 max=1580
    "T092": 18808,  # n=34 p95=4702 max=4747
    "T096": 7412,  # n=353 p95=1853 max=1896
    "T097": 3012,  # n=122 p95=753 max=826
    "T105": 2776,  # n=477 p95=694 max=1275
    "T107": 5372,  # n=858 p95=1343 max=1884
    "T112": 376,  # n=102 p95=94 max=175
    "T115": 70596,  # n=139 p95=17649 max=18283
    "T116": 16460,  # n=36 p95=4115 max=4936
    "T117": 23192,  # n=80 p95=5798 max=6774
    "T118": 11128,  # n=32 p95=2782 max=3118
    "T119": 38248,  # n=104 p95=9562 max=11583
}


def openai_output_ceiling(task_id):
    """The output ceiling for one callsite on the openai provider, or None."""
    value = OPENAI_OUTPUT_CEILING_CHARS.get(task_id)
    return value if isinstance(value, int) and value > 0 else None
# Reviewed source inventory: 73 register_callsite IDs (T014 and T091 retired in P4-e/P4-f) plus enabled T104, plus the
# NPC-voice family T105 (voice+affinity) and T107 (profile seed). Keep this
# independent from _DECLARATIONS so deleting/adding a binding cannot make the
# expected set silently redefine itself.
REGISTERED_TASK_IDS = tuple(
    "T012 T013 T015 T016 T017 T018 T019 T020 T021 T022 T023 T024 T025 "
    "T026 T027 T028 T029 T030 T031 T032 T033 T034 T035 T036 T037 T038 T039 "
    "T040 T041 T042 T043 T044 T045 T046 T047 T048 T049 T050 T051 T052 T053 "
    "T054 T059 T063 T064 T065 T066 T067 T078 T079 T081 T082 T083 T084 "
    "T085 T086 T087 T088 T089 T090 T092 T093 T094 T095 T096 T097 T098 "
    "T099 T100 T101 T102 T103 T105 T107 T108 T112 T113 T114 "
    "T115 T116 T117 T118 T119 T120 T121 T122 T123".split()
)
EXPECTED_TASK_IDS = tuple(sorted(REGISTERED_TASK_IDS + ("T104",)))


def candidate_profile(model_id: str, effort: str):
    """Return a detached eligible GPT-5.6 candidate configuration."""
    entry = MODEL_CATALOG.get(model_id)
    if entry is None:
        raise ValueError(
            "Model is not in the evaluated eligibility catalog: %s" % model_id
        )
    if effort not in EVALUATION_EFFORTS:
        raise ValueError("Effort is outside the evaluation ceiling: %s" % effort)
    if effort not in entry.supported_efforts:
        raise ValueError("Unsupported effort %s for %s" % (effort, model_id))
    return {"model": model_id, "reasoning_effort": effort}
