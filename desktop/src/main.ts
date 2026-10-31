import { app, BrowserWindow, dialog, ipcMain, Menu, shell } from 'electron'
import { spawn } from 'node:child_process'
import * as fs from 'node:fs'
import * as http from 'node:http'
import * as path from 'node:path'
import { HEALTH_PATH, LAST_PORT_FILE_PARTS, LOCAL_HOST, PORT_FILE_PARTS, SHUTDOWN_PATH, TOKEN_HEADER } from './contract'
import { Lifecycle, type ChildHandle, type Status } from './lifecycle'
import { buildMenu } from './menu'
import { lockedPreferences } from './prefs'
import { installSecurity } from './security'
import { childEnv, devPython, forceKillCommand, LineSplitter, newToken, serverCommand } from './serverSpawn'
import { statusPageUrl } from './statusPage'

const dataDir = path.join(app.getPath('appData'), 'NeverEndingQuest')
const logsDir = path.join(dataDir, 'logs')
const portFile = path.join(dataDir, ...PORT_FILE_PARTS)
const lastPortFile = path.join(dataDir, ...LAST_PORT_FILE_PARTS)
const desktopLog = path.join(logsDir, 'desktop.log')
const serverLog = path.join(logsDir, 'server.log')
const repoRoot = path.resolve(__dirname, '..', '..')
const LOG_ROTATE_BYTES = 5 * 1024 * 1024

// Chromium's own profile lives in a subfolder so it never mixes with saves at the data root.
app.setPath('userData', path.join(dataDir, 'desktop'))

function rotate(file: string): void {
  try {
    if (fs.statSync(file).size > LOG_ROTATE_BYTES) fs.renameSync(file, `${file}.1`)
  } catch { /* no log yet */ }
}

function log(msg: string): void {
  try { fs.appendFileSync(desktopLog, `${new Date().toISOString()} ${msg}\n`) } catch { /* logging never stops the app */ }
}

function request(method: 'GET' | 'POST', port: number, urlPath: string, token: string): Promise<{ status: number, body: string } | null> {
  return new Promise(resolve => {
    const req = http.request({ host: LOCAL_HOST, port, path: urlPath, method, headers: { [TOKEN_HEADER]: token }, timeout: 5000 }, res => {
      let body = ''
      res.setEncoding('utf8')
      res.on('data', chunk => { if (body.length < 65536) body += chunk })
      res.on('end', () => resolve({ status: res.statusCode ?? 0, body }))
      res.on('error', () => resolve(null))
    })
    req.on('timeout', () => req.destroy())
    req.on('error', () => resolve(null))
    req.end()
  })
}

let mainWindow: BrowserWindow | null = null
let statusWindow: BrowserWindow | null = null
let exiting = false

function spawnServer(token: string, port: number | null): ChildHandle {
  const cmd = serverCommand({
    packaged: app.isPackaged,
    resourcesPath: process.resourcesPath,
    repoRoot,
    dataDir,
    python: devPython(process.env),
    port,
  })
  const env = childEnv(process.env, token)
  // Argv and env key names only; values (the token above all) never reach a log.
  log(`spawn ${cmd.file} ${cmd.args.join(' ')} env-keys=${Object.keys(env).sort().join(',')}`)
  rotate(serverLog)
  const out = fs.createWriteStream(serverLog, { flags: 'a' })
  const child = spawn(cmd.file, cmd.args, { cwd: cmd.cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  const splitter = new LineSplitter()
  const lineCbs: ((line: string) => void)[] = []
  const exitCbs: ((code: number | null) => void)[] = []
  child.stdout.setEncoding('utf8')
  child.stdout.on('data', (chunk: string) => {
    out.write(chunk)
    for (const line of splitter.push(chunk)) for (const cb of lineCbs) cb(line)
  })
  child.stderr.on('data', chunk => out.write(chunk))
  let exited = false
  const fireExit = (code: number | null) => {
    if (exited) return
    exited = true
    out.end()
    for (const cb of exitCbs) cb(code)
  }
  child.on('exit', code => fireExit(code))
  child.on('error', err => {
    log(`spawn failed: ${err.message}`)
    fireExit(null)
  })
  return {
    pid: child.pid,
    onExit: cb => exitCbs.push(cb),
    onStdoutLine: cb => lineCbs.push(cb),
  }
}

function forceKill(pid: number): void {
  const cmd = forceKillCommand(pid, process.platform)
  if (cmd) {
    spawn(cmd.file, cmd.args, { windowsHide: true, stdio: 'ignore' }).on('error', err => log(`taskkill failed: ${err.message}`))
  } else {
    try { process.kill(pid, 'SIGKILL') } catch (err) { log(`kill failed: ${String(err)}`) }
  }
}

function showStatus(kind: Status, elapsed: number): void {
  if (!statusWindow || statusWindow.isDestroyed()) {
    statusWindow = new BrowserWindow({ width: 520, height: 280, resizable: false, show: false, title: 'NeverEndingQuest', webPreferences: lockedPreferences() })
    statusWindow.on('close', event => {
      if (!exiting && lifecycle.requestQuit()) event.preventDefault()
    })
    statusWindow.once('ready-to-show', () => statusWindow?.show())
  }
  void statusWindow.loadURL(statusPageUrl(kind, elapsed))
  if (kind.startsWith('closing') && mainWindow && !mainWindow.isDestroyed()) mainWindow.hide()
  if (statusWindow.isVisible()) statusWindow.focus()
}

function showGame(url: string): void {
  if (!mainWindow || mainWindow.isDestroyed()) {
    mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      show: false,
      title: 'NeverEndingQuest',
      webPreferences: lockedPreferences(path.join(__dirname, 'preload.js')),
    })
    // Only the game window's close quits; the /toolkit popup closes on its own.
    mainWindow.on('close', event => {
      if (!exiting && lifecycle.requestQuit()) event.preventDefault()
    })
    // Windows logoff or shutdown: ask the server to save; the OS sets the deadline from here.
    mainWindow.on('session-end', () => { lifecycle.requestQuit() })
    mainWindow.once('ready-to-show', () => {
      mainWindow?.show()
      if (statusWindow && !statusWindow.isDestroyed()) statusWindow.hide()
    })
  }
  void mainWindow.loadURL(url)
}

