# Progression and Leveling

## #323 source-echo removal (2026-09-13; live acceptance pending)

Specialist output now contains only calculations, rule facts/references, variations
and proposed changes. Code retains an independent input snapshot; original sheet
data is supplied as context, never regenerated as evidence. Existing withdrawal
compares actual sheet/choice/upstream values and rebuilds changed consumers. Equal
rule reassertion does not invalidate unchanged input merely because origin changes.
Arithmetic admission and independent proposal/final reviews remain. Interview,
consent, forward ordering, writer and post-save narration are unchanged.

## #323 saved-spell evidence delta (2026-09-10; acceptance pending)

Under #193 D-323-8, the existing SRD reference index supplies full definitions for
explicit names from saved spell lists and preparedSpells. One session-local frame
is shared unchanged by T047 and every T048. Metadata is not coerced or mutated;
unresolved names mean missing evidence, never illegal spells. A failed reference
read warns and leaves the same interview path active. This is evidence, not spell
availability, mutation authority, or a catalog of future selections. Existing
author/reviewer guidance separates granted spells from ordinary occupancy, checks
attained feature levels and derived components, and distinguishes optional prose
from affected mechanics. T048 retains its four-field verdict; recommendation now
requests applicable source/value comparisons before the verdict. No new agent,
rules engine, provider route, parser, schema or writer in this delta.

## #323 explicit resource-state delta (2026-09-09; live acceptance pending)

Under #193 D-323-6/7, classFeatures usage accepts a complete numeric object or
explicit null. Null means no independent use pool, never free/unlimited use.
Omission still preserves the current value in the existing named merge. The
model identifies the exact shared parent and cost; existing combat resource
events spend that parent's counter. No resource registry or alternate writer.
The effects initializer skips an existing usage key, so null survives that pass.
Compression and player/NPC tooltips omit a counter for null without dropping
the feature or changing numeric-counter rendering. T047/T048/T079 share these
storage instructions; rest amounts and granted-spell accounting remain model
adjudication using actual rules, not a new rules engine. Pure checks pass;
actual level-up/use/rest/Save/Load evidence is still required.

Purpose: award combat XP exactly once to participating character sheets, expose cumulative XP against the next threshold, and perform advancement through a separate agentic level-up conversation.

