import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useSession, useWorld, useDialogs, useLog } from '../../stores'
import { SettingsMenu } from '../settings/SettingsMenu'
import { useUiMode } from '../../modes/useUiMode'

/**
 * Request location/time now and after every new log message (the React
 * replacement for the legacy poll, same pattern as PartyStrip); returns
 * the unsubscribe function.
 */
function requestLocationOnLogActivity(): () => void {
  emitC('request_location_data', undefined)
  const unsubscribe = useLog.subscribe((state, previous) => {
    if (state.messages !== previous.messages) {
      emitC('request_location_data', undefined)
    }
  })
  const timer = window.setInterval(() => emitC('request_location_data', undefined), 5000)
  return () => { unsubscribe(); window.clearInterval(timer) }
}

function ShimmerTitle() {
  return (
    <h1 className="neq-shimmer-title whitespace-nowrap text-[28px] leading-none">
      Never<span>Ending</span>Quest
    </h1>
  )
}

function ConnectionDot() {
  const connected = useSession((s) => s.connected)
  const label = connected ? 'Connected' : 'Disconnected'
  return <div className="flex items-center gap-2"><span>{label}</span><span title={connected ? 'Connected' : 'Disconnected'} aria-label={connected ? 'Connected' : 'Disconnected'} className="inline-block h-[10px] w-[10px] rounded-full" style={{ backgroundColor: connected ? 'var(--accent)' : '#555' }} /></div>
}

const buttonClass =
  'font-chrome text-sm text-primary bg-[#555] border-0 rounded px-3 py-1.5 ' +
  'cursor-pointer hover:border-soft disabled:cursor-not-allowed'

export function HeaderBar() {
  const { mode } = useUiMode()
  const connected = useSession((s) => s.connected)
  const sessionMode = useSession((s) => s.mode)
  const version = useSession((s) => s.version)
  const location = useWorld((s) => s.location)
  const isLocalEdition = (import.meta.env.VITE_EDITION ?? 'local') === 'local'

  useEffect(() => requestLocationOnLogActivity(), [])

  const handleStart = () => {
    if (!connected) return
    useSession.getState().startRequested()
    emitC('start_game', undefined)
  }
  const handleSave = () => useDialogs.getState().openDialog('save')
  const handleLoad = () => {
    emitC('action', { action: 'listSaves' })
    useDialogs.getState().openDialog('load')
  }
  const handleReset = () => useDialogs.getState().openDialog('reset')
  const handleVersion = () => useDialogs.getState().openDialog('update')
  const handleToolkit = () => {
    window.open('/toolkit', 'ModuleToolkit', 'width=1400,height=900')
  }
  const handleExit = () => {
    if (!window.confirm('Are you sure you want to exit the game?')) return
    emitC('user_exit', undefined)
    window.close()
    useDialogs.getState().setActionResult({ kind: 'exit', message: 'You can now safely close this browser tab.' })
  }
  const gameReady = sessionMode === 'play'
  const startLabel = localStorage.getItem('neq_hasPlayed') ? 'Start Game' : 'New Game'

  return (
    <div className="neq-header flex items-center justify-between gap-4 border-b-2 border-card bg-panel px-5 py-[10px]">
      <div className="neq-header-brand flex items-baseline gap-2">
        <ShimmerTitle />
        {version && (
          <><span className="font-log text-[10px] text-secondary">v{version.local_version}</span>{version.update_available && <button type="button" onClick={handleVersion} className="rounded bg-[#4caf50] px-3 py-1 text-xs text-white">[UPDATE] Update Available</button>}</>
        )}
      </div>

      <div className="neq-header-location min-w-0 flex-1 px-2 text-center">
        {location ? (
          <><div className="truncate font-log text-sm font-bold text-accent">{location.currentLocation} ({location.currentArea})</div><div className="mt-0.5 truncate font-log text-xs text-secondary">{location.day} {location.month} {location.year} - {location.time} {location.currentLocationId ? `[${location.currentAreaId}:${location.currentLocationId}]` : ''}</div></>
        ) : (
          <div className="truncate font-log text-sm text-secondary">No location data</div>
        )}
      </div>

      <div className="neq-header-actions flex items-center gap-2">
        <ConnectionDot />
        <button type="button" className={buttonClass} onClick={handleStart}
          disabled={!connected || mode === 'starting' || gameReady}
          style={{ backgroundColor: '#2196f3', color: 'white', fontWeight: 700 }}>
          {gameReady ? 'Game Running' : startLabel}
        </button>
        <button type="button" className={buttonClass} onClick={handleSave} disabled={!connected || !gameReady}
          style={{ backgroundColor: gameReady ? '#ff9800' : '#555', color: 'white' }}>
          Save
        </button>
        <button type="button" className={buttonClass} onClick={handleLoad} disabled={!connected || !gameReady}
          style={{ backgroundColor: gameReady ? '#9c27b0' : '#555', color: 'white' }}>
          Load
        </button>
        <button type="button" className={buttonClass} onClick={handleReset} disabled={!connected || !gameReady}
          style={{ backgroundColor: gameReady ? '#f44336' : '#555', color: 'white' }}>
          Reset
        </button>
        {isLocalEdition && <SettingsMenu />}
        <button type="button" className={buttonClass} onClick={handleToolkit}>
          Toolkit
        </button>
        <button type="button" className={buttonClass} onClick={handleExit} style={{ backgroundColor: '#c00', color: 'white', fontWeight: 700 }}>
          × Exit
        </button>
      </div>
    </div>
  )
}
