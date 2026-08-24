import { create } from 'zustand'
import type { ServerEvents } from '../contract/events'
import type { MapDataPayload } from '../types/map'

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
  connectionEpoch: number
  serverInstanceId: string | null
  /** Current location + in-game time (location_data_response). */
  location: LocationData | null
  locationError: string | null
  /** Party members and NPCs present at the location (party_data_response). */
  party: PartyMember[]
  locationNpcs: PartyMember[]
  partyError: string | null
  /** Combat initiative (initiative_data_response). */
  initiative: InitiativeState
  initiativeError: string | null
  /** Plot / journal data (plot_data_response). */
  plot: PlotData | null
  plotError: string | null
  /** Player storage (storage_data_response). */
  storage: Record<string, unknown> | null
  storageError: string | null
  /** Spoiler-safe fog-of-war map for the current area (map_data_response). */
  mapData: MapDataPayload | null
  mapDataError: string | null
  /**
   * Highest `revision` ever accepted into `mapData`, across all areas.
   * `revision` is one server-wide monotonic counter shared by every
   * `_ui_response` event (see web/web_interface.py::_ui_response), not a
   * per-area sequence, so a response with a lower revision than this floor
   * is always stale -- even for a *different* areaId (e.g. a delayed/retried
   * response for a previous area arriving after the area transition already
   * landed). A genuine area transition always carries a higher revision than
   * anything seen for the prior area, so it is still accepted.
   */
  mapDataRevision: number
  revisions: Record<'location' | 'party' | 'initiative' | 'plot' | 'storage', number>

  beginConnection: (epoch: number) => void
  bindServerInstance: (epoch: number, serverInstanceId?: string) => void
  setLocation: (payload: ServerEvents['location_data_response']) => void
  setParty: (payload: ServerEvents['party_data_response']) => void
  setInitiative: (payload: ServerEvents['initiative_data_response']) => void
  setPlot: (payload: ServerEvents['plot_data_response']) => void
  setStorage: (payload: ServerEvents['storage_data_response']) => void
  setMapData: (payload: ServerEvents['map_data_response']) => void
}

export const useWorld = create<WorldState>((set) => ({
  connectionEpoch: 0,
  serverInstanceId: null,
  location: null,
  locationError: null,
  party: [],
  locationNpcs: [],
  partyError: null,
  initiative: { active: false, combatants: [], round: 0 },
  initiativeError: null,
  plot: null,
  plotError: null,
  storage: null,
  storageError: null,
  mapData: null,
  mapDataError: null,
  mapDataRevision: -1,
  revisions: { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 },

  beginConnection: (epoch) =>
    set((s) => epoch <= s.connectionEpoch ? {} : ({
      connectionEpoch: epoch,
      serverInstanceId: null,
      mapDataRevision: -1,
      revisions: { location: -1, party: -1, initiative: -1, plot: -1, storage: -1 },
    })),
  bindServerInstance: (epoch, serverInstanceId) =>
    set((s) => {
      if (epoch !== s.connectionEpoch || !serverInstanceId) return {}
      if (s.serverInstanceId && s.serverInstanceId !== serverInstanceId) return {}
      return { serverInstanceId }
    }),

  setLocation: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      if (payload.revision !== undefined && payload.revision < s.revisions.location) return {}
      const common = {
        serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
        locationError: payload.error ?? null,
        revisions: { ...s.revisions, location: payload.revision ?? s.revisions.location },
      }
      return payload.error ? common : { ...common, location: payload.data ?? null }
    }),
  setParty: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      if (payload.revision !== undefined && payload.revision < s.revisions.party) return {}
      const common = {
        serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
        partyError: payload.error ?? null,
        revisions: { ...s.revisions, party: payload.revision ?? s.revisions.party },
      }
      return payload.error ? common : { ...common, party: payload.members, locationNpcs: payload.location_npcs ?? [] }
    }),
  setInitiative: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      if (payload.revision !== undefined && payload.revision < s.revisions.initiative) return {}
      const common = {
        serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
        initiativeError: payload.error ?? null,
        revisions: { ...s.revisions, initiative: payload.revision ?? s.revisions.initiative },
      }
      return payload.error ? common : {
        ...common,
        initiative: {
          active: payload.active,
          combatants: payload.combatants,
          round: payload.round ?? 0,
        },
      }
    }),
  setPlot: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      if (payload.revision !== undefined && payload.revision < s.revisions.plot) return {}
      const common = {
        serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
        plotError: payload.error ?? null,
        revisions: { ...s.revisions, plot: payload.revision ?? s.revisions.plot },
      }
      return payload.error ? common : { ...common, plot: payload.data ?? null }
    }),
  setStorage: (payload) => set((s) => {
    if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
    if (payload.revision !== undefined && payload.revision < s.revisions.storage) return {}
    const common = {
      serverInstanceId: payload.server_instance_id ?? s.serverInstanceId,
      storageError: payload.error ?? null,
      revisions: { ...s.revisions, storage: payload.revision ?? s.revisions.storage },
    }
    return payload.error ? common : { ...common, storage: payload.data }
  }),
  setMapData: (payload) =>
    set((s) => {
      if (payload.server_instance_id && s.serverInstanceId && payload.server_instance_id !== s.serverInstanceId) return {}
      const serverInstanceId = payload.server_instance_id ?? s.serverInstanceId
      // `{data: null}` (transient read failure, or no active area yet) is a
      // decision NOT to update mapData: it only surfaces the error and keeps
      // whatever map was last displayed, so a single flaky read never blanks
      // the panel mid-session. Only a non-null payload ever replaces mapData.
      if (!payload.data) {
        return { serverInstanceId, mapDataError: payload.error ?? null }
      }
      if (payload.revision !== undefined && payload.revision < s.mapDataRevision) return {}
      return {
        serverInstanceId,
        mapData: payload.data,
        mapDataError: null,
        mapDataRevision: payload.revision ?? s.mapDataRevision,
      }
    }),
}))
