declare module 'mapper-lib' {
  export interface MapperGraph {
    mapId: string;
    mapName: string;
    rooms: Map<string, { id: string; name: string; type: string; connections: string[]; gx: number; gy: number }>;
    edges: Array<{ a: string; b: string; twoWay: boolean; from?: string }>;
    warnings: string[];
  }
  export interface MapperHandle {
    svg: SVGSVGElement;
    graph: MapperGraph;
    reveal(id: string): void;
    revealAll(): void;
    setRevealed(ids: string[]): void;
    revealed(): string[];
    /** Cancels pending reveal timers/animations without clearing the DOM. */
    dispose(): void;
    /** dispose() plus clears the container. */
    destroy(): void;
  }
  export interface MapperPalette {
    bg: string; ink: string; accent: string; floor: string;
    grainPaper: [number, number, number, number];
    grainBlotch: [number, number, number, number] | null;
    blend: 'multiply' | 'screen'; paperOpacity: number; blotchOpacity: number;
    vig: [string, string];
  }
  export interface MapperOpts {
    uid?: string;
    mode?: 'interior' | 'overland';
    fontCss?: boolean;
    quiet?: boolean;
    /** Multiplies room-name/type-tag text size (0.5–3, default 1). Map furniture is unaffected. */
    labelScale?: number;
    /** 'day' (parchment, default), 'night' (ink on dark), or a partial palette merged over day. */
    palette?: 'day' | 'night' | Partial<MapperPalette>;
    /** Reveal animation timings in ms (defaults 900 / 700); `instant` skips animation. */
    trailMs?: number;
    fadeMs?: number;
    instant?: boolean;
  }
  /**
   * DOM contract: every room group `[data-room]` carries `data-anchor="x,y"`
   * (the room's layout position, in the 1200x900 viewBox) and every overland
   * edge group `[data-edge]` carries `data-mid="x,y"` (its curve control point).
   * Hosts should fit and place markers from these, not from measured bounds.
   */
  export const PALETTES: { day: MapperPalette; night: MapperPalette };
  /**
   * `mapJson` may carry an optional `grid: { cols, rows, originX, originY }`
   * (all integers; cols/rows >= 1) describing the WHOLE area's extent as the
   * host computed it: origin is the smallest X/Y over every room in the area.
   * Hosts that redact hidden rooms should pass it — coordinates are then
   * normalised against that origin and the canvas keeps the area's full
   * cols/rows, so explored rooms stay put as the reveal set grows. With `grid`
   * present, rooms whose coordinates are missing or unparseable are omitted
   * (with a warning) along with their connections instead of being auto-placed.
   */
  export function createMap(
    container: HTMLElement,
    mapJson: unknown,
    areaJson?: unknown,
    opts?: MapperOpts
  ): MapperHandle;
}
