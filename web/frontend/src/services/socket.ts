/**
 * services/socket.ts -- the ONLY module in src/ allowed to import socket.io-client.
 * It owns the connection to the Flask-SocketIO server (:8357, default /socket.io
 * path, proxied by Vite in dev) and dispatches every player-scope server event
 * into the Zustand stores. Components never touch the socket: they call emitC()
 * for user intents and subscribe to stores for state. No logic here beyond
 * store writes (plan Task 4.2).
 */
import { io, Socket } from 'socket.io-client'
import type { ClientEvents, ServerEvents } from '../contract/events'
import { useSession, useLog, useWorld, usePlayer, useDialogs } from '../stores'
import { cancelPendingRestart, reloadIfRestartPending } from './restart'

// Use Socket.IO's default polling-first negotiation. The local Flask/Werkzeug
// server does not guarantee direct WebSocket support on every supported setup;
// forcing websocket-only leaves the UI permanently disconnected there.
export const socket: Socket = io()

let connectionEpoch = 0
let requestSequence = 0
const latestRequests = new Map<string, string>()

function requestKey(event: string, payload: unknown): string | null {
  if (event === 'request_player_data' && payload && typeof payload === 'object') {
    return `${event}:${String((payload as Record<string, unknown>).dataType ?? '')}`
  }
  if (event.startsWith('request_') || event === 'generate_image') return event
  return null
}

function withRequestIdentity(event: string, payload: unknown): { payload: unknown; requestId?: string } {
  const key = requestKey(event, payload)
  if (!key) return { payload }
  const requestId = `e${connectionEpoch}-${++requestSequence}`
  latestRequests.set(key, requestId)
  return { payload: { ...(payload && typeof payload === 'object' ? payload : {}), request_id: requestId }, requestId }
}

function accepts(resource: string, payload: { request_id?: string }): boolean {
  if (!payload.request_id) return true // backward-compatible old server
  return latestRequests.get(resource) === payload.request_id
}

/** Typed emit: event names and payloads come from the frozen contract. */
export function emitC<K extends keyof ClientEvents>(ev: K, payload: ClientEvents[K]): string | undefined {
  const identified = withRequestIdentity(String(ev), payload)
  if (identified.payload === undefined) {
    socket.emit(ev)
  } else {
    socket.emit(ev, identified.payload)
  }
  return identified.requestId
}

/** Typed on-registration against the frozen contract. */
function on<K extends keyof ServerEvents>(
  ev: K,
  handler: (payload: ServerEvents[K]) => void,
): void {
  socket.on(ev as string, handler as (...args: unknown[]) => void)
}

// ---------- transport-level ----------
socket.on('connect', () => {
  void reloadIfRestartPending()
  connectionEpoch += 1
  latestRequests.clear()
  useSession.getState().setConnected(true)
  // These values can change while a tab is asleep or disconnected. Components
  // remain mounted across reconnects, so their mount effects will not run again.
  // Refresh the volatile server-owned state on every successful connection.
  emitC('request_location_data', undefined)
  emitC('request_party_data', undefined)
  emitC('request_initiative_data', undefined)
  emitC('request_ui_snapshot', undefined)
  for (const dataType of ['stats', 'inventory', 'spells', 'npcs'] as const) emitC('request_player_data', { dataType })
  emitC('request_plot_data', undefined)
  emitC('request_storage_data', undefined)
})
socket.on('disconnect', () => {
  useSession.getState().setConnected(false)
  useLog.getState().append({ type: 'system', content: 'Disconnected from the game server. Reconnecting...', message_id: `disconnect-${connectionEpoch}` })
})

// ---------- session / startup ----------
on('connected', () => useSession.getState().setConnected(true))
on('version_status', (v) => useSession.getState().setVersion(v))
on('status_update', (s) => useSession.getState().setStatus(s))
on('startup_status', (s) => useSession.getState().setStartup(s.status, s.phase, s.startupAttemptId))
on('game_started', (p) => {
  localStorage.setItem('neq_hasPlayed', 'true')
  useSession.getState().gameStarted(p.message)
})
on('game_resumed', (p) => {
  useSession.getState().gameResumed(p.is_processing)
  useLog.getState().append({ type: 'system', content: p.message })
})
on('startup_recovery_response', (p) => useSession.getState().setRecovery(p))
on('ui_state_snapshot', (p) => {
  if (!accepts('request_ui_snapshot', p)) return
  useSession.getState().applySnapshot(p)
  if (p.operations) {
    useDialogs.getState().applyOperationSnapshot(p.operations)
    const module = p.operations.module
    const currentModule = useDialogs.getState().moduleOperation
    // A terminal snapshot heals a client that actually saw this build running,
    // but must not resurrect a completed modal on every fresh page load.
    if (module && (!module.terminal || currentModule?.buildId === module.build_id)) {
      useDialogs.getState().moduleProgress(module)
    }
  }
})

