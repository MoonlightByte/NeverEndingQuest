import { mulberry32, hashSeed } from './primitives.js';

const FURNITURE = [
  { x0: 900, y0: 36, x1: 1160, y1: 130 },  // cartouche
  { x0: 56, y0: 66, x1: 190, y1: 190 },    // compass
  { x0: 860, y0: 830, x1: 1050, y1: 870 }  // scale bar
];
const DENSITY = { tree: 0.5, reed: 0.38, peak: 0.3, rubble: 0.14, grass: 0.1, stone: 0.22 };

function kindsFor(area) {
  const text = `${area.areaType} ${area.terrain}`.toLowerCase();
  const kinds = [];
  const indoor = /dungeon|crypt|tomb|cave|cavern|underground|passage|cell|chamber/.test(text);
  const paved = /keep|castle|ruin/.test(text);
  if (indoor) kinds.push(['stone', 0.8], ['rubble', 0.2]);
  else {
    if (/forest|wood/.test(text)) kinds.push(['tree', 1]);
    if (/marsh|swamp|bog/.test(text)) kinds.push(['reed', 0.92], ['pool', 0.08]);
    if (/mountain|hill|crag/.test(text)) kinds.push(['peak', 1]);
    if (paved) kinds.push(['rubble', 1]);
  }
  // base ground cover between features: flagstones underground and in
  // fortresses, grass tufts everywhere else
  return { kinds, base: indoor || paved ? 'stone' : 'grass' };
}

function samplePath(A, mid, B, n) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, u = 1 - t;
    pts.push([u * u * A.x + 2 * u * t * mid[0] + t * t * B.x, u * u * A.y + 2 * u * t * mid[1] + t * t * B.y]);
  }
  return pts;
}

export function planFlavor(graph, layout) {
  const rng = mulberry32(hashSeed(graph.mapId + ':flavor'));
  const { kinds, base } = kindsFor(graph.area);
  const totalW = kinds.reduce((s, [, w]) => s + w, 0);
  const trailPts = layout.trails.flatMap(t => samplePath(layout.rooms.get(t.a), t.mid, layout.rooms.get(t.b), 12));
  const decos = [];
  const { x, y, w, h } = layout.content;
  for (let gy = y; gy <= y + h; gy += 34) {
    for (let gx = x; gx <= x + w; gx += 34) {
      const px = Math.min(x + w, Math.max(x, gx + (rng() - 0.5) * 22));
      const py = Math.min(y + h, Math.max(y, gy + (rng() - 0.5) * 22));
      const roll = rng(), sizeRoll = rng(), kindRoll = rng();
      if (FURNITURE.some(f => px >= f.x0 && px <= f.x1 && py >= f.y0 && py <= f.y1)) continue;
      let nearRoom = null, nd = Infinity;
      for (const [id, r] of layout.rooms) { const d = Math.hypot(px - r.x, py - r.y); if (d < nd) { nd = d; nearRoom = id; } }
      if (nd < 70) continue;
      if (trailPts.some(([tx, ty]) => Math.hypot(px - tx, py - ty) < 26)) continue;
      let kind = base;
      if (kinds.length && kindRoll < 0.86) {
        let acc = 0, pick = rng() * totalW;
        for (const [k, wt] of kinds) { acc += wt; if (pick <= acc) { kind = k; break; } }
      }
      if (roll > DENSITY[kind === 'pool' ? 'reed' : kind]) continue;
      decos.push({ kind, x: +px.toFixed(1), y: +py.toFixed(1), s: +(7 + sizeRoll * 5).toFixed(1), seed: Math.floor(rng() * 1e9), nearRoom });
    }
  }
  return decos;
}
