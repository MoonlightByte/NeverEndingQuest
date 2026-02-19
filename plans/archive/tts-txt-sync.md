# TTS Text Sync - Implementation Plan

## Overview

This document describes the implementation of word-by-word text display synchronized with TTS (Text-to-Speech) playback in the NeverEndingQuest web interface. The goal is to enhance the immersive feel of DM narration by having text appear in sync with speech, creating a "live LLM communication" aesthetic.

## Problem Statement

Currently, the system delivers DM narration as complete text blocks to the GUI, then plays TTS separately. This creates a two-step visual-then-audio experience rather than the more immersive simultaneous text-and-speech delivery.

**Current Flow:**
```
LLM generates narration
    → Server receives complete text block
    → Text displayed all at once in chat
    → TTS begins playing (separately)
```

**Desired Flow:**
```
LLM generates narration
    → Server receives complete text block
    → Text appears word-by-word IN SYNC with TTS speech
    → Player sees and hears narration simultaneously
```

## Technical Background

### TTS Engines Available

| Engine | How It Works | Sync Capability |
|--------|--------------|-----------------|
| **Browser TTS** | Web Speech API (`SpeechSynthesis`) | ✅ Precise via `onboundary` events |
| **OpenAI TTS** | Server generates audio, returns blob | ❌ No server-side word timing |

### Browser TTS API Capabilities

The Web Speech API provides `SpeechSynthesisUtterance.onboundary` events that fire at word and sentence boundaries:

```javascript
utterance.onboundary = (event) => {
    console.log(event.name);        // 'word' or 'sentence'
    console.log(event.charIndex);   // Character position in text
    console.log(event.charLength);  // Length of the word/sentence
};
```

This enables **precise character-level sync** - we can reveal exactly which word is being spoken at each moment.

---

## Option 1: Browser TTS Only (Immediate Implementation)

### Scope

Implement word-reveal animation synced precisely to Browser TTS playback only. This provides perfect sync for users who use the Browser TTS engine.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT MESSAGE FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│  Python Server                                                  │
│      ↓ (complete text)                                         │
│  game_output_queue → socket.emit('game_output')               │
│      ↓                                                          │
│  Frontend addMessage() → DOM element created                  │
│      ↓                                                          │
│  playTTSQueued() → TTS playback begins                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    MODIFIED MESSAGE FLOW                         │
├─────────────────────────────────────────────────────────────────┤
│  Python Server                                                  │
│      ↓ (complete text + ttsSync: true)                         │
│  game_output_queue → socket.emit('game_output')               │
│      ↓                                                          │
│  Frontend addMessage() → DOM with .reveal-mode                 │
│      ↓                                                          │
│  playTTSQueued() → playBrowserTTSWithSync()                   │
│      ├── onboundary event fires                                │
│      ├── Update .revealed-text span with charIndex             │
│      └── Cursor blinks at current position                    │
└─────────────────────────────────────────────────────────────────┘
```

### Files to Modify

| File | Changes | Est. Lines |
|------|---------|------------|
| `web/templates/game_interface.html` | CSS + JS handlers | ~120 |
| `web/static/js/tts_queue_manager.js` | Sync mode support | ~30 |
| `model_config.py` | Add config flag | ~5 |

### Implementation Details

#### 1. CSS: Reveal Animation Styles (~30 lines)

**Location:** `game_interface.html` (in `<style>` block)

```css
/* Narration content in reveal mode */
.narration-content.reveal-mode {
    position: relative;
    display: inline;
}

/* The revealed portion (visible) */
.narration-content.reveal-mode .revealed-text {
    color: #e8e8e8;
    transition: color 0.1s ease;
}

/* The unrevealed portion (hidden but space reserved) */
.narration-content.reveal-mode .unrevealed-text {
    color: transparent;
    user-select: none;
}

/* Blinking cursor during TTS playback */
.narration-content.reveal-mode .tts-cursor {
    display: none;
    position: absolute;
    width: 2px;
    height: 1.2em;
    background-color: #4a9eff;
    animation: cursor-blink 0.8s infinite;
}

.narration-content.reveal-mode.speaking .tts-cursor {
    display: inline-block;
}

@keyframes cursor-blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

/* Message container states */
.message-narration.tts-complete .revealed-text,
.message-narration.tts-complete .unrevealed-text {
    color: #e8e8e8 !important;
}

