import { describe, expect, it } from 'vitest'
import { type Spend, spendHoverText, spendLineText } from './spendText'

const base: Spend = {
  calls: 30, usd: 0.42, prompt: 1000, cached: 200, completion: 100,
  turn_calls: 5, turn_usd: 0.03, unpriced: 0, possibly_billed: 0,
  portraits: 0, voice: 0, build_calls: 0, build_usd: 0,
  priced_at: '2026-11-01', provider_kind: 'openai', available: true,
}

const buildLine = (text: string) => text.split('\n').filter((line) => line.startsWith('New adventure being built:'))

describe('spendHoverText: the new adventure line (#2033, D-SPEND-LINE-1)', () => {
  it('is absent while no build has spent anything', () => {
    expect(buildLine(spendHoverText(base))).toEqual([])
  })

  it('reads the owner words with the session dollar format on openai', () => {
    expect(buildLine(spendHoverText({ ...base, build_calls: 25, build_usd: 0.31 }))).toEqual([
      'New adventure being built: 25 AI calls, about $0.31 (included in this session)',
    ])
  })

  it('uses the same small-amount wording as the session line', () => {
    expect(buildLine(spendHoverText({ ...base, build_calls: 3, build_usd: 0.004 }))).toEqual([
      'New adventure being built: 3 AI calls, under $0.01 (included in this session)',
    ])
  })

  it('says call for one, as the turn line does', () => {
    expect(buildLine(spendHoverText({ ...base, build_calls: 1, build_usd: 0.02 }))).toEqual([
      'New adventure being built: 1 AI call, about $0.02 (included in this session)',
    ])
  })

  it('shows no dollars where the turn line shows none (gemini, local)', () => {
    for (const provider_kind of ['gemini', 'local'] as const) {
      expect(buildLine(spendHoverText({ ...base, provider_kind, build_calls: 25, build_usd: 0 }))).toEqual([
        'New adventure being built: 25 AI calls (included in this session)',
      ])
    }
  })

  it('leaves the header line and the other hover lines as they were', () => {
    const withBuild = { ...base, build_calls: 25, build_usd: 0.31 }
    expect(spendLineText(withBuild)).toBe(spendLineText(base))
    const others = (text: string) => text.split('\n').filter((line) => !line.startsWith('New adventure being built:'))
    expect(others(spendHoverText(withBuild))).toEqual(others(spendHoverText(base)))
  })
})
