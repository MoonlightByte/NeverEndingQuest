/**
 * InputBar -- player text input + Send button (plan Task 4.4b).
 * Emits user_input via the socket service; the server echoes it back as
 * game_output type user-input (web_interface.py handle_user_input), so
 * there is no local echo. Locked while session.isProcessing, with the
 * status_update.message placed in the legacy input placeholder.
 */
import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useDialogs, useSession } from '../../stores'

export function InputBar() {
  const isProcessing = useSession((s) => s.isProcessing)
  const connected = useSession((s) => s.connected)
  const mode = useSession((s) => s.mode)
  const inputAuthorized = useSession((s) => s.inputAuthorized)
  const startupInputReady = useSession((s) => s.startupInputReady)
  const startupStatus = useSession((s) => s.startupStatus)
  const statusMessage = useSession((s) => s.statusMessage)
  const destructiveAction = useDialogs((s) => s.actionResult?.kind)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const startupStillLocks = mode === 'starting'
    && startupStatus !== 'failed'
    && !(startupStatus === 'in_progress' && startupInputReady)
  const locked = destructiveAction === 'exit' || destructiveAction === 'reset'
    || isProcessing || !connected || mode === 'disconnected' || startupStillLocks

  // The legacy client places focus in the command field as soon as a live
  // game becomes interactive. Preserve that initial keyboard-ready state.
  useEffect(() => {
    if (locked) inputRef.current?.blur()
    else inputRef.current?.focus()
  }, [locked])

  const send = () => {
    const input = draft.trim()
    // Legacy may visually re-enable the controls after a failed startup when
    // status processing settles, but sendInput still refuses commands until a
    // game is actually running. Keep that failure-safe behavioral gate even
    // when the visual controls are enabled for exact surface parity.
    if (!input || locked || !inputAuthorized) return
    emitC('user_input', { input })
    setDraft('')
  }

  return (
    <div className="neq-input-container shrink-0 border-t border-card bg-[#333] p-[10px]">
      {isProcessing && <span className="sr-only" role="status">{statusMessage || 'The DM is thinking...'}</span>}
      <div className="flex items-center">
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
          disabled={locked}
          placeholder={isProcessing ? (statusMessage || 'The DM is thinking...') : 'Enter your command...'}
          aria-label="Player input"
          className="neq-input-field min-w-0 flex-1 rounded border border-card bg-page px-3 py-2 font-log text-sm text-primary"
        />
        <button
          type="button"
          onClick={send}
          disabled={locked}
          className="neq-send-button cursor-pointer rounded border-0 bg-[#4caf50] px-5 py-2 font-chrome text-sm font-bold text-white hover:bg-[#45a049] disabled:cursor-not-allowed disabled:bg-[#555]"
        >
          Send
        </button>
      </div>
    </div>
  )
}