.message-narration.tts-complete .tts-cursor {
    display: none !important;
}
```

#### 2. JavaScript: Modified addMessage() Function (~40 lines)

**Location:** `game_interface.html`, around line 5250

**Changes:**
- Detect if message should use reveal mode (based on engine and config)
- Wrap content in `<span class="revealed-text"></span><span class="unrevealed-text"></span><span class="tts-cursor"></span>` structure
- Store original text in data attribute for TTS sync access

```javascript
// New function to prepare reveal mode content
function prepareRevealModeContent(originalContent) {
    // Escape HTML to prevent XSS
    const escaped = originalContent
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    return `<span class="revealed-text"></span>` +
           `<span class="unrevealed-text" data-full-text="${escaped}">${escaped}</span>` +
           `<span class="tts-cursor"></span>`;
}

// Modified addMessage for narration type
if (message.type === 'narration' && shouldUseRevealMode()) {
    const content = message.content;
    const revealedHtml = prepareRevealModeContent(content);
    contentDiv.innerHTML = revealedHtml;
    messageElement.classList.add('reveal-mode');
    // Store reference for TTS sync
    messageElement.dataset.revealText = content;
}
```

#### 3. JavaScript: playBrowserTTSWithSync() (~50 lines)

**Location:** `game_interface.html`, new function

```javascript
function playBrowserTTSWithSync(text, voiceName, button, messageElement) {
    if (!('speechSynthesis' in window)) {
        playBrowserTTS(text, voiceName, button);  // Fallback
        return;
    }
    
    speechSynthesis.cancel();
    
    const utterance = new SpeechSynthesisUtterance(text);
    const voices = speechSynthesis.getVoices();
    const selectedVoice = voices.find(v => v.name === voiceName);
    if (selectedVoice) {
        utterance.voice = selectedVoice;
    }
    
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    
    // Get the message element for reveal sync
    const revealElement = messageElement || document.querySelector('.reveal-mode:last-child');
    
    currentBrowserUtterance = utterance;
    currentTTSButton = button;
    
    // onboundary event - fires at word/sentence boundaries
    utterance.onboundary = (event) => {
        if (revealElement && event.name === 'word') {
            updateRevealProgress(revealElement, event.charIndex, event.charLength);
        }
    };
    
    utterance.onend = () => {
        if (revealElement) {
            completeReveal(revealElement);
        }
        button.classList.remove('playing-tts');
        button.textContent = '▶';
        button.title = 'Play DM Voice';
        currentBrowserUtterance = null;
        currentTTSButton = null;
    };
    
    utterance.onerror = (event) => {
        console.error('Browser TTS Error:', event);
        if (revealElement) {
            completeReveal(revealElement);
        }
        // ... error handling ...
    };
    
    // Mark as speaking for cursor display
    if (revealElement) {
        revealElement.classList.add('speaking');
    }
    
    button.classList.add('playing-tts');
    button.textContent = '■';
    button.title = 'Stop playback';
    
    speechSynthesis.speak(utterance);
}

