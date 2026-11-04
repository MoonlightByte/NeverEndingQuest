import { useEffect, useRef, useState } from 'react'
import { useLog, useSettings } from '../../stores'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'
import { claimAudio, finishAudio as finishPlayback, ownsAudio, stopAudio as stopActive } from '../../services/audioCoordinator'

const buttonClass =
  'mr-1.5 inline-flex h-[22px] w-[22px] min-w-[22px] cursor-pointer items-center justify-center rounded ' +
  'border-0 bg-[#4a4a4a] p-0 font-chrome text-xs leading-none hover:bg-[#666] disabled:cursor-not-allowed disabled:bg-[#666]'

const VOICE_LOST = "I've lost my voice for now, so I'll carry on in text. You can choose another voice in Settings."

// #1786: the server's word that the online voice failed; the provider's own text stays in the server log.
class SpeechUnavailable extends Error {
  permanent: boolean
  constructor(permanent: boolean) {
    super('Speech unavailable')
    this.permanent = permanent
  }
}

// Told once, however many narrations fail; a refusal that will stay also rests autoplay.
function tellVoiceLost(permanent: boolean): void {
  const settings = useSettings.getState()
  if (permanent) settings.setVoiceLost(true)
  if (settings.voiceNoticed) return
  settings.setVoiceNoticed(true)
  useLog.getState().append({ type: 'system', content: VOICE_LOST })
}

const audioCache = new Map<string, string>()
export function resetNarrationAudio() {
  stopActive()
  for (const url of audioCache.values()) URL.revokeObjectURL(url)
  audioCache.clear()
}

async function createOpenAiAudio(text: string, voice: string, engine: 'openai' | 'openai-hd', signal: AbortSignal): Promise<string> {
  const key = `${engine}:${voice}:${text}`
  const cached = audioCache.get(key)
  if (cached) return cached
  const response = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, model: engine === 'openai-hd' ? 'tts-1-hd' : 'tts-1' }),
    signal,
  })
  if (!response.ok) {
    let failure: { error?: string; code?: string; permanent?: boolean } = {}
    try { failure = await response.json() as typeof failure } catch { /* non-JSON */ }
    if (failure.code === 'speech_unavailable') throw new SpeechUnavailable(failure.permanent === true)
    throw new Error(failure.error ?? 'TTS generation failed')
  }
  const blob = await response.blob()
  if (signal.aborted) throw new DOMException('Cancelled', 'AbortError')
  const url = URL.createObjectURL(blob)
  if (audioCache.size >= 12) {
    const first = audioCache.keys().next().value
    if (first) { URL.revokeObjectURL(audioCache.get(first)!); audioCache.delete(first) }
  }
  audioCache.set(key, url)
  return url
}

export function TtsButton({ content, autoplay = false }: { content: string; autoplay?: boolean }) {
  const ember = useEmberDesktop()
  const enabled = useSettings((s) => s.ttsEnabled)
  const engine = useSettings((s) => s.engine)
  const voice = useSettings((s) => s.voices[s.engine])
  const voiceLost = useSettings((s) => s.voiceLost)
  const idleTitle = voiceLost ? 'DM Voice unavailable. Press to try again.' : 'Play DM Voice'
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const mounted = useRef(true)
  const playGeneration = useRef(0)
  const ownerRef = useRef(Symbol('narration'))

  // React StrictMode intentionally runs an effect setup/cleanup/setup cycle in
  // development. Reset the flag in setup as well as clearing it in cleanup so
  // asynchronous playback completion can never inherit the simulated cleanup
  // and leave the control stuck in its loading/playing state.
  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false; stopActive(ownerRef.current) }
  }, [])

  // Match the legacy global DM Voice switch: turning the feature off stops
  // whichever narration is active, including paid OpenAI audio (not only the
  // browser speech engine).
  useEffect(() => {
    if (!enabled) stopActive()
  }, [enabled])
  useEffect(() => {
    return () => stopActive(ownerRef.current)
  }, [engine, voice])

  const play = async () => {
    if (!enabled) {
      useLog.getState().append({ type: 'system', content: 'Enable "DM Voice" toggle in Settings to use text-to-speech.' })
      return
    }
    if (state === 'playing' || state === 'loading') { stopActive(); return }
    stopActive()
    const owner = Symbol('narration-play')
    ownerRef.current = owner
    const generation = ++playGeneration.current
    claimAudio(owner, () => { playGeneration.current += 1; if (mounted.current) setState('idle') })
    try {
      if (engine === 'browser') {
        if (!('speechSynthesis' in window)) throw new Error('Your browser does not support text-to-speech.')
        const utterance = new SpeechSynthesisUtterance(content)
        const selected = window.speechSynthesis.getVoices().find((entry) => entry.name === voice)
        if (selected) utterance.voice = selected
        utterance.onend = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        utterance.onerror = utterance.onend
        claimAudio(owner, () => { window.speechSynthesis.cancel(); if (mounted.current) setState('idle') })
        setState('playing')
        window.speechSynthesis.speak(utterance)
      } else {
        const controller = new AbortController()
        claimAudio(owner, () => {
          controller.abort()
          playGeneration.current += 1
          if (mounted.current) setState('idle')
        })
        setState('loading')
        const url = await createOpenAiAudio(content, voice || 'fable', engine, controller.signal)
        if (!mounted.current || controller.signal.aborted || generation !== playGeneration.current || !ownsAudio(owner)) return
        const audio = new Audio(url)
        audio.onended = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        audio.onerror = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        claimAudio(owner, () => { audio.onended = null; audio.onerror = null; audio.pause(); audio.currentTime = 0; if (mounted.current) setState('idle') })
        setState('playing')
        await audio.play()
        useSettings.getState().setVoiceLost(false)
      }
    } catch (error) {
      if (generation !== playGeneration.current || !ownsAudio(owner)) return
      finishPlayback(owner, () => { if (mounted.current) setState('idle') })
      if (error instanceof DOMException && error.name === 'AbortError') return
      if (error instanceof SpeechUnavailable) { tellVoiceLost(error.permanent); return }
      useLog.getState().append({ type: 'error', content: `Voice generation failed: ${error instanceof Error ? error.message : String(error)}` })
    }
  }

  useEffect(() => {
    if (autoplay && enabled && !useSettings.getState().voiceLost) { const timer = window.setTimeout(() => void play(), 100); return () => window.clearTimeout(timer) }
    return undefined
    // Only run once for a newly mounted narration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (ember) return <button type="button" onClick={() => void play()} title={state === 'playing' ? 'Stop playback' : idleTitle} className="ember-message-action"><EmberIcon name="sound" />{state === 'loading' ? 'Loading…' : state === 'playing' ? 'Stop' : 'Listen'}</button>
  return <button type="button" onClick={() => void play()} title={state === 'playing' ? 'Stop playback' : idleTitle} className={buttonClass} style={{ backgroundColor: state === 'playing' ? '#e74c3c' : state === 'loading' ? '#ffa500' : autoplay ? '#27ae60' : '#4a4a4a', color: '#ddd' }}>{state === 'loading' ? '...' : state === 'playing' ? '■' : '▶'}</button>
}
