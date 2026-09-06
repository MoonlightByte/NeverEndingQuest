import { useEffect, useRef, useState } from 'react'
import type { CSSProperties, FocusEventHandler, MouseEventHandler } from 'react'
import { createPortal } from 'react-dom'
import { useDialogs, useLog, useSettings } from '../../stores'
import type { MapTheme, TtsEngine } from '../../stores'
import { LocalProviderPanel } from './LocalProviderPanel'
import { StartupRecoveryPanel } from './StartupRecoveryPanel'
import { DialogShell } from '../dialogs/DialogShell'
import { useEmberViewport } from '../layout/useEmberViewport'
import { claimAudio, finishAudio, stopAudio } from '../../services/audioCoordinator'
import { useModalLayer } from '../dialogs/useModalLayer'
import './settings-parity.css'

const OPENAI_VOICES = [
  ['fable', 'Fable (Storyteller)'], ['onyx', 'Onyx (Deep)'], ['nova', 'Nova (Warm)'],
  ['alloy', 'Alloy (Neutral)'], ['echo', 'Echo (Soft)'], ['shimmer', 'Shimmer (Clear)'],
] as const

function AutoplayTip({ position, close }: { position: { left: number; top: number }; close: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useModalLayer(ref, close, { modal: false })
  return createPortal(<div ref={ref} className="neq-autoplay-tooltip visible" style={position} role="tooltip"><div className="neq-autoplay-tooltip-header">Auto-play Voice</div><div className="neq-autoplay-tooltip-content">Automatically plays DM voice when new messages arrive from the Dungeon Master.</div></div>, document.body)
}

function Toggle({ id, label, checked, onChange, onMouseEnter, onMouseLeave, onFocus, onBlur }: { id: string; label: string; checked: boolean; onChange: (value: boolean) => void; onMouseEnter?: MouseEventHandler<HTMLDivElement>; onMouseLeave?: MouseEventHandler<HTMLDivElement>; onFocus?: FocusEventHandler<HTMLDivElement>; onBlur?: FocusEventHandler<HTMLDivElement> }) {
  return <div className="neq-settings-item" onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} onFocus={onFocus} onBlur={onBlur}><span>{label}</span><label className="neq-settings-toggle"><input id={id} aria-label={label} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} /><span /></label></div>
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
  const [autoplayTooltip, setAutoplayTooltip] = useState<{ left: number; top: number } | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  const generation = useRef(0)
  const owner = useRef(Symbol('voice-preview'))
  useEffect(() => () => stopAudio(owner.current), [engine, voice])

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const load = () => setBrowserVoices(window.speechSynthesis.getVoices().filter((entry) => entry.lang.startsWith('en') || entry.lang.startsWith('es')).sort((a, b) => Number(b.localService) - Number(a.localService) || a.name.localeCompare(b.name)))
    load(); window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  const stopPreview = () => {
    generation.current += 1
    requestRef.current?.abort()
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
    if (audioRef.current) {
      audioRef.current.onended = null
      audioRef.current.onerror = null
      audioRef.current.pause()
      audioRef.current = null
    }
    if (audioUrlRef.current) {
      URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
    }
    setPreviewing(false)
  }

  useEffect(() => () => {
    stopAudio(owner.current)
    generation.current += 1
    requestRef.current?.abort()
    if (audioRef.current) {
      audioRef.current.onended = null
      audioRef.current.onerror = null
      audioRef.current.pause()
      audioRef.current = null
    }
    if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
    audioUrlRef.current = null
  }, [])

  const preview = async () => {
    if (previewing) { stopAudio(owner.current); return }
    const spanish = browserVoices.find((entry) => entry.name === voice)?.lang.startsWith('es')
    const text = spanish ? 'Bienvenidos, aventureros. Vuestra travesía comienza en una taberna misteriosa.' : 'Welcome, adventurers. Your journey begins in a mysterious tavern.'
    setPreviewing(true)
    const current = ++generation.current
    const playbackOwner = Symbol('voice-preview-play')
    owner.current = playbackOwner
    claimAudio(playbackOwner, stopPreview)
    const controller = new AbortController()
    requestRef.current = controller
    try {
      if (engine === 'browser') {
        if (!('speechSynthesis' in window)) throw new Error('Browser speech is unavailable.')
        const utterance = new SpeechSynthesisUtterance(text)
        const selected = browserVoices.find((entry) => entry.name === voice)
        if (selected) utterance.voice = selected
        utterance.onend = () => { if (current === generation.current) finishAudio(playbackOwner, () => setPreviewing(false)) }; utterance.onerror = utterance.onend
        window.speechSynthesis.speak(utterance)
      } else {
        const response = await fetch('/api/tts', { signal: controller.signal, method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, voice: voice || 'fable', model: engine === 'openai-hd' ? 'tts-1-hd' : 'tts-1' }) })
        if (!response.ok) throw new Error('TTS preview failed.')
        const blob = await response.blob()
        if (current !== generation.current) return
        const url = URL.createObjectURL(blob)
        audioUrlRef.current = url
        const audio = new Audio(url); audioRef.current = audio
        const finished = () => { if (current !== generation.current) return; URL.revokeObjectURL(url); audioUrlRef.current = null; audioRef.current = null; finishAudio(playbackOwner, () => setPreviewing(false)) }
        audio.onended = finished
        audio.onerror = finished; await audio.play()
      }
    } catch (error) {
      if (current !== generation.current) return
      if (audioRef.current) audioRef.current.pause()
      audioRef.current = null
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = null
      setPreviewing(false)
      finishAudio(playbackOwner, () => undefined)
      useLog.getState().append({ type: 'error', content: error instanceof Error ? error.message : String(error) })
    }
  }

  const options = engine === 'browser' ? browserVoices.map((entry) => [entry.name, `${entry.name} (${entry.lang})`] as const) : OPENAI_VOICES
  return <div className="neq-settings-section neq-settings-voice">
    <div className="neq-settings-title">DM Voice</div>
    <div className="neq-settings-item"><label htmlFor="tts-engine-select">Engine</label><select id="tts-engine-select" value={engine} onChange={(event) => { stopAudio(owner.current); setEngine(event.target.value as TtsEngine) }}><option value="browser">Browser (Free)</option><option value="openai">OpenAI Standard</option><option value="openai-hd">OpenAI HD</option></select></div>
    <div className="neq-settings-item"><label htmlFor="tts-voice-select">Voice</label><div className="neq-voice-controls-parity"><select id="tts-voice-select" value={voice} onChange={(event) => { stopAudio(owner.current); setVoice(engine, event.target.value) }}>{options.length === 0 && <option value="" aria-label="No browser voices available" />}{options.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><button type="button" className={`neq-preview-button neq-preview-button-parity${previewing ? ' playing' : ''}`} onClick={() => void preview()} title={previewing ? 'Stop preview' : 'Preview voice'}>{previewing ? '■' : '▶'}</button></div></div>
    <Toggle
      id="setting-tts-autoplay"
      label="Auto-play"
      checked={autoplay}
      onChange={setAutoplay}
      onMouseEnter={(event) => {
        const rect = event.currentTarget.getBoundingClientRect()
        setAutoplayTooltip({ left: rect.left, top: rect.bottom + 5 })
      }}
      onMouseLeave={() => setAutoplayTooltip(null)}
      onFocus={(event) => { const rect = event.currentTarget.getBoundingClientRect(); setAutoplayTooltip({ left: Math.min(rect.left, window.innerWidth - 292), top: Math.min(rect.bottom + 5, window.innerHeight - 150) }) }}
      onBlur={() => setAutoplayTooltip(null)}
    />
    {autoplayTooltip && <AutoplayTip position={autoplayTooltip} close={() => setAutoplayTooltip(null)} />}
  </div>
}

