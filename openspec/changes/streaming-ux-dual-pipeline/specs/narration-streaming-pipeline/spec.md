## ADDED Requirements

### Requirement: Web Narration Stream Transport
The system SHALL support web-only incremental narration streaming for narrative and combat generation paths by emitting start, delta, end, and error events with deterministic stream identifiers.

#### Scenario: Start stream for narrative generation
- **WHEN** a web turn begins narration generation with streaming enabled
- **THEN** the backend emits `narration_stream_start` containing `streamId`, `turnId`, `mode`, and `attempt` before any deltas

#### Scenario: Emit ordered deltas
- **WHEN** narration tokens are produced by the provider stream
- **THEN** the backend emits `narration_stream_delta` events with strictly increasing `seq` per `streamId`

#### Scenario: Complete stream with assembled text
- **WHEN** provider streaming completes successfully
- **THEN** the backend emits `narration_stream_end` with server-assembled `fullText` for that attempt

#### Scenario: Stream capability unavailable
- **WHEN** streaming is unsupported or fails to initialize for a turn
- **THEN** the system falls back to current non-stream batch generation path for that turn

### Requirement: Backward-Compatible Web Transport
The system SHALL preserve the existing `game_output` and `status_update` behavior as compatibility channels while introducing streaming events.

#### Scenario: Streaming disabled by flag
- **WHEN** `ENABLE_CHAT_STREAMING` is false
- **THEN** the system emits narration via existing `game_output` flow only

#### Scenario: Status lock remains authoritative
- **WHEN** stream events are active
- **THEN** input lock and unlock state continues to be controlled through existing `status_update` semantics

### Requirement: SP MP Runtime Invariance
Streaming transport SHALL NOT alter single-player or multi-player runtime mechanics, including initiative gates and combat command semantics.

#### Scenario: Multi-PC combat command flow
- **WHEN** streaming is enabled during multi-PC combat
- **THEN** existing combat commands and phase transitions continue to function with unchanged semantics
