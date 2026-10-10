// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { formatFreeRolls } from './DiceStrip'
const sides = [4, 6, 8, 10, 12, 20]
function format(rolls: {sides:number;result:number}[]) {
  return formatFreeRolls(rolls.filter(r => r.sides === 20).map(r => r.result), rolls.filter(r => r.sides !== 20))
}
describe('natural free-roll sentences', () => {
  it('preserves every possible face on every supported single die', () => {
    for (const die of sides) for (let face = 1; face <= die; face++) {
      expect(format([{sides:die,result:face}])).toBe(`I rolled a ${face} on a d${die}.`)
    }
  })
  it('preserves all ordered die pairs and face combinations, summing only damage', () => {
    for (const a of sides) for (const b of sides) for (let x=1;x<=a;x++) for (let y=1;y<=b;y++) {
      const rolls = [{sides:a,result:x},{sides:b,result:y}]
      const ordered = [...rolls.filter(r=>r.sides===20), ...rolls.filter(r=>r.sides!==20)]
      const expected = `I rolled a ${ordered[0].result} on a d${ordered[0].sides} and a ${ordered[1].result} on a d${ordered[1].sides}.` + (a!==20 && b!==20 ? ` My damage dice add up to ${x+y}.` : '')
      expect(format(rolls)).toBe(expected)
    }
  })
  it('handles empty, repeated and longer mixed sequences without losing faces', () => {
    expect(format([])).toBe('')
    expect(formatFreeRolls([1,20], [{sides:8,result:5},{sides:8,result:5},{sides:4,result:2}])).toBe('I rolled a 1 on a d20, a 20 on a d20, a 5 on a d8, a 5 on a d8 and a 2 on a d4. My damage dice add up to 12.')
  })
})