function SettingsDropdown({ desktop = false }: { desktop?: boolean }) {
  const [section, setSection] = useState('providers')
  const aiImages = useSettings((s) => s.aiImages)
  const setAiImages = useSettings((s) => s.setAiImages)
  const ttsEnabled = useSettings((s) => s.ttsEnabled)
  const setTtsEnabled = useSettings((s) => s.setTtsEnabled)
  const mapTheme = useSettings((s) => s.mapTheme)
  const setMapTheme = useSettings((s) => s.setMapTheme)
  return <div className={`neq-settings-dropdown neq-settings-dropdown-parity${desktop ? ' ember-settings-content' : ''}`} role={desktop ? undefined : 'menu'} aria-label="Settings">
    {desktop && <nav className="ember-settings-nav" aria-label="Settings sections">{[['providers', 'AI providers'], ['voice', 'Voice & images'], ['map', 'Map']].map(([id, label]) => <button key={id} type="button" aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)}>{label}</button>)}</nav>}
    <div className="ember-settings-fields">
    <div hidden={desktop && section !== 'voice'}>
    <div className="neq-settings-section"><div className="neq-settings-title">Features</div><Toggle id="setting-ai-images" label="AI Images" checked={aiImages} onChange={setAiImages} /><Toggle id="setting-dm-voice" label="DM Voice" checked={ttsEnabled} onChange={(value) => { if (!value) stopAudio(); setTtsEnabled(value) }} /></div>
    {ttsEnabled ? <VoiceSettings /> : <div className="neq-settings-collapsed-spacer-parity" aria-hidden="true" />}
    </div>
    <div hidden={desktop && section !== 'map'}>
    <div className="neq-settings-section"><div className="neq-settings-title">Map</div>
      <div className="neq-settings-item"><label htmlFor="map-theme-select">Map style</label><select id="map-theme-select" value={mapTheme} onChange={(event) => setMapTheme((event.target.value as MapTheme) === 'night' ? 'night' : 'day')}><option value="day">Parchment</option><option value="night">Night ink</option></select></div>
    </div>
    </div>
    <div hidden={desktop && section !== 'providers'}>
    <LocalProviderPanel />
    <StartupRecoveryPanel />
    </div>
    </div>
  </div>
}

