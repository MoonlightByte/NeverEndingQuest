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
  kind: 'chronicle' | 'memory'
  running: boolean
  terminal: boolean
  totalSections: number
  completed: number
  total: number
  fromCache: boolean
  message: string
  result: ServerEvents['compression_complete'] | null
  error: string | null
}

export interface ActionResult {
  kind: 'restore' | 'reset' | 'exit'
  message: string
}

export interface UpdateState {
  running: boolean
  log: string[]
  error: string | null
  complete: string | null
}

export interface ModuleOperationState {
  buildId: string | null
  stage: number
  totalStages: number
  stageName: string
  percentage: number
  message: string
  terminal: boolean
  success: boolean | null
  error: string | null
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
  update: UpdateState
  moduleOperation: ModuleOperationState | null

  openDialog: (name: Exclude<DialogName, null>) => void
  closeDialog: () => void
  setSaveList: (list: Array<Record<string, unknown>>) => void
  setModuleList: (list: Array<Record<string, unknown>>) => void
  setActionResult: (result: ActionResult) => void
  compressionStart: (payload: ServerEvents['compression_start']) => void
  compressionProgress: (payload: ServerEvents['compression_progress']) => void
  compressionComplete: (payload: ServerEvents['compression_complete']) => void
  compressionFailed: (payload: ServerEvents['compression_error']) => void
  memoryUpgradeStart: (payload: ServerEvents['episodic_upgrade_start']) => void
  memoryUpgradeProgress: (payload: ServerEvents['episodic_upgrade_progress']) => void
  memoryUpgradeComplete: (payload: ServerEvents['episodic_upgrade_complete']) => void
  setProvider: (payload: ServerEvents['provider_changed']) => void
  setLocalEndpoint: (payload: ServerEvents['local_endpoint_changed']) => void
  setOpenaiKeyStatus: (payload: ServerEvents['openai_key_status']) => void
  setGeminiKeyStatus: (payload: ServerEvents['gemini_key_status']) => void
  setEndpointTestResult: (payload: ServerEvents['local_endpoint_test_result']) => void
  updateStarted: () => void
  updateLog: (payload: ServerEvents['update_log']) => void
  updateError: (payload: ServerEvents['update_error']) => void
  updateComplete: (payload: ServerEvents['update_complete']) => void
  moduleProgress: (payload: ServerEvents['module_creation_progress']) => void
  applyOperationSnapshot: (payload: NonNullable<ServerEvents['ui_state_snapshot']['operations']>) => void
}

