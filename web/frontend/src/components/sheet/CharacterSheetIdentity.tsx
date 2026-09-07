import type { ReactNode } from 'react'
import { EmberCurrency } from './EmberCurrency'
import { capitalizeWords, currencyOf, num, str } from './characterData'
import '../../theme/tavern-sheet-polish.css'

/** Shared identity grid keeps the player and companion sheets aligned. */
export function CharacterSheetIdentity({ stats, portrait }: { stats: Record<string, unknown>; portrait: ReactNode }) {
  const xp = num(stats['experience_points'])
  const next = num(stats['exp_required_for_next_level'])
  const hasXp = stats['experience_points'] !== undefined && stats['exp_required_for_next_level'] !== undefined
  return <header className="tcs-identity">
    <div className="tcs-portrait">{portrait}</div>
    <div className="tcs-name">
      <h3>{str(stats['name'], 'Unknown Adventurer')}</h3>
      <p className="tcs-class-line">Level {num(stats['level'], 1)} · {[str(stats['race']), str(stats['class'])].filter(Boolean).join(' ')}</p>
      <p className="tcs-background-line">{[str(stats['background']), capitalizeWords(str(stats['alignment']))].filter(Boolean).join(' · ')}</p>
    </div>
    <div className="tcs-progression">
      {hasXp && <div className="tcs-experience">
        <div className="tcs-experience-line"><span className="tcs-label">Experience</span><strong>{xp} / {next}</strong></div>
        <div className="tcs-xp-track" role="progressbar" aria-label="Experience" aria-valuemin={0} aria-valuemax={Math.max(next, xp, 1)} aria-valuenow={Math.max(0, xp)}><span style={{ width: `${Math.max(0, Math.min(100, xp / (next || 1) * 100))}%` }} /></div>
        <span className="tcs-next-level">Next level at {next} XP</span>
      </div>}
      {stats['currency'] !== undefined && <EmberCurrency currency={currencyOf(stats)} />}
    </div>
  </header>
}
