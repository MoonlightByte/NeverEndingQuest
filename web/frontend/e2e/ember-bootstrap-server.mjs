// Empty first-run presentation fixture. No engine, credentials or file writes.
import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Server } from 'socket.io'
import { createProviderFixture } from './provider-fixture.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const dist = path.resolve(here, '../dist')
const providers = createProviderFixture()
let state = 'notice'
const states = new Set(['loading', 'notice', 'error'])
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname
  if (req.method === 'POST' && pathname.startsWith('/__bootstrap__/')) {
    const next = pathname.split('/').at(-1)
    if (!states.has(next)) { res.writeHead(400).end(); return }
    state = next; res.writeHead(200).end(); return
  }
  const clockArt = pathname === '/static/media/environment/midday.jpg'
  if (req.method !== 'GET' || (!clockArt && !pathname.startsWith('/play/'))) { res.writeHead(404).end(); return }
  const file = clockArt ? path.resolve(here, '../../static/media/environment/midday.jpg')
    : path.resolve(dist, pathname.slice('/play/'.length) || 'index.html')
  if (!clockArt && !file.startsWith(`${dist}${path.sep}`)) { res.writeHead(404).end(); return }
  const stream = fs.createReadStream(file)
  stream.on('open', () => {
    res.writeHead(200, { 'content-type': ({ '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.jpg': 'image/jpeg' })[path.extname(file)] ?? 'application/octet-stream' })
    stream.pipe(res)
  })
  stream.on('error', () => { if (res.headersSent) res.destroy(); else res.writeHead(404).end() })
})
const io = new Server(server)
io.on('connection', socket => {
  socket.emit('connected', { data: 'Synthetic first-run state' })
  socket.emit('cached_messages', [])
  socket.on('request_player_data', ({ dataType }) => {
    if (state === 'loading') return
    // Exact no-character notice/error shapes from handle_player_data_request.
    socket.emit('player_data_response', {
      dataType, data: dataType === 'npcs' ? [] : null,
      ...(dataType === 'npcs' ? {} : state === 'notice'
        ? { notice: 'No character yet. Your hero appears here once character creation finishes.' }
        : { error: 'Player data not found' }),
    })
  })
  socket.on('request_location_data', () => {
    if (state === 'loading') return
    socket.emit('location_data_response', { data: null, error: 'Party tracker not found' })
  })
  socket.on('request_party_data', () => socket.emit('party_data_response', { members: [], location_npcs: [] }))
  socket.on('request_initiative_data', () => socket.emit('initiative_data_response', { active: false, combatants: [], round: 0 }))
  providers.attach(socket)
})
server.listen(4216, '127.0.0.1', () => console.log('Synthetic empty first-run review: http://127.0.0.1:4216/play/'))
