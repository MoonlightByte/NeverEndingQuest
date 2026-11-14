import { useRulesRoll } from '../../stores/rulesRoll'
import { useInputSuggestion } from '../../stores/inputSuggestion'
import { useUnsentLine } from '../../stores/unsentLine'
import { RulesRollPanel } from '../log/RulesRollPanel'
/**
 * InputBar -- player text input + Send button (plan Task 4.4b).
 * Emits user_input via the socket service; the server echoes it back as
 * game_output type user-input (web_interface.py handle_user_input), so
 * there is no local echo. Locked while session.isProcessing, with the
 * progress presented above the input, leaving its prompt and draft stable.
 * #1732: a line the server never acknowledged comes back to the box with a
 * note (stores/unsentLine); it is not sent again by itself.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { emitC } from '../../services/socket'
import { useTurnStatus } from './turnStatus'
import { ThinkingMist, useDmBusy } from './ThinkingMist'
import { useComposerGating } from '../../modes/useComposerGating'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'
import type { TrayDie } from './DiceStrip'

/** A dice-tray insertion: its sentence and, #1750, the same faces as typed dice. */
export interface RollInsertion { id: number; text: string; dice?: TrayDie[] }

/** #1990: the line under the box while it holds the words given back after a turn the game could not carry out. */
export const RETURNED_WORDS_HINT = 'Your last action is back here; press Send to try again.'

export function InputBar({ rollInsertion }: { rollInsertion?: RollInsertion } = {}) {
  const ember = useEmberDesktop()
  const turnStatus = useTurnStatus()
  const dmBusy = useDmBusy()
  const gating = useComposerGating()
  const rulesRoll = useRulesRoll((s) => s.prompt)
  // #214: background welcome liveness - presentational, never locks input.
  // (The lock/canSend gate itself lives in useComposerGating, which already
  // folds in destructiveAction + the #214 startup lifecycle -- see useUiMode.)
  const [draft, setDraft] = useState('')
  // #1990: the current draft for effects, read outside any setDraft updater.
  const draftRef = useRef(draft)
  draftRef.current = draft
  // #1990: the returned words this box took; the hint shows only while the box holds exactly them.
  const [offered, setOffered] = useState<string | null>(null)
  const hintId = useId()
  const forgotten = useInputSuggestion((s) => s.forgotten)
  const inputRef = useRef<HTMLInputElement>(null)
  const insertedRoll = useRef<number | null>(null)
  // #1750: the tray sentence that filled an empty draft, with its typed dice;
  // sent beside the line only while the draft is still exactly that sentence.
  const trayLine = useRef<{ text: string; dice: TrayDie[] } | null>(null)
  const suggestion = useInputSuggestion((s) => s.suggestion)
  const unsentLine = useUnsentLine((s) => s.line)
  const [unsent, setUnsent] = useState(false)
  useEffect(() => {
    if (!rollInsertion || insertedRoll.current === rollInsertion.id) return
    insertedRoll.current = rollInsertion.id
    setDraft((previous) => {
      trayLine.current = !previous.trim() && rollInsertion.dice?.length
        ? { text: rollInsertion.text.trim(), dice: rollInsertion.dice } : null
      return previous.trim() ? `${previous.trimEnd()} ${rollInsertion.text}` : rollInsertion.text
    })
    inputRef.current?.focus()
  }, [rollInsertion])
  // #882: an offered action fills an empty draft only; a typed draft stays.
  // #1990: decided here from the current draft, then both setters; a typed draft
  // keeps its hint state, so an earlier hint stays only while still true.
  useEffect(() => {
    if (suggestion === null) return
    const taken = useInputSuggestion.getState().take()
    if (!taken?.text || draftRef.current.trim()) return
    setDraft(taken.text)
    setOffered(taken.reason === 'lost_words' ? taken.text : null)
  }, [suggestion])
  // #1990: Load, Reset or a new game drops the hint; the box text stays.
  const seenForgotten = useRef(forgotten)
  useEffect(() => {
    if (seenForgotten.current === forgotten) return
    seenForgotten.current = forgotten
    setOffered(null)
  }, [forgotten])

  // #1732: the unacknowledged line goes back in front of anything typed since.
  useEffect(() => {
    if (unsentLine === null) return
    const text = useUnsentLine.getState().take()
    if (!text) return
    setDraft((typed) => typed.trim() ? `${text} ${typed.trimStart()}` : text)
    setUnsent(true)
  }, [unsentLine])

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
    setUnsent(false)
    setOffered(null)
    const tray = trayLine.current
    trayLine.current = null
    emitC('user_input', tray && input === tray.text ? { input, dice: tray.dice } : { input })
    setDraft('')
  }

  const returned = offered !== null && draft === offered
  // #1118 item 4: a waiting check's panel sits above the text input, which stays:
  // the player can answer the check in words, ask a question first, or move on.
  // #1734: the panel is the ask, whether or not the narration asked. The box answers to
  // it without naming the check, and the live line, always rendered, announces it.
  return (
    <>
    <p className="sr-only" aria-live="polite">{rulesRoll ? [`${rulesRoll.label} for ${rulesRoll.characterName}`, rulesRoll.reason].filter(Boolean).join(': ') : ''}</p>
    {rulesRoll && <RulesRollPanel key={rulesRoll.id} prompt={rulesRoll} />}
    <div className="neq-input-container shrink-0 border-t border-card bg-[#333] p-[10px]">
      {unsent && <p className="neq-turn-status neq-input-unsent" role="alert">Not sent: the connection to the game dropped. Your line is back in the box; press Send to try again.</p>}
      {turnStatus && <p className={dmBusy ? 'neq-turn-status neq-turn-status--busy' : 'neq-turn-status'} role="status"><ThinkingMist />{turnStatus}</p>}
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
          placeholder={rulesRoll ? `${rulesRoll.faces === 2 ? 'Your rolls' : 'Your roll'}, or what you do next...` : 'Enter your command...'}
          aria-label="Player input"
          aria-describedby={returned ? hintId : undefined}
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
      {/* #1990: under the box; always rendered, so a screen reader says the hint once; polite, never focus. */}
      <p id={hintId} className={returned ? 'neq-turn-status neq-input-returned' : 'neq-input-returned-empty'} aria-live="polite">{returned ? RETURNED_WORDS_HINT : ''}</p>
    </div>
    </>
  )
}
