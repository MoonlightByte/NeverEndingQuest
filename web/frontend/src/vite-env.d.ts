/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Build-time edition flag: local = operator settings panel included. */
  readonly VITE_EDITION?: 'local' | 'hosted'
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
