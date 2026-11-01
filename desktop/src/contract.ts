// Server contract shared with the A1.2 server flags (ELECTRON-PACKAGING-PLAN r2, "Contract fixed").
// Changing a value here means the server side changes with it.

export const TOKEN_HEADER = 'X-NEQ-Local-Token'
export const TOKEN_ENV = 'NEQ_LOCAL_TOKEN'
export const HEALTH_PATH = '/health'
export const SHUTDOWN_PATH = '/shutdown'
export const PLAY_PATH = '/play/'
export const LOCAL_HOST = '127.0.0.1'

// <data root>/run/port, body {"port": n, "pid": n}, written temp + rename by the server.
export const PORT_FILE_PARTS = ['run', 'port'] as const

// <data root>/run/last-port: the port of the last run, passed back as --port-or-free so the game's origin
// (and with it the page's localStorage settings) stays the same across launches. Written by the shell.
export const LAST_PORT_FILE_PARTS = ['run', 'last-port'] as const
export const DEFAULT_PORT = 8357

// Copied from the parent environment when present (matched upper-cased; Windows names are case-insensitive).
export const ENV_ALLOW = [
  'PATH', 'SYSTEMROOT', 'SYSTEMDRIVE', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TEMP',
  'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'USERNAME', 'PROCESSOR_ARCHITECTURE', 'NUMBER_OF_PROCESSORS',
] as const

// NEQ_* names that are never inherited: the shell sets its own or they would change where the server listens.
export const ENV_DROP = [
  'NEQ_WEB_HOST', 'NEQ_START_PATH', 'NEQ_DATA_DIR', 'NEQ_LOCAL_TOKEN', 'NEQ_DESKTOP', 'NEQ_DESKTOP_PYTHON',
] as const

// Dev-only switch (owner mandate D-A0-6, Electron shell): absolute path of the python that runs run_web.py
// from a source checkout. Read by the shell only; never passed to the child.
export const DEV_PYTHON_ENV = 'NEQ_DESKTOP_PYTHON'
