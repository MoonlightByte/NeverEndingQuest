import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'

export type PlayerDataType = 'stats' | 'inventory' | 'spells' | 'npcs'

export interface NpcDetails {
  npcName: string
  modalType: 'saves' | 'skills' | 'spells'
  data: Record<string, unknown> | null
  error?: string
}

export interface NpcInventory {
  npcName: string
  data: unknown[] | null
  error?: string
}

export interface PlayerState {
  serverInstanceId: string | null
  /** Character sheet data (player_data_response per dataType). */
  stats: Record<string, unknown> | null
  inventory: Record<string, unknown> | null
  spells: Record<string, unknown> | null
  /** Full NPC character files; never substitute party/location summaries. */
  npcs: Array<Record<string, unknown>>
  dataErrors: Partial<Record<PlayerDataType, string>>
  revisions: Record<PlayerDataType, number>
  /** NPC detail modal payloads (npc_details_response / npc_inventory_response). */
  npcDetails: NpcDetails | null
  npcInventory: NpcInventory | null

  setPlayerData: (payload: ServerEvents['player_data_response']) => void
  setNpcDetails: (payload: ServerEvents['npc_details_response']) => void
  setNpcInventory: (payload: ServerEvents['npc_inventory_response']) => void
  clearNpcModal: () => void
}

export const usePlayer = create<PlayerState>((set) => ({
  serverInstanceId: null,
  stats: null,
  inventory: null,
  spells: null,
  npcs: [],
  dataErrors: {},
  revisions: { stats: -1, inventory: -1, spells: -1, npcs: -1 },
  npcDetails: null,
  npcInventory: null,

  setPlayerData: (payload) =>
    set((s) => {
      const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
      const baseRevisions = changed ? { stats: -1, inventory: -1, spells: -1, npcs: -1 } : s.revisions
      if (payload.revision !== undefined && payload.revision < baseRevisions[payload.dataType]) return {}
      const dataErrors = { ...s.dataErrors }
      const revisions = { ...baseRevisions, [payload.dataType]: payload.revision ?? baseRevisions[payload.dataType] }
      const common = { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, dataErrors, revisions }
      if (payload.error) {
        dataErrors[payload.dataType] = payload.error
      } else {
        delete dataErrors[payload.dataType]
      }
      if (payload.dataType === 'stats') return { stats: payload.data, ...common }
      if (payload.dataType === 'inventory') return { inventory: payload.data, ...common }
      if (payload.dataType === 'spells') return { spells: payload.data, ...common }
      return { npcs: Array.isArray(payload.data) ? payload.data : [], ...common }
    }),
  setNpcDetails: (payload) =>
    set({
      npcDetails: {
        npcName: payload.npcName,
        modalType: payload.modalType,
        data: payload.data,
        error: payload.error,
      },
    }),
  setNpcInventory: (payload) =>
    set({
      npcInventory: {
        npcName: payload.npcName,
        data: payload.data,
        error: payload.error,
      },
    }),
  clearNpcModal: () => set({ npcDetails: null, npcInventory: null }),
}))
