import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'

export type LocationData = NonNullable<ServerEvents['location_data_response']['data']>
export type PartyMember = Record<string, unknown>
export type Combatant = Record<string, unknown>
export type PlotData = NonNullable<ServerEvents['plot_data_response']['data']>

export interface InitiativeState {
  active: boolean
  combatants: Combatant[]
  round: number
}

export interface WorldState {
  serverInstanceId: string | null
  /** Current location + in-game time (location_data_response). */
  location: LocationData | null
  locationError: string | null
  /** Party members and NPCs present at the location (party_data_response). */
  party: PartyMember[]
  locationNpcs: PartyMember[]
  /** Combat initiative (initiative_data_response). */
  initiative: InitiativeState
  /** Plot / journal data (plot_data_response). */
  plot: PlotData | null
  plotError: string | null
  /** Player storage (storage_data_response). */
  storage: Record<string, unknown> | null
  revisions: Record<'location' | 'party' | 'initiative' | 'plot' | 'storage', number>

  setLocation: (payload: ServerEvents['location_data_response']) => void
  setParty: (payload: ServerEvents['party_data_response']) => void
  setInitiative: (payload: ServerEvents['initiative_data_response']) => void
  setPlot: (payload: ServerEvents['plot_data_response']) => void
  setStorage: (payload: ServerEvents['storage_data_response']) => void
}

export const useWorld = create<WorldState>((set) => ({
  serverInstanceId: null,
  location: null,
  locationError: null,
  party: [],
  locationNpcs: [],
  initiative: { active: false, combatants: [], round: 0 },
  plot: null,
  plotError: null,
  storage: null,
  revisions: { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 },

  setLocation: (payload) =>
    set((s) => {
      const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
      const revisions = changed ? { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 } : s.revisions
      if (payload.revision !== undefined && payload.revision < revisions.location) return {}
      return { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, location: payload.data ?? null, locationError: payload.error ?? null, revisions: { ...revisions, location: payload.revision ?? revisions.location } }
    }),
  setParty: (payload) =>
    set((s) => {
      const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
      const revisions = changed ? { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 } : s.revisions
      if (payload.revision !== undefined && payload.revision < revisions.party) return {}
      return { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, party: payload.members, locationNpcs: payload.location_npcs ?? [], revisions: { ...revisions, party: payload.revision ?? revisions.party } }
    }),
  setInitiative: (payload) =>
    set((s) => {
      const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
      const revisions = changed ? { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 } : s.revisions
      if (payload.revision !== undefined && payload.revision < revisions.initiative) return {}
      return {
      serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
      initiative: {
        active: payload.active,
        combatants: payload.combatants,
        round: payload.round ?? 0,
      }, revisions: { ...revisions, initiative: payload.revision ?? revisions.initiative },
    }}),
  setPlot: (payload) =>
    set((s) => {
      const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
      const revisions = changed ? { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 } : s.revisions
      if (payload.revision !== undefined && payload.revision < revisions.plot) return {}
      return { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, plot: payload.data ?? null, plotError: payload.error ?? null, revisions: { ...revisions, plot: payload.revision ?? revisions.plot } }
    }),
  setStorage: (payload) => set((s) => {
    const changed = Boolean(payload.server_instance_id && payload.server_instance_id !== s.serverInstanceId)
    const revisions = changed ? { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 } : s.revisions
    if (payload.revision !== undefined && payload.revision < revisions.storage) return {}
    return { serverInstanceId: payload.server_instance_id ?? s.serverInstanceId, storage: payload.error ? { success: false, error: payload.error } : payload.data, revisions: { ...revisions, storage: payload.revision ?? revisions.storage } }
  }),
}))
