## ADDED Requirements

### Requirement: Sentence-Synced Browser Stream TTS
The system SHALL support sentence-level browser TTS synchronization for streamed narration by buffering stream deltas and enqueueing complete sentence fragments for speech.

#### Scenario: Sentence boundary enqueue
- **WHEN** streamed narration buffer reaches a sentence boundary
- **THEN** the frontend enqueues that sentence for browser speech playback in arrival order

#### Scenario: Final fragment flush
- **WHEN** a stream is committed and buffered residual text remains
- **THEN** the frontend flushes the residual fragment to speech queue as final utterance

### Requirement: Supersede-Safe Playback
The system SHALL prevent stale narration from continuing to play after a stream attempt is superseded.

#### Scenario: Superseded stream cancellation
- **WHEN** `narration_stream_superseded` is received
- **THEN** queued unsaid utterances for that stream are cancelled and stale text is not spoken

#### Scenario: Active utterance policy
- **WHEN** a stream is superseded while a sentence is currently speaking
- **THEN** the frontend applies configured cancel policy to stop stale playback before speaking replacement content

### Requirement: Existing TTS Controls Compatibility
The system SHALL preserve current manual/API TTS controls and suppression filters while adding stream TTS behavior.

#### Scenario: skipTTS suppression
- **WHEN** a narration message or stream is marked with `skipTTS`
- **THEN** stream TTS does not enqueue or speak that content

#### Scenario: Manual TTS continuity
- **WHEN** stream sync is enabled
- **THEN** existing manual TTS button behavior remains available and functional
