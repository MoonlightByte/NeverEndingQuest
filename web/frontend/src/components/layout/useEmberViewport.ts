import { useSyncExternalStore } from 'react'

// Preserve the current public small-screen shell pending its separate review.
// A media-query subscription changes layout without duplicating hydration owners.
const query = '(min-width: 1024px)'
const snapshot = () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches
function subscribe(notify: () => void) {
  if (typeof window.matchMedia !== 'function') return () => {}
  const media = window.matchMedia(query)
  media.addEventListener('change', notify)
  return () => media.removeEventListener('change', notify)
}
export const useEmberViewport = () => useSyncExternalStore(subscribe, snapshot, () => false)
