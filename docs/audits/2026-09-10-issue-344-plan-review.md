# Issue #344 - independent plan review

2026-09-10. Controller consolidation of nine independent agent returns, not
nine verbatim reports. No product code or live acceptance was run. The forensic
agent was separate and was not counted as a plan-review seat.

Reviewed substantive SHA256:
bafd1104ebfd31c166a81a34222f4cbb881704a06a317b6d2ec394709845eb48.
Plan: 2026-09-10-issue-344-character-evidence-plan.md in this directory.
Worktree: /home/loup/neq-worktrees/344-character-validator-evidence.
Branch: plan/344-character-validator-evidence.
Base/HEAD/origin/main: 8c242fa1c7433dfc76c6af44828775a2799e1cec.
Live #193 v3.1 epoch: 2026-09-10T21:54:15Z, independently refreshed at end.

## Seat verdicts and checked evidence

All seats read the complete same-SHA plan and embedded resolution ledger,
applicable live rules and current code. Read-only, blind, separate agents in
parallel waves; controller single-writes. No consensus authorizes execution.

| Seat / agent | Verdict | Independently checked |
| --- | --- | --- |
| Architecture / 344_architecture | No blocking findings | main.py:3268 normalized candidate versus :3354 original; :3492 precompression inventory versus :3617/:3655 canonical facts; path resolver92/205; shared review10487/10522; AP1-7 and doc boundaries |
| Fail-Forward / 344_failforward | No blocking findings | native classifier29-47 and reader53-77; live_provider_call893-925; 0.25 cadence CONTINUES not exhausts; cancellation3754-3755/10577-10578; unavailable records do not erase others or mutate files |
| Acceptance / 344_acceptance | No blocking findings | actual E1 index5 candidate actions[] and+3 rejection; E2 index4 consistent3->8 and5->0 rejected without sheet; A1/A2 require real branch and writer results, A3 negative polarity and A4 freshness; no captured playback claimed live |
| Consumer/Compat / 344_compat | No blocking findings | repository caller-family: ordinary9465, stale recovery6975, membership9870 -> shared10487; nonmembership9865 bypass preserved; authentic roster/character shapes; null/zero/nested equipment retained; stored/effective distinction |
| Legacy-Contract / 344_legacy | No blocking findings; citation polish | a5c64749 unlimited inventory/arrow/potion/trade goals; d7b47fda preserved them; baseline691b5a2f inventory code; structure-note begins3445 so projection endpoint corrected3443 |
| Player-Experience / 344_px | No blocking findings | C:/354-resume-OlHrRC/player/turn03-check.json:5 records/bookkeeping refusal; meaningful healing, dice/agency, hidden facts, five state claims and private-feedback leakage probes; broader354 sample remains incomplete |
| Leanness / 344_leanness | No blocking findings | one private evidence boundary, no store/cache/public API/new model call; all applicable entrants; transient retry uses existing primitives; no test self-stubbing; explicit full-sheet cost measurement |
| No-Limits / 344_limits | No blocking in-scope findings | raw diff and main.py scans below; external build_npc_context caps recorded on276, not repaired here |
| Single-Path / 344_singlepath | No blocking in-scope findings | sole validate_ai_response/T065 boundary, replace not duplicate projection, normalized target re-read, common assembly before provider selection; complete raw scan below |

Schema-Freeze: no persisted schema or format changes; authentic records inspected
by Compat. Platform/Provider and Hygiene remain execution gates. FULL and GL-1
apply. No agent certified absent implementation, active-effect live behavior,
native locks, fresh model compliance, all save variants, actual tokens/latency,
or twenty-turn browser coverage. These remain named development/acceptance tasks.

## Findings reconciliation and convergence

- F9: endpoint citation3446 ->3443, fixed-inline. No changed code step; the plan
  already retained structure validation. Independently verified on current source.
- F10: PRE_EXISTING_OUT, core/ai/build_npc_context.py153/169 limits50/30. Blame
  4d1816a96. Concrete input51/31 names drops last alphabetic identity. Filed
  specific evidence under existing #276 this turn:
  https://github.com/MoonlightByte/NeverEndingQuest/issues/276#issuecomment-5628144334.
- F11: fyi, broader #354 twenty-turn coverage not satisfied by this focused plan.

All nine seats returned zero in-scope blocking findings on the same substantive
SHA. Only citation polish and external tracking/coverage notes were folded. Under
NEQ-REVIEW-11 plan-polish termination after full coverage, review completes
without a ceremonial redispatch. No separate confirmation pass is claimed.
No code-class correction is awaiting R2 verification. The final plan checksum
is reported separately so this evidence record does not create a hash cycle.

