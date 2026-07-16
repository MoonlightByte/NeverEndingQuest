import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'

/** Which modal is open; null = none. MODAL overlays are orthogonal to UiMode. */
export type DialogName =
  | 'save'
  | 'load'
  | 'reset'
  | 'journal'
  | 'storage'
  | 'settings'
  | 'update'
  | null

export interface CompressionState {
  running: boolean
  totalSections: number
  completed: number
  total: number
  fromCache: boolean
  result: ServerEvents['compression_complete'] | null
}

export interface ActionResult {
  kind: 'restore' | 'reset' | 'exit'
  message: string
}

/** Local-edition operator settings payloads (VITE_EDITION=local). */
export interface ProviderSettings {
  provider: string | null
  localEndpoint: ServerEvents['local_endpoint_changed'] | null
  openaiHasKey: boolean | null
  geminiHasKey: boolean | null
  endpointTest: ServerEvents['local_endpoint_test_result'] | null
}

export interface DialogsState {
  open: DialogName
  /** save_list_response payload for the Load dialog. */
  saveList: Array<Record<string, unknown>> | null
  /** module_list_response payload. */
  moduleList: Array<Record<string, unknown>> | null
  /** restore_complete / reset_complete / exit_acknowledged outcome. */
  actionResult: ActionResult | null
  /** compression_start/progress/complete overlay state. */
  compression: CompressionState
  settings: ProviderSettings

  openDialog: (name: Exclude<DialogName, null>) => void
  closeDialog: () => void
  setSaveList: (list: Array<Record<string, unknown>>) => void
  setModuleList: (list: Array<Record<string, unknown>>) => void
  setActionResult: (result: ActionResult) => void
  compressionStart: (payload: ServerEvents['compression_start']) => void
  compressionProgress: (payload: ServerEvents['compression_progress']) => void
  compressionComplete: (payload: ServerEvents['compression_complete']) => void
  setProvider: (payload: ServerEvents['provider_changed']) => void
  setLocalEndpoint: (payload: ServerEvents['local_endpoint_changed']) => void
  setOpenaiKeyStatus: (payload: ServerEvents['openai_key_status']) => void
  setGeminiKeyStatus: (payload: ServerEvents['gemini_key_status']) => void
  setEndpointTestResult: (payload: ServerEvents['local_endpoint_test_result']) => void
}

const idleCompression: CompressionState = {
  running: false,
  totalSections: 0,
  completed: 0,
  total: 0,
  fromCache: false,
  result: null,
}

export const useDialogs = create<DialogsState>((set) => ({
  open: null,
  saveList: null,
  moduleList: null,
  actionResult: null,
  compression: idleCompression,
  settings: {
    provider: null,
    localEndpoint: null,
    openaiHasKey: null,
    geminiHasKey: null,
    endpointTest: null,
  },

  openDialog: (name) => set({ open: name }),
  closeDialog: () => set({ open: null }),
  setSaveList: (saveList) => set({ saveList }),
  setModuleList: (moduleList) => set({ moduleList }),
  setActionResult: (actionResult) => set({ actionResult }),
  compressionStart: (payload) =>
    set({
      compression: {
        ...idleCompression,
        running: true,
        totalSections: payload.total_sections,
      },
    }),
  compressionProgress: (payload) =>
    set((s) => ({
      compression: {
        ...s.compression,
        running: true,
        completed: payload.completed,
        total: payload.total,
        fromCache: payload.from_cache,
      },
    })),
  compressionComplete: (payload) =>
    set((s) => ({
      compression: { ...s.compression, running: false, result: payload },
    })),
  setProvider: (payload) =>
    set((s) => ({ settings: { ...s.settings, provider: payload.provider } })),
  setLocalEndpoint: (payload) =>
    set((s) => ({ settings: { ...s.settings, localEndpoint: payload } })),
  setOpenaiKeyStatus: (payload) =>
    set((s) => ({ settings: { ...s.settings, openaiHasKey: payload.has_key } })),
  setGeminiKeyStatus: (payload) =>
    set((s) => ({ settings: { ...s.settings, geminiHasKey: payload.has_key } })),
  setEndpointTestResult: (payload) =>
    set((s) => ({ settings: { ...s.settings, endpointTest: payload } })),
}))
