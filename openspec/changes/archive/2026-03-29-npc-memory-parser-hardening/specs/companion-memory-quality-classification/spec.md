## ADDED Requirements

### Requirement: Companion memory packets are quality-classified before narrator injection
The runtime MUST classify each companion memory packet before narrator injection. The classification model MUST distinguish at least healthy, sparse, degraded-extract, and malformed states so that parser weakness, low-signal history, and true data breakage are not treated as the same condition.

#### Scenario: Sparse valid packet is not treated as malformed
- **WHEN** a companion memory packet has valid structure but contains no crystallized memories and no strong emotional state
- **THEN** the runtime MUST classify that packet as a valid low-signal state such as sparse or degraded-extract rather than automatically marking it malformed

#### Scenario: Truly malformed packet is rejected
- **WHEN** a companion memory packet is missing required fields, has unreadable value shapes, or cannot be interpreted safely by the runtime
- **THEN** the runtime MUST classify that packet as malformed and MUST NOT inject it into narrator context as if it were valid memory state

### Requirement: Corruption warnings represent true data breakage, not ordinary extraction misses
The runtime MUST only emit corruption-style exclusion warnings for truly malformed companion memory packets. Packets that are structurally valid but low-signal or extraction-degraded MUST use a softer degraded-state classification path.

#### Scenario: Degraded extraction logs softer warning
- **WHEN** a companion NPC has evidence of meaningful interaction accounting but lacks expected crystallized output
- **THEN** the runtime MUST classify the packet as degraded-extract and SHOULD log a degraded extraction warning instead of a corruption warning

#### Scenario: Healthy packet remains unchanged
- **WHEN** a companion memory packet contains valid structure and usable memory or emotional-state data
- **THEN** the runtime MUST classify it as healthy and inject it through the normal companion-memory path without degraded-state handling
