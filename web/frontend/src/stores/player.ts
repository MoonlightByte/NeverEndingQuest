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
  connectionEpoch: number
  serverInstanceId: string | null
  /** Character sheet data (player_data_response per dataType). */
  stats: Record<string, unknown> | null
  inventory: Record<string, unknown> | null
  spells: Record<string, unknown> | null
  /** Full NPC character files; never substitute party/location summaries. */
  npcs: Array<Record<string, unknown>>
  dataErrors: Partial<Record<PlayerDataType, string>>
  /** Benign empty-state notices (no character yet); rendered neutral, not red. */
  dataNotices: Partial<Record<PlayerDataType, string>>
  revisions: Record<PlayerDataType, number>
  /** NPC detail modal payloads (npc_details_response / npc_inventory_response). */
  npcDetails: NpcDetails | null
  npcInventory: NpcInventory | null

  beginConnection: (epoch: number) => void
  bindServerInstance: (epoch: number, serverInstanceId?: string) => void
  setPlayerData: (payload: ServerEvents['player_data_response']) => void
  setNpcDetails: (payload: ServerEvents['npc_details_response']) => void
  setNpcInventory: (payload: ServerEvents['npc_inventory_response']) => void
  clearNpcModal: () => void
}

export const usePlayer = create<PlayerState>((set) => ({
  connectionEpoch: 0,
  serverInstanceId: null,
  stats: null,
  inventory: null,
  spells: null,
  npcs: [],
  dataErrors: {},
  dataNotices: {},
  revisions: { stats: -1, inventory: -1, spells: -1, npcs: -1 },
  npcDetails: null,
  npcInventory: null,

  beginConnection: (epoch) =>
    set((s) => epoch <= s.connectionEpoch ? {} : ({
      connectionEpoch: epoch,
      serverInstanceId: null,
      revisions: { stats: -1, inventory: -1, spells: -1, npcs: -1 },
    })),
  bindServerInstance: (epoch, serverInstanceId) =>
    set((s) => {
      if (epoch !== s.connectionEpoch || !serverInstanceId) return {}
      if (s.serverInstanceId && s.serverInstanceId !== serverInstanceId) return {}
      return { serverInstanceId }
    }),

  setPlayerData: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      if (payload.revision !== undefined && payload.revision < s.revisions[payload.dataType]) return {}
      const dataErrors = { ...s.dataErrors }
      const dataNotices = { ...s.dataNotices }
      const revisions = { ...s.revisions, [payload.dataType]: payload.revision ?? s.revisions[payload.dataType] }
      const common = { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, dataErrors, dataNotices, revisions }
      if (payload.error) {
        dataErrors[payload.dataType] = payload.error
        delete dataNotices[payload.dataType]
        return common
      }
      delete dataErrors[payload.dataType]
      const notice = 'notice' in payload ? payload.notice : undefined
      if (notice && payload.data === null && payload.dataType !== 'npcs') {
        dataNotices[payload.dataType] = notice
        return { [payload.dataType]: null, ...common }
      }
      delete dataNotices[payload.dataType]
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
