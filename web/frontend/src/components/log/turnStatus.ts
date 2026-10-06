import { useSession } from '../../stores'

/** Presentation only: never changes turn gates, provider calls or retries. */
export function turnStatusText(message: string): string {
  // Keep actionable operational failures explicit, even when they need more
  // than one line. Do not dress up a recovery instruction as normal progress.
  if (/error|failed|recovery|retry|rate limit|quota|paused|timed out|timeout|unavailable|disconnected|cancel|blocked|denied|settings|configuration|authentication|billing|credit|40[123]/i.test(message)) return message
  if (/companion|voices/i.test(message)) return 'Your companions are sharing their thoughts…'
  if (/character/i.test(message)) return 'Your deeds leave their mark…'
  if (/level.?up/i.test(message)) return 'Your hero grows stronger…'
  if (/party/i.test(message)) return 'Your party gathers its bearings…'
  if (/combat|encounter/i.test(message)) return 'The clash unfolds…'
  if (/location|travel/i.test(message)) return 'The path ahead comes into view…'
  if (/journal|summary|history|compress|saving/i.test(message)) return 'Your tale is being recorded…'
  if (/plot/i.test(message)) return 'The threads of your tale unfold…'
  if (/world time/i.test(message)) return 'Time moves on around you…'
  if (/loading|welcome/i.test(message)) return 'Your adventure comes into view…'
  return 'The Dungeon Master is weaving the tale'
}

export function useTurnStatus(): string | null {
  const busy = useSession((s) => s.isProcessing)
  const message = useSession((s) => s.statusMessage)
  const recovery = useSession((s) => s.restoreRecoveryRequired)
  const welcome = useSession((s) => s.welcomeMessage)
  if (recovery) return message || 'Gameplay is paused. Use the recovery controls to continue.'
  if (busy) return turnStatusText(message)
  if (welcome) return `${turnStatusText(welcome)} You can act anytime.`
  return null
}
