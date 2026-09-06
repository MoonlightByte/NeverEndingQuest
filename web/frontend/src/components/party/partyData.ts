import { asString } from './media'

const identity = (name: string) => name.replace(/_/g, ' ').trim().toLocaleLowerCase()

/** Only match supplied identities, never infer an NPC from its class or portrait. */
export function matchingNpc(npcs: Record<string, unknown>[], name: string) {
  const matches = npcs.filter(npc => identity(asString(npc['name']) ?? '') === identity(name))
  return matches.length === 1 ? matches[0] : undefined
}

/** The live roster owns current combat values; full sheets supply optional XP. */
export function partySummary(roster: Record<string, unknown>, sheet?: Record<string, unknown> | null) {
  return { ...sheet, ...roster }
}
