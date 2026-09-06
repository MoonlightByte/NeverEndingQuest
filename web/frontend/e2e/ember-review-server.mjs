// Read-only, loopback-only design review. Explicit file allowlist; no game APIs.
import http from 'node:http'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
const repo = new URL('../../../', import.meta.url)
const files = {
  '/': ['docs/design/ember-public/review.html', 'text/html; charset=utf-8'],
  '/review.css': ['docs/design/ember-public/review.css', 'text/css; charset=utf-8'],
  '/review.js': ['docs/design/ember-public/review.js', 'text/javascript; charset=utf-8'],
  '/intermediate': ['docs/design/ember-public/intermediate/index.html', 'text/html; charset=utf-8'],
  '/intermediate.css': ['docs/design/ember-public/intermediate/style.css', 'text/css; charset=utf-8'],
  '/intermediate.js': ['docs/design/ember-public/intermediate/prototype.js', 'text/javascript; charset=utf-8'],
  '/static/css/ember-tokens.css': ['web/static/css/ember-tokens.css', 'text/css; charset=utf-8'],
  '/static/css/ember-fonts.css': ['web/static/css/ember-fonts.css', 'text/css; charset=utf-8'],
  '/art/ranger': ['web/static/media/class_portraits/ranger.png', 'image/png'],
  '/art/merek': ['graphic_packs/photorealistic/npcs/captain_merek.jpg', 'image/jpeg'],
  '/art/cira': ['graphic_packs/photorealistic/npcs/cira_the_innkeeper.jpg', 'image/jpeg'],
  '/art/goblin': ['graphic_packs/photorealistic/monsters/goblin.jpg', 'image/jpeg'],
  '/art/marcus': ['graphic_packs/photorealistic/npcs/ranger_marcus.jpg', 'image/jpeg'],
  '/art/elen': ['graphic_packs/photorealistic/npcs/ranger_elen.jpg', 'image/jpeg'],
  '/art/kira': ['graphic_packs/photorealistic/npcs/scout_kira.jpg', 'image/jpeg'],
  '/art/rusk': ['graphic_packs/photorealistic/npcs/rusk.jpg', 'image/jpeg'],
}
// Exact existing public font basenames only; no arbitrary static-file exposure.
for (const name of fs.readdirSync(new URL('web/static/fonts/ember/', repo)).filter(name => /^[\w-]+\.woff2$/.test(name))) {
  files[`/static/fonts/ember/${name}`] = [`web/static/fonts/ember/${name}`, 'font/woff2']
}
const port = Number(process.env.NEQ_REVIEW_PORT || 4202)
http.createServer((req, res) => {
  const entry = files[new URL(req.url || '/', 'http://localhost').pathname]
  if (req.method !== 'GET' || !entry) { res.writeHead(404).end(); return }
  const path = fileURLToPath(new URL(entry[0], repo))
  if (!fs.existsSync(path)) { res.writeHead(404).end(); return }
  res.writeHead(200, { 'Content-Type': entry[1], 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
  fs.createReadStream(path).pipe(res)
}).listen(port, '127.0.0.1', () => console.log(`Read-only Ember review: http://127.0.0.1:${port}`))
