import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useSession, useWorld, useDialogs, useLog } from '../../stores'
import { SettingsMenu } from '../settings/SettingsMenu'

/**
 * Request location/time now and after every new log message (the React
 * replacement for the legacy poll, same pattern as PartyStrip); returns
 * the unsubscribe function.
 */
function requestLocationOnLogActivity(): () => void {
  emitC('request_location_data', undefined)
  return useLog.subscribe((state, previous) => {
    if (state.messages !== previous.messages) {
      emitC('request_location_data', undefined)
    }
  })
}

function ShimmerTitle() {
  return (
    <h1 className="neq-shimmer-title text-[28px] leading-none">
      Never<span>Ending</span>Quest
    </h1>
  )
}

function ConnectionDot() {
  const connected = useSession((s) => s.connected)
  return (
    <span
      title={connected ? 'Connected' : 'Disconnected'}
      aria-label={connected ? 'Connected' : 'Disconnected'}
      className="inline-block h-3 w-3 rounded-full"
      style={{ backgroundColor: connected ? 'var(--accent)' : '#c0392b' }}
    />
  )
}

const buttonClass =
  'font-chrome text-sm text-primary bg-panel border-2 border-card rounded px-3 py-1 ' +
  'cursor-pointer hover:border-soft disabled:opacity-50 disabled:cursor-not-allowed'

export function HeaderBar() {
  const mode = useSession((s) => s.mode)
  const version = useSession((s) => s.version)
  const location = useWorld((s) => s.location)
  const isLocalEdition = (import.meta.env.VITE_EDITION ?? 'local') === 'local'

  useEffect(() => requestLocationOnLogActivity(), [])

  const handleStart = () => {
    useSession.getState().startRequested()
    emitC('start_game', undefined)
  }
  const handleSave = () => useDialogs.getState().openDialog('save')
  const handleLoad = () => {
    emitC('action', { action: 'listSaves' })
    useDialogs.getState().openDialog('load')
  }
  const handleReset = () => useDialogs.getState().openDialog('reset')
  // JournalModal requests plot data itself on open.
  const handleJournal = () => useDialogs.getState().openDialog('journal')
  const handleVersion = () => useDialogs.getState().openDialog('update')
  const handleToolkit = () => {
    window.open('/toolkit')
  }
  const handleExit = () => emitC('user_exit', undefined)

  return (
    <div className="neq-card neq-header flex items-center justify-between gap-4 px-4 py-2">
      <div className="neq-header-brand flex items-center gap-3">
        <ShimmerTitle />
        <ConnectionDot />
        {version && (
          <button
            type="button"
            onClick={handleVersion}
            title={version.update_available ? version.message : 'Version info'}
            className="cursor-pointer border-none bg-transparent p-0 font-log text-xs"
            style={{ color: version.update_available ? '#FFA500' : 'var(--text-secondary)' }}
          >
            v{version.local_version}
            {version.update_available && ' (update available)'}
          </button>
        )}
      </div>

      <div className="neq-header-location min-w-0 flex-1 px-2 text-center">
        {location ? (
          <div className="truncate font-log text-sm" style={{ color: '#FFA500' }}>
            {location.currentLocation} ({location.currentArea}) -- {location.time}, Day{' '}
            {location.day} of {location.month}, {location.year}
          </div>
        ) : (
          <div className="truncate font-log text-sm text-secondary">No location data</div>
        )}
      </div>

      <div className="neq-header-actions flex items-center gap-2">
        <button type="button" className={buttonClass} onClick={handleStart}
          disabled={mode === 'starting'}
          style={{ borderColor: 'var(--accent)', color: 'var(--accent)' }}>
          Start
        </button>
        <button type="button" className={buttonClass} onClick={handleSave}>
          Save
        </button>
        <button type="button" className={buttonClass} onClick={handleLoad}>
          Load
        </button>
        <button type="button" className={buttonClass} onClick={handleReset}>
          Reset
        </button>
        <button type="button" className={buttonClass} onClick={handleJournal}>
          Journal
        </button>
        {isLocalEdition && <SettingsMenu />}
        <button type="button" className={buttonClass} onClick={handleToolkit}>
          Toolkit
        </button>
        <button type="button" className={buttonClass} onClick={handleExit}>
          Exit
        </button>
      </div>
    </div>
  )
}
