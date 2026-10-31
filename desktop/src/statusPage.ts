// Static status pages for the small status window (starting, closing). No script, no links:
// Open logs and Force quit live in the app menu and native dialogs.
import type { Status } from './lifecycle'

const TEXT: Record<Status, (s: number) => [string, string]> = {
  'starting': () => ['Starting NeverEndingQuest...', 'Getting the game server ready.'],
  'reloading': () => ['Loading...', 'The game server is restarting to load your game.'],
  'still-starting': s => ['Still starting...', `${s} s so far. The first run sets up your saves folder, which can take a while. Game > Open logs shows progress.`],
  'closing-starting': () => ['Starting, will close when ready', 'The game server is still starting. It will close as soon as it is ready. Game > Force quit stops it now.'],
  'closing': () => ['Saving and closing...', 'The game is saving.'],
  'closing-turn': () => ['Finishing your turn...', 'The game will close as soon as the current turn is saved. Game > Force quit stops it now.'],
  'closing-unanswered': () => ['Closing...', 'The game server is not answering yet. Keep waiting, or use Game > Force quit.'],
}

function escapeHtml(s: string): string {
  return s.replace(/[&<>"']/g, c => `&#${c.charCodeAt(0)};`)
}

export function statusPageUrl(kind: Status, elapsedSeconds: number): string {
  const [title, body] = TEXT[kind](elapsedSeconds).map(escapeHtml)
  const html = `<!doctype html><html><head><meta charset="utf-8">`
    + `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">`
    + `<title>NeverEndingQuest</title><style>`
    + `body{margin:0;height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;`
    + `background:#1b1712;color:#e8dcc4;font-family:Georgia,serif;text-align:center;padding:0 24px;box-sizing:border-box}`
    + `h1{font-size:20px;font-weight:normal;margin:0 0 12px}p{font-size:13px;line-height:1.5;margin:0;color:#b9ab90}`
    + `</style></head><body><h1>${title}</h1><p>${body}</p></body></html>`
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`
}
