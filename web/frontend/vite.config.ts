import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The existing Flask-SocketIO server (run_web.py) that this standalone app talks to.
const FLASK_BACKEND = 'http://localhost:8357'

// https://vite.dev/config/
export default defineConfig({
  // Served by Flask at /play (see web/web_interface.py serve_react_play route),
  // so built asset URLs must resolve under /play/.
  base: '/play/',
  plugins: [react(), tailwindcss()],
  test: {
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
  },
  server: {
    proxy: {
      // Socket.IO transport negotiation to the Flask-SocketIO server.
      '/socket.io': { target: FLASK_BACKEND, ws: true },
      // Game media served by the Flask 3-tier media routes.
      '/media': { target: FLASK_BACKEND },
      '/graphic_packs': { target: FLASK_BACKEND },
    },
  },
  // build.outDir intentionally left at the Vite default ('dist').
})
