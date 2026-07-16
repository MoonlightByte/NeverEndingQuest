/**
 * Mode machine tests (plan Task 4.5): exhaustive transition coverage of
 * deriveUiMode, driven the same way the socket service drives the stores.
 * Store-level tests simulate the real event flow (connect -> start_game ->
 * startup_status -> game_started -> initiative -> disconnect -> resume).
 */
import { beforeEach, describe, expect, it } from 'vitest'
import { deriveUiMode } from './useUiMode'
import type { UiModeInputs } from './useUiMode'
import { useDialogs, useSession, useWorld } from '../stores'

// ---------- pure transition table ----------

const base: UiModeInputs = {
  connected: false,
  sessionMode: 'disconnected',
  startupStatus: 'idle',
  isProcessing: false,
  combatActive: false,
  modalOpen: false,
}

describe('deriveUiMode transition table', () => {
  it('default state is disconnected with input locked', () => {
    const snap = deriveUiMode(base)
    expect(snap.mode).toBe('disconnected')
    expect(snap.inputLocked).toBe(true)
    expect(snap.modalOpen).toBe(false)
    expect(snap.startupFailed).toBe(false)
  })

  it('connected but not started stays disconnected (inputs off)', () => {
    const snap = deriveUiMode({ ...base, connected: true })
    expect(snap.mode).toBe('disconnected')
    expect(snap.inputLocked).toBe(true)
  })

  it('disconnected -> starting when start_game is emitted', () => {
    const snap = deriveUiMode({ ...base, connected: true, sessionMode: 'starting' })
    expect(snap.mode).toBe('starting')
    expect(snap.inputLocked).toBe(true)
  })

  it('starting locks all while startup_status is in_progress', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'starting',
      startupStatus: 'in_progress',
    })
    expect(snap.mode).toBe('starting')
    expect(snap.inputLocked).toBe(true)
    expect(snap.startupFailed).toBe(false)
  })

  it('starting + startup_status failed exposes recovery messaging', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'starting',
      startupStatus: 'failed',
    })
    expect(snap.mode).toBe('starting')
    expect(snap.startupFailed).toBe(true)
    expect(snap.inputLocked).toBe(true)
  })

  it('startup failure is only surfaced while in starting mode', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'play',
      startupStatus: 'failed',
    })
    expect(snap.mode).toBe('play')
    expect(snap.startupFailed).toBe(false)
  })

  it('starting -> play on game_started', () => {
    const snap = deriveUiMode({ ...base, connected: true, sessionMode: 'play' })
    expect(snap.mode).toBe('play')
    expect(snap.inputLocked).toBe(false)
  })

  it('play locks input while the server is processing', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'play',
      isProcessing: true,
    })
    expect(snap.mode).toBe('play')
    expect(snap.inputLocked).toBe(true)
  })

  it('play -> combat when initiative is present', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'play',
      combatActive: true,
    })
    expect(snap.mode).toBe('combat')
    expect(snap.inputLocked).toBe(false)
  })

  it('combat -> play when initiative clears', () => {
    const during = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'combat',
      combatActive: true,
    })
    const after = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'combat',
      combatActive: false,
    })
    expect(during.mode).toBe('combat')
    expect(after.mode).toBe('play')
  })

  it('combat honours the processing input lock', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'play',
      combatActive: true,
      isProcessing: true,
    })
    expect(snap.mode).toBe('combat')
    expect(snap.inputLocked).toBe(true)
  })

  it('disconnect wins over every other mode', () => {
    for (const sessionMode of ['disconnected', 'starting', 'play', 'combat'] as const) {
      const snap = deriveUiMode({
        ...base,
        connected: false,
        sessionMode,
        combatActive: true,
        startupStatus: 'in_progress',
      })
      expect(snap.mode).toBe('disconnected')
      expect(snap.inputLocked).toBe(true)
    }
  })

  it('combat during starting does not preempt startup', () => {
    const snap = deriveUiMode({
      ...base,
      connected: true,
      sessionMode: 'starting',
      combatActive: true,
    })
    expect(snap.mode).toBe('starting')
  })

  it('MODAL overlay is orthogonal to every mode', () => {
    const cases: Array<Partial<UiModeInputs>> = [
      { connected: false },
      { connected: true, sessionMode: 'starting' },
      { connected: true, sessionMode: 'play' },
      { connected: true, sessionMode: 'play', combatActive: true },
    ]
    for (const overrides of cases) {
      const closed = deriveUiMode({ ...base, ...overrides, modalOpen: false })
      const open = deriveUiMode({ ...base, ...overrides, modalOpen: true })
      expect(open.mode).toBe(closed.mode)
      expect(open.modalOpen).toBe(true)
      expect(closed.modalOpen).toBe(false)
    }
  })
})