## No-Limits raw scans

`git diff HEAD | rg -n '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat'`

Output: EMPTY. There is no candidate production implementation.

`rg -n '\[:[0-9]+\]|\[-[0-9]+:\]|max_tokens|max_completion|maxItems|maxLength|truncat' main.py`

```text
3928:                debug(f"Removed duplicate combat system message at index {i}: {content[:60]}...", category="conversation_management")
7228:            "user_input": user_input[:200],  # First 200 chars
7411:                "user_input": user_input[:200],
7554:    main_prompt_start = main_system_prompt_text[:50]  # First 50 characters as identifier
7571:                debug(f"Removing old format system prompt starting with: {msg['content'][:50]}...", category="conversation_management")
7586:            if msg["content"].startswith(main_system_prompt_text[:50]):
8850:            time_display = f"{current_time_str[:5]} ({time_context})"  # Show HH:MM (context)
10725:        print(f"DEBUG: [LocationGraph] First 5 location IDs: {list(location_graph.nodes.keys())[:5]}")
```

Every hit DEFENSIBLE outside model-I/O cap predicate:3928/7571/10725 diagnostic
previews;7228/7411 quality-control telemetry excerpts (not actual input);
7554/7586 identify/reorder complete prompts (full replacement at7576);
8850 formats terminal time. Not invented Part5 cap exceptions.

Additional unchanged dependency scan:

```text
153:    lines.append(f"@CURRENT_MODULE[{current_module}]: {','.join(sorted(module_npcs)[:50]) if module_npcs else 'NONE'}")
169:    other_npcs_list = sorted(other_npcs)[:30]
```

Consumer main.py3466 ->3490 ->T0653741. CRITICAL-class caps but PRE_EXISTING_OUT;
specific #276 tracking above, no #344 scope expansion.

## Single-Path raw scans

`git diff HEAD -- main.py | rg -n 'legacy|use_new|_v2\b|mode ?==|if .*provider ?==|fallback'`

Output: EMPTY. Touched-file scan with that same regex:

```text
289:    "Starting..." until the slow prompt fallback fires.
1246:    """Run startup kickoff with exactly-once lease and one fallback recovery attempt."""
1571:        else:  # legacy
1628:        return f"You arrive at {new_location_name}."  # Deterministic fallback.
1678:        else:  # legacy
2258:    memory = checkpoint["legacy_memory"]
2972:                # Module publication is deliberately stricter than legacy
3149:    candidate pair is preserved verbatim and adjacent; cloud/legacy/gemini requests
3724:    if _val_provider == "openai":
3726:    elif _val_provider == "gemini":
3728:    elif _val_provider == "lmstudio":
3730:    else:  # legacy
3897:    # Normalize legacy DM note headers before reuse.
3938:    from core.ai.cumulative_summary import normalize_legacy_dm_notes
3940:    normalized = normalize_legacy_dm_notes(conversation_history)
3945:def _legacy_absent_target(path):
3949:def _legacy_json_target(path):
3952:        return _legacy_absent_target(path)
3960:def _find_legacy_location_repair(conversation_history):
3961:    """Return the earliest raw legacy transition segment that can be repaired."""
4046:def _prepare_legacy_memory_targets(journal_entry, party_tracker_data, operation_id):
4047:    """Compute legacy companion-memory mutations in an isolated temporary tree."""
4050:    # is absent here, so there are no legacy-memory targets to prepare.
4054:        str(path): _legacy_json_target(path)
4057:    with tempfile.TemporaryDirectory(prefix="neq-legacy-memory-") as temporary:
4101:                    "legacy memory compression failed with exit code %s"
4116:            after = _legacy_json_target(temporary_path)
4118:            prior = before.get(relative, _legacy_absent_target(relative))
4124:def _apply_legacy_json_target(target):
4128:    current = _legacy_json_target(path)
4140:def _apply_legacy_repair_checkpoint_unlocked(checkpoint, conversation_history):
4141:    repair = checkpoint.get("legacy_repair") or {}
4146:        outcome = _apply_legacy_json_target(target)
4178:def _apply_legacy_repair_checkpoint(checkpoint, conversation_history):
4182:        return _apply_legacy_repair_checkpoint_unlocked(
4193:        if existing.get("version") == 2 and existing.get("kind") == "legacy_repair":
4194:            return _apply_legacy_repair_checkpoint(existing, conversation_history)
4197:    repair = _find_legacy_location_repair(conversation_history)
4209:    journal_target_before = _legacy_json_target("journal.json")
4223:    memory_targets = _prepare_legacy_memory_targets(
4239:        "kind": "legacy_repair",
4242:        "legacy_repair": {
4270:    return _apply_legacy_repair_checkpoint(checkpoint, conversation_history)
4452:                else:  # legacy
4496:                warning(f"FAILURE: Error generating AI summary from conversation, using fallback", category="summary_building")
4498:        debug(f"STATE_CHANGE: Not enough meaningful conversation for AI summary ({len(meaningful_messages)} messages), using fallback", category="summary_building")
4501:        error(f"FAILURE: Error processing conversation for summary, using fallback", exception=e, category="summary_building")
5129:        fallback = dict(result)
5130:        fallback["status"] = "published"
5131:        fallback["needs_dm_response"] = False
5132:        return fallback
5288:        # Preserve the legacy response-wide fence for ordinary responses.
6011:                memory_record = transition_checkpoint["legacy_memory"]
6013:                    # [travel-clean #209] legacy companion-memory reconciliation deferred until
7339:    else:  # legacy
7452:    fallback_message = (
7456:    cleaned_history.append({"role": "assistant", "content": fallback_message})
7669:            # Check root directory (legacy structure)
8127:                                f"STARTUP_REPAIR: Fixed legacy character {member_name}: {', '.join(repairs)}",
8141:                                    f"STARTUP_REPAIR: Fixed legacy NPC {npc_name}: {', '.join(repairs)}",
8209:        # Convert legacy effect bookkeeping once, before combat resume or any new
8232:                    "The campaign remains on its legacy effect handling for this session."
9148:                            # Handle legacy string format (just use the string)
9325:        # hints; keep the legacy inventory inputs unchanged on no-match turns.
9366:            except Exception as legacy_compression_error:
9369:                    % type(legacy_compression_error).__name__,
9372:        pending_legacy = safe_json_load(
9376:            isinstance(pending_legacy, dict)
9377:            and pending_legacy.get("version") == 2
9378:            and pending_legacy.get("kind") == "legacy_repair"
9833:        # ready signal must be re-sent AFTER the scope closes or the legacy
```

