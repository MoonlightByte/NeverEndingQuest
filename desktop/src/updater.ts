// Updates for the installed app (A4), kept free of electron so the kit rows can drive it.
// A downloaded update is offered only at a safe moment and installed only after the normal quit:
// /shutdown has ended the server and nothing from the install folder but the app itself is running.
import type { Health } from './serverSpawn'

export const OFFER_POLL_MS = 10_000
export const WAIT_RECHECK_MS = 2_000

// Only the installed tag release turns updates on (electron-builder.release.yml sets neqUpdates).
export function updatesEnabled(isPackaged: boolean, pkg: { neqUpdates?: unknown }): boolean {
  return isPackaged && pkg.neqUpdates === true
}

// Never mid-turn or while a save drains: offer on the start screen, or once a save has landed
// since the update was downloaded.
export function shouldOffer(health: Health, seqAtDownload: number | null): boolean {
  if (health.inFlight > 0 || health.backgroundPending > 0) return false
  if (health.atStart) return true
  return health.saveSeq !== null && seqAtDownload !== null && health.saveSeq > seqAtDownload
}

export interface RunningProcess {
  pid: number
  name: string
}

// "<pid> <name>" lines for processes under the install folder. The app's own processes are
// excluded: they exit as part of the install.
export function blockingProcesses(lines: string[], appExe: string): RunningProcess[] {
  const out: RunningProcess[] = []
  for (const line of lines) {
    const m = /^\s*(\d+)\s+(.+?)\s*$/.exec(line)
    if (m && m[2].toLowerCase() !== appExe.toLowerCase()) out.push({ pid: Number(m[1]), name: m[2] })
  }
  return out
}

export interface UpdaterDeps {
  enabled: boolean
  check(): void
  health(): Promise<Health | null>
  // true = Update and restart, false = Later.
  offer(version: string): Promise<boolean>
  requestQuit(): void
  // Processes under the install folder other than the app; null when they cannot be listed.
  installProcesses(): Promise<RunningProcess[] | null>
  // Keep waiting / Force quit; never decided by a timer.
  waiting(running: RunningProcess[]): Promise<'wait' | 'force'>
  kill(pids: number[]): void
  install(silent: boolean, runAfter: boolean): void
  exit(code: number): void
  schedule(fn: () => void, ms: number): void
  log(msg: string): void
}

export class Updater {
  downloadedVersion: string | null = null
  // 'restart' after Update and restart; otherwise a downloaded update installs on a plain Quit.
  private mode: 'restart' | 'on-quit' = 'on-quit'
  private seqAtDownload: number | null = null
  private exiting = false

  constructor(private readonly d: UpdaterDeps) {}

  // Once per launch.
  start(): void {
    if (!this.d.enabled) return
    this.d.log('update check')
    this.d.check()
  }

  async downloaded(version: string): Promise<void> {
    if (!this.d.enabled || this.downloadedVersion !== null) return
    this.downloadedVersion = version
    this.seqAtDownload = (await this.d.health())?.saveSeq ?? null
    this.d.log(`update ${version} downloaded save_seq=${this.seqAtDownload}`)
    this.pollOffer()
  }

  private pollOffer(): void {
    void this.d.health().then(async health => {
      // Quitting: no dialog over the closing app.
      if (this.exiting) return
      if (health === null || !shouldOffer(health, this.seqAtDownload)) {
        this.d.schedule(() => this.pollOffer(), OFFER_POLL_MS)
        return
      }
      // Offered once per launch: the poll stops here whatever the answer.
      const now = await this.d.offer(this.downloadedVersion ?? '')
      if (now && !this.exiting) {
        this.d.log('update and restart chosen')
        this.mode = 'restart'
        this.d.requestQuit()
      }
    })
  }

  // The lifecycle's exit: the server is gone. Installs only after a normal quit (not Force quit).
  async onExit(code: number, forced: boolean): Promise<void> {
    if (this.exiting) return
    this.exiting = true
    if (this.downloadedVersion === null || forced || code !== 0) {
      this.d.exit(code)
      return
    }
    for (;;) {
      const running = await this.d.installProcesses()
      if (running === null) {
        this.d.log('update not installed: install-folder processes could not be listed')
        this.d.exit(code)
        return
      }
      if (running.length === 0) break
      this.d.log(`update waiting for ${running.map(p => `${p.name}(${p.pid})`).join(', ')}`)
      const choice = await this.d.waiting(running)
      if (choice === 'force') this.d.kill(running.map(p => p.pid))
      await new Promise<void>(resolve => this.d.schedule(resolve, WAIT_RECHECK_MS))
    }
    const restart = this.mode === 'restart'
    this.d.log(`installing update ${this.downloadedVersion} restart=${restart}`)
    this.d.install(!restart, restart)
  }
}
