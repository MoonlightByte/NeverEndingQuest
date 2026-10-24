import { useLog } from '../../stores'
import { spendHoverText, spendLineText } from './spendText'

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