// Helper to update revealed text
function updateRevealProgress(element, charIndex, charLength) {
    const revealedSpan = element.querySelector('.revealed-text');
    const unrevealedSpan = element.querySelector('.unrevealed-text');
    const fullText = unrevealedSpan.dataset.fullText || '';
    
    // Decode HTML entities
    const decodedFull = fullText
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>');
    
    const revealedText = decodedFull.substring(0, charIndex + charLength);
    const unrevealedText = decodedFull.substring(charIndex + charLength);
    
    // Re-encode for HTML display
    revealedSpan.innerHTML = revealedText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    
    unrevealedSpan.innerHTML = unrevealedText
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

// Helper to complete reveal
function completeReveal(element) {
    element.classList.remove('speaking');
    element.classList.add('tts-complete');
    
    const messageContainer = element.closest('.message-narration');
    if (messageContainer) {
        messageContainer.classList.add('tts-complete');
    }
}
```

#### 4. TTS Queue Manager Integration (~30 lines)

**Location:** `web/static/js/tts_queue_manager.js`

```javascript
// Modified queueItem for sync mode
class TTSQueueManager {
    // ... existing code ...
    
    async playWhenReady(item) {
        // Check if sync mode is enabled
        const useSyncMode = item.useSyncMode && item.engine === 'browser';
        
        if (useSyncMode) {
            // Wait for any current playback to finish
            while (this.isPlaying) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            this.isPlaying = true;
            
            // Play with sync
            await this.playWithSync(item);
            
            this.isPlaying = false;
            this.processQueue();
        } else {
            // Original behavior
            this.enqueue(item);
        }
    }
    
    async playWithSync(item) {
        // Call the sync version of playBrowserTTS
        const messageElement = item.messageElement;
        await playBrowserTTSWithSync(
            item.text,
            item.voice,
            item.button,
            messageElement
        );
    }
}
```

#### 5. Configuration Flag (~5 lines)

**Location:** `model_config.py`

```python
# TTS Text Sync Configuration
ENABLE_TTS_TEXT_SYNC = False  # Enable word-by-word reveal synced to TTS playback
```

### User Experience

1. **Default Behavior (OFF):** No change - text appears as complete blocks
2. **When Enabled (Browser TTS only):**
   - DM narration arrives as complete block
   - If user clicks TTS button or auto-play triggers:
     - Text is wrapped in reveal-mode HTML structure
     - TTS begins playing
     - Words appear one-by-one as they're spoken
     - Blinking cursor shows current position
     - When TTS completes, full text is visible
   - If user clicks Stop mid-speech:
     - Revealed portion stays visible
     - Unrevealed portion stays hidden
     - Player can continue reading or click TTS again

### Edge Cases Handled

| Scenario | Behavior |
|----------|----------|
| Browser doesn't support onboundary | Fall back to block display |
| Very long narration (>1000 words) | Works - only visible portion rendered |
| User stops TTS mid-speech | Revealed text stays visible |
| User clicks TTS again | Continues from current position |
| Multiple messages in queue | Each syncs independently |
| Page reload during playback | No sync state persists (acceptable) |

### Testing Checklist

- [ ] Enable feature in model_config.py
- [ ] Play narration with Browser TTS - words reveal in sync
- [ ] Stop TTS mid-speech - partial text stays visible
- [ ] Complete TTS - full text visible, cursor hidden
- [ ] Auto-play works with sync
- [ ] Queue manager handles multiple synced messages
- [ ] OpenAI TTS still works (falls back to block display)
- [ ] Mobile browsers - graceful degradation

---

## Option 2: Dual-Engine Support (Future Implementation)

### Scope

Extend sync support to OpenAI TTS engine by estimating word timing based on audio duration. This enables the immersive experience for both TTS engines.

### Technical Challenge

OpenAI TTS returns a complete audio blob - there's no word-level timing data in the response. We must estimate timing.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                 DUAL-ENGINE SYNC ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐     ┌──────────────────────────────┐ │
│  │    Browser TTS       │     │       OpenAI TTS             │ │
│  ├──────────────────────┤     ├──────────────────────────────┤ │
│  │ onboundary events    │     │ duration_ms from response    │ │
│  │ charIndex provides  │     │                              │ │
│  │ exact position      │     │ Estimate:                    │ │
│  │                      │     │ words = text.split()         │ │
│  │ PERFECT SYNC         │     │ time_per_word = duration/    │ │
│  │                      │     │   word_count                 │ │
│  │                      │     │                              │ │
│  │                      │     │ APPROXIMATE SYNC             │ │
│  │                      │     │ (±10-20% accuracy)           │ │
│  └──────────────────────┘     └──────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Details

#### 1. JavaScript: OpenAI TTS Duration Estimation (~60 lines)

**Location:** `game_interface.html`, new function `playOpenAITTSWithSync()`

```javascript
async function playOpenAITTSWithSync(text, selectedVoice, engine, button, messageElement) {
    const model = engine === 'openai-hd' ? 'tts-1-hd' : 'tts-1';
    const cacheKey = `${engine}:${selectedVoice}:${text}`;
    
    if (ttsCache.has(cacheKey)) {
        const cachedUrl = ttsCache.get(cacheKey);
        await playAudioFromUrlWithSync(cachedUrl, button, messageElement, text);
        return;
    }
    
    button.disabled = true;
    button.classList.add('loading-tts');
    button.textContent = '...';
    button.title = 'Generating voice...';
    
    try {
        const response = await fetch('/api/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, voice: selectedVoice, model: model })
        });
        
        if (!response.ok) {
            throw new Error('TTS generation failed');
        }
        
        // Get duration from response headers if available
        const durationHeader = response.headers.get('X-TTS-Duration-MS');
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        
        ttsCache.set(cacheKey, audioUrl);
        
        button.disabled = false;
        button.classList.remove('loading-tts');
        
        // Play with estimated sync
        await playAudioFromUrlWithSync(audioUrl, button, messageElement, text, 
            durationHeader ? parseInt(durationHeader) : null);
        
    } catch (error) {
        // Fallback to non-sync
        playAudioFromUrl(audioUrl, button);
    }
}

