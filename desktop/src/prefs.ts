import type { WebPreferences } from 'electron'

export function lockedPreferences(preload?: string): WebPreferences {
  return { contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, preload }
}

// Same-origin popups (the /toolkit window): the same locks and never the game page's preload.
export function popupPreferences(): WebPreferences {
  return lockedPreferences()
}