const idleCompression: CompressionState = {
  kind: 'chronicle',
  running: false,
  terminal: false,
  totalSections: 0,
  completed: 0,
  total: 0,
  fromCache: false,
  message: '',
  result: null,
  error: null,
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
  update: { running: false, log: [], error: null, complete: null },
  moduleOperation: null,

  openDialog: (name) => set({ open: name }),
  closeDialog: () => set({ open: null }),
  setSaveList: (saveList) => set({ saveList }),
  setModuleList: (moduleList) => set({ moduleList }),
  setActionResult: (actionResult) => set({ actionResult }),
  compressionStart: (payload) =>
    set({
      compression: {
        ...idleCompression,
        kind: 'chronicle',
        running: true,
        totalSections: payload.total_sections,
      },
    }),
  compressionProgress: (payload) =>
    set((s) => ({
      compression: {
        ...s.compression,
        kind: 'chronicle',
        running: true,
        terminal: false,
        completed: payload.completed,
        total: payload.total,
        fromCache: payload.from_cache,
        message: '',
        result: null,
        error: null,
      },
    })),
  compressionComplete: (payload) =>
    set((s) => ({
      compression: { ...s.compression, kind: 'chronicle', running: false, terminal: true, result: payload },
    })),
  compressionFailed: (payload) =>
    set((s) => ({ compression: { ...s.compression, kind: 'chronicle', running: false, terminal: true, result: null, error: payload.error } })),
  memoryUpgradeStart: (payload) =>
    set({
      compression: {
        ...idleCompression,
        kind: 'memory',
        running: true,
        terminal: false,
        completed: payload.completed,
        total: payload.total,
        message: payload.message,
        result: null,
        error: null,
      },
    }),
  memoryUpgradeProgress: (payload) =>
    set((s) => ({
      compression: {
        ...s.compression,
        kind: 'memory',
        running: true,
        completed: payload.completed,
        total: payload.total,
        message: payload.message,
      },
    })),
  memoryUpgradeComplete: (payload) =>
    set((s) => ({
      compression: {
        ...s.compression,
        kind: 'memory',
        running: false,
        terminal: true,
        completed: payload.completed,
        total: payload.total,
        message: payload.message,
        result: null,
        error: payload.stage === 'error' ? payload.message || 'Companion memory recovery failed' : null,
      },
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
  updateStarted: () => set({ update: { running: true, log: ['Starting update...'], error: null, complete: null } }),
  updateLog: (payload) => set((s) => ({ update: { ...s.update, log: [...s.update.log, payload.message] } })),
  updateError: (payload) => set((s) => ({ update: { ...s.update, running: false, error: payload.error } })),
  updateComplete: (payload) => set((s) => ({ update: { ...s.update, running: false, complete: payload.message } })),
  moduleProgress: (payload) => set((s) => {
    const buildId = payload.build_id
    if (!buildId || !Number.isFinite(payload.stage) || !Number.isFinite(payload.total_stages) || !Number.isFinite(payload.percentage)) return {}
    const status = payload.status?.toLowerCase() ?? ''
    const running = status === 'running'
    const terminal = status === 'published' || status === 'generated' || status === 'failed'
    if (!running && !terminal) return {}
    if (payload.terminal !== terminal) return {}
    if (running && Object.prototype.hasOwnProperty.call(payload, 'success')) return {}
    if (terminal && payload.success !== (status !== 'failed')) return {}
    if (payload.stage < 0 || payload.total_stages <= 0 || payload.stage > payload.total_stages || payload.percentage < 0 || payload.percentage > 100) return {}
    if (running && payload.percentage > 99) return {}
    const current = s.moduleOperation
    if (current?.terminal && current.buildId === buildId) return {}
    if (current && current.buildId !== buildId && (!current.terminal || !running)) return {}
    if (current?.buildId === buildId && payload.stage < current.stage) return {}
    if (current?.buildId === buildId && payload.percentage < current.percentage) return {}
    const success = terminal ? payload.success ?? null : null
    return { moduleOperation: {
      buildId,
      stage: payload.stage,
      totalStages: payload.total_stages,
      stageName: payload.stage_name,
      percentage: payload.percentage,
      message: payload.message,
      terminal,
      success,
      error: payload.error ?? null,
    } }
  }),
  applyOperationSnapshot: (operations) => set((s) => {
    const next: Partial<DialogsState> = {}
    const compression = operations.compression
    if (compression === null) {
      next.compression = idleCompression
    } else if (compression) {
      const event = typeof compression['event'] === 'string' ? compression['event'] : ''
      if (event.startsWith('episodic_upgrade_')) {
        const terminal = event === 'episodic_upgrade_complete'
        const message = String(compression['message'] ?? '')
        next.compression = {
          ...idleCompression,
          kind: 'memory',
          running: !terminal,
          terminal,
          completed: Number(compression['completed'] ?? 0),
          total: Number(compression['total'] ?? 0),
          message,
          error: terminal && compression['stage'] === 'error' ? message || 'Companion memory recovery failed' : null,
        }
      } else if (event === 'compression_error') {
        next.compression = { ...s.compression, kind: 'chronicle', running: false, terminal: true, result: null, error: String(compression['error'] ?? 'Compression failed') }
      } else if (event === 'compression_complete') {
        next.compression = {
          ...s.compression,
          kind: 'chronicle',
          running: false,
          terminal: true,
          result: {
            reduction_percentage: Number(compression['reduction_percentage'] ?? 0),
            original_size: Number(compression['original_size'] ?? 0),
            compressed_size: Number(compression['compressed_size'] ?? 0),
          },
        }
      } else {
        next.compression = {
          ...s.compression,
          kind: 'chronicle',
          running: compression['status'] === 'running',
          terminal: false,
          totalSections: Number(compression['total_sections'] ?? s.compression.totalSections),
          completed: Number(compression['completed'] ?? s.compression.completed),
          total: Number(compression['total'] ?? s.compression.total),
          fromCache: compression['from_cache'] === true,
          message: '',
          result: null,
          error: null,
        }
      }
    }
    const update = operations.update
    if (update === null) next.update = { running: false, log: [], error: null, complete: null }
    else if (update) next.update = { running: update.status === 'running', log: update.log ?? [], error: update.error ?? null, complete: update.complete ?? null }
    if (operations.module === null) next.moduleOperation = null
    return next
  }),
}))
