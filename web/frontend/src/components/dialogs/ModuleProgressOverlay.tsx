import { useDialogs } from '../../stores'

/**
 * #2067: an in-play adventure build is a progress line in the story column, not a blocking
 * overlay. The build runs in the background while the party plays on, so the composer, header and
 * panels stay usable. The line renders from the store, which both module_creation_progress and the
 * hydration snapshot feed (a reload mid-build shows it again).
 *
 * - running: the stage and percent;
 * - success: nothing (the DM's own announcement turn tells the player);
 * - failure: one short line plus Close; the reason stays in the story's error card
 *   (module-build-failure-<build_id>). Close is keyed on build_id, so a snapshot of the same
 *   build never brings it back; a new build shows normally.
 */
export const BUILD_FAILED_LINE = 'The new adventure could not be prepared.'

export function ModuleProgressOverlay() {
  const operation = useDialogs((s) => s.moduleOperation)
  const dismissedBuildId = useDialogs((s) => s.dismissedBuildId)
  if (!operation || (operation.buildId !== null && operation.buildId === dismissedBuildId)) return null
  if (operation.terminal && operation.success !== false) return null
  const failed = operation.terminal
  const percentage = Math.max(0, Math.min(100, operation.percentage))
  return <div className="neq-build-line mx-2 my-1 flex shrink-0 items-center gap-3 rounded-md border border-card bg-[#2b2b2b] px-3 py-2 font-chrome text-[13px] leading-snug text-primary" role="status" aria-live="polite">
    {failed
      ? <>
        <span className="flex-1" style={{ color: '#ff8a80' }}>{BUILD_FAILED_LINE}</span>
        <button type="button" onClick={() => useDialogs.getState().dismissModuleOperation(operation.buildId)} className="rounded bg-[#555] px-3 py-1 text-xs text-white" style={{ minHeight: 32 }}>Close</button>
      </>
      : <>
        <span className="flex-1">{`A new adventure is being prepared: ${operation.stageName} (stage ${operation.stage} of ${operation.totalStages})`}</span>
        <span className="neq-build-line-percent text-accent" aria-hidden="true">{`${operation.percentage}%`}</span>
        <span className="h-1.5 w-20 overflow-hidden rounded bg-[#444]" role="progressbar" aria-label="New adventure progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
          <span className="block h-full bg-accent transition-[width] duration-500" style={{ width: `${percentage}%` }} />
        </span>
      </>}
  </div>
}
