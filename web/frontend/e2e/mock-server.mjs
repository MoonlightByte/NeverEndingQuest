import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Server } from 'socket.io'
import { createProviderFixture } from './provider-fixture.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
// Canned map_data_response: a server-shaped, spoiler-safe map projection with
// a mid-reveal set (A01-A03 revealed, A04-A06 still fogged). Same fixture the
// React vitest integration suite uses -- see the checked-in, hand-maintained
// ../src/components/sheet/__fixtures__/mapDataMidReveal.json.
const mapDataMidReveal = JSON.parse(
  fs.readFileSync(
    path.resolve(here, '..', 'src', 'components', 'sheet', '__fixtures__', 'mapDataMidReveal.json'),
    'utf8',
  ),
)
const dist = path.resolve(here, '..', 'dist')
const port = Number(process.env.NEQ_E2E_PORT ?? 4174)
const providerFixture = createProviderFixture()
const supportedHydrationModes = new Set(['legacy', 'correlated', 'mixed', 'delayed'])
let hydrationMode = supportedHydrationModes.has(process.env.NEQ_E2E_HYDRATION_MODE)
  ? process.env.NEQ_E2E_HYDRATION_MODE
  : 'correlated'

const contentTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.svg': 'image/svg+xml',
}

const server = http.createServer((request, response) => {
  const requestPath = new URL(request.url ?? '/', `http://${request.headers.host}`).pathname
  if (request.method === 'POST' && ['/__e2e__/providers/reset', '/__e2e__/providers/reject'].includes(requestPath)) {
    if (requestPath.endsWith('/reset')) providerFixture.reset()
    else providerFixture.reject()
    response.writeHead(200, { 'content-type': 'application/json' }).end('{"ok":true}')
    return
  }
  if (request.method === 'POST' && requestPath.startsWith('/__e2e__/hydration/')) {
    const requestedMode = requestPath.split('/').at(-1)
    if (!supportedHydrationModes.has(requestedMode)) {
      response.writeHead(400, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ ok: false, supported: [...supportedHydrationModes] }))
      return
    }
    hydrationMode = requestedMode
    response.writeHead(200, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ ok: true, mode: hydrationMode }))
    return
  }
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
  abilities: {
    strength: 15, dexterity: 13, constitution: 14,
    intelligence: 8, wisdom: 12, charisma: 10,
  },
  savingThrows: ['strength', 'constitution'],
  savingThrowProficiencies: ['strength', 'constitution'], proficiencyBonus: 2,
}

const party = [
  { name: 'Rowan Vale', type: 'player', currentHp: 12, maxHp: 12, ac: 18, level: 1, class: 'Fighter' },
  { name: 'Lira Sandwalk', type: 'npc', currentHp: 9, maxHp: 11, ac: 14, level: 1, class: 'Ranger' },
  { name: 'Oren Flint', type: 'npc', currentHp: 15, maxHp: 15, ac: 16, level: 1, class: 'Cleric' },
  { name: 'Mara Quill', type: 'npc', currentHp: 8, maxHp: 10, ac: 13, level: 1, class: 'Wizard' },
]

const locationNpcs = [
  { name: 'Keeper Noll', type: 'location_npc', currentHp: 7, maxHp: 7, ac: 11 },
  { name: 'Scout Pell', type: 'location_npc', currentHp: 6, maxHp: 8, ac: 12 },
]

const initialMessages = [
  { type: 'narration', content: 'The wind whispers across the Forsaken Crossroads.' },
]

io.on('connection', (socket) => {
  let initiative = { active: false, combatants: [], round: 0 }
  let revision = 0
  let delayedSequence = 0
  const correlated = (event, requestPayload, payload) => {
    const withMetadata = {
      ...payload,
      revision: ++revision,
      server_instance_id: 'e2e-deterministic-server',
      ...(requestPayload?.request_id ? { request_id: requestPayload.request_id } : {}),
    }
    if (hydrationMode === 'legacy') return payload
    if (hydrationMode === 'mixed' && event === 'location_data_response') return payload
    return withMetadata
  }
  const hydrate = (event, requestPayload, payload) => {
    const responsePayload = correlated(event, requestPayload, payload)
    if (hydrationMode !== 'delayed') {
      socket.emit(event, responsePayload)
      return
    }
    // Deterministically invert adjacent response timing. This exercises the
    // production client's request-id/revision rejection without introducing
    // random sleeps into screenshots.
    const delay = delayedSequence++ % 2 === 0 ? 35 : 0
    setTimeout(() => socket.emit(event, responsePayload), delay)
  }
  socket.emit('connected', { data: 'Connected to NeverEndingQuest' })
  socket.emit('version_status', {
    update_available: false, local_version: 'e2e', remote_version: 'e2e', message: 'Current',
  })
  socket.emit('cached_messages', initialMessages)
  socket.emit('game_resumed', { is_processing: false, message: 'Reconnected to your game.' })

  socket.on('request_location_data', (requestPayload) => hydrate('location_data_response', requestPayload, { data: location }))
  socket.on('request_party_data', (requestPayload) => hydrate('party_data_response', requestPayload, {
    members: party,
    location_npcs: locationNpcs,
  }))
  socket.on('request_initiative_data', (requestPayload) => hydrate('initiative_data_response', requestPayload, initiative))
  socket.on('request_map_data', (requestPayload) => hydrate('map_data_response', requestPayload, { data: mapDataMidReveal }))
  socket.on('request_player_data', (requestPayload) => {
    const { dataType } = requestPayload
    if (dataType === 'stats') socket.emit('player_data_response', { dataType, data: stats })
    else socket.emit('player_data_response', { dataType, data: {} })
  })
  providerFixture.attach(socket)

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
