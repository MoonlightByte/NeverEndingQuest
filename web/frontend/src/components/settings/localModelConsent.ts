import { useState } from 'react'
import { useDialogs } from '../../stores'

export const LOCAL_CONSENT_VERSION = 'local-model-alpha-1'
const LOCAL_DISCLAIMER = 'Local models vary widely in capability and safeguards. They may produce inappropriate or unreliable content, misunderstand game rules, or behave unpredictably. This integration is experimental and still in development. I understand these limitations and want to enable a local model.'


export function useLocalModelConsent() {
  const settings = useDialogs((s) => s.settings)
  const [localAcknowledged, setLocalAcknowledged] = useState(false)
  const confirmLocalModel = () => {
    const accepted = localAcknowledged || (settings.localEndpoint?.consent_version === LOCAL_CONSENT_VERSION && settings.localEndpoint.consent_accepted)
    if (!accepted && !window.confirm(LOCAL_DISCLAIMER)) return false
    setLocalAcknowledged(true)
    return true
  }
  return confirmLocalModel
}
