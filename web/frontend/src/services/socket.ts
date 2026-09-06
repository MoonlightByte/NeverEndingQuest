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
import { CLIENT_EVENT_ARITY } from '../contract/events'
import { useSession, useLog, useWorld, usePlayer, useDialogs } from '../stores'
import { shouldAcceptSnapshot } from '../stores/session'
import {
  HydrationCoordinator,
  isHydrationEvent,
  type HydrationEvent,
  type HydrationPayload,
} from './hydration'
import { cancelPendingRestart, reloadIfRestartPending } from './restart'

// Use Socket.IO's default polling-first negotiation. The local Flask/Werkzeug
// server does not guarantee direct WebSocket support on every supported setup;
// forcing websocket-only leaves the UI permanently disconnected there.
export const socket: Socket = io()

let requestSequence = 0
const baseDocumentTitle = document.title
let readyTitleMarked = false

function clearReadyTitle(): void {
  if (!readyTitleMarked) return
  document.title = baseDocumentTitle
  readyTitleMarked = false
}

function applyProcessingTransition(nextProcessing: boolean, apply: () => void): void {
  const wasProcessing = useSession.getState().isProcessing
  apply()
  if (wasProcessing && !nextProcessing && document.hidden) {
    document.title = `Adventure ready — ${baseDocumentTitle}`
    readyTitleMarked = true
  }
}

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) clearReadyTitle()
})
window.addEventListener('focus', clearReadyTitle)

const hydration = new HydrationCoordinator((event, payload, arity) => {
  // socket.io-client queues emits made while disconnected and replays every
  // one on reconnect. Periodic hydration must never enter that send buffer;
  // the connect handler performs one authoritative refresh instead.
  if (!socket.connected) return
  if (arity === 0) socket.emit(event)
  else socket.emit(event, payload ?? {})
})

function requestKey(event: string): string | null {
  if (event === 'generate_image') return event
  return null
}

function withRequestIdentity(event: string, payload: unknown): { payload: unknown; requestId?: string } {
  const key = requestKey(event)
  if (!key) return { payload }
  const requestId = `e${hydration.currentEpoch()}-${++requestSequence}`
  return { payload: { ...(payload && typeof payload === 'object' ? payload : {}), request_id: requestId }, requestId }
}

