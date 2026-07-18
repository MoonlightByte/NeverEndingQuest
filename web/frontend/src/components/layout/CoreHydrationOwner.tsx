import { useEffect } from 'react'
import { emitC } from '../../services/socket'
import { useLog } from '../../stores'

export function refreshCoreHydration(): void {
  emitC('request_location_data', undefined)
  emitC('request_party_data', undefined)
  emitC('request_initiative_data', undefined)
}

/** Single mounted owner for periodic and log-driven shell hydration. */
export function CoreHydrationOwner() {
  useEffect(() => {
    refreshCoreHydration()
    const unsubscribe = useLog.subscribe((state, previous) => {
      if (state.messages !== previous.messages) refreshCoreHydration()
    })
    const timer = window.setInterval(refreshCoreHydration, 5000)
    return () => {
      unsubscribe()
      window.clearInterval(timer)
    }
  }, [])

  return null
}
