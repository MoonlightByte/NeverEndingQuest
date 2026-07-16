/**
 * useUiMode (plan Task 4.5) -- the 5-mode UI state machine, derived as a pure
 * function of the Zustand stores (single source of truth: the stores; this
 * hook is the single place that turns them into a UI mode).
 *
 * Modes:
 *   DISCONNECTED -- default; socket down OR connected but no game started yet
 *                   (inputs off, Start available while connected)
 *   STARTING     -- start_game emitted; startup_status in_progress locks all;
 *                   startup_status failed surfaces recovery messaging
 *   PLAY         -- game_started | game_resumed received
 *   COMBAT       -- initiative present (world.initiative.active) <-> cleared
 *   MODAL        -- orthogonal overlay flag (dialogs store), NOT a mode of its
 *                   own: it layers over whichever mode is active.
 */
import { useDialogs, useSession, useWorld } from '../stores'
import type { StartupStatus, UiMode } from '../stores'

export interface UiModeInputs {
  /** Socket transport connected (session.connected). */
  connected: boolean
  /** Session lifecycle mode written by the socket service (session.mode). */
  sessionMode: UiMode
  /** startup_status lifecycle (session.startupStatus). */
  startupStatus: StartupStatus
  /** status_update.is_processing (session.isProcessing). */
  isProcessing: boolean
  /** initiative_data_response.active (world.initiative.active). */
  combatActive: boolean
  /** A dialog is open (dialogs.open !== null). */
  modalOpen: boolean
}

export interface UiModeSnapshot {
  /** The active coarse mode. */
  mode: UiMode
  /** MODAL overlay flag -- orthogonal to mode. */
  modalOpen: boolean
  /** True whenever the player input must be locked. */
  inputLocked: boolean
  /** startup_status reported failed -- show recovery messaging. */
  startupFailed: boolean
}

/**
 * Pure transition table. Precedence (first match wins):
 *   1. !connected            -> disconnected
 *   2. never started         -> disconnected (connected, pre-Start)
 *   3. starting              -> starting (in_progress/failed both stay here;
 *                               failed exposes startupFailed for recovery UI)
 *   4. combat active         -> combat
 *   5. otherwise             -> play
 */
export function deriveUiMode(inputs: UiModeInputs): UiModeSnapshot {
  const { connected, sessionMode, startupStatus, isProcessing, combatActive, modalOpen } = inputs

  let mode: UiMode
  if (!connected) {
    mode = 'disconnected'
  } else if (sessionMode === 'disconnected') {
    // Connected but no game started/resumed yet: inputs stay off.
    mode = 'disconnected'
  } else if (sessionMode === 'starting') {
    mode = 'starting'
  } else if (combatActive) {
    mode = 'combat'
  } else {
    mode = 'play'
  }

  const startupFailed = mode === 'starting' && startupStatus === 'failed'
  const inputLocked = mode === 'disconnected' || mode === 'starting' || isProcessing

  return { mode, modalOpen, inputLocked, startupFailed }
}

/** React hook: subscribes to session + world + dialogs and derives the mode. */
export function useUiMode(): UiModeSnapshot {
  const connected = useSession((s) => s.connected)
  const sessionMode = useSession((s) => s.mode)
  const startupStatus = useSession((s) => s.startupStatus)
  const isProcessing = useSession((s) => s.isProcessing)
  const combatActive = useWorld((s) => s.initiative.active)
  const modalOpen = useDialogs((s) => s.open !== null)

  return deriveUiMode({
    connected,
    sessionMode,
    startupStatus,
    isProcessing,
    combatActive,
    modalOpen,
  })
}
