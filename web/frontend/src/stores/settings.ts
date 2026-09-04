import { create } from 'zustand'

export type TtsEngine = 'browser' | 'openai' | 'openai-hd'
export type MapTheme = 'day' | 'night'

function read(key: string, fallback: string): string {
  try { return localStorage.getItem(key) ?? fallback } catch { return fallback }
}

function readBool(key: string, fallback: boolean): boolean {
  return read(key, String(fallback)) === 'true'
}

function persist(key: string, value: string | boolean): void {
  try { localStorage.setItem(key, String(value)) } catch { /* session-only */ }
}

export interface SettingsState {
  aiImages: boolean
  ttsEnabled: boolean
  autoplay: boolean
  engine: TtsEngine
  voices: Record<TtsEngine, string>
  mapTheme: MapTheme
  setAiImages: (value: boolean) => void
  setTtsEnabled: (value: boolean) => void
  setAutoplay: (value: boolean) => void
  setEngine: (value: TtsEngine) => void
  setVoice: (engine: TtsEngine, value: string) => void
  setMapTheme: (value: MapTheme) => void
}

export const useSettings = create<SettingsState>((set) => ({
  aiImages: readBool('imageGenerationEnabled', true),
  ttsEnabled: readBool('ttsEnabled', false),
  autoplay: readBool('ttsAutoplayEnabled', false),
  engine: read('ttsEngine', 'browser') as TtsEngine,
  voices: {
    browser: read('ttsVoice_browser', ''),
    openai: read('ttsVoice_openai', 'fable'),
    'openai-hd': read('ttsVoice_openai-hd', 'fable'),
  },
  mapTheme: read('mapTheme', 'day') === 'night' ? 'night' : 'day',
  setAiImages: (aiImages) => { persist('imageGenerationEnabled', aiImages); set({ aiImages }) },
  setTtsEnabled: (ttsEnabled) => { persist('ttsEnabled', ttsEnabled); set({ ttsEnabled }) },
  setAutoplay: (autoplay) => { persist('ttsAutoplayEnabled', autoplay); set({ autoplay }) },
  setEngine: (engine) => { persist('ttsEngine', engine); set({ engine }) },
  setVoice: (engine, voice) => {
    persist(`ttsVoice_${engine}`, voice)
    set((state) => ({ voices: { ...state.voices, [engine]: voice } }))
  },
  setMapTheme: (mapTheme) => { persist('mapTheme', mapTheme); set({ mapTheme }) },
}))
