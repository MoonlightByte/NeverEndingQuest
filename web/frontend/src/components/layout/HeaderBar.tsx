import { emitC } from '../../services/socket'
import { useSession, useWorld, useDialogs } from '../../stores'
import { SettingsMenu } from '../settings/SettingsMenu'
import { useUiMode } from '../../modes/useUiMode'

const injectedVersion = document
  .querySelector<HTMLMetaElement>('meta[name="neq-version"]')
  ?.content.replace('__NEQ_VERSION__', '') || undefined

function ShimmerTitle({ version, updateAvailable, onUpdate }: { version?: string | undefined; updateAvailable: boolean; onUpdate: () => void }) {
  return (
    <h1 className="neq-shimmer-title whitespace-nowrap">
      Never<span>Ending</span>Quest{' '}{version && <small className="neq-version">{`v${version}`}</small>}
      {updateAvailable && <button type="button" onClick={onUpdate} className="neq-update-button-parity">[UPDATE] Update Available</button>}
    </h1>
  )
}

function ConnectionDot() {
  const connected = useSession((s) => s.connected)
  const label = connected ? 'Connected' : 'Disconnected'
  return <div className="neq-connection flex items-center"><span>{label}</span><span title={connected ? 'Connected' : 'Disconnected'} aria-label={connected ? 'Connected' : 'Disconnected'} className="inline-block h-[10px] w-[10px] rounded-full" style={{ backgroundColor: connected ? 'var(--accent)' : '#555' }} /></div>
}

const buttonClass =
  'font-chrome text-sm text-primary bg-[#555] border-0 rounded px-3 py-1.5 ' +
  'cursor-pointer hover:border-soft disabled:cursor-not-allowed'

export const EXIT_SAFE_MESSAGE = 'You can now safely close this browser tab.'

export function HeaderBar() {
  const { mode } = useUiMode()
  const connected = useSession((s) => s.connected)
  const sessionMode = useSession((s) => s.mode)
  const recoveryRequired = useSession((s) => s.restoreRecoveryRequired)
  const restorePending = useSession((s) => s.restorePending)
  const startupStatus = useSession((s) => s.startupStatus)
  const version = useSession((s) => s.version)
  const location = useWorld((s) => s.location)
  const locationError = useWorld((s) => s.locationError)
  const resetPending = useDialogs((s) => s.actionResult?.kind === 'reset')
  const isLocalEdition = (import.meta.env.VITE_EDITION ?? 'local') === 'local'

  const handleStart = () => {
    if (!connected || recoveryRequired || restorePending) return
    useSession.getState().startRequested()
    emitC('start_game', undefined)
  }
  const handleSave = () => useDialogs.getState().openDialog('save')
  const handleLoad = () => useDialogs.getState().openDialog('load')
  const handleReset = () => useDialogs.getState().openDialog('reset')
  const handleVersion = () => useDialogs.getState().openDialog('update')
  const handleToolkit = () => {
    window.open('/toolkit', 'ModuleToolkit', 'width=1400,height=900')
  }
  const handleExit = () => {
    if (!window.confirm('Are you sure you want to exit the game?')) return
    // Socket.IO queues emits made while offline. Do not enqueue a stale exit
    // that could be delivered after an automatic reconnect; the legacy client
    // only notifies the server when it is connected.
    if (connected) emitC('user_exit', undefined)
    window.close()
    useDialogs.getState().setActionResult({ kind: 'exit', message: EXIT_SAFE_MESSAGE })
  }
  const gameReady = sessionMode === 'play' && !recoveryRequired && !restorePending
  const lifecycleAvailable = !recoveryRequired && !restorePending
    && (gameReady || startupStatus === 'in_progress' || startupStatus === 'failed')
  const recoveryControlsAvailable = lifecycleAvailable || recoveryRequired || restorePending
  const isStarting = mode === 'starting' || sessionMode === 'starting'
  // Legacy changes the initial connected/pre-start label to "New Game" until
  // the first successful start records neq_hasPlayed. Subsequent fresh starts
  // retain the normal "Start Game" wording.
  const startLabel = connected && !localStorage.getItem('neq_hasPlayed') ? 'New Game' : 'Start Game'
  const locationName = location
    ? `${location.currentLocation} (${location.currentArea})`
    : ''
  const locationDetails = location
    ? `${location.time ? `${location.day} ${location.month} ${location.year} - ${location.time}` : 'Time Unknown'} ${location.currentLocationId ? `[${location.currentAreaId}:${location.currentLocationId}]` : ''}`
    : ''

  return (
    <div className="neq-header flex items-center justify-between border-b-2 border-card bg-panel px-5 py-[10px]">
      <div className="neq-header-brand flex items-baseline gap-2">
        <ShimmerTitle version={version?.local_version ?? injectedVersion} updateAvailable={version?.update_available === true} onUpdate={handleVersion} />
      </div>

      <div className="neq-header-location min-w-0 flex-1 text-center">
        {location ? (
          <><div className="neq-location-name truncate font-log text-sm font-bold text-accent">{locationName}</div><div className="neq-location-details truncate font-log text-xs text-secondary">{locationDetails}</div></>
        ) : locationError ? (
          <div className="neq-location-name truncate font-log text-sm font-bold">Location Unknown</div>
        ) : (
          <div className="neq-location-name truncate font-log text-sm font-bold">Loading location...</div>
        )}
      </div>

      <div className="neq-header-actions flex items-center gap-2">
        <ConnectionDot />
        <button type="button" className={buttonClass} onClick={handleStart}
          disabled={!connected || isStarting || gameReady || recoveryRequired || restorePending}
          style={{ backgroundColor: isStarting ? '#1976d2' : '#2196f3', borderRadius: '3px', color: 'white', fontWeight: 700 }}>
          {gameReady ? 'Game Running' : isStarting ? 'Starting...' : startLabel}
        </button>
        <button type="button" className={buttonClass} onClick={handleSave} disabled={resetPending || !connected || !lifecycleAvailable}
          style={{ backgroundColor: lifecycleAvailable ? '#ff9800' : '#555', color: 'white' }}>
          Save
        </button>
        <button type="button" className={buttonClass} onClick={handleLoad} disabled={resetPending || !connected || !recoveryControlsAvailable}
          style={{ backgroundColor: recoveryControlsAvailable ? '#9c27b0' : '#555', color: 'white' }}>
          Load
        </button>
        <button type="button" className={buttonClass} onClick={handleReset} disabled={resetPending || !connected || !recoveryControlsAvailable}
          style={{ backgroundColor: recoveryControlsAvailable ? '#f44336' : '#555', color: 'white' }}>
          Reset
        </button>
        {isLocalEdition && <SettingsMenu />}
        <button type="button" className={`${buttonClass} neq-toolkit-button`} onClick={handleToolkit} title="Open Module Toolkit">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M22,2V8H20V4H17V2H22M2,8V2H7V4H4V8H2M20,13.09A2.5,2.5 0 0,0 22.5,15.59C22.5,16.9 21.4,18 20,18H4C2.6,18 1.5,16.9 1.5,15.59C1.5,14.09 2.59,12.83 4,12.5V10H20V13.09M20,16H4A1,1 0 0,1 3,15A1,1 0 0,1 4,14H20A1,1 0 0,1 21,15A1,1 0 0,1 20,16Z" /></svg>
          <span>Toolkit</span>
        </button>
        <button type="button" className={`${buttonClass} neq-exit-button`} onClick={handleExit} style={{ color: 'white', fontWeight: 700 }}>
          × Exit
        </button>
      </div>
    </div>
  )
}
