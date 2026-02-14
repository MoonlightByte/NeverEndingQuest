## ADDED Requirements

### Requirement: Bounded Stream TTS Queue
The system SHALL keep stream sentence TTS queue growth bounded during active draft playback.

#### Scenario: Rapid delta arrival under active playback
- **WHEN** stream deltas produce sentence fragments faster than playback completion
- **THEN** queued sentence fragments are bounded by configured pending budget and do not grow unbounded

#### Scenario: Superseded attempt clears stale speech
- **WHEN** a stream attempt is superseded
- **THEN** queued stale fragments for that attempt are removed and stale playback is cancelled according to policy

### Requirement: Stream TTS and Existing Controls Compatibility
The system SHALL preserve existing manual/API TTS controls while applying stream queue policy.

#### Scenario: Manual TTS remains functional
- **WHEN** stream sentence sync is enabled
- **THEN** manual TTS control paths continue to operate without regression

#### Scenario: Stream TTS disabled by flag
- **WHEN** `ENABLE_BROWSER_TTS_STREAM_SYNC` is false
- **THEN** stream sentence-level TTS enqueue does not execute
