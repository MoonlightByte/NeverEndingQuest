/**
 * #2067: after a Load restarts the server, the page reloads with the typed outcome in its URL
 * (`/play/?restarted=<ms>&restore=<outcome>`, services/restart.ts). This module reads it once.
 *
 * - selected_applied: start the game without a click, with the same two calls the Start Game
 *   button makes, once the socket is connected and the first snapshot has arrived.
 * - previous_restored / unchanged: the chosen save could not be loaded; its notice was lost with
 *   the reload, so show the fixed line for that outcome and leave the game to the player.
 * - anything else (recovery_required never reloads; reset and update reloads carry nothing): nothing.
 *
 * The parameters leave the address bar at once, so a manual refresh or a bookmark never starts a
 * game. At most once per page load; no timer, no retry.
 */
import { useDialogs, useSession } from '../stores'
import { useConnectionNotice } from '../stores/connectionNotices'
import { needsOpenaiKey } from '../components/settings/keySetupText'
import { emitC } from './socket'

export const RESTORE_FAILED_LINES: Readonly<Record<string, string>> = {
  previous_restored: 'That save could not be loaded. Your game is as it was before.',
  unchanged: 'That save could not be loaded. Nothing in your game was changed.',
}

let consumed = false

/** Remove `restore` and `restarted` from the URL and return the outcome that was there. */
function takeRestoreOutcome(): string | null {
  if (typeof window === 'undefined') return null
  const url = new URL(window.location.href)
  const outcome = url.searchParams.get('restore')
  if (outcome === null && !url.searchParams.has('restarted')) return null
  url.searchParams.delete('restore')
  url.searchParams.delete('restarted')
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash)
  return outcome
}

function readyToStart(): boolean | null {
  const s = useSession.getState()
  if (!s.connected || s.serverInstanceId === null) return null // wait for connect + first snapshot
  if (s.mode !== 'disconnected' || s.restorePending || s.restoreRecoveryRequired) return false
  const isLocalEdition = (import.meta.env.VITE_EDITION ?? 'local') === 'local'
  if (!isLocalEdition) return true
  // Local: the header asks for the provider and key status on connect; decide once both are known,
  // so a page that would open the key gate on Start Game keeps Start Game instead.
  const settings = useDialogs.getState().settings
  if (settings.provider === null || settings.openaiHasKey === null) return null
  return !needsOpenaiKey(settings)
}

/** Called once from AppShell on mount. */
export function startAfterRestoreReload(): void {
  if (consumed) return
  consumed = true
  const outcome = takeRestoreOutcome()
  if (outcome === null) return
  const failedLine = RESTORE_FAILED_LINES[outcome]
  if (failedLine) {
    useConnectionNotice.getState().show(failedLine)
    return
  }
  if (outcome !== 'selected_applied') return
  let decided = false
  const decide = () => {
    if (decided) return true
    const ready = readyToStart()
    if (ready === null) return false
    decided = true // before startRequested, whose store update re-enters the subscription
    if (ready) {
      useSession.getState().startRequested()
      emitC('start_game', undefined)
    }
    return true
  }
  if (decide()) return
  const stops: Array<() => void> = []
  const check = () => { if (decide()) stops.splice(0).forEach((stop) => stop()) }
  stops.push(useSession.subscribe(check), useDialogs.subscribe(check))
}
