// Pure helpers for starting and talking to the game server. No electron import, so the kit rows
// can exercise them under plain node.
import { randomBytes } from 'node:crypto'
import * as path from 'node:path'
import { DEV_PYTHON_ENV, ENV_ALLOW, ENV_DROP, LOCAL_HOST, TOKEN_ENV } from './contract'

export interface Health {
  version: string
  ready: boolean
  inFlight: number
}

export interface ServerCommand {
  file: string
  args: string[]
  cwd: string
}

function validPort(n: unknown): number | null {
  return typeof n === 'number' && Number.isInteger(n) && n >= 1 && n <= 65535 ? n : null
}

// run/port body; a pid other than our child's means a stale file from an earlier run.
export function parsePortFile(body: string, childPid: number | undefined): number | null {
  let data: unknown
  try { data = JSON.parse(body) } catch { return null }
  if (!data || typeof data !== 'object') return null
  const { port, pid } = data as { port?: unknown, pid?: unknown }
  if (childPid === undefined || pid !== childPid) return null
  return validPort(port)
}

const PORT_LINE = /^NEQ_PORT=(\d{1,5})$/

// Stdout fallback: the server prints NEQ_PORT=<n> once bound; banner lines may come first.
export function parsePortLine(line: string): number | null {
  const m = PORT_LINE.exec(line.trim())
  return m ? validPort(Number(m[1])) : null
}

export function parseHealth(body: string): Health | null {
  let data: unknown
  try { data = JSON.parse(body) } catch { return null }
  if (!data || typeof data !== 'object') return null
  const { version, ready, in_flight: inFlight } = data as { version?: unknown, ready?: unknown, in_flight?: unknown }
  if (typeof version !== 'string' || typeof ready !== 'boolean') return null
  if (typeof inFlight !== 'number' || !Number.isInteger(inFlight) || inFlight < 0) return null
  return { version, ready, inFlight }
}

// Splits a byte stream into lines without ever holding more than maxLen characters of one line,
// so a runaway line cannot grow memory and the pipe is always drained.
export class LineSplitter {
  private buf = ''
  private skipping = false
  constructor(private readonly maxLen = 4096) {}

  push(chunk: string): string[] {
    const out: string[] = []
    let rest = chunk
    while (rest.length) {
      const nl = rest.indexOf('\n')
      const piece = nl === -1 ? rest : rest.slice(0, nl)
      rest = nl === -1 ? '' : rest.slice(nl + 1)
      if (!this.skipping) {
        this.buf += piece
        if (this.buf.length > this.maxLen) {
          out.push(this.buf.slice(0, this.maxLen))
          this.buf = ''
          this.skipping = true
        }
      }
      if (nl !== -1) {
        if (!this.skipping) out.push(this.buf.replace(/\r$/, ''))
        this.buf = ''
        this.skipping = false
      }
    }
    return out
  }
}

export function childEnv(parent: NodeJS.ProcessEnv, token: string): NodeJS.ProcessEnv {
  const allow = new Set<string>(ENV_ALLOW)
  const drop = new Set<string>(ENV_DROP)
  const env: NodeJS.ProcessEnv = {}
  for (const [key, value] of Object.entries(parent)) {
    if (value === undefined) continue
    const upper = key.toUpperCase()
    if (allow.has(upper) || (upper.startsWith('NEQ_') && !drop.has(upper))) env[key] = value
  }
  env.NEQ_DESKTOP = '1'
  env[TOKEN_ENV] = token
  env.PYTHONUNBUFFERED = '1'
  return env
}

export function devPython(parent: NodeJS.ProcessEnv): string {
  return parent[DEV_PYTHON_ENV] || (process.platform === 'win32' ? 'python' : 'python3')
}

export function serverCommand(opts: {
  packaged: boolean
  resourcesPath: string
  repoRoot: string
  dataDir: string
  python: string
}): ServerCommand {
  const flags = ['--no-browser', '--port', '0', '--data-dir', opts.dataDir]
  if (opts.packaged) {
    return { file: path.join(opts.resourcesPath, 'server', 'run_web.exe'), args: flags, cwd: opts.dataDir }
  }
  // --serve runs the server in-process (one interpreter), as the frozen build does.
  return { file: opts.python, args: [path.join(opts.repoRoot, 'run_web.py'), '--serve', ...flags], cwd: opts.repoRoot }
}

export function newToken(): string {
  return randomBytes(32).toString('hex')
}

export function localOrigin(port: number): string {
  return `http://${LOCAL_HOST}:${port}`
}

export type UrlClass = 'local' | 'external' | 'deny'

export function classifyUrl(url: string, origin: string): UrlClass {
  let u: URL
  try { u = new URL(url) } catch { return 'deny' }
  if (u.protocol !== 'http:' && u.protocol !== 'https:') return 'deny'
  return u.origin === origin ? 'local' : 'external'
}

// The token goes only to our own server: http or ws on 127.0.0.1 at the current port.
export function wantsToken(url: string, port: number | null): boolean {
  if (port === null) return false
  let u: URL
  try { u = new URL(url) } catch { return false }
  return (u.protocol === 'http:' || u.protocol === 'ws:') && u.hostname === LOCAL_HOST && u.port === String(port)
}

export function isToolkitPath(pathname: string): boolean {
  return pathname === '/toolkit' || pathname.startsWith('/toolkit/')
}

// /toolkit keeps its inline script block and onclick handlers; everything else is strict.
// socket.io for the toolkit is served locally (A1.5), so no CDN origin appears anywhere.
export function cspFor(pathname: string, port: number): string {
  const script = isToolkitPath(pathname) ? "'self' 'unsafe-inline'" : "'self'"
  return [
    "default-src 'self'",
    `script-src ${script}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "font-src 'self'",
    `connect-src 'self' ws://${LOCAL_HOST}:${port}`,
    "object-src 'none'",
    "base-uri 'none'",
    "frame-ancestors 'none'",
  ].join('; ')
}

export function forceKillCommand(pid: number, platform: NodeJS.Platform): { file: string, args: string[] } | null {
  if (platform === 'win32') return { file: 'taskkill', args: ['/PID', String(pid), '/T', '/F'] }
  return null
}
