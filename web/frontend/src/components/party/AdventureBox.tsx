/**
 * AdventureBox (plan Task 4.4c) -- the small header box beside the party
 * rail. Outside combat it shows the time-of-day environment art (sunrise /
 * midday / sunset / nightfall picked from world.location.time, same hour
 * bands as the legacy updateTimeOfDayImage()). While world.initiative.active
 * it becomes the COMBAT / ROUND N box, mirroring the legacy swap between
 * #adventure-box and #combat-round-box.
 */
import type { CSSProperties } from 'react'
import { useWorld } from '../../stores'

/** Map an in-game "HH:MM:SS" time to the environment art URL (legacy hour bands). */
export function timeOfDayImage(time: string | null | undefined): string {
  let imageName = 'midday.jpg'
  if (time) {
    const hour = Number.parseInt(time.split(':')[0] ?? '', 10)
    if (Number.isFinite(hour)) {
      if (hour >= 5 && hour < 9) imageName = 'sunrise.jpg'
      else if (hour >= 9 && hour < 17) imageName = 'midday.jpg'
      else if (hour >= 17 && hour < 21) imageName = 'sunset.jpg'
      else imageName = 'nightfall.jpg'
    }
  }
  return `/static/media/environment/${imageName}`
}

const recessedBox: CSSProperties = {
  backgroundColor: '#1e1e1e',
  border: '2px solid #555',
  boxShadow: 'inset 0 0 8px rgba(0,0,0,0.6)',
}

export function AdventureBox() {
  const time = useWorld((s) => s.location?.time ?? null)
  const initiative = useWorld((s) => s.initiative)

  if (initiative.active) {
    const round = initiative.round > 0 ? initiative.round : 1
    return (
      <div
        aria-label={`Combat, round ${round}`}
        className="flex h-[60px] w-[85px] shrink-0 flex-col items-center justify-center rounded-md p-1 text-center"
        style={recessedBox}
      >
        <div
          className="font-display font-bold"
          style={{ fontSize: 13, color: '#FFA500', letterSpacing: 1, lineHeight: 1 }}
        >
          COMBAT
        </div>
        <div
          style={{ width: '80%', height: 1, backgroundColor: 'var(--border-card)', margin: '2px 0' }}
        />
        <div className="uppercase" style={{ fontSize: 10, color: '#888', lineHeight: 1 }}>
          Round
        </div>
        <div
          className="font-bold"
          style={{ fontSize: 20, color: 'var(--accent)', lineHeight: 1.1 }}
        >
          {round}
        </div>
      </div>
    )
  }

  return (
    <div
      aria-label="Time of day"
      className="relative h-[60px] w-[60px] shrink-0 overflow-hidden rounded-md"
      style={recessedBox}
    >
      <img
        src={timeOfDayImage(time)}
        alt=""
        className="absolute inset-0 h-full w-full object-cover"
      />
    </div>
  )
}
