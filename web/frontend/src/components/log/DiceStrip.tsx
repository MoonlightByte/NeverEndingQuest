/**
 * DiceStrip -- quick-roll buttons D20..D4 (plan Task 4.4b).
 * Client-side rolls with crypto.getRandomValues using rejection sampling
 * (ported as-is from the legacy game_interface.html rollDice) to avoid
 * modulo bias. d20 rolls are listed individually; the other dice accumulate
 * into a damage list with a running total. Purely client-side flavor -- no
 * socket traffic; the server remains the authority on real game rolls.
 */
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'
import { useComposerGating } from '../../modes/useComposerGating'
import { useRulesRoll } from '../../stores/rulesRoll'
import { EmberDieIcon } from '../layout/EmberDieIcon'
import { RulesRollActions } from './RulesRollPanel'

const DICE_SIDES = [20, 12, 10, 8, 6, 4] as const

/** Rejection sampling to avoid modulo bias (legacy rollDice, ported as-is). */
export function rollDie(sides: number): number {
  const maxValid = Math.floor(4294967296 / sides) * sides
  let value: number
  do {
    const array = new Uint32Array(1)
    crypto.getRandomValues(array)
    value = array[0]!
  } while (value >= maxValid)
  return (value % sides) + 1
}

interface DamageRoll {
  sides: number
  result: number
}

/** Preserve every face; d20 checks must never be summed into damage. */
export function formatFreeRolls(d20Rolls: number[], damageRolls: DamageRoll[]): string {
  const parts = [
    ...d20Rolls.map((r) => `a ${r} on a d20`),
    ...damageRolls.map((r) => `a ${r.result} on a d${r.sides}`),
  ]
  if (!parts.length) return ''
  const rolls = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts.at(-1)}` : parts[0]
  const total = damageRolls.reduce((sum, r) => sum + r.result, 0)
  return `I rolled ${rolls}.${damageRolls.length > 1 ? ` My damage dice add up to ${total}.` : ''}`
}

const diceButtonClass =
  'relative min-w-[50px] cursor-pointer overflow-hidden rounded-md border border-white/50 px-3 py-1.5 ' +
  'font-chrome text-[13px] font-bold text-white/90 shadow-[0_4px_6px_rgba(0,0,0,.2),inset_0_1px_0_rgba(255,255,255,.6)] ' +
  'bg-[linear-gradient(145deg,rgba(38,97,156,.4),rgba(25,118,210,.5),rgba(13,71,161,.6))]'

const clearButtonClass =
  'cursor-pointer rounded border-0 bg-[#f44336] px-3 py-1.5 font-chrome text-[13px] text-white hover:bg-[#d32f2f]'

export function useDiceRolls() {
  const [d20Rolls, setD20Rolls] = useState<number[]>([])
  const [damageRolls, setDamageRolls] = useState<DamageRoll[]>([])
  return { d20Rolls, setD20Rolls, damageRolls, setDamageRolls }
}

export function DiceStrip({ state, onInsertRoll }: { state?: ReturnType<typeof useDiceRolls>; onInsertRoll?: (text: string) => void }) {
  const gating = useComposerGating()
  const requestedCheck = useRulesRoll((s) => s.prompt)
  const ember = useEmberDesktop()
  const local = useDiceRolls()
  const { d20Rolls, setD20Rolls, damageRolls, setDamageRolls } = state ?? local
  const [rolling, setRolling] = useState<number | null>(null)
  const [resultsHost, setResultsHost] = useState<HTMLElement | null>(null)
  // Resolve after commit: a breakpoint move replaces the previous dock node.
  useLayoutEffect(() => { setResultsHost(document.getElementById('neq-dice-results-host')) }, [ember])
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const previousCheck = useRef<string | null>(null)
  useEffect(() => {
    if (previousCheck.current && previousCheck.current !== requestedCheck?.id) {
      setD20Rolls([])
      setDamageRolls([])
    }
    previousCheck.current = requestedCheck?.id ?? null
  }, [requestedCheck?.id, setD20Rolls, setDamageRolls])
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  const roll = (sides: number) => {
    if (timer.current) clearTimeout(timer.current)
    setRolling(sides)
    timer.current = setTimeout(() => setRolling(null), 280)
    const result = rollDie(sides)
    if (sides === 20) {
      setD20Rolls((rolls) => [...rolls, result])
      useRulesRoll.getState().addQuickFace(result)
    } else {
      setDamageRolls((rolls) => [...rolls, { sides, result }])
    }
  }

  const clear = () => {
    setD20Rolls([])
    useRulesRoll.getState().clearQuickFaces()
    setDamageRolls([])
  }

  const damageTotal = damageRolls.reduce((sum, r) => sum + r.result, 0)
  const hasResults = d20Rolls.length > 0 || damageRolls.length > 0
  const clearButton = <button type="button" title="Clear results" onClick={clear} className={clearButtonClass}>
    {ember && <EmberIcon name="clear" />}Clear
  </button>

  const insertRoll = () => {
    if (!gating.canSend || requestedCheck || !onInsertRoll) return
    onInsertRoll(formatFreeRolls(d20Rolls, damageRolls))
  }

  const results = hasResults ? (
    <div className="neq-dice-results font-log text-sm" data-testid="dice-results">
      {d20Rolls.length > 0 && (
        <span className="neq-dice-result-item">
          {d20Rolls.map((r) => `d20: ${r}`).join(', ')}
        </span>
      )}
      {d20Rolls.length > 0 && damageRolls.length > 0 && <span>{'\u00a0| '}</span>}
      {damageRolls.length > 0 && (
        <>
          <span className="neq-dice-result-item">
            {damageRolls.map((r) => `d${r.sides}: ${r.result}`).join(', ')}
          </span>
          <span className="neq-dice-total">Total: {damageTotal}</span>
        </>
      )}
      {onInsertRoll && !requestedCheck && <button type="button" className="neq-insert-roll" disabled={!gating.canSend} onClick={insertRoll}>Insert roll</button>}
    </div>
  ) : null

  return (
    <>
    <div className="neq-dice-strip flex shrink-0 flex-col items-center">
      <div className="neq-dice-label relative w-full text-center before:absolute before:left-0 before:right-0 before:top-1/2 before:h-px before:bg-[#ffa500]">
        <span className="neq-dice-label-text relative z-10 inline-block rounded border border-[#ffa500] bg-[#333] px-5 py-0.5 font-chrome text-xs font-bold uppercase tracking-wider text-[#ffa500]">Quick {ember ? 'rolls' : 'Rolls'}</span>
        {ember && <span className="ember-dice-disclaimer">Roll, then submit requested checks</span>}
      </div>
      <div className="neq-dice-buttons flex items-center gap-1.5">
        {DICE_SIDES.map((sides) => (
          <button
            key={sides}
            type="button"
            title={`Roll D${sides}`}
            onClick={() => roll(sides)}
            className={diceButtonClass}
          >
            {ember && <EmberDieIcon sides={sides} rolling={rolling === sides} />}D{sides}
          </button>
        ))}
        {ember && requestedCheck ? <span className="neq-dice-submit-controls"><RulesRollActions prompt={requestedCheck} />{clearButton}</span> : clearButton}
      </div>
    </div>
    {resultsHost && results ? createPortal(results, resultsHost) : results}
    </>
  )
}