/** Typed emit: event names and payloads come from the frozen contract. */
export function emitC<K extends keyof ClientEvents>(ev: K, payload: ClientEvents[K]): string | undefined {
  if (isHydrationEvent(String(ev))) {
    return hydration.request(ev as HydrationEvent, payload as HydrationPayload)
  }
  const identified = withRequestIdentity(String(ev), payload)
  if (CLIENT_EVENT_ARITY[ev] === 0) {
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

function refreshAuthoritativeState(): void {
  emitC('request_location_data', undefined)
  emitC('request_party_data', undefined)
  emitC('request_initiative_data', undefined)
  emitC('request_ui_snapshot', undefined)
  for (const dataType of ['stats', 'inventory', 'spells', 'npcs'] as const) {
    emitC('request_player_data', { dataType })
  }
  emitC('request_plot_data', undefined)
  emitC('request_storage_data', undefined)
  // Payload-only refresh: MapTab (Task 7) additionally polls while active, but
  // keeping this here means the map is never more than one connection-refresh
  // stale even before the tab has mounted, and a redundant response is cheap
  // (store write, no render for an unmounted tab).
  emitC('request_map_data', undefined)
}

// ---------- transport-level ----------
socket.on('connect', () => {
  void reloadIfRestartPending()
  const connectionEpoch = hydration.beginConnection()
  useSession.getState().beginConnection()
  useWorld.getState().beginConnection(connectionEpoch)
  usePlayer.getState().beginConnection(connectionEpoch)
  useSession.getState().setConnected(true)
  // These values can change while a tab is asleep or disconnected. Components
  // remain mounted across reconnects, so their mount effects will not run again.
  // Refresh the volatile server-owned state on every successful connection.
  refreshAuthoritativeState()
})
socket.on('disconnect', () => {
  useSession.getState().setConnected(false)
  // #214 F10: a welcome clear emitted while disconnected is lost; drop the
  // placeholder now - a still-active welcome's next heartbeat restores it.
  useSession.getState().setWelcome('')
  useLog.getState().append({ type: 'system', content: 'Disconnected from the game server. Reconnecting...', message_id: `disconnect-${hydration.currentEpoch()}` })
})

// ---------- session / startup ----------
on('connected', (payload) => {
  hydration.advertise(payload.capabilities, payload.server_instance_id)
  useWorld.getState().bindServerInstance(hydration.currentEpoch(), payload.server_instance_id)
  usePlayer.getState().bindServerInstance(hydration.currentEpoch(), payload.server_instance_id)
  useSession.getState().setConnected(true)
})
on('version_status', (v) => useSession.getState().setVersion(v))
on('status_update', (s) => {
  const wasProcessing = useSession.getState().isProcessing
  applyProcessingTransition(s.is_processing, () => useSession.getState().setStatus(s))
  if (wasProcessing && !s.is_processing) refreshAuthoritativeState()
})
on('startup_status', (s) => {
  useSession.getState().setStartup(s.status, s.phase, s.startupAttemptId)
  if (s.status === 'ready') refreshAuthoritativeState()
})
// #214 D-214-4=A: background welcome liveness - presentational only, never
// touches isProcessing, so it can never lock the input.
on('welcome_progress', (p) => useSession.getState().setWelcome((p && p.message) || ''))
on('game_started', (p) => {
  localStorage.setItem('neq_hasPlayed', 'true')
  useSession.getState().gameStarted(p.message)
  refreshAuthoritativeState()
})
on('game_resumed', (p) => {
  applyProcessingTransition(p.is_processing, () => useSession.getState().gameResumed(p.is_processing))
  useLog.getState().append({ type: 'system', content: p.message })
  refreshAuthoritativeState()
})
on('startup_recovery_response', (p) => useSession.getState().setRecovery(p))
on('ui_state_snapshot', (p) => {
  if (!hydration.accept('request_ui_snapshot', p)) return
  const session = useSession.getState()
  // A snapshot is one atomic revision. If its session portion is stale or
  // belongs to another server instance, its operation portion must not be
  // allowed to roll a terminal dialog back to an older running state.
  if (!shouldAcceptSnapshot(session, p)) return
  applyProcessingTransition(
    p.is_processing,
    () => session.applySnapshot(p),
  )
  if (p.operations) {
    if (p.operations.restore?.can_resume === false || p.operations.restore?.restart_required === false) cancelPendingRestart()
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
  if (hydration.accept('request_location_data', p)) useWorld.getState().setLocation(p)
})
on('party_data_response', (p) => {
  if (hydration.accept('request_party_data', p)) useWorld.getState().setParty(p)
})
on('initiative_data_response', (p) => {
  if (!hydration.accept('request_initiative_data', p)) return
  useWorld.getState().setInitiative(p)
})
on('plot_data_response', (p) => {
  if (hydration.accept('request_plot_data', p)) useWorld.getState().setPlot(p)
})
on('storage_data_response', (p) => {
  if (hydration.accept('request_storage_data', p)) useWorld.getState().setStorage(p)
})
on('map_data_response', (p) => {
  if (hydration.accept('request_map_data', p)) useWorld.getState().setMapData(p)
})

// ---------- player / NPC data ----------
on('player_data_response', (p) => {
  if (hydration.accept('request_player_data', p)) usePlayer.getState().setPlayerData(p)
})
on('npc_details_response', (p) => usePlayer.getState().setNpcDetails(p))
on('npc_inventory_response', (p) => usePlayer.getState().setNpcInventory(p))

// ---------- dialogs / flows ----------
on('save_list_response', (list) => useDialogs.getState().setSaveList(list))
on('module_list_response', (list) => useDialogs.getState().setModuleList(list))
on('restore_complete', (p) => {
  if (p.can_resume === false || p.restart_required === false) cancelPendingRestart()
  useSession.getState().setRestoreResult(p)
  useDialogs.getState().setActionResult({ kind: 'restore', ...p })
  useLog.getState().append({ type: 'system', content: p.message })
})
on('reset_complete', (p) => {
  useDialogs.getState().setActionResult({ kind: 'reset', message: p.message })
  useLog.getState().append({ type: 'system', content: 'Campaign has been reset. The page will now reload.' })
})
on('exit_acknowledged', () => {
  // The legacy overlay owns fixed player-facing copy. Do not let the server's
  // transport acknowledgment ("Exit acknowledged") replace that sentence.
  const current = useDialogs.getState().actionResult
  if (current?.kind !== 'exit') {
    useDialogs.getState().setActionResult({ kind: 'exit', message: 'You can now safely close this browser tab.' })
  }
})
on('compression_start', (p) => useDialogs.getState().compressionStart(p))
on('compression_progress', (p) => useDialogs.getState().compressionProgress(p))
on('compression_complete', (p) => useDialogs.getState().compressionComplete(p))
on('compression_error', (p) => useDialogs.getState().compressionFailed(p))
on('episodic_upgrade_start', (p) => useDialogs.getState().memoryUpgradeStart(p))
on('episodic_upgrade_progress', (p) => useDialogs.getState().memoryUpgradeProgress(p))
on('episodic_upgrade_complete', (p) => useDialogs.getState().memoryUpgradeComplete(p))
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
