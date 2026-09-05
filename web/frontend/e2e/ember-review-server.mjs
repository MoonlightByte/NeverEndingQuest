// Read-only, loopback-only design review. Explicit file allowlist; no game APIs.
import http from 'node:http'
import fs from 'node:fs'
import { fileURLToPath } from 'node:url'
const repo = new URL('../../../', import.meta.url)
const files = {
  '/': ['docs/design/ember-public/review.html', 'text/html; charset=utf-8'],
  '/review.css': ['docs/design/ember-public/review.css', 'text/css; charset=utf-8'],
  '/review.js': ['docs/design/ember-public/review.js', 'text/javascript; charset=utf-8'],
  '/art/ranger': ['web/static/media/class_portraits/ranger.png', 'image/png'],
  '/art/merek': ['graphic_packs/photorealistic/npcs/captain_merek.jpg', 'image/jpeg'],
  '/art/cira': ['graphic_packs/photorealistic/npcs/cira_the_innkeeper.jpg', 'image/jpeg'],
  '/art/goblin': ['graphic_packs/photorealistic/monsters/goblin.jpg', 'image/jpeg'],
}
http.createServer((req, res) => {
  const entry = files[new URL(req.url || '/', 'http://localhost').pathname]
  if (req.method !== 'GET' || !entry) { res.writeHead(404).end(); return }
  const path = fileURLToPath(new URL(entry[0], repo))
  if (!fs.existsSync(path)) { res.writeHead(404).end(); return }
  res.writeHead(200, { 'Content-Type': entry[1], 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' })
  fs.createReadStream(path).pipe(res)
}).listen(4202, '127.0.0.1', () => console.log('Read-only Ember review: http://127.0.0.1:4202'))
