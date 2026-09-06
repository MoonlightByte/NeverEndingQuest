import { useEffect, useSyncExternalStore } from 'react'

type ReferenceState = { data: Record<string, Record<string, unknown>>; status: 'loading' | 'ready' | 'error' }
let snapshot: ReferenceState = { data: {}, status: 'loading' }
let request: Promise<void> | null = null
const listeners = new Set<() => void>()
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener) } }
function load() {
  if (request) return
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  snapshot = { ...snapshot, status: 'loading' }; listeners.forEach(listener => listener())
  request = fetch('/spell-data', { signal: controller.signal }).then(async response => {
    if (!response.ok) throw new Error('Spell reference unavailable')
    const data: unknown = await response.json()
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid spell reference')
    snapshot = { data: data as ReferenceState['data'], status: 'ready' }
  }).catch(() => { snapshot = { data: {}, status: 'error' } }).finally(() => {
    clearTimeout(timeout)
    request = null; listeners.forEach(listener => listener())
  })
}
export function useSpellReference() {
  const state = useSyncExternalStore(subscribe, () => snapshot)
  useEffect(() => { if (snapshot.status === 'loading' && !request) load() }, [])
  return { ...state, retry: load }
}
