// Start, quit and restart of the game server, kept free of electron so the kit rows can drive it.
// Nothing here kills the server on a clock: only the child exiting or the player's Force quit ends it.
import { localOrigin, parseHealth, parsePortFile, parsePortLine, preferredPort, type Health, type LastPortRead } from './serverSpawn'

export interface ChildHandle {
  pid: number | undefined
  onExit(cb: (code: number | null) => void): void
  onStdoutLine(cb: (line: string) => void): void
}

export type Status = 'starting' | 'reloading' | 'still-starting' | 'closing-starting' | 'closing' | 'closing-turn' | 'closing-unanswered'

export interface Ui {
  status(kind: Status, elapsedSeconds: number): void
  showGame(url: string): void
  startFailed(): void
  serverStopped(): void
  exit(code: number): void
}

export interface Deps {
  newToken(): string
  deletePortFile(): void
  readPortFile(): string | null
  readLastPort(): LastPortRead
  writeLastPort(port: number): void
  spawnServer(token: string, port: number | null): ChildHandle
  getHealth(port: number, token: string): Promise<string | null>
  postShutdown(port: number, token: string): Promise<boolean>
  forceKill(pid: number): void
  schedule(fn: () => void, ms: number): void
  now(): number
  log(msg: string): void
  ui: Ui
}

type Phase = 'idle' | 'starting' | 'ready' | 'quitting' | 'stopped' | 'exited'

export const POLL_MS = 250
export const HEALTH_POLL_MS = 500
export const SLOW_START_MS = 30_000

export class Lifecycle {
  phase: Phase = 'idle'
  port: number | null = null
  token = ''
  serverVersion = ''
  private child: ChildHandle | null = null
  private childAlive = false
  private quitRequested = false
  private generation = 0
  private startedAt = 0
  // Set while a server that exited 0 on its own (Load or Reset, D-A1-2) is being started again.
  private relaunching = false

  constructor(private readonly d: Deps) {}

  // Also the Restart path: every start deletes run/port and mints a new token before spawning.
  start(): void {
    this.token = this.d.newToken()
    this.relaunching = false
    this.spawn()
  }

  // A Load or Reset ends the server with exit 0 and expects it back: same token, same root, last port.
  private relaunch(): void {
    this.relaunching = true
    this.spawn()
  }

  private spawn(): void {
    const gen = ++this.generation
    this.port = null
    this.d.deletePortFile()
    const child = this.d.spawnServer(this.token, preferredPort(this.d.readLastPort()))
    this.child = child
    this.childAlive = true
    this.phase = 'starting'
    this.startedAt = this.d.now()
    this.d.log(`server spawned pid=${child.pid}${this.relaunching ? ' (relaunch after exit 0)' : ''}`)
    this.d.ui.status(this.relaunching ? 'reloading' : 'starting', 0)
    child.onStdoutLine(line => {
      if (gen === this.generation && this.port === null) {
        const port = parsePortLine(line)
        if (port !== null) this.port = port
      }
    })
    child.onExit(code => this.onChildExit(gen, code))
    this.d.schedule(() => this.slowNotice(gen), SLOW_START_MS)
    this.d.schedule(() => void this.pollStart(gen), POLL_MS)
  }

  private slowNotice(gen: number): void {
    if (gen !== this.generation || this.phase !== 'starting' || this.quitRequested) return
    this.d.ui.status('still-starting', this.elapsed())
    this.d.schedule(() => this.slowNotice(gen), 5_000)
  }

  private elapsed(): number {
    return Math.round((this.d.now() - this.startedAt) / 1000)
  }

  private async pollStart(gen: number): Promise<void> {
    if (gen !== this.generation || this.phase !== 'starting') return
    if (this.port === null) {
      const body = this.d.readPortFile()
      if (body !== null) {
        const port = parsePortFile(body, this.child?.pid)
        if (port !== null) this.port = port
      }
    }
    let health: Health | null = null
    if (this.port !== null) {
      const body = await this.d.getHealth(this.port, this.token)
      health = body === null ? null : parseHealth(body)
    }
    if (gen !== this.generation || this.phase !== 'starting') return
    if (health && health.ready && this.port !== null) {
      this.serverVersion = health.version
      this.phase = 'ready'
      this.relaunching = false
      this.d.log(`server ready port=${this.port} version=${health.version}`)
      this.d.writeLastPort(this.port)
      if (this.quitRequested) {
        void this.shutdown()
      } else {
        this.d.ui.showGame(`${localOrigin(this.port)}/play/`)
      }
      return
    }
    this.d.schedule(() => void this.pollStart(gen), this.port === null ? POLL_MS : HEALTH_POLL_MS)
  }

  private onChildExit(gen: number, code: number | null): void {
    if (gen !== this.generation) return
    this.childAlive = false
    this.d.log(`server exited code=${code}`)
    if (this.quitRequested) {
      this.phase = 'exited'
      this.d.ui.exit(0)
    } else if (this.phase === 'ready' && code === 0) {
      // Not our /shutdown: a Load or Reset asking to be relaunched. A relaunched server that then
      // exits before it is ready falls through to the start-failed dialog below.
      this.relaunch()
    } else if (this.phase === 'starting') {
      this.phase = 'stopped'
      this.d.ui.startFailed()
    } else if (this.phase === 'ready') {
      this.phase = 'stopped'
      this.d.ui.serverStopped()
    }
  }

  // Main window close or menu Quit. Returns true while the shell is still closing.
  requestQuit(): boolean {
    if (this.phase === 'exited') return false
    if (this.quitRequested) return true
    this.quitRequested = true
    if (!this.childAlive) {
      this.phase = 'exited'
      this.d.ui.exit(0)
      return false
    }
    if (this.phase === 'starting') {
      // No port or no ready server yet: wait for ready, then take the normal shutdown path.
      this.d.ui.status('closing-starting', this.elapsed())
      return true
    }
    void this.shutdown()
    return true
  }

  forceQuit(): void {
    this.d.log('force quit requested by the player')
    this.quitRequested = true
    if (!this.childAlive || this.child?.pid === undefined) {
      this.phase = 'exited'
      this.d.ui.exit(0)
      return
    }
    this.d.forceKill(this.child.pid)
  }

  private async shutdown(): Promise<void> {
    if (this.port === null) return
    this.phase = 'quitting'
    this.d.ui.status('closing', 0)
    const ok = await this.d.postShutdown(this.port, this.token)
    this.d.log(`shutdown requested ok=${ok}`)
    this.watchClosing(this.generation)
  }

  // Shows what the server is doing while it closes; never ends it.
  private watchClosing(gen: number): void {
    if (gen !== this.generation || !this.childAlive || this.port === null) return
    const port = this.port
    void this.d.getHealth(port, this.token).then(body => {
      if (gen !== this.generation || !this.childAlive) return
      const health = body === null ? null : parseHealth(body)
      if (health === null) this.d.ui.status('closing-unanswered', 0)
      else this.d.ui.status(health.inFlight > 0 ? 'closing-turn' : 'closing', 0)
      this.d.schedule(() => this.watchClosing(gen), HEALTH_POLL_MS)
    })
  }

  // Restart from the crash dialog: same steps as a first start.
  restart(): void {
    if (this.childAlive) return
    this.quitRequested = false
    this.start()
  }
}
