import { useEffect, useRef, useState } from 'react'
import { useLog, useSettings } from '../../stores'

const buttonClass =
  'mr-1.5 inline-flex h-[22px] w-[22px] min-w-[22px] cursor-pointer items-center justify-center rounded ' +
  'border-0 bg-[#4a4a4a] p-0 font-chrome text-xs leading-none hover:bg-[#666] disabled:cursor-not-allowed disabled:bg-[#666]'

let activeStop: (() => void) | null = null
let activeOwner: symbol | null = null
const audioCache = new Map<string, string>()

function stopActive(): void {
  const stop = activeStop
  activeStop = null
  activeOwner = null
  stop?.()
}

function finishPlayback(owner: symbol, setIdle: () => void): void {
  if (activeOwner !== owner) return
  activeOwner = null
  activeStop = null
  setIdle()
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
    let detail = 'TTS generation failed'
    try { detail = (await response.json() as { error?: string }).error ?? detail } catch { /* non-JSON */ }
    throw new Error(detail)
  }
  const url = URL.createObjectURL(await response.blob())
  audioCache.set(key, url)
  return url
}

export function TtsButton({ content, autoplay = false }: { content: string; autoplay?: boolean }) {
  const enabled = useSettings((s) => s.ttsEnabled)
  const engine = useSettings((s) => s.engine)
  const voice = useSettings((s) => s.voices[s.engine])
  const [state, setState] = useState<'idle' | 'loading' | 'playing'>('idle')
  const mounted = useRef(true)
  const playGeneration = useRef(0)

  useEffect(() => () => { mounted.current = false }, [])

  const play = async () => {
    if (!enabled) {
      useLog.getState().append({ type: 'system', content: 'Enable "DM Voice" toggle in Settings to use text-to-speech.' })
      return
    }
    if (state === 'playing' || state === 'loading') { stopActive(); return }
    stopActive()
    const owner = Symbol('tts-playback')
    activeOwner = owner
    const generation = ++playGeneration.current
    try {
      if (engine === 'browser') {
        if (!('speechSynthesis' in window)) throw new Error('Your browser does not support text-to-speech.')
        const utterance = new SpeechSynthesisUtterance(content)
        const selected = window.speechSynthesis.getVoices().find((entry) => entry.name === voice)
        if (selected) utterance.voice = selected
        utterance.onend = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        utterance.onerror = utterance.onend
        activeStop = () => { window.speechSynthesis.cancel(); if (mounted.current) setState('idle') }
        setState('playing')
        window.speechSynthesis.speak(utterance)
      } else {
        const controller = new AbortController()
        activeStop = () => {
          controller.abort()
          playGeneration.current += 1
          if (mounted.current) setState('idle')
        }
        setState('loading')
        const url = await createOpenAiAudio(content, voice || 'fable', engine, controller.signal)
        if (!mounted.current || controller.signal.aborted || generation !== playGeneration.current || activeOwner !== owner) return
        const audio = new Audio(url)
        audio.onended = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        audio.onerror = () => finishPlayback(owner, () => { if (mounted.current) setState('idle') })
        activeStop = () => { audio.pause(); audio.currentTime = 0; if (mounted.current) setState('idle') }
        setState('playing')
        await audio.play()
      }
    } catch (error) {
      finishPlayback(owner, () => { if (mounted.current) setState('idle') })
      if (error instanceof DOMException && error.name === 'AbortError') return
      useLog.getState().append({ type: 'error', content: `Voice generation failed: ${error instanceof Error ? error.message : String(error)}` })
    }
  }

  useEffect(() => {
    if (autoplay && enabled) { const timer = window.setTimeout(() => void play(), 100); return () => window.clearTimeout(timer) }
    return undefined
    // Only run once for a newly mounted narration.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return <button type="button" onClick={() => void play()} title={state === 'playing' ? 'Stop playback' : 'Play DM Voice'} className={buttonClass} style={{ backgroundColor: state === 'playing' ? '#e74c3c' : state === 'loading' ? '#ffa500' : autoplay ? '#27ae60' : '#4a4a4a', color: '#ddd' }}>{state === 'loading' ? '...' : state === 'playing' ? '■' : '▶'}</button>
}
