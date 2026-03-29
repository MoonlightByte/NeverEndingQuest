## ADDED Requirements

### Requirement: Sparse or degraded companion memories receive bounded context fallback
When a companion memory packet is valid but classified as sparse or degraded-extract, the narrator context assembly path MUST provide a bounded continuity fallback instead of excluding the NPC entirely. The fallback MUST preserve continuity without asserting unsupported fine-grained emotional detail.

#### Scenario: Sparse companion remains visible to narrator context
- **WHEN** a companion NPC has a valid sparse memory packet
- **THEN** narrator context assembly MUST include a bounded fallback entry for that NPC rather than dropping the NPC from companion-memory context altogether

#### Scenario: Degraded extraction uses bounded fallback
- **WHEN** a companion NPC has a degraded-extract packet caused by extraction weakness rather than malformed data
- **THEN** narrator context assembly MUST include a bounded degraded-state fallback entry and MUST NOT treat the NPC as absent from continuity

### Requirement: Soft fallback packets remain bounded and compatibility-safe
Soft fallback packets MUST stay compact, MUST preserve backward compatibility with the current prompt injection flow, and MUST avoid prompt bloat. They MUST expose only limited continuity signals such as identity, role, quality marker, and minimal recent continuity notes.

#### Scenario: Fallback packet does not widen prompt scope excessively
- **WHEN** narrator context assembly projects a soft fallback packet for one or more companion NPCs
- **THEN** the packet MUST remain a compact summary and MUST NOT inline large journal excerpts or full raw memory files

#### Scenario: Healthy packets continue to use normal injection path
- **WHEN** a companion NPC has a healthy memory packet
- **THEN** the runtime MUST continue to use the normal companion-memory injection path instead of replacing healthy data with fallback-only context
