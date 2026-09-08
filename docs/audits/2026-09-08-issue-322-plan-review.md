# Issue 322 FULL plan review, round 1

Date: 2026-09-08. Controller consolidation of eight independent reports, NOT
eight verbatim transcripts. No implementation or provider acceptance executed.
Reviewed plan SHA256:
a79168a8dca056159e616d13c661fca66634e77380b56e80fee010a0bd7a1d27.
Source HEAD:6d18d09ba3d943e018ef4c4aef58934974f9f06a, ancestor of origin/main.
All seats read the same plan and full resolution ledger, relevant live-policy
snapshot and source independently. Three simultaneous slots were available;
seats ran in overlapping waves, blind to one another, with no combined seats.

| Seat | Verdict | Evidence/check and limits |
| --- | --- | --- |
| Architecture Custodian | PASSED | Real T039 entire request/output, validator, shared entrants, transaction, AP1-7, coverage/net-negative. Evidence-root polish. Did not prove all live context callers. |
| Fail-Forward | PASSED scoped | Existing failure terminal traces, phase locks released, reaped transport, no new FS1 hit. Does not bless inherited fallback policy. |
| Acceptance | FAILED plan | Claimed live get_campaign_context is uncalled; actual hub reader assumes nested fields. Correct actual-consumer attribution and preservation acceptance. |
| Consumer/Compat | BLOCKED plan | Hub strings/status-only objects admitted then replace authentic rich hub; actual reader can omit packet. No new schema restriction authorized. |
| Legacy-Contract | PASSED | Original prompt ae007a83 and validator715732d5 mainline lineage; five goals retained. Polish exact origin and two-strikes bisect. |
| Player-Experience | BLOCKED plan | Authentic Shadowfall Keep stronghold/services can disappear; friendly place can be called party-owned. Concrete input->import->packet counterexample. |
| No-Limits Sentinel | PASSED plan only | Raw diff empty; full file scan below; no new input/output cap. Must repeat implementation scan. |
| Single-Path Sentinel | PASSED plan only | Same generator for completion/regeneration; one T039. Existing partial-manager branch has no proven gameplay entrant; FYI, no speculative deletion. |

## Load-bearing finding and reconciliation

Authentic campaign-before.json has Shadowfall Keep hubType=stronghold,
services=[rest,storage,sanctuary,information], ownership=party. A proposal with
all correct outer containers but hubs["Shadowfall Keep"] containing only
status/details passes campaign_manager.py127-157, overwrites the existing object
at4402-4404 and loses its fields. conversation_utils.py815-824 instead defaults
to settlement/basic services/party owned; a scalar raises and826-828 swallows
the whole world-state packet. main.py9128-9143 is another actual hub reader.
This is CODE-PROVEN, NOT observed loss in the original failed regeneration.

The review also corrected the architecture: get_campaign_context has only an
unused utility caller. Real consumers are conversation_utils.py778-834,
main.py9128-9143 and action_handler.py4522 -> accumulated summaries/worldState.
Relationship/artifact facts reappearing in T038 prose do not establish their
typed T039 map injection. Preserve that provenance distinction in acceptance.

CC1/ACC1 maps to task-C3; document correction is made but not a clean
confirmation verdict. CC2/PX1 -> issue-#328 plus escalate:#293/D-322-2.
Owner proposal: include narrow existing hub contract/preservation repair as a
coupled slice, without activating unused context helpers or new storage. Plan
revision stops here until the owner decides scope; no silent expansion.
Escalation: https://github.com/MoonlightByte/NeverEndingQuest/issues/293#issuecomment-5589710783
Issue: https://github.com/MoonlightByte/NeverEndingQuest/issues/328

## Sentinel evidence

Both git diff HEAD and git diff origin/main...HEAD over production files empty.
No product candidate exists; this is NOT a future implementation verdict.
Raw minimum No-Limits source grep:

```text
117:            source_turn_id=str(source_turn_id or "")[:120],
625:    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
```

