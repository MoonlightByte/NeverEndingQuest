/**
 * TtsButton -- per-message Web Speech playback for DM narration (plan 4.4b).
 * Toggles speak/stop for this message's content via window.speechSynthesis.
 * Starting playback cancels any other utterance (one voice at a time), and
 * the cancelled button resets itself through its utterance onend/onerror.
 * Disabled when the browser has no Web Speech API support.
 */
import { useEffect, useRef, useState } from 'react'

const buttonClass =
  'cursor-pointer rounded border border-card bg-page px-1.5 py-0.5 font-chrome text-[11px] ' +
  'hover:border-accent disabled:cursor-not-allowed disabled:opacity-50'

export function TtsButton({ content }: { content: string }) {
  const supported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const [speaking, setSpeaking] = useState(false)
  const speakingRef = useRef(false)

  useEffect(() => {
    speakingRef.current = speaking
  }, [speaking])

  // Stop our own playback when the message unmounts (e.g. log replaced).
  useEffect(() => {
    return () => {
      if (speakingRef.current && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel()
      }
    }
  }, [])

  const toggle = () => {
    if (!supported) return
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    window.speechSynthesis.cancel() // one utterance at a time
    const utterance = new SpeechSynthesisUtterance(content)
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    setSpeaking(true)
    window.speechSynthesis.speak(utterance)
  }

  return (
    <button
      type="button"
      onClick={toggle}
      disabled={!supported}
      title={
        supported
          ? speaking
            ? 'Stop DM voice'
            : 'Play DM voice'
          : 'Text-to-speech is not supported in this browser'
      }
      className={buttonClass}
      style={{ color: speaking ? 'var(--accent)' : 'var(--text-secondary)' }}
    >
      {speaking ? 'Stop' : 'Play'}
    </button>
  )
}
