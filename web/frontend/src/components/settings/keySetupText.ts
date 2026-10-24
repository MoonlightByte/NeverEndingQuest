import type { ServerEvents } from '../../contract/events'
import type { ProviderSettings } from '../../stores/dialogs'

/**
 * #1399: the player's OpenAI key lines, word for word from the audited plan
 * (plan-byo-key-ux-r2 section 6). The legacy page carries the same strings.
 */

export const KEY_HELP =
  'Needed for the Legacy and OpenAI providers. Saved on this machine and sent only to OpenAI. Environment variables such as OPENAI_API_KEY are not used here -- paste the key in this box. If a game is already running, restart the game to use a new key.'

export const KEY_RESTART = 'Restart the game to start using the new key.'

export const KEY_NO_KEYCHAIN =
  'No system keychain was found, so your key is saved in the file user_settings.json in the game folder. Anyone who can open that folder can read it. Do not share or upload that file.'

export const GUIDE_HEADING = 'One step before your adventure: your OpenAI API key'
export const GUIDE_INTRO =
  'NeverEndingQuest runs on your own OpenAI account, so you only pay OpenAI for what you play -- usually a few cents an hour.'
export const GUIDE_STEPS = [
  'Get a key: sign in at https://platform.openai.com/api-keys and choose "Create new secret key". Your account needs a little credit at https://platform.openai.com/settings/organization/billing.',
  'Copy the key. It starts with "sk-".',
  'Paste it in the box below and press Save.',
]
export const GUIDE_FOOTER = 'Your key is saved on this machine and is only ever sent to OpenAI.'

export const START_ADVENTURE = 'Start my adventure'

/** "about 20 seconds", or "about a minute" without a Retry-After. */
export function waitText(seconds: number | null | undefined): string {
  if (typeof seconds !== 'number' || seconds <= 0) return 'about a minute'
  if (seconds < 60) return `about ${seconds} ${seconds === 1 ? 'second' : 'seconds'}`
  const minutes = Math.round(seconds / 60)
  return minutes <= 1 ? 'about a minute' : `about ${minutes} minutes`
}

type KeyCheck = ServerEvents['openai_key_check']

/** The status line for a key check; null when no line applies. */
export function keyCheckText(check: KeyCheck): string | null {
  switch (check.result) {
    case 'checking':
      return 'Checking your key with OpenAI...'
    case 'accepted':
      return 'Key accepted. Your key is saved on this machine and is only ever sent to OpenAI.'
    case 'rejected':
      return 'OpenAI did not accept this key. Check that you copied the whole key (it starts with "sk-") and that it has not been revoked, then save it again.'
    case 'rate_limited':
      return `Your key is saved. OpenAI is limiting how often this account can make requests right now; new accounts start with lower limits that rise as you use them. Wait ${waitText(check.wait_seconds)}, then carry on.`
    case 'denied':
      return 'Your key is saved, but OpenAI refused access for this account. Check your OpenAI project settings at https://platform.openai.com/settings, or use a key from another project.'
    case 'no_quota':
      return 'OpenAI accepted this key, but the account has no credit left. Add credit to your OpenAI account; the game will use this key once it can.'
    case 'unreachable':
      return 'Could not reach OpenAI to check this key. It has been saved anyway; if it is wrong, the game will say so on your first turn.'
    case 'no_new_key':
      // With no saved key the guided panel says what to do instead.
      return check.has_key ? 'No new key entered. Your saved key was kept.' : null
  }
  return null
}

/** nql-55: "Start my adventure" only after these three results. */
export function canStartAfter(check: KeyCheck | null): boolean {
  return check !== null && ['accepted', 'rate_limited', 'unreachable'].includes(check.result)
}

/** The OpenAI key is needed and known to be missing (Legacy and OpenAI; the
 * server's default provider is OpenAI). Unknown status never blocks. */
export function needsOpenaiKey(settings: ProviderSettings): boolean {
  const provider = settings.provider ?? 'openai'
  return (provider === 'openai' || provider === 'legacy') && settings.openaiHasKey === false
}
