---
name: read-chat-log
description: Read and interpret NeverEndingQuest chat log with context-based incremental tracking, fading memory OCNote threading, and token-efficient summaries for developer feedback loop
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: debugging
  project: NeverEndingQuest
---

## Trigger Phrases

### Initial Read (First invocation in session)
- `"read chat log"` → Shows summaries of last 20 entries + OCNote analysis + bookmark
- `"read chat log last N"` → Shows last N entries + analysis + bookmark

### Incremental Read (Bookmark exists in session context)
- `"read chat log"` OR `"update chat log"` → Shows only NEW entries since last bookmark
- `"read more"` → New entries + NEW OCNote analysis
- `"read next"` → New entries + NEW OCNote analysis  
- `"show chat updates"` → New entries + NEW OCNote analysis
- `"read chat"` → Incremental if bookmark exists, else last 20

## Output Format

### Initial Read Example:
```
## Narrative Summary
[3 sentences max - story flow only, no duplication]

## Combat Interactions  
[2 sentences max - mechanics summary or "No combat"]

## OCNote Analysis

### Ongoing Summary
[Persistent synthesis of all OCNote themes observed this session - 4 sentences max]

### Latest OCNotes (Last 5 detailed)
**OCNote 1 [Line 65] [Character]**
**Your Observation:** "..."
**My Analysis:** [2 sentences max]

[Repeat for up to 5 most recent OCNotes]

=====LAST LOG [2026-02-03T18:53:18]=====
Analyzed entries 55-75 of 75 total
```

### Incremental Read Example:
```
## New Entries Summary
[3 sentences max - what happened since last read]

## OCNote Analysis

### Updated Ongoing Summary
[Accumulated themes from ALL OCNotes this session - 4 sentences max]

### New OCNotes Since Last Read (up to 5)
**OCNote X [Line 89] [Character]**
**Your Observation:** "..."
**My Analysis:** [2 sentences max]

=====LAST LOG [2026-02-05T09:50:18]=====
Entries 76-82 of 82 total (7 new since last read)
```

## How It Works

1. **Locate Log:** `debug/logs/live_chat_monitor.json`

2. **Initial Read:**
   - Read entire file (no truncation - use chunked reading if >1000 lines)
   - Parse last N entries (default 20, or specified count)
   - Generate narrative summary (3 sentences max)
   - Generate combat summary (2 sentences max)
   - Extract ALL [OCNote: ...] entries in the window
   - Create ongoing summary synthesizing themes (4 sentences max)
   - Detail up to 5 most recent OCNotes individually
   - Format bookmark: `=====LAST LOG [timestamp]=====`

3. **Incremental Read:**
   - Search my previous response for bookmark pattern
   - Parse timestamp from `=====LAST LOG [timestamp]=====`
   - Show ONLY entries after that timestamp
   - Retrieve existing ongoing summary from context
   - Analyze NEW OCNotes, update ongoing summary
   - Show up to 5 newest OCNotes individually
   - Update bookmark with new latest timestamp

4. **Context Lost:**
   - If bookmark not found: "⚠️ Previous bookmark not found. Defaulting to last 20 entries. Creating new bookmark."
   - Show last 20 + new bookmark

5. **OCNote "Fading Memory" Threshold:**
   - When total OCNotes > 8: Collapse oldest into ongoing summary
   - Always keep last 5 OCNotes as individual entries
   - Ongoing summary persists and accumulates across incremental reads

## OCNote Handling

**Format:** `[OCNote: ...]` within user_input content

**Treatment:** In-game developer communication TO the AI assistant (not in-character dialogue)

**Response Style:** Analytical + conversational hybrid
- Acknowledge your observation in 1 sentence
- Confirm or refine your diagnosis in 1 sentence
- Suggest action or pose question

**Token Efficiency:**
- Never reproduce raw log entries
- Never duplicate content visible in web GUI
- Brevity over completeness
- Focus on insights, not recounting

## Developer Diary (ONCNotes)

**Location:** `memory-bank/ONCNotes.md`

**Purpose:** Shared development whiteboard - ongoing conversational record of chat log analyses, OCNote patterns, and architectural insights discovered through gameplay testing. This diary facilitates our development discussion and persists insights across sessions.

**What I Write:**
- Chronological entries with timestamps
- Narrative summaries of gameplay sessions
- Combat interaction summaries
- OCNote analysis with architectural insights
- Actionable next steps and hypotheses
- Code recommendations based on observed behavior

**Format:**
```markdown
## Entry XXX - [TIMESTAMP] - [Brief Description]

### Narrative Summary
[Story flow analysis]

### Combat Interactions
[Mechanical summary]

### OCNote Analysis
**OCNote N [Character]:** "Quote"
- **Insight:** What we learned
- **Implication:** Why it matters
- **Action:** What to do next

### Next Steps
- [ ] Action items discovered
```

**Relationship to Other Docs:**
- Complements `AGENTS.md` (formal technical documentation)
- Complements `memory-bank/activeContext.md` (current work focus)
- Complements `memory-bank/progress.md` (achievements and todos)
- **Primary purpose:** Development discussion facilitation between human and AI
- Captures architectural insights and implementation hypotheses
- Becomes reference for future coding decisions

## Key Principles

1. **Token Efficiency First** - Minimal output, maximum insight
2. **No Raw Entry Reproduction** - User sees entries in web GUI
3. **OCNote Fading Memory** - Ongoing summary + latest 5 detailed
4. **Context-Based Bookmarking** - No state files, uses conversation context
5. **Incremental by Default** - Show only new content when bookmark exists
6. **Diary Persistence** - Full analyses written to ONCNotes.md for development reference
7. **Complete File Reading** - Never truncate, read all entries regardless of log size
