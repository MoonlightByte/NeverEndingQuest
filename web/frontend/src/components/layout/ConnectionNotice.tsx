import { useEffect } from 'react'
import { useConnectionNotice } from '../../stores/connectionNotices'

/** Transport notices are temporary UI, never campaign history. */
export function ConnectionNotice() {
  const { text, revision, clear } = useConnectionNotice()
  useEffect(() => {
    if (!text) return
    const timer = window.setTimeout(clear, 8000)
    return () => window.clearTimeout(timer)
  }, [text, revision, clear])
  if (!text) return null
  return <div role="status" style={{ position: 'fixed', top: 'max(8px, env(safe-area-inset-top))', left: '50%', transform: 'translateX(-50%)', width: 'min(90vw, 480px)', zIndex: 10000, display: 'flex', alignItems: 'center', gap: 12, padding: 12, border: '1px solid #a98c59', borderRadius: 8, background: '#252118', color: '#f4e1be', fontSize: 15, boxShadow: '0 4px 18px #0008' }}>
    <span style={{ flex: 1 }}>{text}</span><button type="button" aria-label="Dismiss notification" onClick={clear} style={{ minWidth: 44, minHeight: 44 }}>×</button>
  </div>
}
