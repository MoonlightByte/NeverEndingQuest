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
  const hasCompleted = compression.result !== null || compression.error !== null

  // A new run starts: show the banner and pick a fresh flavor line.
  useEffect(() => {
    if (compression.running) {
      setVisible(true)
      setFlavor(FLAVOR_MESSAGES[Math.max(0, compression.totalSections - 1) % FLAVOR_MESSAGES.length])
    }
  }, [compression.running, compression.totalSections])

  // Run finished: keep the completion state on screen briefly, then hide.
  useEffect(() => {
    if (!compression.running && hasCompleted) {
      const timer = window.setTimeout(() => setVisible(false), HIDE_DELAY_MS)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [compression.running, hasCompleted])

  if (!visible) return null

  const { result, completed, total, totalSections, fromCache } = compression
  const percent =
    result !== null ? 100 : total > 0 ? Math.round((completed / total) * 100) : 0

  let statusText: string
  if (compression.error !== null) {
    statusText = `Chronicle compression failed: ${compression.error}`
  } else if (result !== null) {
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
      className="fixed left-1/2 top-1/2 z-[10000] min-w-[400px] -translate-x-1/2 -translate-y-1/2 rounded-lg border-[3px] border-[#FFA500] bg-[#1e1e1e] p-5 shadow-[0_4px_8px_rgba(0,0,0,.5)]"
      role="status"
      aria-live="polite"
    >
      <h4 className="mb-[10px] text-center font-display text-[18px] font-bold text-[#FFA500]">Chronicle Compression</h4>
      <p className="mb-[15px] text-center font-chrome text-sm italic leading-[1.4] text-primary">{flavor}</p>
      <div className="relative h-6 w-full overflow-hidden rounded-xl border-2 border-card bg-[#2a2a2a]">
        <div
          className="h-full rounded transition-all duration-300"
          style={{
            width: `${percent}%`,
            background: 'linear-gradient(90deg, #2d7a2d, #4CAF50, #5cbf5c)',
            boxShadow: '0 0 10px rgba(76,175,80,.5)',
          }}
        />
      </div>
      <p className="mt-[10px] text-center font-chrome text-xs text-[#b0b0b0]">{statusText}</p>
    </div>
  )
}
