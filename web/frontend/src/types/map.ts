/**
 * Spoiler-safe fog-of-war map payload shape. Mirrors the projection the server
 * sends -- keep in sync with the server's payload, not with any client
 * assumption. SECURITY NOTE: the server sends a spoiler-safe projection, so
 * unrevealed rooms never carry name/type. Coordinates are further restricted:
 * only revealed rooms and their direct ("frontier") neighbours carry
 * coordinates -- a frontier room's coordinates let the client draw a stub
 * trail toward it. Rooms two or more steps from any revealed room get
 * coordinates: null; because the payload also carries `map.grid`, the mapper
 * omits those rooms entirely rather than auto-placing them, so the explored
 * rooms keep their positions as the reveal set grows.
 */
export interface MapRoom {
  id: string
  /** null when unrevealed and not a frontier neighbour (or the source room record is malformed); with map.grid present the mapper omits such rooms */
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
    /**
     * The WHOLE area's extent and origin (smallest X/Y over every room with
     * parseable coordinates), so the renderer normalises against the area
     * rather than against the rooms that happen to be visible. Omitted when
     * no room has parseable X#Y# coordinates.
     */
    grid?: { cols: number; rows: number; originX: number; originY: number }
  }
  area: {
    areaType?: string | null
    terrain?: string | null
    climate?: string | null
    areaDescription?: string | null
  }
  revealed: string[]
  currentLocationId: string | null
  /** Count of real rooms not yet revealed (known_room_ids - revealed_set on the server). */
  undiscoveredCount?: number
}
