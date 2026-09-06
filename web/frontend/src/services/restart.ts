const RESTART_BASELINE_KEY = 'neq_restart_server_instance'

export function hasServerRestarted(baseline: string | null, current: string | null, observedUnavailable = false): boolean {
  if (!current) return false
  if (baseline === 'unavailable') return observedUnavailable
  if (baseline) return current !== baseline
  return observedUnavailable
}

async function readServerInstance(): Promise<string | null> {
  try {
    const response = await fetch(`/api/server-instance?restart_probe=${Date.now()}`, { cache: 'no-store' })
    if (!response.ok) return null
    return ((await response.json()) as { server_instance_id?: string }).server_instance_id ?? null
  } catch { return null }
}

/** Capture process identity before emitting an action that will restart it. */
export async function prepareForServerRestart(isCurrent: () => boolean = () => true): Promise<string | null> {
  if (typeof window === 'undefined') return null
  const instance = await readServerInstance()
  if (isCurrent()) window.sessionStorage.setItem(RESTART_BASELINE_KEY, instance ?? 'unavailable')
  return instance
}

function navigateAfterRestart(path: string): void {
  window.sessionStorage.removeItem(RESTART_BASELINE_KEY)
  window.location.replace(`${path}?restarted=${Date.now()}`)
}

export function cancelPendingRestart(): void {
  if (typeof window !== 'undefined') window.sessionStorage.removeItem(RESTART_BASELINE_KEY)
}

/** A missed completion packet still converges when Socket.IO reconnects. */
export async function reloadIfRestartPending(path = '/play/'): Promise<boolean> {
  if (typeof window === 'undefined') return false
  const baseline = window.sessionStorage.getItem(RESTART_BASELINE_KEY)
  if (!baseline) return false
  const current = await readServerInstance()
  // This runs on a Socket.IO connect. For an unavailable baseline, that
  // reconnect is the post-action transition the HTTP probe could not observe.
  if (hasServerRestarted(baseline, current, true)) {
    navigateAfterRestart(path)
    return true
  }
  return false
}

/** Poll after restore/reset/update and bound the wait instead of hanging forever. */
export async function reloadWhenServerReady(path = '/play/', intervalMs = 1000, timeoutMs = 120_000): Promise<void> {
  if (typeof window === 'undefined') return
  const baseline = window.sessionStorage.getItem(RESTART_BASELINE_KEY)
  const deadline = Date.now() + timeoutMs
  let observedUnavailable = false
  while (Date.now() < deadline) {
    const current = await readServerInstance()
    if (!current) observedUnavailable = true
    else if (hasServerRestarted(baseline, current, observedUnavailable)) {
      navigateAfterRestart(path)
      return
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, intervalMs))
  }
  // Retain the marker. A later Socket.IO reconnect can finish recovery; never
  // clear it by reloading a process whose replacement was not proven.
}
