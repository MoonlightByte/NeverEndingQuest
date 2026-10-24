import { useLog } from '../../stores'
import type { ServerEvents } from '../../contract/events'

type Spend = NonNullable<ServerEvents['token_update']['spend']>

/** The approved disclaimer (#1388), verbatim; <priced_at> is the catalog's list-price date. */
export function spendDisclaimer(pricedAt: string): string {
  return `Estimate only: worked out from the token usage OpenAI reports with each response, at OpenAI's list prices dated ${pricedAt}. Your OpenAI bill is the authority.`
}

function dollars(usd: number): string {
  return usd < 0.01 ? 'under $0.01' : `about $${usd.toFixed(2)}`
}

/** The header text for one spend snapshot. */
export function spendLineText(spend: Spend): string {
  if (!spend.available) return 'This session: estimate unavailable'
  const calls = `This session: ${spend.calls} AI ${spend.calls === 1 ? 'call' : 'calls'}`
  if (spend.provider_kind === 'local') return `${calls}, local model`
  if (spend.provider_kind !== 'openai') return calls
  const other = spend.portraits + spend.voice > 0 ? '; images and voice not included' : ''
  return `${calls}, ${dollars(spend.usd)} for AI text${other}`
}

/** The hover breakdown: this turn, tokens, the unpriced counts, billed retries, the disclaimer. */
export function spendHoverText(spend: Spend): string {
  const lines = [
    `This turn: ${spend.turn_calls} AI ${spend.turn_calls === 1 ? 'call' : 'calls'}` +
      (spend.provider_kind === 'openai' ? `, ${dollars(spend.turn_usd)}` : ''),
    `Tokens: ${spend.prompt.toLocaleString()} in (${spend.cached.toLocaleString()} cached), ${spend.completion.toLocaleString()} out`,
  ]
  if (spend.portraits + spend.voice > 0) lines.push(`Images: ${spend.portraits}, voice clips: ${spend.voice} (not priced)`)
  if (spend.possibly_billed > 0) lines.push(`${spend.possibly_billed} ${spend.possibly_billed === 1 ? 'retry' : 'retries'} that failed part-way may also have been billed.`)
  if (spend.provider_kind === 'openai') lines.push(spendDisclaimer(spend.priced_at))
  return lines.join('\n')
}

/** The session cost line in the header (#1388). Hidden until the server sends a snapshot. */
export function SpendLine() {
  const spend = useLog((s) => s.tokens.spend)
  if (!spend) return null
  const hover = spendHoverText(spend)
  return (
    <div className="neq-spend-line font-chrome text-xs text-secondary whitespace-nowrap" title={hover} aria-label={`${spendLineText(spend)}. ${hover}`} tabIndex={0}>
      {spendLineText(spend)}
    </div>
  )
}
