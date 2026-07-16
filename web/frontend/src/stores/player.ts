import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'

export type PlayerDataType = 'stats' | 'inventory' | 'spells'

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
  /** Character sheet data (player_data_response per dataType). */
  stats: Record<string, unknown> | null
  inventory: Record<string, unknown> | null
  spells: Record<string, unknown> | null
  dataErrors: Partial<Record<PlayerDataType, string>>
  /** NPC detail modal payloads (npc_details_response / npc_inventory_response). */
  npcDetails: NpcDetails | null
  npcInventory: NpcInventory | null

  setPlayerData: (payload: ServerEvents['player_data_response']) => void
  setNpcDetails: (payload: ServerEvents['npc_details_response']) => void
  setNpcInventory: (payload: ServerEvents['npc_inventory_response']) => void
  clearNpcModal: () => void
}

export const usePlayer = create<PlayerState>((set) => ({
  stats: null,
  inventory: null,
  spells: null,
  dataErrors: {},
  npcDetails: null,
  npcInventory: null,

  setPlayerData: (payload) =>
    set((s) => {
      const dataErrors = { ...s.dataErrors }
      if (payload.error) {
        dataErrors[payload.dataType] = payload.error
      } else {
        delete dataErrors[payload.dataType]
      }
      if (payload.dataType === 'stats') return { stats: payload.data, dataErrors }
      if (payload.dataType === 'inventory') return { inventory: payload.data, dataErrors }
      return { spells: payload.data, dataErrors }
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
