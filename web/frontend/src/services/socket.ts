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

export const socket: Socket = io({ transports: ['websocket'] })

/** Typed emit: event names and payloads come from the frozen contract. */
export function emitC<K extends keyof ClientEvents>(ev: K, payload: ClientEvents[K]): void {
  if (payload === undefined) {
    socket.emit(ev)
  } else {
    socket.emit(ev, payload)
  }
}

/** Typed on-registration against the frozen contract. */
function on<K extends keyof ServerEvents>(
  ev: K,
  handler: (payload: ServerEvents[K]) => void,
): void {
  socket.on(ev as string, handler as (...args: unknown[]) => void)
}

// ---------- transport-level ----------
socket.on('connect', () => useSession.getState().setConnected(true))
socket.on('disconnect', () => useSession.getState().setConnected(false))

// ---------- session / startup ----------
on('connected', () => useSession.getState().setConnected(true))
on('version_status', (v) => useSession.getState().setVersion(v))
on('status_update', (s) => useSession.getState().setStatus(s))
on('startup_status', (s) => useSession.getState().setStartup(s.status, s.phase))
on('game_started', (p) => useSession.getState().gameStarted(p.message))
on('game_resumed', (p) => {
  useSession.getState().gameResumed(p.is_processing)
  useLog.getState().append({ type: 'info', content: p.message })
})
on('startup_recovery_response', (p) => useSession.getState().setRecovery(p))

// ---------- game log ----------
on('game_output', (m) => useLog.getState().append(m))
on('cached_messages', (ms) => useLog.getState().replaceAll(ms))
on('debug_output', (m) => useLog.getState().appendDebug(m))
on('system_message', (p) => useLog.getState().append({ type: 'info', content: p.content }))
on('error', (p) => useLog.getState().append({ type: 'error', content: p.message }))
on('token_update', (t) => useLog.getState().setTokens(t))
on('image_generated', (p) => useLog.getState().addImage(p))
on('image_generation_error', (p) => useLog.getState().append({ type: 'error', content: p.message }))

// ---------- world ----------
on('location_data_response', (p) => useWorld.getState().setLocation(p))
on('party_data_response', (p) => useWorld.getState().setParty(p))
on('initiative_data_response', (p) => {
  useWorld.getState().setInitiative(p)
  useSession.getState().setCombatActive(p.active)
})
on('plot_data_response', (p) => useWorld.getState().setPlot(p))
on('storage_data_response', (p) => useWorld.getState().setStorage(p))

// ---------- player / NPC data ----------
on('player_data_response', (p) => usePlayer.getState().setPlayerData(p))
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
