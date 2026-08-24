/**
 * Spoiler-safe fog-of-war map payload shape. Mirrors the server projection in
 * web/map_projection.py::project_map_payload -- keep in sync with that module,
 * not with any client assumption. Unrevealed rooms carry id/coordinates only
 * (no name/type), per the SECURITY NOTE in map_projection.py.
 */
export interface MapRoom {
  id: string
  /** null when the source room record is malformed; the mapper auto-places such rooms */
  coordinates: string | null
  connections: string[]
  name?: string
  type?: string
}

export interface MapDataPayload {
  areaId: string
  areaName: string
  map: {
    mapId: string
    mapName: string
    rooms: MapRoom[]
  }
  area: {
    areaType?: string | null
    terrain?: string | null
    climate?: string | null
    areaDescription?: string | null
  }
  revealed: string[]
  currentLocationId: string | null
}