async function serverDialog(message: string): Promise<void> {
  for (;;) {
    const { response } = await dialog.showMessageBox({
      type: 'error',
      title: 'NeverEndingQuest',
      message,
      detail: `The log is in ${logsDir}`,
      buttons: ['Restart', 'Open logs', 'Quit'],
      defaultId: 0,
      cancelId: 2,
    })
    if (response === 0) {
      lifecycle.restart()
      return
    }
    if (response === 1) {
      await shell.openPath(logsDir)
      continue
    }
    exitApp(0)
    return
  }
}

function exitApp(code: number): void {
  exiting = true
  app.exit(code)
}

const lifecycle = new Lifecycle({
  newToken,
  deletePortFile: () => fs.rmSync(portFile, { force: true }),
  readPortFile: () => {
    try { return fs.readFileSync(portFile, 'utf8') } catch { return null }
  },
  readLastPort: () => {
    try {
      return { kind: 'text', body: fs.readFileSync(lastPortFile, 'utf8') }
    } catch (err) {
      return (err as NodeJS.ErrnoException).code === 'ENOENT' ? { kind: 'missing' } : { kind: 'unreadable' }
    }
  },
  writeLastPort: port => {
    try {
      fs.writeFileSync(`${lastPortFile}.tmp`, `${port}\n`)
      fs.renameSync(`${lastPortFile}.tmp`, lastPortFile)
    } catch (err) {
      log(`last-port not saved: ${String(err)}`)
    }
  },
  spawnServer,
  getHealth: async (port, token) => {
    const res = await request('GET', port, HEALTH_PATH, token)
    return res && res.status === 200 ? res.body : null
  },
  postShutdown: async (port, token) => {
    const res = await request('POST', port, SHUTDOWN_PATH, token)
    return res !== null && res.status >= 200 && res.status < 300
  },
  forceKill,
  schedule: (fn, ms) => { setTimeout(fn, ms) },
  now: () => Date.now(),
  log,
  ui: {
    status: showStatus,
    showGame,
    startFailed: () => void serverDialog("NeverEndingQuest's game server could not start."),
    serverStopped: () => {
      if (mainWindow && !mainWindow.isDestroyed()) mainWindow.hide()
      void serverDialog("NeverEndingQuest's game server stopped.")
    },
    exit: exitApp,
  },
})

if (!app.requestSingleInstanceLock()) {
  app.exit(0)
} else {
  app.on('second-instance', () => {
    const win = mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible() ? mainWindow : statusWindow
    if (win && !win.isDestroyed()) {
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
    }
  })

  // Windows closing on their own (the toolkit popup, the status window hiding) never ends the app.
  app.on('window-all-closed', () => { /* the lifecycle decides when to exit */ })

  app.on('before-quit', event => {
    if (exiting) return
    if (lifecycle.requestQuit()) event.preventDefault()
  })

  void app.whenReady().then(() => {
    for (const dir of [dataDir, logsDir, path.dirname(portFile)]) fs.mkdirSync(dir, { recursive: true })
    rotate(desktopLog)
    log(`desktop ${app.getVersion()} start packaged=${app.isPackaged}`)

    installSecurity({ port: () => lifecycle.port, token: () => lifecycle.token })

    const fromGamePage = (event: Electron.IpcMainInvokeEvent) =>
      mainWindow !== null && event.sender === mainWindow.webContents
      && event.senderFrame !== null && new URL(event.senderFrame.url).pathname.startsWith('/play/')
    ipcMain.handle('neq:open-data-folder', event => { if (fromGamePage(event)) void shell.openPath(dataDir) })
    ipcMain.handle('neq:open-logs', event => { if (fromGamePage(event)) void shell.openPath(logsDir) })

    Menu.setApplicationMenu(buildMenu({
      dataDir,
      logsDir,
      serverVersion: () => lifecycle.serverVersion,
      quit: () => { lifecycle.requestQuit() },
      forceQuit: () => lifecycle.forceQuit(),
      closing: () => lifecycle.phase === 'quitting',
    }))

    lifecycle.start()
  })
}
