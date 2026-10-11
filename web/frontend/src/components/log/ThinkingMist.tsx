import { useSession } from '../../stores'

/**
 * Green swirling mist beside the turn status while the Dungeon Master is
 * working, so a long model turn reads as busy rather than stalled.
 * Presentation only; it follows isProcessing and never gates input.
 */
export function useDmBusy(): boolean {
  return useSession((s) => s.isProcessing && !s.restoreRecoveryRequired)
}

export function ThinkingMist() {
  const busy = useDmBusy()
  if (!busy) return null
  return (
    <span className="neq-thinking-mist" data-testid="thinking-mist" aria-hidden="true">
      <span className="neq-thinking-mist-swirl" />
      <span className="neq-thinking-mist-swirl neq-thinking-mist-swirl--inner" />
    </span>
  )
}
