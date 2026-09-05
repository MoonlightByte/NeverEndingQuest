/**
 * DiceStrip -- quick-roll buttons D20..D4 (plan Task 4.4b).
 * Client-side rolls with crypto.getRandomValues using rejection sampling
 * (ported as-is from the legacy game_interface.html rollDice) to avoid
 * modulo bias. d20 rolls are listed individually; the other dice accumulate
 * into a damage list with a running total. Purely client-side flavor -- no
 * socket traffic; the server remains the authority on real game rolls.
 */
import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useEmberDesktop } from '../layout/EmberPresentation'
import { EmberIcon } from '../layout/EmberIcon'

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

const diceButtonClass =
  'relative min-w-[50px] cursor-pointer overflow-hidden rounded-md border border-white/50 px-3 py-1.5 ' +
  'font-chrome text-[13px] font-bold text-white/90 shadow-[0_4px_6px_rgba(0,0,0,.2),inset_0_1px_0_rgba(255,255,255,.6)] ' +
  'bg-[linear-gradient(145deg,rgba(38,97,156,.4),rgba(25,118,210,.5),rgba(13,71,161,.6))]'

const clearButtonClass =
  'cursor-pointer rounded border-0 bg-[#f44336] px-3 py-1.5 font-chrome text-[13px] text-white hover:bg-[#d32f2f]'

export function DiceStrip() {
  const ember = useEmberDesktop()
  const [d20Rolls, setD20Rolls] = useState<number[]>([])
  const [damageRolls, setDamageRolls] = useState<DamageRoll[]>([])

  const roll = (sides: number) => {
    const result = rollDie(sides)
    if (sides === 20) {
      setD20Rolls((rolls) => [...rolls, result])
    } else {
      setDamageRolls((rolls) => [...rolls, { sides, result }])
    }
  }

  const clear = () => {
    setD20Rolls([])
    setDamageRolls([])
  }

  const damageTotal = damageRolls.reduce((sum, r) => sum + r.result, 0)
  const hasResults = d20Rolls.length > 0 || damageRolls.length > 0
  const resultsHost = typeof document === 'undefined' ? null : document.getElementById('neq-dice-results-host')

  const results = hasResults ? (
    <div className="neq-dice-results font-log text-sm" data-testid="dice-results">
      {d20Rolls.length > 0 && (
        <span className="neq-dice-result-item">
          {d20Rolls.map((r) => `d20: ${r}`).join(', d20: ')}
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
    </div>
  ) : null

  return (
    <>
    <div className="neq-dice-strip flex shrink-0 flex-col items-center">
      <div className="neq-dice-label relative w-full text-center before:absolute before:left-0 before:right-0 before:top-1/2 before:h-px before:bg-[#ffa500]">
        <span className="neq-dice-label-text relative z-10 inline-block rounded border border-[#ffa500] bg-[#333] px-5 py-0.5 font-chrome text-xs font-bold uppercase tracking-wider text-[#ffa500]">Quick {ember ? 'rolls' : 'Rolls'}</span>
        {ember && <span className="ember-dice-disclaimer">Local dice · not game checks</span>}
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
            {ember && <EmberIcon name="dice" />}D{sides}
          </button>
        ))}
        <button type="button" title="Clear results" onClick={clear} className={clearButtonClass}>
          {ember && <EmberIcon name="clear" />}Clear
        </button>
      </div>
    </div>
    {resultsHost && results ? createPortal(results, resultsHost) : results}
    </>
  )
}