117 is inherited lifecycle source ID, not changed T039 context. 625 is an
inherited path digest; no model input/output cap and no new authority blessing
(#293/D-2 remains undecided). Proposed instruction-block scan empty. Numeric
container cardinality describes the existing five-key schema, not content cap.

Single-Path raw diff grep output empty. Source scan found inherited data-default,
provider-profile, fallback, ownership-replay and partial-manager branches at
168,289,596,1296,1603,1625,1880,1964,3158,3402,3754,3872,3930,3955-3974,
3981,4001,4294,4605,4688,4716. No introduced parallel extractor. Provider
profiles converge at the one capture call; inherited fallback remains explicitly
unratified by this review. Partial-manager branch lacks a proven production
constructor, so FYI only under R13/R15. Full raw seat output remains in this
session; this paragraph is a consolidation, not pasted command output.

## Stop condition

Round 1 exposed an actual compatibility dependency; NOT CONVERGED. No second
confirmation round is claimed. Owner must rule D-322-2, then exact scoped design
must be revised and receive all required reviews and confirmation on one SHA.
Only a later post-presentation owner execution approval can authorize code.

## Revision history after owner scope approval

2026-09-08: Owner approved including #328, codified in live #193 Part5 D-322-2
at epoch2026-09-08T18:57:23Z. Historical round1 stop above is superseded as a
scope decision, not erased. Execution D-322-1 remains owner-open.
Scope resolution: https://github.com/MoonlightByte/NeverEndingQuest/issues/293#issuecomment-5590268747
Hub issue record: https://github.com/MoonlightByte/NeverEndingQuest/issues/328#issuecomment-5590268936

Round2 (draft SHA prefix37c2d1ef) was superseded after concrete checks; no full
round or convergence is claimed. Fail-Forward found accepted generated-summary
checkpoints can bypass fresh T039 validation and carry a scalar hub. Compat
found a proposed new shared-validator restriction would also reject old tracker
fallback and empty unrelated categories. Architecture found a null-only mapping
could erase an old scalar if adaptation happened before effective-field checks.
PX passed that draft, not the later implementation. The controller removed
validator tightening, specified one origin-independent importer for all admitted
JSON shapes, and put no-fact filtering before any adaptation/publication.

## Revised round3 review target

Full plan and resolution-ledger SHA256:
2d60ce66b984aef1fc4d607cef505adc7c194663797cb18cf4ac39a1d2ad4d0d

Nine separate seats; Leanness added because one shared public formatter is now
proposed. Read-only independent source checks, overlapping waves constrained by
available worker slots; controller is the sole document writer. This record
consolidates reports, not verbatim seat transcripts. No product/provider runs.

| Seat | Round3 verdict | Independently checked evidence and limits |
| --- | --- | --- |
| Architecture | PASSED | Effective patch before scalar adaptation; exact opaque details; no new store/schema/framework; implementation not checked. |
| Fail-Forward | PASSED | Checkpoints1436-1518,3261,3312 and common import3525; no new refusal or lock wait; existing fallback debt not blessed. |
| Consumer/Compat | PASSED | Unchanged validator/fallback; both actual reader families; false/zero/empty-list vs no-fact; real acceptance remains pending. |
| Leanness | PASSED | D-322-2/#328 warrant; one importer covers fresh/fallback/replay; two intended consumers; no new recovery machinery. |
| Acceptance | PASSED | Primitive checks distinguished from real acceptance; authentic hub oracle; exact reader attribution; no live outcome claimed. |
| Player-Experience | PASSED | Both reader defaults retired; source-grounded empty services and field preservation; narration proof remains pending. |
| Legacy-Contract | PASSED | ae007a83,329496ba,be4df1cb lineage; commit-time base3506-3529; exact historical shapes; all GL-1 goals accounted for. |
| No-Limits | PASSED | Three whole-file scans and empty candidate diffs; all hits inherited, not new content caps; implementation scan remains pending. |
| Single-Path | PASSED | Fresh/fallback/accepted-replay converge at import3525; both renderers and main-note branches covered; no provenance-specific behavior introduced. |

Round3 full coverage completed with zero in-scope blockers. The separate clean
confirmation pass below also completed; neither authorizes implementation.

## Revised-scope raw sentinel evidence

Controller reproduced the source scans on unchanged HEAD6d18d09b. These are
source inventories, not product acceptance or verbatim reviewer transcripts.
Candidate production diffs (HEAD and origin/main...HEAD) both have empty output.

No-Limits grep expression:
`\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat`

```text
core/managers/campaign_manager.py:117:            source_turn_id=str(source_turn_id or "")[:120],
core/managers/campaign_manager.py:625:    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
core/ai/conversation_utils.py:587:    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
main.py:3804:                debug(f"Removed duplicate combat system message at index {i}: {content[:60]}...", category="conversation_management")
main.py:7104:            "user_input": user_input[:200],  # First 200 chars
main.py:7287:                "user_input": user_input[:200],
main.py:7430:    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
main.py:7447:                debug(f"Removing old format system prompt starting with: {msg['content'][:50]}...", category="conversation_management")
main.py:7462:            if msg["content"].startswith(main_system_prompt_text[:50]):
main.py:8723:            time_display = f"{current_time_str[:5]} ({time_context})"  # Show HH:MM (context)
main.py:10601:        print(f"DEBUG: [LocationGraph] First 5 location IDs: {list(location_graph.nodes.keys())[:5]}")
```

Dispositions: campaign117 inherited lifecycle source ID, not ratified;625 path
digest, not model text (#293 authority debt unchanged);conversation587/main7430/
7462 identify prompts, not truncate inserted content;main3804/7447/10601 debug;
main7104/7287 quality logs;main8723 HH:MM display. None is introduced by the plan.

Single-Path grep expression:
`legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback`

```text
core/managers/campaign_manager.py:168:    """A local durability failure that must not become an AI fallback."""
core/managers/campaign_manager.py:289:    """Absent is legacy; null producer is relinquished, never malformed-live."""
core/managers/campaign_manager.py:596:        _normalize_completion_id(completion_id) or "__legacy_module_flight__",
core/managers/campaign_manager.py:1296:        # so the legacy pending-then-work cleanup window is safe here.
core/managers/campaign_manager.py:1603:    fallback: Optional[Dict[str, Any]] = None,
core/managers/campaign_manager.py:1625:            persisted = copy.deepcopy(fallback) if isinstance(fallback, dict) else {}
core/managers/campaign_manager.py:1880:            fallback=_default_campaign_data(),
core/managers/campaign_manager.py:1964:                        fallback=_default_campaign_data(),
core/managers/campaign_manager.py:3158:            # Receipt replay and legacy-overlap reuse are completion fast
core/managers/campaign_manager.py:3402:                    # into an engine failure or a generated-summary fallback.
core/managers/campaign_manager.py:3754:-   **Moral and Ethical Fingerprints:** Your chronicle must be an honest record. Detail the significant good *and* evil deeds performed by the characters. Did they save the village, only to loot its sacred temple? Did they lie to an ally for personal gain? These choices are their legacy and must be remembered.
core/managers/campaign_manager.py:3872:            else:  # legacy
core/managers/campaign_manager.py:3930:            else:  # legacy
core/managers/campaign_manager.py:3955:                debug(f"T039 fallback to local processor: {e}", category="campaign_management")
core/managers/campaign_manager.py:3959:                export_source = "local_fallback"
core/managers/campaign_manager.py:3962:                fallback_error = "Local T039 fallback returned invalid campaign export data"
core/managers/campaign_manager.py:3964:                    fallback_error = f"{export_error}; {fallback_error}"
core/managers/campaign_manager.py:3973:                export_error = fallback_error
core/managers/campaign_manager.py:3974:                export_source = "empty_fallback"
core/managers/campaign_manager.py:3981:                # _update_available_modules consumes this legacy top-level
core/managers/campaign_manager.py:4001:            # fallback keys (keyDecisions/consequences/unlockedModules/
core/managers/campaign_manager.py:4294:            # instances retain the legacy summary-only behavior.
core/managers/campaign_manager.py:4605:        The prose summary remains the durable T038 record.  This fallback
core/managers/campaign_manager.py:4688:            fallback=_default_campaign_data(),
core/managers/campaign_manager.py:4716:            fallback=_default_campaign_data(),
main.py:289:    "Starting..." until the slow prompt fallback fires.
main.py:1246:    """Run startup kickoff with exactly-once lease and one fallback recovery attempt."""
main.py:1571:        else:  # legacy
main.py:1628:        return f"You arrive at {new_location_name}."  # Deterministic fallback.
main.py:1678:        else:  # legacy
main.py:2258:    memory = checkpoint["legacy_memory"]
main.py:2972:                # Module publication is deliberately stricter than legacy
main.py:3149:    candidate pair is preserved verbatim and adjacent; cloud/legacy/gemini requests
main.py:3600:    if _val_provider == "openai":
main.py:3602:    elif _val_provider == "gemini":
main.py:3604:    elif _val_provider == "lmstudio":
main.py:3606:    else:  # legacy
main.py:3773:    # Normalize legacy DM note headers before reuse.
main.py:3814:    from core.ai.cumulative_summary import normalize_legacy_dm_notes
main.py:3816:    normalized = normalize_legacy_dm_notes(conversation_history)
main.py:3821:def _legacy_absent_target(path):
main.py:3825:def _legacy_json_target(path):
main.py:3828:        return _legacy_absent_target(path)
main.py:3836:def _find_legacy_location_repair(conversation_history):
main.py:3837:    """Return the earliest raw legacy transition segment that can be repaired."""
main.py:3922:def _prepare_legacy_memory_targets(journal_entry, party_tracker_data, operation_id):
main.py:3923:    """Compute legacy companion-memory mutations in an isolated temporary tree."""
main.py:3926:    # is absent here, so there are no legacy-memory targets to prepare.
main.py:3930:        str(path): _legacy_json_target(path)
main.py:3933:    with tempfile.TemporaryDirectory(prefix="neq-legacy-memory-") as temporary:
main.py:3977:                    "legacy memory compression failed with exit code %s"
main.py:3992:            after = _legacy_json_target(temporary_path)
main.py:3994:            prior = before.get(relative, _legacy_absent_target(relative))
main.py:4000:def _apply_legacy_json_target(target):
main.py:4004:    current = _legacy_json_target(path)
main.py:4016:def _apply_legacy_repair_checkpoint_unlocked(checkpoint, conversation_history):
main.py:4017:    repair = checkpoint.get("legacy_repair") or {}
main.py:4022:        outcome = _apply_legacy_json_target(target)
main.py:4054:def _apply_legacy_repair_checkpoint(checkpoint, conversation_history):
main.py:4058:        return _apply_legacy_repair_checkpoint_unlocked(
main.py:4069:        if existing.get("version") == 2 and existing.get("kind") == "legacy_repair":
main.py:4070:            return _apply_legacy_repair_checkpoint(existing, conversation_history)
main.py:4073:    repair = _find_legacy_location_repair(conversation_history)
main.py:4085:    journal_target_before = _legacy_json_target("journal.json")
main.py:4099:    memory_targets = _prepare_legacy_memory_targets(
main.py:4115:        "kind": "legacy_repair",
main.py:4118:        "legacy_repair": {
main.py:4146:    return _apply_legacy_repair_checkpoint(checkpoint, conversation_history)
main.py:4328:                else:  # legacy
main.py:4372:                warning(f"FAILURE: Error generating AI summary from conversation, using fallback", category="summary_building")
main.py:4374:        debug(f"STATE_CHANGE: Not enough meaningful conversation for AI summary ({len(meaningful_messages)} messages), using fallback", category="summary_building")
main.py:4377:        error(f"FAILURE: Error processing conversation for summary, using fallback", exception=e, category="summary_building")
main.py:5005:        fallback = dict(result)
main.py:5006:        fallback["status"] = "published"
main.py:5007:        fallback["needs_dm_response"] = False
main.py:5008:        return fallback
main.py:5164:        # Preserve the legacy response-wide fence for ordinary responses.
main.py:5887:                memory_record = transition_checkpoint["legacy_memory"]
main.py:5889:                    # [travel-clean #209] legacy companion-memory reconciliation deferred until
main.py:7215:    else:  # legacy
main.py:7328:    fallback_message = (
main.py:7332:    cleaned_history.append({"role": "assistant", "content": fallback_message})
main.py:7545:            # Check root directory (legacy structure)
main.py:8000:                                f"STARTUP_REPAIR: Fixed legacy character {member_name}: {', '.join(repairs)}",
main.py:8014:                                    f"STARTUP_REPAIR: Fixed legacy NPC {npc_name}: {', '.join(repairs)}",
main.py:8082:        # Convert legacy effect bookkeeping once, before combat resume or any new
main.py:8105:                    "The campaign remains on its legacy effect handling for this session."
main.py:9021:                            # Handle legacy string format (just use the string)
main.py:9204:        # hints; keep the legacy inventory inputs unchanged on no-match turns.
main.py:9245:            except Exception as legacy_compression_error:
main.py:9248:                    % type(legacy_compression_error).__name__,
main.py:9251:        pending_legacy = safe_json_load(
main.py:9255:            isinstance(pending_legacy, dict)
main.py:9256:            and pending_legacy.get("version") == 2
main.py:9257:            and pending_legacy.get("kind") == "legacy_repair"
main.py:9712:        # ready signal must be re-sent AFTER the scope closes or the legacy
```

Campaign dispositions:168/3402 forbid fallback;3754 narrative legacy;289/596/
1296/3158/3981/4001 persisted compatibility, not parallel extractor;1603/1625/
1880/1964/4688/4716 load defaults;3872/3930 provider profiles converge;3955-3974/
4605 inherited fallback stays #322 observation, not ratified;4294 has no proven
production entrant (SP1 FYI). All main.py hits lie outside the allowed hub block
and are unchanged. No new provenance branch is proposed in that block. These
inventories do not certify unrelated mainline behavior safe. Implementation
must repeat the whole-file and actual candidate-diff scans.

## Clean confirmation and final plan verdict

2026-09-08: all nine separate reviewers independently reread the same full plan
and resolution ledger at SHA256
2d60ce66b984aef1fc4d607cef505adc7c194663797cb18cf4ac39a1d2ad4d0d.
No plan edits occurred between round3 and confirmation. Current live #193 epoch
rechecked unchanged at2026-09-08T18:57:23Z. This review document is an external
controller consolidation and is not the frozen plan/ledger artifact.

| Confirmation seat | Verdict | Fresh decisive recheck |
| --- | --- | --- |
| Architecture | PASSED | Admitted scalar + null-only mapping leaves exact scalar; unchanged validator and existing commit ownership. |
| Fail-Forward | PASSED | Accepted checkpoint3261/3312 reaches importer3525; existing failure4272-4280 unchanged; empty FS-1 candidate scan. |
| Consumer/Compat | PASSED | Validator calls3950/3961 and fallback4622-4633 remain admitted; both readers covered; no-fact vs explicit value. |
| Acceptance | PASSED | Authentic T039/stronghold evidence and both live consumer oracles; primitive/native and NOT-REACHED distinctions. |
| Legacy-Contract | PASSED | Original ae007a83 five goals/full summary; overwrite/reader blame; omission preservation plus explicit services clear. |
| Player-Experience | PASSED | Both defaulting readers; authentic friendly/owned hub polarity and five real narration-to-disk claims required. |
| Leanness | PASSED | One importer caller3525, two intended reader seams; public symbol absent because implementation absent, post-code audit required. |
| No-Limits | PASSED | Whole-file/diff/mechanics scans repeated; same raw results above, no new bound or cap. |
| Single-Path | PASSED | Completion3368/regeneration4342 converge to importer3525; two readers/DM-note branches use one planned formatter; raw scans repeated. |

Final disposition: CONVERGED PLAN, nine-seat full round plus separate clean
confirmation on one SHA. No unresolved in-scope design finding remains.
D-322-1 execution remains escalate:@owner after architectural presentation.
Only two uncommitted documentation files exist in the isolated worktree;
production diff empty, no code/commits/push/provider runs. Compile/runtime/
native acceptance, actual helper wiring, factual model compliance, Save/Load/
cancellation and postimplementation audit are all NOT EXECUTED. No universal
regression-free or hallucination-free claim follows from plan convergence.
