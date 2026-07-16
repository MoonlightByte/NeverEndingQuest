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

  setLocation: (payload: ServerEvents['location_data_response']) => void
  setParty: (payload: ServerEvents['party_data_response']) => void
  setInitiative: (payload: ServerEvents['initiative_data_response']) => void
  setPlot: (payload: ServerEvents['plot_data_response']) => void
  setStorage: (payload: ServerEvents['storage_data_response']) => void
}

export const useWorld = create<WorldState>((set) => ({
  location: null,
  locationError: null,
  party: [],
  locationNpcs: [],
  initiative: { active: false, combatants: [], round: 0 },
  plot: null,
  plotError: null,
  storage: null,

  setLocation: (payload) =>
    set({ location: payload.data ?? null, locationError: payload.error ?? null }),
  setParty: (payload) =>
    set({ party: payload.members, locationNpcs: payload.location_npcs ?? [] }),
  setInitiative: (payload) =>
    set({
      initiative: {
        active: payload.active,
        combatants: payload.combatants,
        round: payload.round ?? 0,
      },
    }),
  setPlot: (payload) =>
    set({ plot: payload.data ?? null, plotError: payload.error ?? null }),
  setStorage: (payload) => set({ storage: payload.data }),
}))
