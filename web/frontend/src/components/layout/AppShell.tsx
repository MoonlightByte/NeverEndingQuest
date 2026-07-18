/**
 * AppShell (plan 4.4a) -- the full player layout:
 *
 *   +----------------------------------------------+
 *   | HeaderBar (title, location/time, buttons)    |
 *   +---------------------------------+------------+
 *   | party rail (AdventureBox +      | RightPanel |
 *   |   PartyStrip <-> Initiative)    |   Tabs     |
 *   | GameLog                         |            |
 *   | InputBar                        |            |
 *   | DiceStrip                       |            |
 *   +---------------------------------+------------+
 *
 * All dialogs are mounted here behind the dialogs store (each self-gates on
 * useDialogs.open), plus the CompressionOverlay which drives itself from
 * compression_* events. The 5-mode machine (modes/useUiMode.ts) gates the
 * center column: pre-start and starting states show status panels instead of
 * a dead input bar.
 */
import { emitC } from '../../services/socket'
import { useSession } from '../../stores'
import { useUiMode } from '../../modes/useUiMode'
import { HeaderBar } from './HeaderBar'
import { GameLog } from '../log/GameLog'
import { InputBar } from '../log/InputBar'
import { DiceStrip } from '../log/DiceStrip'
import { AdventureBox, InitiativeTracker, PartyStrip } from '../party'
import { RightPanelTabs } from '../sheet/RightPanelTabs'
import { SaveDialog } from '../dialogs/SaveDialog'
import { LoadDialog } from '../dialogs/LoadDialog'
import { ResetDialog } from '../dialogs/ResetDialog'
import { JournalModal } from '../dialogs/JournalModal'
import { StorageModal } from '../dialogs/StorageModal'
import { UpdateDialog } from '../dialogs/UpdateDialog'
import { CompressionOverlay } from '../dialogs/CompressionOverlay'

/** Pre-start panel: connected but no game running yet (mode 'disconnected'). */
function StartPanel({ connected }: { connected: boolean }) {
  const handleStart = () => {
    useSession.getState().startRequested()
    emitC('start_game', undefined)
  }
  return (
    <div className="neq-card flex flex-col items-center gap-3 p-4 text-center">
      {connected ? (
        <>
          <p className="font-body text-sm text-secondary">
            The realm awaits. Press Start to begin your adventure.
          </p>
          <button
            type="button"
            onClick={handleStart}
            className="cursor-pointer rounded border-2 bg-panel px-6 py-2 font-display text-base hover:brightness-125"
            style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}
          >
            Start Game
          </button>
        </>
      ) : (
        <p className="font-log text-sm" style={{ color: '#e74c3c' }}>
          Disconnected from the game server. Reconnecting...
        </p>
      )}
    </div>
  )
}

/** Starting panel: startup_status phases + failed-startup recovery action. */
function StartingPanel() {
  const startupStatus = useSession((s) => s.startupStatus)
  const startupPhase = useSession((s) => s.startupPhase)
  const recovery = useSession((s) => s.recovery)

  const handleRecover = () => emitC('action', { action: 'recover_startup_handoff' })

  return (
    <div className="neq-card flex flex-col items-center gap-2 p-4 text-center">
      {startupStatus === 'failed' ? (
        <>
          <p className="font-log text-sm" style={{ color: '#e74c3c' }}>
            Startup failed{startupPhase ? ` during: ${startupPhase}` : ''}.
          </p>
          {recovery?.error && (
            <p className="font-log text-xs text-secondary">{recovery.error}</p>
          )}
          <button
            type="button"
            onClick={handleRecover}
            className="cursor-pointer rounded border-2 border-card bg-panel px-4 py-2 font-chrome text-sm text-accent hover:border-accent"
          >
            Attempt Recovery
          </button>
        </>
      ) : (
        <p className="animate-pulse font-log text-sm" style={{ color: 'var(--accent)' }}>
          {startupPhase || 'Preparing your adventure...'}
        </p>
      )}
    </div>
  )
}

/** Center column: party/initiative rail above the log, then input + dice. */
function CenterColumn() {
  const { mode } = useUiMode()
  const connected = useSession((s) => s.connected)

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 items-start gap-3">
        <AdventureBox />
        <div className="min-w-0 flex-1">
          {/* Self-gating pair: PartyStrip out of combat, InitiativeTracker in. */}
          <PartyStrip />
          <InitiativeTracker />
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <GameLog />
      </div>
      {mode === 'disconnected' && <StartPanel connected={connected} />}
      {mode === 'starting' && <StartingPanel />}
      {(mode === 'play' || mode === 'combat') && (
        <>
          <InputBar />
          <DiceStrip />
        </>
      )}
    </div>
  )
}

/** App shell: CSS grid of header / center column / right panel rail. */
export function AppShell() {
  return (
    <>
      <div
        className="neq-app-grid"
      >
        <header style={{ gridArea: 'header' }}>
          <HeaderBar />
        </header>
        <main className="min-h-0" style={{ gridArea: 'main' }}>
          <CenterColumn />
        </main>
        <aside className="min-h-0" style={{ gridArea: 'rail' }}>
          <RightPanelTabs />
        </aside>
      </div>

      {/* Dialogs: each self-gates on the dialogs store (MODAL overlay). */}
      <SaveDialog />
      <LoadDialog />
      <ResetDialog />
      <JournalModal />
      <StorageModal />
      <UpdateDialog />
      {/* Compression banner drives itself from compression_* events. */}
      <CompressionOverlay />
    </>
  )
}
