/**
 * #2067: after a Load restarts the server, the page reloads with the typed outcome in its URL
 * (`/play/?restarted=<ms>&restore=<outcome>`, services/restart.ts). This module reads it once.
 *
 * - selected_applied: say "Game loaded." and start the game without a click, with the same two
 *   calls the Start Game button makes, once the socket is connected and the first snapshot has arrived.
 * - previous_restored / unchanged: the chosen save could not be loaded; show the fixed line for that
 *   outcome and leave the game to the player.
 * The Load's own notice (restore_complete) is lost with the reload, so the line comes from this fixed
 * map of the typed outcome (the server's words, owner D-UX-3), never from the server's text.
 * - anything else (recovery_required never reloads; reset and update reloads carry nothing): nothing.
 *
 * The parameters leave the address bar at once, so a manual refresh or a bookmark never starts a
 * game. At most once per page load; no timer, no retry.
 */
import { useDialogs, useSession } from '../stores'
import { useConnectionNotice } from '../stores/connectionNotices'
import { needsOpenaiKey } from '../components/settings/keySetupText'
import { emitC } from './socket'

export const RESTORE_RELOAD_LINES: Readonly<Record<string, string>> = {
  selected_applied: 'Game loaded.',
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
  const line = RESTORE_RELOAD_LINES[outcome]
  if (!line) return
  let decided = false
  const decide = () => {
    if (decided) return true
    // The socket's connect handler clears notices (services/socket.ts), so the line waits for the
    // connect and the first snapshot, like the start.
    const s = useSession.getState()
    if (!s.connected || s.serverInstanceId === null) return false
    if (outcome !== 'selected_applied') {
      decided = true
      useConnectionNotice.getState().show(line)
      return true
    }
    const ready = readyToStart()
    if (ready === null) return false
    decided = true // before startRequested, whose store update re-enters the subscription
    useConnectionNotice.getState().show(line)
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
