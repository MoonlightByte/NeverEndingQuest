/**
 * Debug tab (plan Task 4.4d): TPM / RPM / total token counters
 * (token_update) above the scrolling debug_output ring, both from the log
 * store. Mirrors the legacy #debug-tab token-usage-header + debug-scrollable.
 */
import { useEffect, useRef } from 'react'
import { useLog } from '../../stores'
import './DebugTab.css'

function formatTimestamp(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString()
}

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
    <div className="neq-debug-tab">
      <div className="neq-token-usage-header">
        <div className="neq-token-stats">
          <span className="neq-token-label">TPM:</span> <span className="neq-token-value">{tokens.tpm.toLocaleString()}</span>
          <span className="neq-token-separator">|</span>
          <span className="neq-token-label">RPM:</span> <span className="neq-token-value">{tokens.rpm.toLocaleString()}</span>
          <span className="neq-token-separator">|</span>
          <span className="neq-token-label">Total:</span> <span className="neq-token-value">{tokens.total_tokens.toLocaleString()}</span>
        </div>
      </div>
      <div ref={scrollRef} className="neq-debug-scrollable">
        {debug.length === 0 ? null : (
          debug.map((entry, i) => (
            <div key={i} className="neq-debug-message">
              <div className="neq-debug-message-content">
                {entry.timestamp && (
                  <span className="neq-debug-timestamp">{formatTimestamp(entry.timestamp)}</span>
                )}
                <div className="neq-debug-message-text">{entry.content}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
