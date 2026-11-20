import { useAllowance } from '../../stores/allowance'
import { allowanceShown, barLine } from './allowanceText'
import type { PlayAllowancePeriod } from '../../contract/events'

/**
 * #2072: the day and week bars at the top of the play page, each filled to the share used. Driven by the data only: shown when a hosted
 * world's read says the player is limited; a player on their own key and every local page show nothing.
 */
function Bar({ period, value }: { period: 'day' | 'week'; value: PlayAllowancePeriod }) {
  const line = barLine(period, value)
  const used = Math.round(Math.min(1, Math.max(0, value.used_fraction)) * 100)
  return (
    <div className="neq-allowance-bar flex min-w-0 flex-1 flex-col gap-1">
      <span className="font-chrome text-xs text-secondary">{line}</span>
      <div role="progressbar" aria-label={line} aria-valuemin={0} aria-valuemax={100} aria-valuenow={used}
        className="h-[6px] w-full overflow-hidden rounded bg-[#444]">
        <div className="h-full rounded bg-[#4caf50]" style={{ width: `${used}%` }} />
      </div>
    </div>
  )
}

export function PlayAllowanceBars() {
  const value = useAllowance((s) => s.value)
  if (!allowanceShown(value)) return null
  return (
    <div className="neq-allowance-bars flex flex-wrap gap-x-6 gap-y-2 border-b border-card bg-panel px-5 py-2" data-testid="play-allowance">
      <Bar period="day" value={value.day} />
      <Bar period="week" value={value.week} />
    </div>
  )
}
