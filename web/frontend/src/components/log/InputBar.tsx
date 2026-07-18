/**
 * InputBar -- player text input + Send button (plan Task 4.4b).
 * Emits user_input via the socket service; the server echoes it back as
 * game_output type user-input (web_interface.py handle_user_input), so
 * there is no local echo. Locked while session.isProcessing, with the
 * status ticker text (status_update.message) shown inline.
 */
import { useState } from 'react'
import { emitC } from '../../services/socket'
import { useSession } from '../../stores'

export function InputBar() {
  const isProcessing = useSession((s) => s.isProcessing)
  const connected = useSession((s) => s.connected)
  const mode = useSession((s) => s.mode)
  const statusMessage = useSession((s) => s.statusMessage)
  const [draft, setDraft] = useState('')

  const send = () => {
    const input = draft.trim()
    if (!input || isProcessing || !connected || mode === 'disconnected') return
    emitC('user_input', { input })
    setDraft('')
  }

  return (
    <div className="shrink-0 border-t border-card bg-[#333] p-[10px]">
      {isProcessing && (
        <div
          role="status"
          className="mb-1 animate-pulse px-1 font-log text-xs"
          style={{ color: 'var(--accent)' }}
        >
          {statusMessage || 'The DM is thinking...'}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
          disabled={isProcessing || !connected || mode === 'disconnected'}
          placeholder={isProcessing ? 'Waiting for the DM...' : 'Enter your command...'}
          aria-label="Player input"
          className="min-w-0 flex-1 rounded border-2 border-card bg-page px-3 py-2 font-log text-sm text-primary outline-none focus:border-accent disabled:opacity-60"
        />
        <button
          type="button"
          onClick={send}
          disabled={isProcessing || !connected || mode === 'disconnected'}
          className="cursor-pointer rounded border-0 bg-[#4caf50] px-5 py-2 font-chrome text-sm font-bold text-white hover:bg-[#45a049] disabled:cursor-not-allowed disabled:bg-[#555]"
        >
          Send
        </button>
      </div>
    </div>
  )
}