// ---------- store-driven flow (the socket service writes these setters) ----------

const sessionInitial = useSession.getState()
const worldInitial = useWorld.getState()
const dialogsInitial = useDialogs.getState()

function snapshotFromStores() {
  const session = useSession.getState()
  const world = useWorld.getState()
  const dialogs = useDialogs.getState()
  return deriveUiMode({
    connected: session.connected,
    sessionMode: session.mode,
    startupStatus: session.startupStatus,
    isProcessing: session.isProcessing,
    combatActive: world.initiative.active,
    modalOpen: dialogs.open !== null,
  })
}

describe('mode machine driven through the stores', () => {
  beforeEach(() => {
    useSession.setState(sessionInitial, true)
    useWorld.setState(worldInitial, true)
    useDialogs.setState(dialogsInitial, true)
  })

  it('full lifecycle: connect -> start -> startup -> play -> combat -> play', () => {
    expect(snapshotFromStores().mode).toBe('disconnected')

    useSession.getState().setConnected(true)
    expect(snapshotFromStores().mode).toBe('disconnected')

    useSession.getState().startRequested() // start_game emitted
    expect(snapshotFromStores().mode).toBe('starting')

    useSession.getState().setStartup('in_progress', 'Loading module...')
    expect(snapshotFromStores().mode).toBe('starting')
    expect(snapshotFromStores().inputLocked).toBe(true)

    useSession.getState().setStartup('ready', 'Ready')
    useSession.getState().gameStarted('Welcome!') // game_started
    expect(snapshotFromStores().mode).toBe('play')
    expect(snapshotFromStores().inputLocked).toBe(false)

    // initiative_data_response active: the socket service writes BOTH stores.
    useWorld.getState().setInitiative({ active: true, combatants: [{}], round: 2 })
    useSession.getState().setCombatActive(true)
    expect(snapshotFromStores().mode).toBe('combat')

    // initiative cleared
    useWorld.getState().setInitiative({ active: false, combatants: [] })
    useSession.getState().setCombatActive(false)
    expect(snapshotFromStores().mode).toBe('play')
  })

  it('startup failure surfaces recovery, then game_started recovers to play', () => {
    useSession.getState().setConnected(true)
    useSession.getState().startRequested()
    useSession.getState().setStartup('failed', 'character creation')
    const failed = snapshotFromStores()
    expect(failed.mode).toBe('starting')
    expect(failed.startupFailed).toBe(true)

    useSession.getState().gameStarted('Recovered')
    expect(snapshotFromStores().mode).toBe('play')
    expect(snapshotFromStores().startupFailed).toBe(false)
  })

  it('disconnect mid-play -> disconnected; reconnect + game_resumed -> play with lock preserved', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('go')
    expect(snapshotFromStores().mode).toBe('play')

    useSession.getState().setConnected(false) // transport drop
    expect(snapshotFromStores().mode).toBe('disconnected')
    expect(snapshotFromStores().inputLocked).toBe(true)

    useSession.getState().setConnected(true)
    useSession.getState().gameResumed(true) // game_resumed{is_processing:true}
    const resumed = snapshotFromStores()
    expect(resumed.mode).toBe('play')
    expect(resumed.inputLocked).toBe(true)

    useSession.getState().setStatus({ message: '', is_processing: false })
    expect(snapshotFromStores().inputLocked).toBe(false)
  })

  it('disconnect during combat falls back to disconnected, combat resumes on reconnect', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('go')
    useWorld.getState().setInitiative({ active: true, combatants: [{}], round: 1 })
    useSession.getState().setCombatActive(true)
    expect(snapshotFromStores().mode).toBe('combat')

    useSession.getState().setConnected(false)
    expect(snapshotFromStores().mode).toBe('disconnected')

    useSession.getState().setConnected(true)
    useSession.getState().gameResumed(false)
    // initiative_data_response re-requested on reconnect still reports active
    expect(snapshotFromStores().mode).toBe('combat')
  })

  it('modal overlay tracks the dialogs store in any mode', () => {
    useSession.getState().setConnected(true)
    useSession.getState().gameStarted('go')
    expect(snapshotFromStores().modalOpen).toBe(false)

    useDialogs.getState().openDialog('save')
    const withModal = snapshotFromStores()
    expect(withModal.modalOpen).toBe(true)
    expect(withModal.mode).toBe('play')

    useDialogs.getState().closeDialog()
    expect(snapshotFromStores().modalOpen).toBe(false)
  })
})
