/**
 * Debug tab (plan Task 4.4d): TPM / RPM / total token counters
 * (token_update) above the scrolling debug_output ring, both from the log
 * store. Mirrors the legacy #debug-tab token-usage-header + debug-scrollable.
 */
import { useEffect, useRef } from 'react'
import { useLog } from '../../stores'

export function DebugTab() {
  const debug = useLog((s) => s.debug)
  const tokens = useLog((s) => s.tokens)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Pin the ring to the newest entry.
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [debug.length])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b-2 border-card px-3 py-2 font-log text-xs text-secondary">
        <span>
          TPM: <span className="text-accent">{tokens.tpm.toLocaleString()}</span>
        </span>
        <span className="px-2 text-soft">|</span>
        <span>
          RPM: <span className="text-accent">{tokens.rpm.toLocaleString()}</span>
        </span>
        <span className="px-2 text-soft">|</span>
        <span>
          Total: <span className="text-accent">{tokens.total_tokens.toLocaleString()}</span>
        </span>
      </div>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto p-3 font-log text-xs">
        {debug.length === 0 ? (
          <p className="text-secondary">No debug output yet.</p>
        ) : (
          debug.map((entry, i) => (
            <p key={i} className="mb-1 whitespace-pre-wrap break-words text-secondary">
              <span className="text-soft">[{entry.timestamp}]</span> {entry.content}
            </p>
          ))
        )}
      </div>
    </div>
  )
}
