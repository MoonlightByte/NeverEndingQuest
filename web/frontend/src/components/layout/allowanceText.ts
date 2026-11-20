import type { PlayAllowancePayload, PlayAllowancePeriod } from '../../contract/events'

/**
 * #2072: the play allowance's words (owner D-UX-5, plan-2072-r1-a2), whole. The server has the same
 * composer lines for the terminal (utils/play_allowance.py). Times are the player's local time.
 */

const SAVED = ' Your adventure is saved.'

function clock(iso: string): string {
  // Some engines put a narrow or no-break space before AM/PM; the approved words use a plain space.
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }).replace(/[\u202f\u00a0]/g, ' ')
}

function weekday(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', { weekday: 'long' })
}

/** True when the allowance should be shown at all: a good read for a limited player. */
export function allowanceShown(value: PlayAllowancePayload | null): value is PlayAllowancePayload & { limited: true; day: PlayAllowancePeriod; week: PlayAllowancePeriod } {
  return !!value && !value.unavailable && value.limited === true && !!value.day && !!value.week && !!value.state
}

/** True when a new submission (or a start) is locked by the allowance. */
export function allowanceLocked(value: PlayAllowancePayload | null): boolean {
  return allowanceShown(value) && value.state !== 'ok'
}

function weekUsed(value: PlayAllowancePayload & { week: PlayAllowancePeriod }): boolean {
  return value.week.used_fraction >= 1
}

/** The time the line names: resume_at, else the reset of the week (when used) or the day. */
function shownTime(value: PlayAllowancePayload & { day: PlayAllowancePeriod; week: PlayAllowancePeriod }): string | null {
  if (value.state === 'paused_for_everyone') return value.resume_at ?? null
  if (value.state === 'player_limit') {
    if (value.resume_at) return value.resume_at
    return (weekUsed(value) ? value.week : value.day).resets_at ?? null
  }
  return null
}

/** The composer line for a locked state, or null. */
export function allowanceLine(value: PlayAllowancePayload | null): string | null {
  if (!allowanceShown(value) || value.state === 'ok') return null
  if (value.state === 'paused_for_account') {
    return 'Free play is paused for this account. Please contact us if you think this is a mistake.'
  }
  const time = shownTime(value)
  if (value.state === 'paused_for_everyone') {
    return time === null
      ? 'Free play is paused for everyone right now. Please check back later.' + SAVED
      : `Free play is paused for everyone right now. It comes back at ${clock(time)}.` + SAVED
  }
  if (time === null) return "You've used your free play for now. Please check back later." + SAVED
  if (weekUsed(value)) return `You've used this week's free play. You can play again on ${weekday(time)} at ${clock(time)}.` + SAVED
  return `You've used today's free play. You can play again at ${clock(time)}.` + SAVED
}

/** A bar's words: minutes left, or the percent used when there is no estimate. */
export function barLine(period: 'day' | 'week', p: PlayAllowancePeriod): string {
  const when = period === 'day' ? 'Today' : 'This week'
  if (p.minutes_left_estimate === null) return `${when}: ${Math.round(p.used_fraction * 100)}% of your free play used`
  return `${when}: about ${Math.round(p.minutes_left_estimate)} minutes of play left`
}
