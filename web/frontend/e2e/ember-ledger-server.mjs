// Isolated public React/Socket.IO ledger-state fixture. No game/provider writes.
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Server } from 'socket.io'
const dist = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../dist')
let scenario = 'loading'
const scenarios = new Set(['loading', 'empty', 'error', 'populated'])
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname
  if (req.method === 'POST' && pathname.startsWith('/__ledger__/')) {
    const next = pathname.split('/').at(-1)
    if (!scenarios.has(next)) { res.writeHead(400).end(); return }
    scenario = next; res.writeHead(200).end('ok'); return
  }
  const file = pathname === '/play/' ? path.join(dist, 'index.html') : path.resolve(dist, '.' + pathname.replace(/^\/play/, ''))
  if (!file.startsWith(dist + path.sep)) { res.writeHead(404).end(); return }
  try { if (!fs.statSync(file).isFile()) { res.writeHead(404).end(); return } }
  catch { res.writeHead(404).end(); return }
  const mime = { '.js': 'application/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.html': 'text/html' }
  const stream = fs.createReadStream(file)
  stream.on('open', () => { res.writeHead(200, { 'content-type': mime[path.extname(file)] ?? 'application/octet-stream' }); stream.pipe(res) })
  stream.on('error', () => { if (res.headersSent) res.destroy(); else res.writeHead(404).end() })
})
const io = new Server(server)
io.on('connection', socket => {
  socket.emit('connected', { data: 'Ledger fixture' })
  socket.emit('game_started', { message: 'Synthetic ledger review' })
  socket.on('request_player_data', ({ dataType }) => socket.emit('player_data_response', { dataType, data: dataType === 'stats' ? { name: 'Ledger Tester', race: 'Human', class: 'Fighter', level: 1, currentHp: 10, maxHp: 10 } : dataType === 'inventory' ? { equipment: [], goldPieces: 3 } : [] }))
  for (const kind of ['plot', 'storage']) socket.on(`request_${kind}_data`, () => {
    if (scenario === 'loading') return
    const error = scenario === 'error' ? 'Synthetic ledger read failure' : undefined
    const data = scenario === 'error' ? (kind === 'plot' ? null : {}) : kind === 'plot'
      ? { plotPoints: scenario === 'empty' ? [] : [{ id: 'active', title: 'The discovered road', description: 'A known objective.', status: 'in progress', sideQuests: [{ title: 'Hidden side quest', description: 'Never revealed', status: 'not started' }] }, { id: 'done', title: 'A finished journey', description: 'A completed objective.', status: 'completed' }, { id: 'hidden', title: 'Hidden plot', description: 'Never revealed', status: 'not started' }] }
      : { success: true, storage: scenario === 'empty' ? [] : [{ name: 'Roadside chest', location: 'Known camp', contents: [{ item_name: 'Rope', quantity: 2 }] }, { name: 'Empty coffer', location: 'Known camp', contents: [] }] }
    socket.emit(`${kind}_data_response`, { data, ...(error ? { error } : {}) })
  })
})
server.listen(4215, '127.0.0.1', () => console.log('Isolated ledger review on 4215'))
