import { useEffect, useState } from 'react'
import { useSession } from '../../stores'
import type { WaitRecord } from '../../contract/events'

/** Presentation only: never changes turn gates, provider calls or retries.
 * #1271: the status text is never read. A model call is rendered from its
 * typed `wait` record; any other busy status is shown exactly as the server
 * wrote it. */

const PURPOSE: Record<string, string> = {
  character_setup: 'Setting up your character',
  adventure_choice: 'Preparing your adventure choices',
  starting_location: 'Choosing your starting location',
  level_up: 'Working on your level-up',
  combat: 'Resolving the fight',
  turn: 'The Dungeon Master is answering',
}

/** After this long, the line says the wait is normal and the turn is safe. */
export const LONG_WAIT_MS = 60_000

function seconds(ms: number): number {
  return Math.max(0, Math.floor(ms / 1000))
}

function duration(ms: number): string {
  const total = seconds(ms)
  if (total < 60) return `${total} s`
  return `${Math.floor(total / 60)} min ${String(total % 60).padStart(2, '0')} s`
}

function phaseText(wait: WaitRecord, sinceReceiptMs: number): string {
  const provider = wait.providerName || 'the AI provider'
  switch (wait.phase) {
    case 'spawned':
    case 'payload_read':
    case 'connecting':
      return `connecting to ${provider}`
    case 'connected':
    case 'secured':
      return `connected to ${provider}, sending your request`
    case 'sent':
      return `request sent, waiting for ${provider} to start`
    case 'acknowledged':
    case 'working':
      return wait.lastActivityMs === null
        ? `${provider} is working`
        : `${provider} is working (last activity ${seconds(wait.lastActivityMs + sinceReceiptMs)} s ago)`
    case 'receiving':
      return `answer arriving from ${provider}`
    case 'done':
      return 'answer received, finishing'
    case 'failed':
      return `connection to ${provider} failed`
    default:
      return `waiting for ${provider}`
  }
}

/** One status line for a waiting model call. `sinceReceiptMs` is the local
 * monotonic time since the record arrived; the server's heartbeat re-bases it. */
export function waitStatusText(wait: WaitRecord, sinceReceiptMs: number): string {
  const elapsed = wait.elapsedMs + sinceReceiptMs
  const purpose = PURPOSE[wait.purpose] ?? `Waiting for ${wait.providerName || 'the AI provider'}`
  let detail: string
  if (wait.retryInMs !== null) {
    const of = wait.maxAttempts !== null ? ` of ${wait.maxAttempts}` : ''
    const left = Math.ceil(Math.max(0, wait.retryInMs - sinceReceiptMs) / 1000)
    detail = `attempt ${wait.attempt - 1}${of} failed; attempt ${wait.attempt} in ${left} s`
  } else {
    detail = phaseText(wait, sinceReceiptMs)
  }
  const line = `${purpose} (${duration(elapsed)}): ${detail}.`
  return elapsed >= LONG_WAIT_MS
    ? `${line} This can take a few minutes. Your turn is safe; there's no need to send it again.`
    : line
}

export function useTurnStatus(): string | null {
  const busy = useSession((s) => s.isProcessing)
  const message = useSession((s) => s.statusMessage)
  const recovery = useSession((s) => s.restoreRecoveryRequired)
  const welcome = useSession((s) => s.welcomeMessage)
  const openingScene = useSession((s) => s.welcomeOpeningScene)
  const wait = useSession((s) => s.wait)
  const receivedAt = useSession((s) => s.waitReceivedAt)
  const [now, setNow] = useState(() => performance.now())
  // A local 1 s re-render while a call is shown: no polling, no socket traffic.
  useEffect(() => {
    if (!busy || !wait) return
    setNow(performance.now())
    const id = setInterval(() => setNow(performance.now()), 1000)
    return () => clearInterval(id)
  }, [busy, wait])
  if (recovery) return message || 'Gameplay is paused. Use the recovery controls to continue.'
  if (busy && wait) return waitStatusText(wait, Math.max(0, now - receivedAt))
  if (busy) return message || 'Working…'
  if (welcome) return openingScene
    ? `${welcome} Anything you type now happens right after it.`
    : `${welcome} You can act anytime.`
  return null
}
