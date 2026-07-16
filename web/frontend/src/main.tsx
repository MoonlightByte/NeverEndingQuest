import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './theme/tokens.css'
// Side-effect import: connects the socket and registers all server-event
// handlers (services/socket.ts is the sole socket.io-client owner).
import './services/socket'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
