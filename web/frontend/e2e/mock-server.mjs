import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { Server } from 'socket.io'
import { createProviderFixture } from './provider-fixture.mjs'
import { applyEmberFixture, emberNarration, emberMediaFiles, emberEquipment, emberNpcs, emberPlot, emberStorage } from './ember-visual-fixture.mjs'

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
const webRoot = path.resolve(here, '../..')
const port = Number(process.env.NEQ_E2E_PORT ?? 4174)
const providerFixture = createProviderFixture()
const emberVisual = process.env.NEQ_E2E_EMBER_VISUAL === '1'
let emberMedia = true
const spellRepository = JSON.parse(fs.readFileSync(path.resolve(here, '../../../data/spell_repository.json'), 'utf8'))
const previewSpells = Object.fromEntries(['goodberry', 'acid_arrow'].flatMap(key => {
  const detail = spellRepository[key]
  return [detail.name, ...(detail.aliases ?? [])].map(name => [name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, ''), detail])
}))
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
  if (emberVisual && ['/toolkit', '/builder'].includes(requestPath)) {
    const template = fs.readFileSync(path.join(webRoot, 'templates', requestPath === '/toolkit' ? 'module_toolkit.html' : 'module_builder.html'), 'utf8')
    const html = template.replace(/\{\{ url_for\('static', filename='((?:css|js)\/ember-[^']+)'\) \}\}/g, '/static/$1')
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(html)
    return
  }
  if (emberVisual && /^\/static\/(?:css\/ember-[\w-]+\.css|js\/ember-[\w-]+\.js|fonts\/ember\/[\w.-]+)$/.test(requestPath)) {
    const file = path.join(webRoot, requestPath)
    if (!fs.existsSync(file)) { response.writeHead(404).end(); return }
    response.writeHead(200, { 'content-type': contentTypes[path.extname(file)] ?? 'font/woff2' })
    fs.createReadStream(file).pipe(response)
    return
  }
  if (emberVisual && requestPath.startsWith('/api/toolkit/')) {
    const data = request.method !== 'GET' ? { success: false, error: 'Interactive preview only: pack changes and generation are not connected to a live backend.' }
      : requestPath === '/api/toolkit/packs' ? [{ name: 'photorealistic', display_name: 'Photorealistic', is_active: true }, { name: 'preview_pack', display_name: 'Preview Pack', is_active: false }]
      : requestPath === '/api/toolkit/modules' ? [{ moduleName: 'preview_module', levelRange: { min: 1, max: 3 } }]
      : requestPath === '/api/toolkit/monsters' ? [{ id: 'preview_wolf', name: 'Preview Wolf', source: 'bestiary' }]
      : requestPath.endsWith('/npcs') ? [{ id: 'ranger_elen', name: 'Ranger Elen', has_portrait: true }]
      : requestPath.endsWith('/unified-assets') ? { success: true, assets: [{ id: 'ranger_elen', name: 'Ranger Elen', type: 'npc', has_description: true, has_image: true }], summary: { total_assets: 1, total_npcs: 1, total_monsters: 0, with_descriptions: 1, with_images: 1 } }
      : requestPath.includes('styles') ? { builtin: { photorealistic: { name: 'Photorealistic', prompt: 'Existing photorealistic treatment' } }, custom: {} } : []
    response.writeHead(request.method === 'GET' ? 200 : 409, { 'content-type': 'application/json' }).end(JSON.stringify(data))
    return
  }
  if (emberVisual && requestPath === '/spell-data') {
    response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(previewSpells))
    return
  }
  if (emberVisual && request.method === 'POST' && ['/__e2e__/media/on', '/__e2e__/media/off'].includes(requestPath)) {
    emberMedia = requestPath.endsWith('/on')
    response.writeHead(200).end()
    return
  }
  if (emberVisual && Object.hasOwn(emberMediaFiles, requestPath)) {
    const file = path.resolve(here, '../../..', emberMediaFiles[requestPath])
    response.writeHead(200, { 'content-type': file.endsWith('.png') ? 'image/png' : 'image/jpeg' })
    fs.createReadStream(file).pipe(response)
    return
  }
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
if (emberVisual) applyEmberFixture({ location, stats, party, locationNpcs, initialMessages })

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
  if (emberVisual) {
    socket.emit('game_started', { message: 'Visual fixture ready' })
    for (const message of initialMessages) socket.emit('game_output', message)
    if (emberMedia) socket.emit('image_generated', { image_url: '/__e2e__/scene.jpg', prompt: emberNarration, source_message_id: 'ember-dm' })
  } else {
    socket.emit('cached_messages', initialMessages)
    socket.emit('startup_status', { status: 'ready', phase: 'complete', startupAttemptId: 'preview-ready' })
    socket.emit('game_resumed', { is_processing: false, message: 'Reconnected to your game.' })
  }

  socket.on('request_location_data', (requestPayload) => hydrate('location_data_response', requestPayload, { data: location }))
  socket.on('request_party_data', (requestPayload) => hydrate('party_data_response', requestPayload, {
    members: party,
    location_npcs: locationNpcs,
  }))
  socket.on('request_initiative_data', (requestPayload) => hydrate('initiative_data_response', requestPayload, initiative))
  socket.on('request_map_data', (requestPayload) => hydrate('map_data_response', requestPayload, { data: mapDataMidReveal }))
  if (emberVisual) {
    socket.on('request_plot_data', payload => hydrate('plot_data_response', payload, { data: emberPlot }))
    socket.on('request_storage_data', payload => hydrate('storage_data_response', payload, { data: emberStorage }))
    socket.on('request_module_list', () => socket.emit('module_list_response', [{ name: 'Preview Module', module_name: 'preview_module', moduleName: 'preview_module', levelRange: { min: 1, max: 3 } }]))
    socket.on('start_build', () => socket.emit('module_error', { error: 'Preview only: no module build was started.' }))
    socket.on('generate_unified_assets', () => socket.emit('unified_generation_error', { error: 'Preview only: no paid asset generation was started.' }))
    socket.on('generate_image', payload => socket.emit('image_generation_error', { message: 'Preview only: no paid image generation was started.', request_id: payload.request_id, source_message_id: payload.source_message_id }))
  }
  socket.on('request_player_data', (requestPayload) => {
    const { dataType } = requestPayload
    if (dataType === 'stats') socket.emit('player_data_response', { dataType, data: stats })
    else if (emberVisual) socket.emit('player_data_response', { dataType, data: dataType === 'npcs' ? emberNpcs(stats) : { ...stats, equipment: emberEquipment } })
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