export function SettingsMenu() {
  const desktop = useEmberViewport()
  const [menuOpen, setMenuOpen] = useState(false)
  const dialogOpen = useDialogs((s) => s.open)
  const open = menuOpen || dialogOpen === 'settings'
  const rootRef = useRef<HTMLDivElement>(null)
  const [mobileTop, setMobileTop] = useState(64)
  const close = () => { setMenuOpen(false); if (useDialogs.getState().open === 'settings') useDialogs.getState().closeDialog() }
  useEffect(() => {
    if (!open || desktop) return
    const position = () => { const bottom = rootRef.current?.getBoundingClientRect().bottom ?? 59; setMobileTop(Math.max(8, Math.min(bottom + 5, window.innerHeight - 200))) }
    position()
    window.addEventListener('resize', position)
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape' && !event.defaultPrevented) { event.preventDefault(); close(); rootRef.current?.querySelector('button')?.focus() } }
    const handler = (event: MouseEvent) => { if (rootRef.current && event.target instanceof Node && !rootRef.current.contains(event.target)) close() }
    document.addEventListener('mousedown', handler)
    document.addEventListener('keydown', key)
    return () => { document.removeEventListener('mousedown', handler); document.removeEventListener('keydown', key); window.removeEventListener('resize', position) }
  }, [open, desktop])
  return <div ref={rootRef} className="neq-settings-root-parity" style={{ '--neq-settings-top': `${mobileTop}px` } as CSSProperties}>
    <button type="button" title="Settings" aria-label="Settings" aria-expanded={open} onClick={() => open ? close() : setMenuOpen(true)} className="neq-settings-button">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z"/></svg>
      Settings
    </button>
    {open && (desktop ? createPortal(<DialogShell title="Settings" onClose={close} maxWidth="960px" className="ember-settings-dialog"><p className="ember-dialog-intro">Your game. Your providers. Your preferences.</p><SettingsDropdown desktop /><div className="ember-settings-footer"><span>Provider and key changes use the Save controls above.</span><button type="button" className="neq-dialog-button-parity secondary" onClick={close}>Done</button></div></DialogShell>, document.body) : <SettingsDropdown />)}
  </div>
}
