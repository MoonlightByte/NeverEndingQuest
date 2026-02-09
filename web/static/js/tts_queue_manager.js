/**
 * TTS Queue Manager - NeverEndingQuest
 * 
 * Manages sequential TTS playback with queue limiting.
 * Designed as plugin extension for upstream TTS functionality.
 * 
 * TABLETOP MODE: TTS queue management extension
 * Copyright (c) 2024 MoonlightByte
 * Licensed under Fair Source License 1.0
 */

class TTSQueueManager {
    constructor() {
        this.isPlaying = false;
        this.queue = [];
        this.maxQueueSize = 3;
        this.currentAudio = null;
        this.playbackTimeout = null;
        
        console.log('[TTS Queue Manager] Initialized');
    }
    
    /**
     * Request TTS playback - queues if playing, plays immediately if not
     * @param {string} text - Text to speak
     * @param {HTMLElement} button - The TTS button element (for visual state)
     */
    playWhenReady(text, button) {
        // Don't queue duplicates
        const isDuplicate = this.queue.some(item => item.text === text);
        if (isDuplicate) {
            console.log('[TTS Queue Manager] Skipping duplicate message');
            return;
        }
        
        // Check queue limit
        if (this.queue.length >= this.maxQueueSize) {
            console.log('[TTS Queue Manager] Queue full, removing oldest item');
            this.queue.shift(); // Remove oldest
        }
        
        // Add to queue
        this.queue.push({ text, button });
        console.log('[TTS Queue Manager] Queued. Queue size: ' + this.queue.length);
        
        // If not currently playing, start playback
        if (!this.isPlaying) {
            this.playNext();
        } else {
            console.log('[TTS Queue Manager] TTS currently playing, queued for next');
        }
    }
    
    /**
     * Play the next item in queue
     */
    playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            this.currentAudio = null;
            console.log('[TTS Queue Manager] Queue empty, ready for next');
            return;
        }
        
        const item = this.queue.shift();
        this.isPlaying = true;
        
        console.log('[TTS Queue Manager] Playing. Remaining in queue: ' + this.queue.length);
        
        // Call the upstream playTTS function
        if (typeof playTTS === 'function') {
            playTTS(item.text, item.button);
            
            // Set a safety timeout in case audio events don't fire
            this.playbackTimeout = setTimeout(() => {
                console.log('[TTS Queue Manager] Safety timeout - assuming playback complete');
                this.onPlaybackEnded();
            }, 60000); // 60 second max per TTS
        } else {
            console.error('[TTS Queue Manager] playTTS function not found');
            this.isPlaying = false;
            this.playNext(); // Try next item
        }
    }
    
    /**
     * Called when TTS playback ends
     */
    onPlaybackEnded() {
        console.log('[TTS Queue Manager] Playback ended or safety timeout');
        
        // Clear safety timeout if set
        if (this.playbackTimeout) {
            clearTimeout(this.playbackTimeout);
            this.playbackTimeout = null;
        }
        
        this.isPlaying = false;
        this.currentAudio = null;
        
        // Play next in queue if available
        if (this.queue.length > 0) {
            // Small delay between messages for better UX
            setTimeout(() => {
                this.playNext();
            }, 300);
        }
    }
    
    /**
     * Cancel all queued and current playback
     */
    cancelAll() {
        console.log('[TTS Queue Manager] Canceling all TTS');
        this.queue = [];
        this.isPlaying = false;
        
        if (this.playbackTimeout) {
            clearTimeout(this.playbackTimeout);
            this.playbackTimeout = null;
        }
        
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio = null;
        }
        
        // Also stop any playing audio elements
        const audioElements = document.querySelectorAll('audio');
        audioElements.forEach(audio => {
            audio.pause();
            audio.currentTime = 0;
        });
    }
    
    /**
     * Get current queue status
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            queueLength: this.queue.length,
            maxQueueSize: this.maxQueueSize
        };
    }
}

// Create global instance
let ttsQueueManager = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Check if upstream TTS is available before initializing
    if (typeof playTTS === 'function') {
        ttsQueueManager = new TTSQueueManager();
        console.log('[TTS Queue Manager] Ready');
    } else {
        console.warn('[TTS Queue Manager] Upstream playTTS not found, queue manager disabled');
    }
});

/**
 * Wrapper function to integrate with upstream auto-play logic
 * Call this instead of playTTS directly for queue-managed playback
 * 
 * @param {string} text - Text to speak
 * @param {HTMLElement} button - The TTS button element
 */
function playTTSQueued(text, button) {
    if (ttsQueueManager) {
        ttsQueueManager.playWhenReady(text, button);
    } else {
        // Fallback to direct play if queue manager not initialized
        if (typeof playTTS === 'function') {
            playTTS(text, button);
        }
    }
}

/**
 * Hook into upstream playTTS to track playback state
 * This wraps the upstream function to add queue management
 * TABLETOP MODE: Deferred wrapping until playTTS is defined to avoid undefined errors
 */
function wrapPlayTTS() {
    if (typeof window.playTTS !== 'function') {
        // playTTS not yet defined, retry shortly
        setTimeout(wrapPlayTTS, 50);
        return;
    }
    
    // Store original function
    const originalPlayTTS = window.playTTS;
    
    // Replace with wrapper
    window.playTTS = function(text, button) {
        console.log('[TTS Queue Manager] playTTS called, hooking completion events');
        
        // Call original upstream function
        const result = originalPlayTTS(text, button);
        
        // Hook into completion
        if (ttsQueueManager) {
            // Wait a bit for audio element to be created
            setTimeout(() => {
                const audioElements = document.querySelectorAll('audio');
                
                if (audioElements.length === 0) {
                    console.log('[TTS Queue Manager] No audio elements found, using fallback');
                    // Fallback: assume 30 seconds for API-based TTS
                    setTimeout(() => {
                        if (ttsQueueManager) {
                            ttsQueueManager.onPlaybackEnded();
                        }
                    }, 30000);
                    return;
                }
                
                const latestAudio = audioElements[audioElements.length - 1];
                
                // Mark as hooked to avoid duplicate handlers
                if (!latestAudio.dataset.queueHooked) {
                    latestAudio.dataset.queueHooked = 'true';
                    ttsQueueManager.currentAudio = latestAudio;
                    
                    console.log('[TTS Queue Manager] Hooked into audio element');
                    
                    // Hook into ended event
                    latestAudio.addEventListener('ended', function() {
                        console.log('[TTS Queue Manager] Audio ended event fired');
                        if (ttsQueueManager) {
                            ttsQueueManager.onPlaybackEnded();
                        }
                    });
                    
                    // Handle errors
                    latestAudio.addEventListener('error', function(e) {
                        console.error('[TTS Queue Manager] Audio playback error:', e);
                        if (ttsQueueManager) {
                            ttsQueueManager.onPlaybackEnded();
                        }
                    });
                    
                    // Handle pause (user might click stop button)
                    latestAudio.addEventListener('pause', function() {
                        if (latestAudio.currentTime >= latestAudio.duration - 0.1) {
                            // Paused at end = finished
                            console.log('[TTS Queue Manager] Audio paused at end');
                            if (ttsQueueManager) {
                                ttsQueueManager.onPlaybackEnded();
                            }
                        }
                    });
                }
            }, 200);
        }
        
        return result;
    };
    
    console.log('[TTS Queue Manager] Successfully wrapped playTTS');
}

// Start the deferred wrapping process
wrapPlayTTS();

console.log('[TTS Queue Manager] Script loaded');
