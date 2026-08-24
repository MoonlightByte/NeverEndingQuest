import { parseMap } from './parser.js';
import { renderMap } from './render.js';
import { createFog } from './fog.js';
import { hasGlyph } from './glyphs.js';

export { parseMap, renderMap, createFog };

export function createMap(container, mapJson, areaJson = null, opts = {}) {
  const graph = parseMap(mapJson, areaJson);
  const warn = opts.quiet ? () => {} : (...args) => console.warn(...args);
  if (!areaJson) warn(`mapper[${graph.mapId}]: no area metadata; render mode inferred from map name`);
  const uid = opts.uid || graph.mapId.replace(/[^a-zA-Z0-9_-]/g, '_');
  container.innerHTML = renderMap(graph, { uid, mode: opts.mode, fontCss: opts.fontCss, labelScale: opts.labelScale });
  const svg = container.querySelector('svg');
  const fog = createFog(svg, graph, opts);
  for (const w of graph.warnings) warn(`mapper[${graph.mapId}]: ${w}`);
  for (const r of graph.rooms.values()) if (!hasGlyph(r.type)) warn(`mapper[${graph.mapId}]: room ${r.id} type "${r.type}" has no glyph, using fallback`);
  return { svg, graph, ...fog, destroy: () => { fog.dispose(); container.innerHTML = ''; } };
}