async function playAudioFromUrlWithSync(audioUrl, button, messageElement, text, durationMs) {
    const audio = new Audio(audioUrl);
    currentTTSAudio = audio;
    currentTTSButton = button;
    
    const revealElement = messageElement || document.querySelector('.reveal-mode:last-child');
    
    // Estimate timing if duration not provided
    if (!durationMs) {
        // Rough estimate: 150 words per minute = 400ms per word
        const wordCount = text.split(/\s+/).length;
        durationMs = wordCount * 400;
    }
    
    const wordCount = text.split(/\s+/).length;
    const msPerWord = durationMs / wordCount;
    
    let currentWord = 0;
    const words = text.split(/(\s+)/);  // Split but keep delimiters
    
    // Get character positions for each word
    let charPositions = [];
    let charIndex = 0;
    for (const word of words) {
        charPositions.push({ word, start: charIndex, length: word.length });
        charIndex += word.length;
    }
    
    // Start playback
    if (revealElement) {
        revealElement.classList.add('speaking');
    }
    
    button.classList.add('playing-tts');
    button.textContent = '■';
    button.title = 'Stop playback';
    
    audio.play();
    
    // Update reveal at estimated intervals
    const updateInterval = setInterval(() => {
        if (audio.paused || audio.ended) {
            clearInterval(updateInterval);
            if (revealElement) {
                completeReveal(revealElement);
            }
            return;
        }
        
        // Calculate which word should be revealed based on current time
        const currentTimeMs = audio.currentTime * 1000;
        const wordsRevealed = Math.floor(currentTimeMs / msPerWord);
        
        // Calculate character position
        let charIndex = 0;
        for (let i = 0; i < Math.min(wordsRevealed, charPositions.length); i++) {
            charIndex += charPositions[i].length;
        }
        
        if (revealElement && charIndex > 0) {
            // Find the actual character position (accounting for whitespace)
            const actualText = text.substring(0, Math.min(charIndex, text.length));
            const match = actualText.match(/[^\s]/);
            const pos = match ? actualText.lastIndexOf(match[0]) + 1 : charIndex;
            updateRevealProgress(revealElement, pos, 1);
        }
    }, 100);  // Update every 100ms
    
    audio.onended = () => {
        clearInterval(updateInterval);
        if (revealElement) {
            completeReveal(revealElement);
        }
        button.classList.remove('playing-tts');
        button.textContent = '▶';
        button.title = 'Play DM Voice';
        currentTTSAudio = null;
        currentTTSButton = null;
    };
    
    audio.onerror = (e) => {
        clearInterval(updateInterval);
        if (revealElement) {
            completeReveal(revealElement);
        }
        // ... error handling ...
    };
}
```

#### 2. Server-Side: Return Duration Header (~20 lines)

**Location:** `web/web_interface.py`, `/api/tts` endpoint

```python
@app.route('/api/tts', methods=['POST'])
def generate_tts():
    # ... existing TTS generation code ...
    
    # Calculate approximate duration
    word_count = len(text.split())
    # Average 150 WPM = 2.5 words/second
    duration_ms = int((word_count / 2.5) * 1000)
    
    response = make_response(audio_data)
    response.headers['Content-Type'] = 'audio/mpeg'
    response.headers['X-TTS-Duration-MS'] = str(duration_ms)
    response.headers['X-TTS-Word-Count'] = str(word_count)
    
    return response
