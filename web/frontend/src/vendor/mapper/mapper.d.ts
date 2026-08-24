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
    destroy(): void;
  }
  export interface MapperOpts {
    uid?: string;
    mode?: 'interior' | 'overland';
    fontCss?: boolean;
    quiet?: boolean;
    /** Multiplies room-name/type-tag text size (0.5–3, default 1). Map furniture is unaffected. */
    labelScale?: number;
  }
  export function createMap(
    container: HTMLElement,
    mapJson: unknown,
    areaJson?: unknown,
    opts?: MapperOpts
  ): MapperHandle;
}
