/**
 * User-intent emitters for the right panel (plan Task 4.4d). Kept out of the
 * component files so those export only components (React fast refresh) and
 * so the tab->event mapping is testable in isolation. All names come from
 * the frozen contract.
 */
import { emitC } from '../../services/socket'

export type SheetTab = 'character' | 'inventory' | 'spells' | 'npcs' | 'debug'

export type NpcDetailTab = 'saves' | 'skills' | 'spells' | 'inventory'

/**
 * Emit the contract request that backs a right-panel tab. The frozen
 * contract's request_player_data dataType union is 'stats' | 'inventory' |
 * 'spells', so the NPCs roster comes from request_party_data
 * (party_data_response members carry type: 'npc'). Debug is local-only
 * (debug_output ring) and needs no request.
 */
export function requestTabData(tab: SheetTab): void {
  if (tab === 'character') {
    emitC('request_player_data', { dataType: 'stats' })
  } else if (tab === 'inventory') {
    emitC('request_player_data', { dataType: 'inventory' })
  } else if (tab === 'spells') {
    emitC('request_player_data', { dataType: 'spells' })
  } else if (tab === 'npcs') {
    emitC('request_party_data', undefined)
  }
}

/** Emit the contract request that backs an NPC detail modal tab. */
export function requestNpcTabData(tab: NpcDetailTab, npcName: string): void {
  if (tab === 'saves') emitC('request_npc_saves', { npcName })
  else if (tab === 'skills') emitC('request_npc_skills', { npcName })
  else if (tab === 'spells') emitC('request_npc_spells', { npcName })
  else emitC('request_npc_inventory', { npcName })
}