// ---------- game log ----------
on('game_output', (m) => useLog.getState().append(m))
on('cached_messages', (ms) => useLog.getState().replaceAll(ms))
on('debug_output', (m) => useLog.getState().appendDebug(m))
on('system_message', (p) => useLog.getState().append({ type: 'system', content: p.content }))
on('error', (p) => useLog.getState().append({ type: 'error', content: p.message }))
on('token_update', (t) => useLog.getState().setTokens(t))
on('image_generated', (p) => useLog.getState().addImage(p))
on('image_generation_error', (p) => useLog.getState().imageFailed(p))

// ---------- world ----------
on('location_data_response', (p) => {
  if (accepts('request_location_data', p)) useWorld.getState().setLocation(p)
})
on('party_data_response', (p) => {
  if (accepts('request_party_data', p)) useWorld.getState().setParty(p)
})
on('initiative_data_response', (p) => {
  if (!accepts('request_initiative_data', p)) return
  useWorld.getState().setInitiative(p)
})
on('plot_data_response', (p) => {
  if (accepts('request_plot_data', p)) useWorld.getState().setPlot(p)
})
on('storage_data_response', (p) => {
  if (accepts('request_storage_data', p)) useWorld.getState().setStorage(p)
})

// ---------- player / NPC data ----------
on('player_data_response', (p) => {
  if (accepts(`request_player_data:${p.dataType}`, p)) usePlayer.getState().setPlayerData(p)
})
on('npc_details_response', (p) => usePlayer.getState().setNpcDetails(p))
on('npc_inventory_response', (p) => usePlayer.getState().setNpcInventory(p))

// ---------- dialogs / flows ----------
on('save_list_response', (list) => useDialogs.getState().setSaveList(list))
on('module_list_response', (list) => useDialogs.getState().setModuleList(list))
on('restore_complete', (p) =>
  useDialogs.getState().setActionResult({ kind: 'restore', message: p.message }))
on('reset_complete', (p) =>
  useDialogs.getState().setActionResult({ kind: 'reset', message: p.message }))
on('exit_acknowledged', (p) =>
  useDialogs.getState().setActionResult({ kind: 'exit', message: p.message }))
on('compression_start', (p) => useDialogs.getState().compressionStart(p))
on('compression_progress', (p) => useDialogs.getState().compressionProgress(p))
on('compression_complete', (p) => useDialogs.getState().compressionComplete(p))
on('compression_error', (p) => useDialogs.getState().compressionFailed(p))
on('update_log', (p) => useDialogs.getState().updateLog(p))
on('update_error', (p) => { cancelPendingRestart(); useDialogs.getState().updateError(p) })
on('update_complete', (p) => useDialogs.getState().updateComplete(p))
on('module_creation_progress', (p) => useDialogs.getState().moduleProgress(p))

// ---------- local-edition operator settings (VITE_EDITION=local) ----------
on('provider_changed', (p) => useDialogs.getState().setProvider(p))
on('local_endpoint_changed', (p) => useDialogs.getState().setLocalEndpoint(p))
on('openai_key_status', (p) => useDialogs.getState().setOpenaiKeyStatus(p))
on('gemini_key_status', (p) => useDialogs.getState().setGeminiKeyStatus(p))
on('local_endpoint_test_result', (p) => useDialogs.getState().setEndpointTestResult(p))

// Toolkit/operator-scope events (module_creation_progress, generation_progress,
// generation_complete, generation_error, npc_portrait_progress,
// npc_generation_complete, build_started, module_progress, module_complete,
// module_error, unified_generation_progress, unified_generation_complete,
// update_log, update_error, update_complete, bestiary_update_*,
// npc_description_*) are intentionally NOT bound here: the player app does not
// own them (plan scope rules -- the /toolkit page handles them).