Every-hit dispositions (grouped, not omitted):

| Lines | Lineage | Disposition |
| --- | --- | --- |
|289,1246|715732d554cd|Existing startup descriptions, no competing evidence implementation|
|1571,1678,3724,3726,3728,3730,4452,7339|715732d554cd|Shared provider selection; NEQ-LEDGER-07(d), no evidence bypass|
|1628|b7f7a8631d33|Existing T063 exception narration; outside repair, not certified anew|
|2258,3938,3940,3945,3949,3952,3960,3961,4046,4047,4054,4057,4101,4116,4118,4124,4128,4140,4141,4146,4178,4182,4193,4194,4197,4209,4223,4239,4242,4270,6011,9366,9369,9372,9376,9377,9378|b7f7a8631d33|Existing transition repair/checkpoint consumers; data adaptation under NEQ-LEDGER-03/09; no new evidence runtime|
|4050,6013|4b53aacec449|Existing209 comments, D-VS-16 transitional memory coexistence|
|2972|715732d554cd|Publication comparison comment, lexical hit|
|3149|db0b0954ae34|Shared exact candidate pair, template compatibility NEQ-PROVIDER-01|
|3897|1ba542e1888a|Header normalization comment, forward adaptation|
|4496|fb0e91f7074e|Existing summary exception diagnostic, outside scope|
|4498,4501|932aceb00adc|Existing summary diagnostics, outside scope|
|5129,5130,5131,5132|691b5a2f06b4|Postpublication handback, not second publication/evidence owner|
|5288|b7f7a8631d33|Existing fence contract comment|
|7452,7456|e4e4e2d08a74|Existing failure text called9506, not new evidence duplication or approval of its policy|
|7669|932aceb00adc|Disk-layout adaptation NEQ-LEDGER-03, not new character fallback|
|8127,8141|715732d554cd|Startup repair diagnostics, unchanged|
|8209,8232|d61f20d317f6|Existing effect migration/message, no new mode; downstream bifurcation not checked, wording alone not proof|
|9148|1830570b2b2e|String-format adaptation NEQ-LEDGER-03/09|
|9325|eb2ecd52f3e3|Different T067 consumer, not retained duplicate T065 inventory frame|
|9833|fdf017739e06|UI readiness comment, not runtime selection|

## Final boundary

PLAN REVIEW COMPLETE. No game source modified, no tests claimed executed against
a fix, no model calls, no commits/push/merge. Owner must approve execution after
presentation. Then C0-C4, D1-D4, A1-A5 and the non-author implementation audit
remain mandatory; NOT-REACHED evidence remains explicit.
