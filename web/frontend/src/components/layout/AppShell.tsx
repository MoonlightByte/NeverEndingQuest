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
 * compression_* events. Startup preserves the legacy command-row geometry;
 * the input's disabled state is controlled by the session mode.
 */
import { useDialogs, useSession, useWorld } from '../../stores'
import { useEffect, useState } from 'react'
import { EXIT_SAFE_MESSAGE, HeaderBar } from './HeaderBar'
import { CoreHydrationOwner } from './CoreHydrationOwner'
import { StartingPanel } from './StartingPanel'
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
import { ModuleProgressOverlay } from '../dialogs/ModuleProgressOverlay'

function FirstRunBanner() {
  const sessionMode = useSession((s) => s.mode)
  const [dismissed, setDismissed] = useState(true)
  useEffect(() => setDismissed(Boolean(localStorage.getItem('neq_bannerDismissed'))), [])
  // Legacy only exposes this first-run guidance before a game starts. A
  // resumed game must not gain a React-only row that shifts the entire log.
  if (dismissed || sessionMode !== 'disconnected') return null
  return <div className="m-2 flex items-center gap-3 rounded-md border border-[#4a6da7] bg-[#2b3a55] px-3.5 py-2.5 text-[13px] leading-snug text-[#dde6f5]"><span className="flex-1">Welcome to NeverEndingQuest! Before you start, open <strong>Settings</strong> (gear icon, top right) to choose your AI provider. Want local/zero-cost or a custom server? Pick <strong>Local / Custom Server</strong>, paste your endpoint URL, then click <strong>Test Connection</strong>. You can also set your OpenAI API key there -- no file editing needed.</span><button type="button" onClick={() => { localStorage.setItem('neq_bannerDismissed', 'true'); setDismissed(true) }} className="rounded bg-[#4a6da7] px-3 py-1 text-xs text-white">Dismiss</button></div>
}

function ExitOverlay() {
  const result = useDialogs((s) => s.actionResult)
  if (result?.kind !== 'exit') return null
  return <div className="fixed left-1/2 top-1/2 z-[10000] -translate-x-1/2 -translate-y-1/2 rounded-[10px] border-2 border-[#8b0000] bg-[#2c2c2c] p-[30px] text-center shadow-[0_0_20px_rgba(0,0,0,.5)]"><h2 className="mb-5 text-2xl font-bold text-accent" style={{ lineHeight: 'normal' }}>Thank you for playing!</h2><p className="mb-5" style={{ lineHeight: 'normal' }}>{EXIT_SAFE_MESSAGE}</p><p className="text-sm text-[#888]" style={{ lineHeight: 'normal' }}>Due to browser security, we cannot close this tab automatically.</p></div>
}

/** Center column: party/initiative rail above the log, then input + dice. */
function CenterColumn() {
  const awaitingInitiative = useWorld((state) => state.revisions.initiative < 0)
  return (
    <div className="neq-main-panel flex min-h-0 flex-col">
      <div className="neq-game-panel-header flex shrink-0 items-center">
        {awaitingInitiative && <span className="neq-panel-header-label">Game Output</span>}
        <AdventureBox />
        <div className="neq-party-scroller min-w-0 flex-1">
          {/* Self-gating pair: PartyStrip out of combat, InitiativeTracker in. */}
          <PartyStrip />
          <InitiativeTracker />
        </div>
        <DiceStrip />
      </div>
      <div className="neq-header-divider" />
      <div id="neq-dice-results-host" />
      <FirstRunBanner />
      <div className="min-h-0 flex-1">
        <GameLog />
      </div>
      <InputBar />
    </div>
  )
}

/** App shell: CSS grid of header / center column / right panel rail. */
export function AppShell() {
  return (
    <>
      <CoreHydrationOwner />
      <StartingPanel />
      <div
        className="neq-app-grid"
      >
        <header style={{ gridArea: 'header' }}>
          <HeaderBar />
        </header>
        <main className="neq-main-area min-h-0" style={{ gridArea: 'main' }}>
          <CenterColumn />
        </main>
        <aside className="neq-rail-area min-h-0" style={{ gridArea: 'rail' }}>
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
      <ModuleProgressOverlay />
      <ExitOverlay />
    </>
  )
}
