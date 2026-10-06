import { useRulesRoll } from '../../stores/rulesRoll'
import { RulesRollPanel } from '../log/RulesRollPanel'
/**
 * InputBar -- player text input + Send button (plan Task 4.4b).
 * Emits user_input via the socket service; the server echoes it back as
 * game_output type user-input (web_interface.py handle_user_input), so
 * there is no local echo. Locked while session.isProcessing, with the
 * progress presented above the input, leaving its prompt and draft stable.
 */
import { useEffect, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useTurnStatus } from './turnStatus'
import { useComposerGating } from '../../modes/useComposerGating'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'

export function InputBar({ rollInsertion }: { rollInsertion?: { id: number; text: string } } = {}) {
  const ember = useEmberDesktop()
  const turnStatus = useTurnStatus()
  const gating = useComposerGating()
  const rulesRoll = useRulesRoll((s) => s.prompt)
  // #214: background welcome liveness - presentational, never locks input.
  // (The lock/canSend gate itself lives in useComposerGating, which already
  // folds in destructiveAction + the #214 startup lifecycle -- see useUiMode.)
  const [draft, setDraft] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const insertedRoll = useRef<number | null>(null)
  useEffect(() => {
    if (!rollInsertion || insertedRoll.current === rollInsertion.id) return
    insertedRoll.current = rollInsertion.id
    setDraft((previous) => previous.trim() ? `${previous.trimEnd()} ${rollInsertion.text}` : rollInsertion.text)
    inputRef.current?.focus()
  }, [rollInsertion])

  // The legacy client places focus in the command field as soon as a live
  // game becomes interactive. Preserve that initial keyboard-ready state.
  useEffect(() => {
    if (gating.locked) inputRef.current?.blur()
    else inputRef.current?.focus()
  }, [gating.locked])

  const send = () => {
    const input = draft.trim()
    // Legacy may visually re-enable the controls after a failed startup when
    // status processing settles, but sendInput still refuses commands until a
    // game is actually running. Keep that failure-safe behavioral gate even
    // when the visual controls are enabled for exact surface parity.
    if (!input || !gating.canSend) return
    emitC('user_input', { input })
    setDraft('')
  }

  if (rulesRoll) return <RulesRollPanel key={rulesRoll.id} prompt={rulesRoll} />

  return (
    <div className="neq-input-container shrink-0 border-t border-card bg-[#333] p-[10px]">
      {turnStatus && <p className="neq-turn-status" role="status">{turnStatus}</p>}
      <div className="flex items-center">
        <input
          ref={inputRef}
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') send()
          }}
          disabled={gating.locked}
          placeholder="Enter your command..."
          aria-label="Player input"
          className="neq-input-field min-w-0 flex-1 rounded border border-card bg-page px-3 py-2 font-log text-sm text-primary"
        />
        <button
          type="button"
          onClick={send}
          disabled={gating.locked}
          className="neq-send-button cursor-pointer rounded border-0 bg-[#4caf50] px-5 py-2 font-chrome text-sm font-bold text-white hover:bg-[#45a049] disabled:cursor-not-allowed disabled:bg-[#555]"
        >
          {ember && <EmberIcon name="send" />}Send
        </button>
      </div>
    </div>
  )
}