```

#### 3. Engine Selection Logic (~10 lines)

**Location:** `game_interface.html`, modify playTTS()

```javascript
async function playTTS(text, button) {
    const isTTSEnabled = document.getElementById('tts-toggle').checked;
    if (!isTTSEnabled) {
        addMessage('game-output', { type: 'system', content: 'Enable "DM Voice" toggle in Settings to use text-to-speech.' });
        return;
    }
    
    const selectedEngine = getSelectedTTSEngine();
    const selectedVoice = getSelectedTTSVoice();
    const useTextSync = ENABLE_TTS_TEXT_SYNC;  // Config flag
    
    // Get the message element for this TTS
    const messageElement = button.closest('.message-narration');
    
    if (currentTTSButton === button) {
        stopCurrentTTS();
        return;
    }
    
    stopCurrentTTS();
    
    if (selectedEngine === 'browser') {
        if (useTextSync) {
            playBrowserTTSWithSync(text, selectedVoice, button, messageElement);
        } else {
            playBrowserTTS(text, selectedVoice, button);
        }
    } else {
        if (useTextSync) {
            await playOpenAITTSWithSync(text, selectedVoice, selectedEngine, button, messageElement);
        } else {
            await playOpenAITTS(text, selectedVoice, selectedEngine, button);
        }
    }
}
```

### Accuracy Considerations

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Variable speech rate | ±15% | Use actual audio duration when available |
| Punctuation pauses | Words may reveal early | Minor - punctuation adds natural pauses |
| Long words | Timing variance | Average across many words smooths this |
| Network latency | First word delayed | Pre-buffer, start after short delay |

**Expected accuracy:** ±10-20% - close enough for immersive feel, but not perfect.

### Comparison: Option 1 vs Option 2

| Aspect | Browser TTS Only | Dual-Engine |
|--------|------------------|-------------|
| Implementation complexity | ~150 lines | ~250 lines |
| Sync accuracy | Perfect (API-driven) | Approximate (estimated) |
| Browser support | All modern browsers | All modern browsers |
| OpenAI TTS users | Falls back to block | Gets sync experience |
| Testing effort | Low | Medium |
| Risk | Low | Medium |

---

## Configuration

### User-Facing Settings

Add to Settings panel in `game_interface.html`:

```html
<div class="settings-group">
    <h4>TTS Text Sync</h4>
    <label class="toggle-setting">
        <input type="checkbox" id="tts-text-sync-toggle">
        <span class="toggle-slider"></span>
        <span class="toggle-label">Word-by-word sync with speech</span>
    </label>
    <p class="setting-help">
        Display narration text synced with TTS playback. 
        Requires Browser TTS for perfect sync.
    </p>
</div>
```

### Model Config

```python
# model_config.py
ENABLE_TTS_TEXT_SYNC = False  # Default off - user must enable

# Future: Per-engine setting
# BROWSER_TTS_SYNC_ENABLED = True
# OPENAI_TTS_SYNC_ENABLED = True  # Uses estimation
```

---

## Rollout Plan

### Phase 1: Browser TTS Only (Immediate)
1. Add CSS reveal styles
2. Implement playBrowserTTSWithSync()
3. Modify addMessage() for reveal mode
4. Integrate with queue manager
5. Add config flag
6. Test with Browser TTS

### Phase 2: OpenAI TTS Estimation (Future)
1. Modify /api/tts to return duration header
2. Implement playOpenAITTSWithSync()
3. Add engine selection logic
4. Test with various narration lengths
5. Measure accuracy, tune estimation

### Phase 3: User Testing
1. Enable for volunteer testers
2. Gather feedback on sync quality
3. Adjust timing algorithm if needed
4. Document known limitations

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Browser compatibility issues | Low | Medium | Feature detection, fallback |
| Sync feels "off" to users | Medium | Low | Clear labeling, allow disable |
| Performance on long text | Low | Low | Only render visible portion |
| Queue breaks with sync | Medium | Medium | Thorough integration testing |

---

## Success Metrics

- [ ] Browser TTS sync achieves >95% word accuracy (tested manually)
- [ ] User can enable/disable feature
- [ ] Fallback works when feature disabled
- [ ] No impact on non-TTS users
- [ ] OpenAI TTS sync achieves >80% word accuracy (Phase 2)

---

## Open Questions for Future

1. **Should we show a "live" indicator during sync playback?**
   - Could add a pulsing "LIVE" badge during TTS playback

2. **Should we sync cursor position even when user hasn't clicked TTS?**
   - More complex - requires auto-triggering TTS in background
   - Currently: user must click TTS button to start sync

3. **How to handle multiple paragraphs?**
   - Currently: reveal treats entire text as one stream
   - Could: pause briefly between paragraphs

4. **Should we persist sync preference?**
   - Currently: not persisted across sessions
   - Could: save to localStorage

---

## Appendix: Related Files

| File | Purpose |
|------|---------|
| `web/templates/game_interface.html` | Main UI template, TTS functions |
| `web/static/js/tts_queue_manager.js` | TTS queue management |
| `web/web_interface.py` | Server-side TTS endpoint |
| `model_config.py` | Feature flags |
| `web/extensions/streaming_events.py` | Existing (dormant) streaming foundation |

---

*Document created: 2026-02-15*
*Last updated: 2026-02-15*
