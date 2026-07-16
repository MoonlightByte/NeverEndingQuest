import { useEffect, useRef, useState } from 'react'
import { useDialogs } from '../../stores'
import { LocalProviderPanel } from './LocalProviderPanel'

/** localStorage keys shared with the legacy interface for setting parity. */
export const SETTING_KEYS = {
  aiImages: 'imageGenerationEnabled',
  dmVoice: 'ttsEnabled',
  autoplay: 'ttsAutoplayEnabled',
  voice: 'ttsVoice_browser',
} as const

function readBoolSetting(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key)
    return value === null ? fallback : value === 'true'
  } catch {
    return fallback
  }
}

function writeSetting(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // localStorage unavailable (private mode etc.) -- setting stays session-only
  }
}

function useBoolSetting(key: string, fallback: boolean): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState(() => readBoolSetting(key, fallback))
  const update = (v: boolean) => {
    setValue(v)
    writeSetting(key, String(v))
  }
  return [value, update]
}

function ToggleRow({
  id,
  label,
  checked,
  onChange,
}: {
  id: string
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <label htmlFor={id} className="text-sm text-primary">
        {label}
      </label>
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 cursor-pointer"
        style={{ accentColor: 'var(--accent)' }}
      />
    </div>
  )
}

function SettingsDropdown() {
  const [aiImages, setAiImages] = useBoolSetting(SETTING_KEYS.aiImages, true)
  const [dmVoice, setDmVoice] = useBoolSetting(SETTING_KEYS.dmVoice, false)
  const [autoplay, setAutoplay] = useBoolSetting(SETTING_KEYS.autoplay, false)
  const [voice, setVoice] = useState(() => {
    try {
      return localStorage.getItem(SETTING_KEYS.voice) ?? ''
    } catch {
      return ''
    }
  })

  // Web Speech voices (loaded async by some browsers via voiceschanged).
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const synth = window.speechSynthesis
    const load = () => setVoices(synth.getVoices())
    load()
    synth.addEventListener('voiceschanged', load)
    return () => synth.removeEventListener('voiceschanged', load)
  }, [])

  const changeVoice = (name: string) => {
    setVoice(name)
    writeSetting(SETTING_KEYS.voice, name)
  }

  return (
    <div
      className="neq-card absolute right-0 top-full z-50 mt-2 max-h-[70vh] w-80 overflow-y-auto p-4 font-chrome"
      role="menu"
      aria-label="Settings"
    >
      <div>
        <div className="font-display text-xs uppercase tracking-wide text-secondary">Features</div>
        <ToggleRow id="setting-ai-images" label="AI Images" checked={aiImages} onChange={setAiImages} />
        <ToggleRow id="setting-dm-voice" label="DM Voice" checked={dmVoice} onChange={setDmVoice} />
      </div>

      {dmVoice && (
        <div className="mt-3 border-t-2 border-card pt-3">
          <div className="font-display text-xs uppercase tracking-wide text-secondary">DM Voice</div>
          <label htmlFor="setting-voice-select" className="mt-2 block text-xs text-secondary">
            Voice
          </label>
          <select
            id="setting-voice-select"
            className="mt-1 w-full rounded border-2 border-card bg-page px-2 py-1 text-sm text-primary outline-none focus:border-accent"
            value={voice}
            onChange={(e) => changeVoice(e.target.value)}
          >
            <option value="">Browser default</option>
            {voices.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name} ({v.lang})
              </option>
            ))}
          </select>
          <ToggleRow
            id="setting-tts-autoplay"
            label="Auto-play"
            checked={autoplay}
            onChange={setAutoplay}
          />
        </div>
      )}

      <LocalProviderPanel />
    </div>
  )
}

/**
 * Gear dropdown (plan 4.4f): AI images toggle, DM voice toggle + voice select,
 * autoplay -- all persisted to localStorage under the legacy keys. Includes the
 * LocalProviderPanel (which renders only outside the hosted edition). Also opens
 * when something else sets the dialogs store to 'settings' (e.g. HeaderBar).
 */
export function SettingsMenu() {
  const [menuOpen, setMenuOpen] = useState(false)
  const dialogOpen = useDialogs((s) => s.open)
  const open = menuOpen || dialogOpen === 'settings'
  const rootRef = useRef<HTMLDivElement>(null)

  const close = () => {
    setMenuOpen(false)
    if (useDialogs.getState().open === 'settings') {
      useDialogs.getState().closeDialog()
    }
  }

  // Close on any click outside the menu.
  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && e.target instanceof Node && !rootRef.current.contains(e.target)) {
        close()
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  return (
    <div ref={rootRef} className="relative inline-block">
      <button
        type="button"
        title="Settings"
        aria-label="Settings"
        aria-expanded={open}
        onClick={() => (open ? close() : setMenuOpen(true))}
        className="flex cursor-pointer items-center gap-1 rounded border-2 border-card bg-panel px-3 py-1 font-chrome text-sm text-primary hover:border-soft"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z" />
        </svg>
        Settings
      </button>
      {open && <SettingsDropdown />}
    </div>
  )
}