Verified against NeverEndingQuest `20f2b0eaf142c33b7f509ce072b55c6a799dfe66` on 2026-09-01. Policy pointers refer to live [issue #193](https://github.com/MoonlightByte/NeverEndingQuest/issues/193), v2.3 at verification time.

Level-up delta: #323 postapproval working candidate on `fix/323-c4-pressure`,
HEAD `8c242fa1c7433dfc76c6af44828775a2799e1cec` plus uncommitted changes, inspected
2026-09-13. The session/writer/publication flow below describes implementation,
not completed native acceptance. Unchanged combat-XP anchors retain their earlier
verification pin. Live #193 v3.1, including D-323-1, remains authority.

## Authority table

| Datum | Source of truth | Acceptance or commit point |
|---|---|---|
| Defeated enemies | Active encounter and typed completion state | Combat completion classifier |
| XP value | Code-owned CR-to-XP table | Defeated-enemy total divided across tracker party members and NPCs |
| Reward recipients | Exact player/NPC character paths derived from encounter combatants | Enemy templates remain read-only |
| Reward idempotence | `completion.pendingRewards` and `completion.rewardsApplied` | Character absolute values write first; encounter receipt writes last |
| Current XP | Character JSON `experience_points` | Level-up code removes any attempted XP change |
| Level and threshold | Character JSON `level` and `exp_required_for_next_level` | Whole validated character update commits |
| Trigger and consent | Accepted T067 `levelUp` action under full/compressed main and validation prompt contracts | Player's advancement request/agreement starts the interview, not unchosen options; informational questions do not consent; eligible party NPC uses the same handoff automatically |
| Advancement choices | Accepted T047 `LevelUpSession` conversation | Real player input and accepted assistant turns; private corrections are separate |
| Storage evidence | Session snapshot from the writer's `load_schema()` and shared `leveling_info.txt` | Same full schema string supplied to T047 and every T048; evidence is not approval |
| Saved-spell rule evidence | Existing `SRDReferenceIndex.reference()` over `data/spell_repository.json` | Explicit saved names resolve to complete entries in one shared session frame; unresolved names are not deletion authority |
| Rules verdict | Exact T048 `{valid,errors,warnings,recommendation}` | Every candidate reviewed against accepted choices, sheet, storage contract and requested transition |
| Domain mechanics | Features/spells/numbers authors T115/T117/T119 plus independent T116/T118/T120 proposal reviews, all Luna none | Private typed proposals and dependency checks; no review of the merged sheet; the interviewer does not author the final delta |
| Final sheet | Canonical character JSON | Existing preparation and guarded commit helpers assemble/write the approved domains; no T079 calculation on this level-up path |
| Level-up publication authority | Session-captured live scope | Existing scope lock orders each replacement/output admission against cancellation |

## Flow

1. Typed combat reaches all-hostiles-resolved and enters idempotent combat completion.
2. XP calculation loads the active encounter and party tracker. Each dead, defeated, or unconscious enemy contributes the CR table value; integer division produces XP per party member and party NPC.
3. Reward application takes ordered encounter and character leases. If `rewardsApplied` is already true, it exits without another award.
4. First application records each recipient's absolute `before` and `after` XP in `pendingRewards` and persists the encounter journal before changing a character.
5. It writes each character's absolute `after`, then sets `rewardsApplied=true`, clears `pendingRewards`, and writes the encounter receipt last. Replay converges without additive duplication.
6. Completion appends the XP narrative to ordinary history and finishes summary/archive receipts before clearing the active encounter.
7. Ordinary DM context exposes each party character's level, XP, and next threshold. Full/compressed main and general-review prompts direct an eligible player's advancement request/agreement to a standalone `levelUp`; informational discussion alone is not consent. Eligible party NPCs use the same handoff automatically, one level at a time. Ordinary updates (including earned XP and temporary maximum-HP effects) retain their normal paths; any independent work must finish before the handoff. This is agentic guidance, not a new dispatcher or deterministic intent filter.
8. Main intercepts the first accepted `levelUp` action before ordinary narration/action handling and starts a `LevelUpSession`.
9. The action handler passes current/new level, original player input and pre-action accepted history to the session. All five main action-dispatch sites forward the same optional context. It does not itself evaluate XP eligibility, consent, or `newLevel == currentLevel + 1`; those are prompt/T048 responsibilities.
10. The session reloads the current module character and captures its live scope. The T047 model reads `character_type` from the sheet: players choose and confirm; NPCs advance automatically through the same path.
11. It initializes the accepted interview with the slim leveling guide, current sheet, transition, storage-schema and saved-spell frames, plus the last accepted exchange from main (one player turn, one DM reply) and the actual input; the rest of the campaign history stays in main. The existing layer report starts as `interviewing`; initialization never launches specialists.
12. T047 emits the private `stage/narration/asking/choices` contract: ask, silent commit or report. The DM interviews before approval, including HP method and any actual supplied roll. Final confirmation approves calculation with lawful defaults, not an already assembled recap. NPCs use automatic `npc-policy` commit without human questions.
13. Structural checks and T048 validate before registering questions or answers. During interview, errors return privately to T047. The latest rejected candidate and corrections remain separate from accepted conversation. Empty pending questions do not imply interview completeness; that is an agentic judgment against actual choices and rules.
14. Validated commit records authorization and launches the domain specialists in dependency order: features first, then spells and numbers side by side (both consume only the approved features output), each with its own independent review. Each consumes the full accepted interview, recorded choices, stored/effective sheets, slim guide, spell evidence and approved upstream output. Specialists return complete changes and variation metadata, never questions. An upstream correction retracts the domain and its dependents, which are rebuilt on the next round. Player-facing progress uses game wording (working out the new class features, choosing the spells, recalculating the numbers), never the internal specialist vocabulary. Specialists receive the level-up interview only (entry request onward), one stored sheet, the schema, spell references and the slim guide; the pre-level-up campaign history is not sent.
15. First answers retain pending interview questions; same-answer correction-plus-approval is supported. Missing selectable preferences receive lawful model-chosen defaults with reviewed explanations; explicit legal choices, actual rolls, cumulative XP and spent resources are preserved. The DM does not author the mechanical delta.
16. Complete domains are merged over the stored sheet and pass the provider-free preparation checks (schema, purge, critical-field preservation, unchanged XP, requested level), then the existing guarded writer commits once. No model reviews the merged sheet (owner ruling 2026-09-14): each domain was authored and independently reviewed at proposal time, and a further review only restarted the chain. A failed deterministic check goes back to its owning domain, or to every approved domain when unowned, without a model call. The ordinary update path's post-write normalizers (T051 armor class, T052 inventory categories, T054 currency, effects validator) do not run inside the level-up: the prepared sheet is exactly what the three domains authored (#407). Those normalizers still run on the next ordinary character update.
17. After commitment, only observed-sheet reporting remains; a failed/mismatching reread cannot trigger another write or claim rollback. Accepted public turns retain the existing `LevelUpTurn`/narration-actions surface contract; private stage JSON and specialist corrections are not player history.
18. Main retains the accepted interview chronologically once, including approval and the final reply, but never internal notes/rejected drafts. Session authority covers display, audit/history and common-tail save. Later preference edits return to ordinary update-character, not another advancement.

## State and atomicity

- `party_tracker.json` owns active encounter identity and party membership.
- The encounter JSON owns `pendingRewards` and `rewardsApplied`. XP award spans multiple files, but the pending absolute postimages make crash replay convergent.
- Character JSON owns cumulative XP, current level, next threshold, and all advancement mechanics. Individual writes are atomic; the broader level-up is not a `StateTransactionCoordinator` transaction.
- `level_up_conversation.json` is overwritten after each interview turn. A new session does not reload it, so it is an audit trace rather than restart authority.
- Main conversation history owns the player-visible opening, completion, and failure records.
- Character updates retain existing backups. Guarded level-up waits for the existing effects-path lease without expiry, then checks its captured authority. Other callers retain their existing lease behavior (#324); no #152 coordinator redesign is included.
- `LevelUpSession` is process-local. EOF aborts visibly; retry creates a new session.
- The schema requires integer level, current XP, and next threshold but sets no min/max there. The ordinary DM validator constrains level 1 through 20; the action entrant only checks required action fields.
- The leveling reference and both specialist prompts preserve earned XP. Character level-up is not an automatic rest; existing resources and unmodified fields remain preserved.
- The shared storage guidance distinguishes proficiency-name saves (numeric bonuses derived by combat) from stored skill-map/attack/spell values. Skills retain their actual list/map shape. Named-array entries retain unmentioned entries, but supplied nested fields replace those fields; partial usage objects must not erase remaining resources. That earlier guidance delta changed no schema or writer behavior; the later D-323-6 nullable exception is described above.
- Main intercepts only the first `levelUp` and does not execute sibling actions. The prompts prohibit mixed handoffs but add no deferred-action scheduler. Original input and accepted history now transfer into the session; semantic extraction, not code parsing of natural language, establishes choices. Live coverage of every entrant is still pending.
- Existing main historical-guidance normalization treats an old leveling note as reference, not renewed consent or a pending transition. The separate writer-side historical adapter remains; this change does not eliminate every historical instruction.
- The per-encounter receipt prevents duplicate award within one encounter identity. Issue #253 tracks duplicate semantic encounters created under a new identity.

## Load-bearing seams

1. `utils/xp.py:10-30` - CR-to-XP table and normalization.
2. `utils/xp.py:35-112` - defeated-enemy accounting and party division.
3. `core/managers/combat_manager.py:1555-1580` - exact recipient character paths.
4. `core/managers/combat_manager.py:2129-2205` - completion, XP history, and summary.
5. `core/managers/combat_transaction.py:1266-1309` - reward journal and receipt-last writes.
6. `schemas/encounter_schema.json:532-549` - completion receipt schema.
7. `schemas/char_schema.json:24-26` and `schemas/char_schema.json:519-548` - progression fields.
8. `prompts/system_prompt.txt:965` and `prompts/validation/validation_prompt.txt:194` - full advancement-entry contracts; their compressed counterparts carry the same distinction.
9. `core/ai/action_handler.py:3759` - `levelUp` entrant and session creation.
10. `main.py:5384` - level-up interception before ordinary action output.
11. `core/managers/level_up_manager.py:78` - captured commit guard and process-local session.
12. `core/managers/level_up_manager.py:230`, `:372`, `:470`, `:484`, `:520`, `:635` and `:726` - interview loop, prospective guards, answer retention, domain packets, preparation, commit and shared evidence (2026-09-12 working candidate).
13. `core/ai/level_up_specialists.py` `collect_domain_work` and `run_layer` - owned collection and fixed forward calculation; `utils/level_up_workspace.py` `promote`/`withdraw` preserve approved fact delivery/currentness. Specialist question/parking helpers are retired.
14. `main.py:9566` and `main.py:9713` - typed handback and guarded common-tail save.
15. `updates/update_character_info.py:1075` and `:1117` - shared preparation and guarded canonical commit used by the current level-up candidate.

## Invariants

- See #193 Part 1 for B1/B2, AP-1 through AP-7, leanness, evidence, and lineage.
- See #193 Part 2 pages 7 through 13 for combat receipts, progression data, lifecycle survival, UI input ownership, providers, schemas, and real acceptance.
- See #193 Part 5 for Always Live, Single Path, and No-Limits rulings.
- This document describes the pinned implementation. If it conflicts with current #193, #193 controls.

## Open items

- #323: postapproval implementation is local, not shipped. Focused component checks pass; historical h/M evidence describes the superseded question flow and is not replacement acceptance. Complete saved level-up, browser, noncaster, multiclass and NPC acceptance remain pending.
- C3 observed real completion and feature/resource preservation, but repeated confirmation, false preservation objections and stale dependent mechanics failed acceptance overall. C4 Task1 proves earlier-proposal timing and unchanged state before consent, but still repeats confirmation and false preservation objections. The contract-aware review amendment is implemented, not yet proven effective; see [C4 staged plan](../superpowers/plans/2026-09-09-323-c4-stage-evidence-amendment.md). Shared arithmetic remains #301.
- #330: entry-contract tweak implemented, real acceptance pending; broader pre-entry choice transfer and compound execution remain separate.
- #152: broader transaction ownership remains separate; #323 adds no coordinator.
- #324: inherited non-level-up retry limits and writer/validator context caps.
- #76: web command input remains active while an approved level-up update runs.
- #253: semantic encounter sources lack stable consumed identity, allowing a second fight and XP award.
- #223: post-combat rebuilt T067 context may carry stale inline HP/XP despite current sheets.
- #203: future terminal input ownership must preserve level-up prompt ordering and EOF behavior.
