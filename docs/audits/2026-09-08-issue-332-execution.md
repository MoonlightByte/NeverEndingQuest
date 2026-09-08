# Issue 332 execution and acceptance

Owner approved execution after eight-seat review and clean confirmation of
plan c41656abfb1f3cacf45baa6740bcc0856160e786a4b8fcd91702d9232004193d.
Authority recorded live in #193 Part 5 D-332-1 on 2026-09-08. This supersedes
the frozen plan's pending-execution status only, not its reviewed mechanics.
Main publication is NOT authorized.

Base: 6916507c74d4bbb4795ad9529a69d33c3ce4efe0, origin/main ancestry verified.
Worktree /home/loup/neq-worktrees/332-plot-validator-plan.

## C0/C1

Live #193 Part 1 and relevant Part 2 p8-p13 reread; D-332-1 appended to current
live issue without replacing unrelated rulings. Gameplay guidelines read from
/mnt/c/dungeon_master_v1/docs/testing/GAMEPLAY_GUIDELINES_FOR_AGENT_PLAYERS.md.
Frozen plan and complete review read before implementation.
One additive main.py evidence block implemented; no other production file.
No existing prompt/validator/writer/schema/transport branch changed.
Focused gates, simplifier and live acceptance pending below; no PASS inferred.

## C2 focused development gates

- WSL and native Windows Python 3.12 py_compile PASSED.
- 15 pure JSON/I/O/assembly cases passed on both runtimes using local
  local-data/332-primitives.py. No game/provider imports or fabricated narration.
- Removing the additive block restores every original main.py byte, including
  line endings; 39 ASCII lines added, no existing bytes changed.
- Pyflakes has zero undefined names and identical baseline warning multiset.
  Initial comparison failed only because a pre-existing redefinition warning's
  embedded source-line reference shifted by 39; the local comparator now
  normalizes that reference. No product change was made to satisfy that check.
- Independent 332_impl_simplifier PASSED, no slimming recommended. Raw candidate
  No-Limits/Single-Path scans empty; all eight whole-file hits inherited nonpayload
  excerpts/comparison keys. No lock, numeric bound or provider call added.
- Source export/prompt equality: 288 present runtime/prompt/schema files compared
  to the worktree, zero mismatches; game prompt directory refreshed and compared.

Native source /mnt/c/332-native-src-D3ahWA; game /mnt/c/332-game-wS56ph.
Evidence /mnt/c/agent-room-fleet-kit/local-data/332-acceptance-7Tjnl2.
main.py SHA256 86fd53291c4904bcdb0389269f9385b4ef2a8da65c4c26c7ac9a5f8749fa509d.
Source+game copies occupy about 47 MB, excluding old debug/backups/saved-games.
Original #322 game untouched. Its original four captured calls are copied into
original-524-527.json; baseline.json records source/prompt identities.
The copied game is the real successful #322 saved-state Load/relaunch at A05,
11:51, before the post-Save greeting. No canonical game values were edited.

The existing native 311-native-relay.py runs run_headless.py serve and forwards
manual commands only (no observer/control modes enabled). It captures complete
NDJSON and provider artifacts. Boot is running; gameplay verdicts pending.
