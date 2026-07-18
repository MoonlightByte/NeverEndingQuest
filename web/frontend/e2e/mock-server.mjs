import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Server } from 'socket.io'

const here = path.dirname(fileURLToPath(import.meta.url))
const dist = path.resolve(here, '..', 'dist')
const port = Number(process.env.NEQ_E2E_PORT ?? 4174)

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
}

const server = http.createServer((request, response) => {
  const requestPath = new URL(request.url ?? '/', `http://${request.headers.host}`).pathname
  if (requestPath === '/') {
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
    response.end('<!doctype html><title>Legacy NeverEndingQuest</title>')
    return
  }
  if (!requestPath.startsWith('/play')) {
    response.writeHead(404).end()
    return
  }

  const relative = requestPath.replace(/^\/play\/?/, '') || 'index.html'
  const candidate = path.resolve(dist, relative)
  const safeCandidate = candidate.startsWith(`${dist}${path.sep}`) ? candidate : ''
  const filename = safeCandidate && fs.existsSync(safeCandidate) && fs.statSync(safeCandidate).isFile()
    ? safeCandidate
    : path.join(dist, 'index.html')
  response.writeHead(200, {
    'content-type': contentTypes[path.extname(filename)] ?? 'application/octet-stream',
  })
  fs.createReadStream(filename).pipe(response)
})

const io = new Server(server)

const location = {
  currentLocation: 'Forsaken Crossroads',
  currentArea: 'Stormglass Coast',
  currentLocationId: 'A03',
  currentAreaId: 'SC001',
  time: '13:00:00',
  day: 1,
  month: 'Springmonth',
  year: 1492,
}

const stats = {
  name: 'Rowan Vale', race: 'Human', class: 'Fighter', level: 1,
  experience_points: 0, exp_required_for_next_level: 300,
  background: 'Soldier', alignment: 'lawful good',
  strength: 15, dexterity: 13, constitution: 14,
  intelligence: 8, wisdom: 12, charisma: 10,
  hitPoints: 12, maxHitPoints: 12, armorClass: 18, initiative: 1,
  savingThrows: ['strength', 'constitution'], proficiencyBonus: 2,
}

const initialMessages = [
  { type: 'narration', content: 'The wind whispers across the Forsaken Crossroads.' },
]

io.on('connection', (socket) => {
  let initiative = { active: false, combatants: [], round: 0 }
  socket.emit('connected', { data: 'Connected to NeverEndingQuest' })
  socket.emit('version_status', {
    update_available: false, local_version: 'e2e', remote_version: 'e2e', message: 'Current',
  })
  socket.emit('cached_messages', initialMessages)
  socket.emit('game_resumed', { is_processing: false, message: 'Reconnected to your game.' })

  socket.on('request_location_data', () => socket.emit('location_data_response', { data: location }))
  socket.on('request_party_data', () => socket.emit('party_data_response', {
    members: [{ name: 'Rowan Vale', type: 'player', hitPoints: 12, maxHitPoints: 12 }],
    location_npcs: [{ name: 'Lira Sandwalk', type: 'npc' }],
  }))
  socket.on('request_initiative_data', () => socket.emit('initiative_data_response', initiative))
  socket.on('request_player_data', ({ dataType }) => {
    if (dataType === 'stats') socket.emit('player_data_response', { dataType, data: stats })
    else socket.emit('player_data_response', { dataType, data: {} })
  })
  socket.on('get_model_provider', () => socket.emit('provider_changed', { provider: 'legacy' }))
  socket.on('get_local_endpoint', () => socket.emit('local_endpoint_changed', {
    base_url: 'http://localhost:1234/v1', model: '', has_key: false,
  }))
  socket.on('get_openai_key', () => socket.emit('openai_key_status', { has_key: false }))
  socket.on('get_gemini_key', () => socket.emit('gemini_key_status', { has_key: false }))

  socket.on('action', ({ action, parameters }) => {
    if (action === 'listSaves') {
      socket.emit('save_list_response', [{
        save_folder: 'e2e-save', save_mode: 'essential', save_date_readable: 'Now',
        module: 'Blackglass_Lighthouse', description: 'E2E validation',
        game_state: { current_location: location.currentLocation },
      }])
    } else if (action === 'saveGame') {
      socket.emit('system_message', { content: `Saved: ${parameters?.description ?? ''}` })
    }
  })

  socket.on('user_input', ({ input }) => {
    socket.emit('game_output', { type: 'user-input', content: input })
    socket.emit('status_update', { message: 'The DM is thinking...', is_processing: true })
    setTimeout(() => {
      if (input.toLowerCase().includes('combat')) {
        initiative = {
          active: true,
          round: 1,
          combatants: [
            { name: 'Rowan Vale', type: 'player', hitPoints: 12, maxHitPoints: 12 },
            { name: 'Storm Wraith', type: 'enemy', monsterType: 'Storm Wraith', hitPoints: 9, maxHitPoints: 9 },
          ],
        }
        socket.emit('initiative_data_response', initiative)
      }
      socket.emit('game_output', {
        type: 'narration',
        content: input.toLowerCase().includes('combat')
          ? 'A Storm Wraith surges forward. Roll initiative!'
          : 'The crossroads answers your careful action.',
      })
      socket.emit('status_update', { message: 'Your turn', is_processing: false })
    }, 20)
  })
})

server.listen(port, '127.0.0.1', () => {
  console.log(`NeverEndingQuest E2E fixture listening on ${port}`)
})
