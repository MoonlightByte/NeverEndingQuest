// Locks applied to every webContents the app creates (main window, status window, the /toolkit
// popup and anything it opens), plus the session-wide token, CSP and permission handlers.
import { app, BrowserWindow, session, shell, type WebContents } from 'electron'
import { TOKEN_HEADER } from './contract'
import { popupPreferences } from './prefs'
import { classifyUrl, cspFor, localOrigin, wantsToken } from './serverSpawn'

export interface ServerRef {
  port(): number | null
  token(): string
}

const namedChildren = new Map<string, BrowserWindow>()

function currentOrigin(server: ServerRef): string | null {
  const port = server.port()
  return port === null ? null : localOrigin(port)
}

function lockContents(wc: WebContents, server: ServerRef): void {
  const onNavigate = (event: Electron.Event, url: string) => {
    const origin = currentOrigin(server)
    const kind = origin === null ? 'deny' : classifyUrl(url, origin)
    if (kind === 'local') return
    event.preventDefault()
    if (kind === 'external') void shell.openExternal(url)
  }
  wc.on('will-navigate', onNavigate)
  wc.on('will-redirect', onNavigate)
  wc.on('will-attach-webview', event => event.preventDefault())

  wc.setWindowOpenHandler(({ url, frameName }) => {
    const origin = currentOrigin(server)
    const kind = origin === null ? 'deny' : classifyUrl(url, origin)
    if (kind === 'external') {
      void shell.openExternal(url)
      return { action: 'deny' }
    }
    if (kind !== 'local') return { action: 'deny' }
    const existing = frameName ? namedChildren.get(frameName) : undefined
    if (existing && !existing.isDestroyed()) {
      existing.focus()
      return { action: 'deny' }
    }
    return { action: 'allow', overrideBrowserWindowOptions: { autoHideMenuBar: true, webPreferences: popupPreferences() } }
  })

  wc.on('did-create-window', (child, { frameName }) => {
    if (!frameName) return
    namedChildren.set(frameName, child)
    child.on('closed', () => {
      if (namedChildren.get(frameName) === child) namedChildren.delete(frameName)
    })
  })
}

export function installSecurity(server: ServerRef): void {
  app.on('web-contents-created', (_event, wc) => lockContents(wc, server))

  const ses = session.defaultSession
  ses.setPermissionRequestHandler((_wc, permission, callback) => callback(permission === 'clipboard-sanitized-write'))
  ses.setPermissionCheckHandler((_wc, permission) => permission === 'clipboard-sanitized-write')

  ses.webRequest.onBeforeSendHeaders((details, callback) => {
    const headers = { ...details.requestHeaders }
    if (wantsToken(details.url, server.port())) headers[TOKEN_HEADER] = server.token()
    else delete headers[TOKEN_HEADER]
    callback({ requestHeaders: headers })
  })

  ses.webRequest.onHeadersReceived((details, callback) => {
    const port = server.port()
    if (port === null || classifyUrl(details.url, localOrigin(port)) !== 'local') {
      callback({})
      return
    }
    const headers = { ...details.responseHeaders }
    for (const key of Object.keys(headers)) {
      if (key.toLowerCase() === 'content-security-policy') delete headers[key]
    }
    headers['Content-Security-Policy'] = [cspFor(new URL(details.url).pathname, port)]
    callback({ responseHeaders: headers })
  })
}
