import { useEffect, useState } from 'react'
import { useDialogs } from '../../stores'

/** DM-themed flavor lines shown while the chronicle compresses (legacy parity). */
const FLAVOR_MESSAGES = [
  'The Dungeon Master carefully inscribes your deeds into the eternal chronicle...',
  'Ancient magics compress your adventures into mystical runes...',
  'The scribes work tirelessly to record your legendary journey...',
  'Your tales are being woven into the tapestry of heroes...',
  "The chronicler's quill dances across enchanted parchment...",
]

const HIDE_DELAY_MS = 2000

/**
 * Themed progress banner driven by compression_start / compression_progress /
 * compression_complete (plan 4.4e). Renders bottom-right; hides itself two
 * seconds after completion.
 */
export function CompressionOverlay() {
  const compression = useDialogs((s) => s.compression)
  const [visible, setVisible] = useState(false)
  const [flavor, setFlavor] = useState(FLAVOR_MESSAGES[0])

  // A new run starts: show the banner and pick a fresh flavor line.
  useEffect(() => {
    if (compression.running) {
      setVisible(true)
      setFlavor(FLAVOR_MESSAGES[Math.floor(Math.random() * FLAVOR_MESSAGES.length)])
    }
  }, [compression.running])

  // Run finished: keep the completion state on screen briefly, then hide.
  useEffect(() => {
    if (!compression.running && compression.result !== null) {
      const timer = window.setTimeout(() => setVisible(false), HIDE_DELAY_MS)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [compression.running, compression.result])

  if (!visible) return null

  const { result, completed, total, totalSections, fromCache } = compression
  const percent =
    result !== null ? 100 : total > 0 ? Math.round((completed / total) * 100) : 0

  let statusText: string
  if (result !== null) {
    statusText = `Chronicle compression complete! Reduced by ${result.reduction_percentage}%`
  } else if (total > 0) {
    statusText = fromCache
      ? `Section ${completed} of ${total} (retrieved from memory)`
      : `Compressing section ${completed} of ${total}...`
  } else {
    statusText = `Compressing ${totalSections} chronicle sections...`
  }

  return (
    <div
      className="neq-card fixed bottom-4 right-4 z-40 w-80 p-4"
      role="status"
      aria-live="polite"
    >
      <h4 className="font-display text-sm text-accent">Chronicle Compression</h4>
      <p className="mt-1 font-body text-xs italic text-secondary">{flavor}</p>
      <div className="mt-3 h-2 overflow-hidden rounded bg-page">
        <div
          className="h-full rounded transition-all duration-300"
          style={{
            width: `${percent}%`,
            background:
              result !== null
                ? 'linear-gradient(90deg, var(--emerald-1), var(--emerald-2))'
                : 'var(--accent)',
          }}
        />
      </div>
      <p className="mt-2 font-log text-xs text-secondary">{statusText}</p>
    </div>
  )
}
