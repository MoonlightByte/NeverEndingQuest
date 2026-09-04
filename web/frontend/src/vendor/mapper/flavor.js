import { mulberry32, hashSeed } from './primitives.js';
export { FURNITURE };

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
    if (/forest|wood|grove|fringe/.test(text)) kinds.push(['tree', 1]);
    if (/marsh|swamp|bog|mire|fen/.test(text)) kinds.push(['reed', 0.92], ['pool', 0.08]);
    if (/mountain|hill|crag|outcrop|moor|ridge|rocky/.test(text)) kinds.push(['peak', 1]);
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

// ---------------------------------------------------------------------------
// Flavour planner: clustered terrain masses instead of evenly
// scattered singletons, a sparser base cover that thins with distance from
// the rooms, and avoidance of the already-planned label boxes.
export function planFlavor(graph, layout, ctx = {}) {
  const rng = mulberry32(hashSeed(graph.mapId + ':flavor2'));
  const { kinds, base } = kindsFor(graph.area);
  const kindSet = new Set(kinds.map(k => k[0]));
  const s = ctx.scale || 1;
  const labelBoxes = ctx.labelBoxes || [];
  const trailPts = layout.trails.flatMap(t => samplePath(layout.rooms.get(t.a), t.mid, layout.rooms.get(t.b), 16));
  const rooms = [...layout.rooms.entries()];
  const { x, y, w, h } = layout.content;
  const decos = [];
  const roomClear = 46 * s;

  const nearest = (px, py) => { let id = null, nd = Infinity; for (const [rid, r] of rooms) { const d = Math.hypot(px - r.x, py - r.y); if (d < nd) { nd = d; id = rid; } } return { id, nd }; };
  const inFurniture = (px, py, pad = 0) => FURNITURE.some(f => px >= f.x0 - pad && px <= f.x1 + pad && py >= f.y0 - pad && py <= f.y1 + pad);
  const inLabel = (px, py, pad = 0) => labelBoxes.some(b => px >= b[0] - pad && px <= b[2] + pad && py >= b[1] - pad && py <= b[3] + pad);
  const nearTrail = (px, py, d) => trailPts.some(([tx, ty]) => Math.hypot(px - tx, py - ty) < d);
  const centres = [];
  const clear = (px, py, rad) => px > x + rad * 0.8 && px < x + w - rad * 0.8 && py > y + rad * 0.8 && py < y + h - rad * 0.8
    && !inFurniture(px, py, rad) && !inLabel(px, py, rad * 0.7) && !nearTrail(px, py, rad * 0.55 + 8) && nearest(px, py).nd > roomClear * 0.7 + rad * 0.6
    && !centres.some(c => Math.hypot(c.x - px, c.y - py) < c.r + rad + 18);

  // rejection-sample a mass centre; prefer a band 80-170px from the nearest room
  function pickCentre(rad, tries = 60) {
    let best = null, bs = -Infinity;
    for (let i = 0; i < tries; i++) {
      const px = x + rad + rng() * (w - 2 * rad), py = y + rad + rng() * (h - 2 * rad);
      if (!clear(px, py, rad)) continue;
      const { nd } = nearest(px, py);
      const score = -Math.abs(nd - 140);
      if (score > bs) { bs = score; best = [px, py]; }
    }
    if (best) centres.push({ x: best[0], y: best[1], r: rad });
    return best;
  }

  const push = (d) => decos.push({ ...d, x: +d.x.toFixed(1), y: +d.y.toFixed(1), seed: Math.floor(rng() * 1e9), nearRoom: nearest(d.x, d.y).id });

  if (kindSet.has('tree')) {
    const stands = 5 + Math.floor(rng() * 4);
    for (let k = 0; k < stands; k++) {
      let n = 16 + Math.floor(rng() * 20), R = Math.sqrt(n) * 7.5 * s;
      let c = pickCentre(R + 8);
      if (!c) { n = Math.floor(n * 0.5); R = Math.sqrt(n) * 7.5 * s; c = pickCentre(R + 8); }
      if (!c) continue;
      decos.push({ kind: 'centre', x: c[0], y: c[1] });
      const pitch = 10.5 * s, rowsN = Math.ceil(R * 2 / (pitch * 0.85));
      let count = 0;
      for (let ry = -rowsN / 2; ry <= rowsN / 2 && count < n; ry++) for (let rx = -rowsN / 2; rx <= rowsN / 2 && count < n; rx++) {
        const px = c[0] + (rx + (ry % 2 ? 0.5 : 0)) * pitch + (rng() - 0.5) * 4, py = c[1] + ry * pitch * 0.85 + (rng() - 0.5) * 4;
        if (Math.hypot(px - c[0], py - c[1]) > R) continue;
        if (nearTrail(px, py, 15) || inLabel(px, py, 6) || nearest(px, py).nd < roomClear) continue;
        push({ kind: 'tree', x: px, y: py, s: (8.5 + rng() * 4.5) * s, mass: true }); count++;
      }
      push({ kind: 'shade', x: c[0], y: c[1] + R * 0.55, w: R * 1.5, s: 1 });
    }
  }
  if (kindSet.has('reed')) {
    const bands = 2 + Math.floor(rng() * 2);
    for (let k = 0; k < bands; k++) {
      const bw = (110 + rng() * 50) * s;
      const c = pickCentre(bw / 2 + 8); if (!c) break;
      decos.push({ kind: 'centre', x: c[0], y: c[1] });
      push({ kind: 'reedband', x: c[0], y: c[1] + 8, w: bw, s: 1 });
    }
  }
  if (kindSet.has('peak')) {
    const ridges = 4 + Math.floor(rng() * 3);
    for (let k = 0; k < ridges; k++) {
      const rs = (15 + rng() * 9) * s;
      const c = pickCentre(rs * 2.6); if (!c) continue;
      decos.push({ kind: 'centre', x: c[0], y: c[1] });
      push({ kind: 'ridge', x: c[0], y: c[1] + rs * 0.8, s: rs });
    }
  }
  // sparse base cover, thinning with distance from the rooms and trails
  const baseKind = base, dens = (DENSITY[baseKind] || 0.1) * 0.95;
  for (let gy = y; gy <= y + h; gy += 40) for (let gx = x; gx <= x + w; gx += 40) {
    const px = Math.min(x + w, Math.max(x, gx + (rng() - 0.5) * 26)), py = Math.min(y + h, Math.max(y, gy + (rng() - 0.5) * 26));
    const roll = rng(), sizeRoll = rng();
    if (inFurniture(px, py) || inLabel(px, py, 4) || nearTrail(px, py, 22)) continue;
    const { nd } = nearest(px, py);
    if (nd < roomClear) continue;
    if (centres.some(c => Math.hypot(c.x - px, c.y - py) < c.r + 12)) continue;
    const falloff = Math.max(0.2, 1 - Math.max(0, nd - 220) / 600);
    if (roll > dens * falloff) continue;
    let kind = baseKind;
    if (kindSet.has('rubble') && rng() < 0.3) kind = 'rubble';
    else if (kindSet.has('tree') && rng() < 0.6) kind = 'tree';
    else if (kindSet.has('reed') && rng() < 0.3) kind = 'reed';
    else if (kindSet.has('peak') && rng() < 0.15) kind = 'peak';
    push({ kind, x: px, y: py, s: (7 + sizeRoll * 5) * (kind === 'tree' ? s : 1) });
  }
  return decos.filter(d => d.kind !== 'centre');
}
