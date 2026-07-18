import { useEffect, useRef, useState } from 'react'
import { useDialogs, useLog, useSettings } from '../../stores'
import type { TtsEngine } from '../../stores'
import { LocalProviderPanel } from './LocalProviderPanel'

const OPENAI_VOICES = [
  ['fable', 'Fable (Storyteller)'], ['onyx', 'Onyx (Deep)'], ['nova', 'Nova (Warm)'],
  ['alloy', 'Alloy (Neutral)'], ['echo', 'Echo (Soft)'], ['shimmer', 'Shimmer (Clear)'],
] as const

function Toggle({ id, label, checked, onChange }: { id: string; label: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <div className="neq-settings-item"><label htmlFor={id}>{label}</label><label className="neq-settings-toggle"><input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span /></label></div>
}

function VoiceSettings() {
  const engine = useSettings((s) => s.engine)
  const voice = useSettings((s) => s.voices[s.engine])
  const setEngine = useSettings((s) => s.setEngine)
  const setVoice = useSettings((s) => s.setVoice)
  const autoplay = useSettings((s) => s.autoplay)
  const setAutoplay = useSettings((s) => s.setAutoplay)
  const [browserVoices, setBrowserVoices] = useState<SpeechSynthesisVoice[]>([])
  const [previewing, setPreviewing] = useState(false)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const load = () => setBrowserVoices(window.speechSynthesis.getVoices().filter((entry) => entry.lang.startsWith('en') || entry.lang.startsWith('es')).sort((a, b) => Number(b.localService) - Number(a.localService) || a.name.localeCompare(b.name)))
    load(); window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  const stopPreview = () => {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    audioRef.current?.pause(); audioRef.current = null; setPreviewing(false)
  }

  const preview = async () => {
    if (previewing) { stopPreview(); return }
    const spanish = browserVoices.find((entry) => entry.name === voice)?.lang.startsWith('es')
    const text = spanish ? 'Bienvenidos, aventureros. Vuestra travesía comienza en una taberna misteriosa.' : 'Welcome, adventurers. Your journey begins in a mysterious tavern.'
    setPreviewing(true)
    try {
      if (engine === 'browser') {
        if (!('speechSynthesis' in window)) throw new Error('Browser speech is unavailable.')
        const utterance = new SpeechSynthesisUtterance(text)
        const selected = browserVoices.find((entry) => entry.name === voice)
        if (selected) utterance.voice = selected
        utterance.onend = () => setPreviewing(false); utterance.onerror = utterance.onend
        window.speechSynthesis.speak(utterance)
      } else {
        const response = await fetch('/api/tts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, voice: voice || 'fable', model: engine === 'openai-hd' ? 'tts-1-hd' : 'tts-1' }) })
        if (!response.ok) throw new Error('TTS preview failed.')
        const url = URL.createObjectURL(await response.blob())
        const audio = new Audio(url); audioRef.current = audio
        audio.onended = () => { URL.revokeObjectURL(url); audioRef.current = null; setPreviewing(false) }
        audio.onerror = () => { audioRef.current = null; setPreviewing(false) }; await audio.play()
      }
    } catch (error) {
      setPreviewing(false)
      useLog.getState().append({ type: 'error', content: error instanceof Error ? error.message : String(error) })
    }
  }

  const options = engine === 'browser' ? browserVoices.map((entry) => [entry.name, `${entry.name} (${entry.lang})`] as const) : OPENAI_VOICES
  return <div className="neq-settings-section neq-settings-voice">
    <div className="neq-settings-title">DM Voice</div>
    <div className="neq-settings-item"><label htmlFor="tts-engine-select">Engine</label><select id="tts-engine-select" value={engine} onChange={(event) => { stopPreview(); setEngine(event.target.value as TtsEngine) }}><option value="browser">Browser (Free)</option><option value="openai">OpenAI Standard</option><option value="openai-hd">OpenAI HD</option></select></div>
    <div className="neq-settings-item"><label htmlFor="tts-voice-select">Voice</label><div className="flex gap-1"><select id="tts-voice-select" value={voice} onChange={(event) => { stopPreview(); setVoice(engine, event.target.value) }}>{options.length === 0 && <option value="">Default Voice</option>}{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button type="button" className="neq-preview-button" onClick={() => void preview()} title={previewing ? 'Stop preview' : 'Preview voice'}>{previewing ? '■' : '▶'}</button></div></div>
    <Toggle id="setting-tts-autoplay" label="Auto-play" checked={autoplay} onChange={setAutoplay} />
  </div>
}

function SettingsDropdown() {
  const aiImages = useSettings((s) => s.aiImages)
  const setAiImages = useSettings((s) => s.setAiImages)
  const ttsEnabled = useSettings((s) => s.ttsEnabled)
  const setTtsEnabled = useSettings((s) => s.setTtsEnabled)
  return <div className="neq-settings-dropdown" role="menu" aria-label="Settings">
    <div className="neq-settings-section"><div className="neq-settings-title">Features</div><Toggle id="setting-ai-images" label="AI Images" checked={aiImages} onChange={setAiImages} /><Toggle id="setting-dm-voice" label="DM Voice" checked={ttsEnabled} onChange={(value) => { setTtsEnabled(value); if (!value && 'speechSynthesis' in window) window.speechSynthesis.cancel() }} /></div>
    {ttsEnabled && <VoiceSettings />}
    <LocalProviderPanel />
  </div>
}

export function SettingsMenu() {
  const [menuOpen, setMenuOpen] = useState(false)
  const dialogOpen = useDialogs((s) => s.open)
  const open = menuOpen || dialogOpen === 'settings'
  const rootRef = useRef<HTMLDivElement>(null)
  const close = () => { setMenuOpen(false); if (useDialogs.getState().open === 'settings') useDialogs.getState().closeDialog() }
  useEffect(() => {
    if (!open) return
    const handler = (event: MouseEvent) => { if (rootRef.current && event.target instanceof Node && !rootRef.current.contains(event.target)) close() }
    document.addEventListener('mousedown', handler); return () => document.removeEventListener('mousedown', handler)
  }, [open])
  return <div ref={rootRef} className="relative inline-block">
    <button type="button" title="Settings" aria-label="Settings" aria-expanded={open} onClick={() => open ? close() : setMenuOpen(true)} className="neq-settings-button">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7M19.43 12.97c.04-.32.07-.64.07-.97s-.03-.66-.07-1l2.11-1.63a.5.5 0 0 0 .12-.64l-2-3.46a.5.5 0 0 0-.61-.22l-2.49 1a7.3 7.3 0 0 0-1.69-.98l-.37-2.65A.5.5 0 0 0 14 2h-4a.5.5 0 0 0-.5.42l-.37 2.65a7.3 7.3 0 0 0-1.69.98l-2.49-1a.5.5 0 0 0-.61.22l-2 3.46a.5.5 0 0 0 .12.64L4.57 11c-.04.34-.07.67-.07 1s.03.65.07.97l-2.11 1.66a.5.5 0 0 0-.12.64l2 3.46a.5.5 0 0 0 .61.22l2.49-1.01c.52.4 1.06.74 1.69.99l.37 2.65A.5.5 0 0 0 10 22h4a.5.5 0 0 0 .5-.42l.37-2.65c.63-.26 1.17-.59 1.69-.99l2.49 1.01a.5.5 0 0 0 .61-.22l2-3.46a.5.5 0 0 0-.12-.64z"/></svg>
      Settings
    </button>
    {open && <SettingsDropdown />}
  </div>
}
