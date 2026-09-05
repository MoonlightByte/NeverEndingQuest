import type { Currency } from './characterData'

export function EmberCurrency({ currency }: { currency: Currency }) {
  return <div className="ember-currency-row">{[['GP', currency.gold], ['SP', currency.silver], ['CP', currency.copper]].map(([label, value]) => <div key={label} className="neq-currency"><span className={`ember-coin ember-coin-${label}`} aria-hidden="true" /><span>{label}</span> {value}</div>)}</div>
}
