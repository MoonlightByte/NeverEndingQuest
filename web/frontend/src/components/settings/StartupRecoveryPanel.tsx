import { useEffect, useState } from 'react'
import { useSession } from '../../stores'
import { emitC } from '../../services/socket'

/** Existing operator-token protected recovery, not a new start/reset action. */
export function StartupRecoveryPanel() {
  const status = useSession(s => s.startupStatus)
  const attempt = useSession(s => s.startupAttemptId)
  const connected = useSession(s => s.connected)
  const response = useSession(s => s.recovery)
  const [token, setToken] = useState('')
  const [pending, setPending] = useState(false)
  const [cooldown, setCooldown] = useState(0)
  const [notice, setNotice] = useState('')
  useEffect(() => { setToken(''); setPending(false) }, [attempt, connected])
  useEffect(() => {
    if (!response) return
    setPending(false)
    setCooldown(Math.max(0, response.retryAfterSeconds ?? 0))
    setNotice(`Recovery: ${response.status}${response.error ? ` (${response.error})` : ''}.`)
  }, [response])
  useEffect(() => {
    if (!pending) return
    const timer = window.setTimeout(() => { setPending(false); setNotice('No recovery response received. Check the connection before retrying.') }, 30000)
    return () => window.clearTimeout(timer)
  }, [pending])
  useEffect(() => {
    if (!cooldown) return
    const timer = window.setTimeout(() => setCooldown(value => Math.max(0, value - 1)), 1000)
    return () => window.clearTimeout(timer)
  }, [cooldown])
  if (status !== 'failed') return null
  const recover = () => {
    if (!connected || !attempt || !token.trim() || pending || cooldown) return
    emitC('action', { action: 'recover_startup_handoff', parameters: { recoveryToken: token, startupAttemptId: attempt } })
    setToken('')
    setPending(true)
    setNotice('Requesting startup recovery…')
  }
  return <section className="neq-settings-section" aria-label="Startup recovery"><div className="neq-settings-title">Startup recovery</div><p className="neq-settings-help-parity">The startup handoff failed. Recovery requires the operator token configured on this server; it does not reset your campaign.</p><div className="neq-settings-item neq-settings-stack-parity"><label htmlFor="startup-recovery-token">Recovery token</label><input id="startup-recovery-token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} /><button type="button" className="neq-settings-button-small-parity" onClick={recover} disabled={!connected || !attempt || !token.trim() || pending || cooldown > 0}>{pending ? 'Recovering…' : cooldown ? `Retry in ${cooldown}s` : 'Recover startup'}</button>{!connected && <p>Reconnect before requesting recovery.</p>}{!attempt && <p>Waiting for the server startup attempt identifier.</p>}{notice && <p role="status">{notice}</p>}</div></section>
}
