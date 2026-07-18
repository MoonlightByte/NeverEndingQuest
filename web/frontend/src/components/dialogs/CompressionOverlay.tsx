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
      setFlavor(FLAVOR_MESSAGES[Math.floor(Math.random() * FLAVOR_MESSAGES.length)])
    }
  }, [compression.running, compression.totalSections])

  // Run finished: keep the completion state on screen briefly, then hide.
  useEffect(() => {
    if (!compression.running && hasCompleted) {
      // A completion/error can be restored from ui_state_snapshot after a
      // reconnect without this tab ever seeing compression_start. Surface the
      // terminal result briefly instead of silently scheduling a hide for an
      // overlay that was never made visible.
      setVisible(true)
      const timer = window.setTimeout(() => setVisible(false), HIDE_DELAY_MS)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [compression.running, hasCompleted])

  if (!visible) return null

  const { result, completed, total, totalSections, fromCache } = compression
  const failed = compression.error !== null
  const complete = result !== null
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
      className={`neq-compression-progress-parity${complete ? ' complete' : ''}${failed ? ' failed' : ''}`}
      role="status"
      aria-live="polite"
    >
      <div className="neq-compression-title-parity">Chronicle Compression</div>
      <div className="neq-compression-text-parity">{flavor}</div>
      <div className="neq-compression-bar-track-parity">
        <div
          className={`neq-compression-bar-parity${complete ? ' complete' : ''}${failed ? ' failed' : ''}`}
          style={{
            width: `${percent}%`,
          }}
        />
      </div>
      <div className="neq-compression-status-parity">{statusText}</div>
    </div>
  )
}
