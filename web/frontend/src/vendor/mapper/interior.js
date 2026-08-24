import { mulberry32, hashSeed, PALETTE, esc, blobPts, toPath, edgeKey, oneWayChevron, splitLabel, planLabels } from './primitives.js';

// Interior (floor-plan) render mode: chambers with hand-drawn walls joined by
// walled corridors, rock-hatched outside, flagstoned inside, furnished by
// room type. Layer order matters for open doorways: corridor casings, then
// chamber walls, then corridor floors (which punch through the walls), then
// chamber floors and furnishings. Fog groups: a room or edge may own SEVERAL
// groups sharing one data-room/data-edge value; fog.js handles them all.

const K = PALETTE.ink, FLOOR = '#e0cc9e', RED = PALETTE.red;
const FONT = `'IM Fell English', Georgia, serif`;
const W = (sw = 1.2) => `fill="none" stroke="${K}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"`;

export function isInterior(area) {
  return /dungeon|crypt|cavern|underground|keep|castle|fortress|stronghold|interior/.test(
    `${area.areaType} ${area.terrain} ${area.nameHint || ''}`.toLowerCase());
}

export function interiorStyle(area) {
  return /cave|cavern|grotto|lair|warren|burrow|tunnel|mine/.test(
    `${area.areaType} ${area.terrain} ${area.nameHint || ''}`.toLowerCase()) ? 'cavern' : 'stone';
}

function chamberGeo(room, rng) {
  if (room.type === 'tower') return { w: 64, h: 64, circle: true };
  const grand = /hall|courtyard|chamber|ritual|crypt|entrance/.test(room.type);
  const w = (grand ? 82 : 64) + rng() * 18;
  const h = (grand ? 64 : 52) + rng() * 14;
  return { w: +w.toFixed(1), h: +h.toFixed(1), circle: false };
}

function outlinePath(x, y, w, h, rng) {
  const hw = w / 2, hh = h / 2;
  const base = [[-hw, -hh], [0, -hh], [hw, -hh], [hw, 0], [hw, hh], [0, hh], [-hw, hh], [-hw, 0]];
  const pts = base.map(([px, py]) => [x + px + (rng() - 0.5) * 3.5, y + py + (rng() - 0.5) * 3.5]);
  return 'M ' + pts.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' L ') + ' Z';
}

// short radial ticks outside the wall: "carved from the living rock"
function hatchRing(x, y, w, h, circle, rng) {
  let g = `<g opacity="0.75">`;
  const hw = w / 2 + 4, hh = h / 2 + 4;
  const perim = circle ? Math.PI * (hw + hh) : 4 * (hw + hh);
  const n = Math.floor(perim / 13);
  for (let i = 0; i < n; i++) {
    const t = i / n;
    let px, py, nx, ny;
    if (circle) {
      const a = t * Math.PI * 2;
      px = x + Math.cos(a) * hw; py = y + Math.sin(a) * hh; nx = Math.cos(a); ny = Math.sin(a);
    } else {
      const u = t * 4;
      if (u < 1) { px = x - hw + u * 2 * hw; py = y - hh; nx = 0; ny = -1; }
      else if (u < 2) { px = x + hw; py = y - hh + (u - 1) * 2 * hh; nx = 1; ny = 0; }
      else if (u < 3) { px = x + hw - (u - 2) * 2 * hw; py = y + hh; nx = 0; ny = 1; }
      else { px = x - hw; py = y + hh - (u - 3) * 2 * hh; nx = -1; ny = 0; }
    }
    const len = 4.5 + rng() * 4, j = (rng() - 0.5) * 3;
    g += `<path d="M ${(px + nx * 1.5 + j * ny).toFixed(1)},${(py + ny * 1.5 - j * nx).toFixed(1)} l ${(nx * len).toFixed(1)},${(ny * len).toFixed(1)}" ${W(0.9)}/>`;
  }
  return g + `</g>`;
}

// brick-offset flagstone dashes inside the floor
function flagstones(x, y, w, h, rng) {
  let g = `<g opacity="0.45">`;
  const hw = w / 2 - 7, hh = h / 2 - 7;
  let row = 0;
  for (let yy = -hh; yy <= hh; yy += 11, row++) {
    for (let xx = -hw + (row % 2 ? 8 : 0); xx <= hw - 4; xx += 16) {
      if (rng() < 0.35) continue;
      g += `<path d="M ${(x + xx).toFixed(1)},${(y + yy).toFixed(1)} l ${(6 + rng() * 3).toFixed(1)},0" ${W(0.6)}/>`;
    }
  }
  return g + `</g>`;
}

function pebbles(x, y, w, h, rng) {
  let g = `<g opacity="0.55">`;
  const n = Math.floor((w * h) / 900);
  for (let i = 0; i < n; i++) {
    const px = x + (rng() - 0.5) * (w - 16), py = y + (rng() - 0.5) * (h - 16);
    if (rng() < 0.4) g += `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="${(0.8 + rng() * 0.8).toFixed(1)}" ${W(0.7)}/>`;
    else g += `<path d="M ${px.toFixed(1)},${py.toFixed(1)} l ${(3 + rng() * 4).toFixed(1)},${((rng() - 0.5) * 3).toFixed(1)}" ${W(0.6)}/>`;
  }
  return g + `</g>`;
}

function stalagmites(x, y, w, h, rng) {
  let g = '';
  for (let c = 0; c < 2; c++) {
    const cx = x + (rng() - 0.5) * (w - 24), cy = y + (rng() - 0.5) * (h - 24);
    for (let i = 0; i < 3; i++) {
      const px = cx + (rng() - 0.5) * 10, py = cy + (rng() - 0.5) * 8, s = 2.5 + rng() * 2.5;
      g += `<path d="M ${(px - s).toFixed(1)},${py.toFixed(1)} L ${px.toFixed(1)},${(py - s * 1.8).toFixed(1)} L ${(px + s).toFixed(1)},${py.toFixed(1)} Z" fill="${FLOOR}" stroke="${K}" stroke-width="1"/>`;
    }
  }
  return g;
}

// ---- top-down furnishings by room type ----
function coffin(px, py, rot) {
  return `<g transform="rotate(${rot} ${px} ${py})"><path d="M ${px - 3.2},${py - 8} L ${px + 3.2},${py - 8} L ${px + 4.2},${py - 3} L ${px + 2.6},${py + 8} L ${px - 2.6},${py + 8} L ${px - 4.2},${py - 3} Z" fill="${FLOOR}" ${W(1.1).replace('fill="none" ', '')}/><path d="M ${px - 2.2},${py - 4.5} l 4.4,0 M ${px},${py - 6.5} l 0,4" ${W(0.7)}/></g>`;
}
function barrel(px, py) {
  return `<circle cx="${px}" cy="${py}" r="4.6" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/><circle cx="${px}" cy="${py}" r="1.4" ${W(0.8)}/><path d="M ${px - 4.6},${py} l 9.2,0" ${W(0.6)}/>`;
}
function crate(px, py, s = 8) {
  return `<rect x="${px - s / 2}" y="${py - s / 2}" width="${s}" height="${s}" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/><path d="M ${px - s / 2},${py - s / 2} l ${s},${s} M ${px + s / 2},${py - s / 2} l ${-s},${s}" ${W(0.6)}/>`;
}
function table(px, py, w, h) {
  return `<rect x="${px - w / 2}" y="${py - h / 2}" width="${w}" height="${h}" fill="${FLOOR}" stroke="${K}" stroke-width="1.2"/>`;
}
function stairs(px, py, dir = 1) {
  let g = '';
  for (let i = 0; i < 5; i++) {
    const ww = 14 - i * 2;
    g += `<path d="M ${px - ww / 2},${py + dir * i * 3.2} l ${ww},0" ${W(1.1)}/>`;
  }
  return g;
}

const PROPS = {
  entrance: (x, y, w, h) => stairs(x, y + h / 2 - 18, 1) +
    `<path d="M ${x - 7},${y - h / 2 + 3} l 0,6 M ${x - 3.5},${y - h / 2 + 3} l 0,7 M ${x},${y - h / 2 + 3} l 0,6.5 M ${x + 3.5},${y - h / 2 + 3} l 0,7 M ${x + 7},${y - h / 2 + 3} l 0,6" ${W(1)}/>`,
  prison: (x, y, w, h) => `<path d="M ${x - w / 2 + 4},${y - 2} L ${x + w / 2 - 4},${y - 2}" ${W(1.6)}/>` +
    `<path d="M ${x - w / 2 + 8},${y - 2} l 0,${h / 2 - 6} M ${x - w / 2 + 16},${y - 2} l 0,${h / 2 - 6} M ${x - w / 2 + 24},${y - 2} l 0,${h / 2 - 6}" ${W(0.9)}/>` +
    `<rect x="${x + w / 2 - 18}" y="${y + h / 2 - 12}" width="12" height="5" fill="${FLOOR}" stroke="${K}" stroke-width="1"/>`,
  crypt: (x, y, w, h) => coffin(x - w / 4, y - 2, -8) + coffin(x + w / 4, y + 2, 6) + coffin(x, y + h / 4, 90) +
    `<circle cx="${x - w / 3}" cy="${y + h / 3}" r="1" fill="${K}"/>`,
  storage: (x, y, w, h) => barrel(x - w / 4, y - h / 5) + barrel(x - w / 4 + 10, y - h / 5 + 6) + crate(x + w / 5, y + h / 5, 9) + crate(x + w / 5 + 10, y + h / 5 - 2, 7),
  garrison: (x, y, w, h) => table(x, y, 20, 9) +
    `<circle cx="${x - 13}" cy="${y - 3}" r="2" ${W(0.9)}/><circle cx="${x + 13}" cy="${y + 3}" r="2" ${W(0.9)}/>` +
    `<path d="M ${x - w / 2 + 4},${y - h / 2 + 6} l 14,0 m -12,-2 l 0,4 m 5,-4 l 0,4 m 5,-4 l 0,4" ${W(0.9)}/>`,
  chamber: (x, y, w, h) => table(x, y, 24, 10) +
    `<path d="M ${x - 12},${y - 5} L ${x + 12},${y + 5} M ${x - 12},${y + 5} L ${x + 12},${y - 5}" ${W(0.7)}/>` +
    `<path d="M ${x - w / 4},${y - h / 2 + 2} l 0,8 M ${x + w / 4},${y - h / 2 + 2} l 0,10" ${W(0.9)}/><circle cx="${x - w / 4}" cy="${y - h / 2 + 11.5}" r="1.4" ${W(0.8)}/><circle cx="${x + w / 4}" cy="${y - h / 2 + 13.5}" r="1.4" ${W(0.8)}/>`,
  ritual: (x, y, w, h) => {
    const r = Math.min(w, h) / 3.4;
    let star = '';
    for (let i = 0; i < 5; i++) {
      const a1 = -Math.PI / 2 + i * 4 * Math.PI / 5, a2 = -Math.PI / 2 + ((i + 1) % 5) * 4 * Math.PI / 5;
      star += `${i ? 'L' : 'M'} ${(x + Math.cos(a1) * r * 0.78).toFixed(1)},${(y + Math.sin(a1) * r * 0.78).toFixed(1)} `;
      if (i === 4) star += `Z`;
    }
    return `<circle cx="${x}" cy="${y}" r="${r}" ${W(1.2)}/><circle cx="${x}" cy="${y}" r="${r * 0.55}" ${W(0.7)}/><path d="${star}" ${W(0.9)}/>` +
      `<circle cx="${x - w / 2 + 8}" cy="${y - h / 2 + 8}" r="1.6" fill="${K}"/><circle cx="${x + w / 2 - 8}" cy="${y - h / 2 + 8}" r="1.6" fill="${K}"/><circle cx="${x - w / 2 + 8}" cy="${y + h / 2 - 8}" r="1.6" fill="${K}"/><circle cx="${x + w / 2 - 8}" cy="${y + h / 2 - 8}" r="1.6" fill="${K}"/>`;
  },
  hall: (x, y, w, h) => table(x, y, w * 0.5, 10) +
    `<circle cx="${x - w / 5}" cy="${y - 8}" r="1.8" ${W(0.8)}/><circle cx="${x}" cy="${y - 8}" r="1.8" ${W(0.8)}/><circle cx="${x + w / 5}" cy="${y - 8}" r="1.8" ${W(0.8)}/><circle cx="${x - w / 5}" cy="${y + 8}" r="1.8" ${W(0.8)}/><circle cx="${x + w / 5}" cy="${y + 8}" r="1.8" ${W(0.8)}/>` +
    `<rect x="${x - 5}" y="${y - h / 2 + 4}" width="10" height="6" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/>`,
  chapel: (x, y, w, h) => `<rect x="${x - 7}" y="${y - h / 2 + 5}" width="14" height="6" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/><path d="M ${x},${y - h / 2 + 6} l 0,4 m -1.6,-2.6 l 3.2,0" ${W(0.8)}/>` +
    `<path d="M ${x - 12},${y + 2} l 9,0 m 6,0 l 9,0 M ${x - 12},${y + 9} l 9,0 m 6,0 l 9,0 M ${x - 12},${y + 16} l 9,0 m 6,0 l 9,0" ${W(1)}/>`,
  study: (x, y, w, h) => table(x - w / 6, y, 16, 8) + `<path d="M ${x - w / 6 - 4},${y - 1.5} l 8,0 m -8,3 l 8,0" ${W(0.6)}/>` +
    `<path d="M ${x + w / 2 - 6},${y - h / 2 + 4} l 0,${h - 8} m -3,-${h - 8} l 0,${h - 8}" ${W(0.9)}/><path d="M ${x + w / 2 - 9},${y - h / 2 + 9} l 3,0 m -3,7 l 3,0 m -3,7 l 3,0" ${W(0.7)}/>`,
  barracks: (x, y, w, h) => {
    let g = '';
    for (let i = -1; i <= 1; i++) g += `<rect x="${x - w / 2 + 6}" y="${y + i * 13 - 4}" width="15" height="8" fill="${FLOOR}" stroke="${K}" stroke-width="1"/><path d="M ${x - w / 2 + 9},${y + i * 13 - 4} l 0,8" ${W(0.6)}/>`;
    g += crate(x + w / 4, y + h / 5, 8);
    return g;
  },
  courtyard: (x, y, w, h) => `<circle cx="${x}" cy="${y}" r="5" fill="${FLOOR}" stroke="${K}" stroke-width="1.2"/><circle cx="${x}" cy="${y}" r="2" ${W(0.8)}/>` +
    `<path d="M ${x - w / 2 + 7},${y - h / 2 + 7} q 2,-2 4,0 q -2,2 -4,0 M ${x + w / 2 - 11},${y + h / 2 - 7} q 2,-2 4,0 q -2,2 -4,0" ${W(0.8)}/>`,
  gatehouse: (x, y, w, h) => `<path d="M ${x - 8},${y} l 0,-${h / 2 - 4} M ${x - 4},${y} l 0,-${h / 2 - 5} M ${x},${y} l 0,-${h / 2 - 4} M ${x + 4},${y} l 0,-${h / 2 - 5} M ${x + 8},${y} l 0,-${h / 2 - 4}" ${W(1)}/>` +
    `<path d="M ${x - w / 2 + 5},${y + h / 4} l 10,0 m -10,3 l 10,0" ${W(0.8)}/>`,
  tower: (x, y, w, h) => {
    let g = `<circle cx="${x}" cy="${y}" r="3" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/>`;
    for (let i = 0; i < 6; i++) {
      const a = i * 0.55 + 0.4;
      g += `<path d="M ${(x + Math.cos(a) * 5).toFixed(1)},${(y + Math.sin(a) * 5).toFixed(1)} L ${(x + Math.cos(a) * (11 + i * 1.6)).toFixed(1)},${(y + Math.sin(a) * (11 + i * 1.6)).toFixed(1)}" ${W(0.9)}/>`;
    }
    return g;
  },
  vault: (x, y, w, h) => `<rect x="${x - 8}" y="${y - 5}" width="16" height="11" fill="${FLOOR}" stroke="${K}" stroke-width="1.3"/><path d="M ${x - 8},${y - 1} l 16,0 M ${x - 3},${y - 5} l 0,11 M ${x + 3},${y - 5} l 0,11" ${W(0.8)}/><circle cx="${x}" cy="${y + 2.5}" r="1.1" fill="${K}"/>` +
    `<path d="M ${x - w / 2 + 3},${y - h / 2 + 3} l 0,7 m 3,-7 l 0,7 m 3,-7 l 0,7" ${W(0.9)}/>`,
  laboratory: (x, y, w, h) => table(x - 2, y, 24, 9) +
    `<circle cx="${x - 8}" cy="${y - 1}" r="2.6" ${W(0.9)}/><circle cx="${x - 1}" cy="${y + 0.5}" r="1.8" ${W(0.9)}/><path d="M ${x + 5},${y + 2} l 1,-6 l 2.5,0 l 1,6" ${W(0.9)}/>` +
    `<path d="M ${x + w / 2 - 7},${y - h / 2 + 4} l 0,${h - 9} m -3,-${h - 9} l 0,${h - 9}" ${W(0.9)}/>`,
  throne: (x, y, w, h) => `<rect x="${x - 14}" y="${y - h / 2 + 4}" width="28" height="12" fill="none" stroke="${K}" stroke-width="0.9"/><rect x="${x - 10}" y="${y - h / 2 + 6}" width="20" height="8" fill="none" stroke="${K}" stroke-width="0.7"/>` +
    `<rect x="${x - 4}" y="${y - h / 2 + 7}" width="8" height="6" fill="${FLOOR}" stroke="${K}" stroke-width="1.2"/><path d="M ${x - 4},${y - h / 2 + 7} l 0,-2.5 m 8,2.5 l 0,-2.5" ${W(1.1)}/>` +
    `<path d="M ${x - 8},${y + h / 2 - 8} l 16,0 m -16,3 l 16,0" ${W(0.9)}/>`,
  treasure: (x, y, w, h) => `<rect x="${x - w / 4 - 6}" y="${y - 4}" width="12" height="8" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/><path d="M ${x - w / 4 - 6},${y - 1} l 12,0" ${W(0.7)}/>` +
    `<rect x="${x + w / 5}" y="${y + 2}" width="10" height="7" fill="${FLOOR}" stroke="${K}" stroke-width="1.1"/><path d="M ${x + w / 5},${y + 4.5} l 10,0" ${W(0.7)}/>` +
    `<circle cx="${x - 2}" cy="${y + 8}" r="1.1" ${W(0.7)}/><circle cx="${x + 2}" cy="${y + 9.5}" r="1.1" ${W(0.7)}/><circle cx="${x - w / 4 + 9}" cy="${y + 6.5}" r="1.1" ${W(0.7)}/>`,
  passage: () => ''
};

export function interiorLayers(graph, layout, uid, ls = 1) {
  const geo = new Map();
  const style = interiorStyle(graph.area);
  const cellW = layout.content.w / graph.cols, cellH = layout.content.h / graph.rows;
  for (const [id, { x, y, room }] of layout.rooms) {
    const rng = mulberry32(hashSeed(graph.mapId + ':' + id + ':shape'));
    const g = chamberGeo(room, rng);
    if (g.circle) {
      const capD = Math.min(cellW * 0.82, cellH * 0.8);
      const d = Math.max(34, Math.min(g.w, capD));
      g.w = d; g.h = d;
    } else {
      g.w = Math.max(34, Math.min(g.w, cellW * 0.82));
      g.h = Math.max(30, Math.min(g.h, cellH * 0.8));
    }
    geo.set(id, { x, y, room, rng, ...g });
  }
  const roomIds = [...layout.rooms.keys()].sort();

  // Label plan (F2): same wrap + clamped de-collision as render.js, routed
  // through the shared planLabels helper so interior stops overlapping long
  // adjacent names at embed scales while ls = 1 stays byte-identical.
  const labelEntries = roomIds.map(id => {
    const { x, y, w, room } = geo.get(id);
    const flip = x > layout.content.x + layout.content.w - 170 * ls;
    const lx = flip ? x - w / 2 - 10 : x + w / 2 + 10, anchor = flip ? 'end' : 'start';
    const lines = ls > 1 ? splitLabel(room.name) : [room.name];
    return { id, y, lx, anchor, lines };
  });
  const labelPlans = planLabels(labelEntries, ls);

  let casings = '', walls = '', edgeFloors = '', roomFloors = '';
  const casingWidth = style === 'cavern' ? 23 : 19;
  const floorWidth = style === 'cavern' ? 16 : 13;
  const wobbleFilter = style === 'cavern' ? 'wobble' : 'wobble2';

  for (const t of layout.trails) {
    const dk = esc(edgeKey(t.a, t.b));
    casings += `<g data-edge="${dk}" class="fog-edge" filter="url(#${uid}-${wobbleFilter})"><path d="${t.path}" class="edge-line" fill="none" stroke="${K}" stroke-width="${casingWidth}" stroke-linecap="butt"/></g>`;
    let ef = `<g data-edge="${dk}" class="fog-edge" filter="url(#${uid}-${wobbleFilter})"><path d="${t.path}" class="edge-line" fill="none" stroke="${FLOOR}" stroke-width="${floorWidth}" stroke-linecap="butt"/></g>`;
    if (t.twoWay === false) {
      const A = layout.rooms.get(t.a), B = layout.rooms.get(t.b);
      ef += `<g data-edge="${dk}">${oneWayChevron([A.x, A.y], t.mid, [B.x, B.y], t.from === t.b, 1.4, K)}</g>`;
    }
    edgeFloors += ef;
  }

  for (const id of roomIds) {
    const g = geo.get(id);
    const { x, y, w, h, circle, rng, room } = g;
    const blob = (style === 'cavern' && !circle) || /^(cave|ravine|grotto)$/.test(room.type);
    let blobPath = null;
    if (blob) {
      const blobRng = mulberry32(hashSeed(graph.mapId + ':' + id + ':blob'));
      blobPath = toPath(blobPts(x, y, w / 2 + 6, h / 2 + 5, 10, 0.45, blobRng), true);
    }
    let wall = `<g data-room="${esc(id)}" class="fog-room" filter="url(#${uid}-wobble2)">`;
    wall += hatchRing(x, y, blob ? w + 12 : w, blob ? h + 10 : h, blob ? true : circle, rng);
    if (circle) wall += `<circle cx="${x}" cy="${y}" r="${w / 2}" fill="none" stroke="${K}" stroke-width="5"/>`;
    else if (blob) wall += `<path d="${blobPath}" fill="none" stroke="${K}" stroke-width="5" stroke-linejoin="round"/>`;
    else wall += `<path d="${outlinePath(x, y, w, h, rng)}" fill="none" stroke="${K}" stroke-width="5" stroke-linejoin="round"/>`;
    walls += wall + `</g>`;

    let fl = `<g data-room="${esc(id)}" class="fog-room">`;
    fl += `<g filter="url(#${uid}-wobble2)">`;
    if (circle) fl += `<circle cx="${x}" cy="${y}" r="${w / 2 - 1}" fill="${FLOOR}"/>`;
    else if (blob) fl += `<path d="${blobPath}" fill="${FLOOR}"/>`;
    else fl += `<path d="${outlinePath(x, y, w, h, rng)}" fill="${FLOOR}"/>`;
    fl += (style === 'cavern' ? pebbles(x, y, circle ? w * 0.72 : w, circle ? h * 0.72 : h, rng) : flagstones(x, y, circle ? w * 0.72 : w, circle ? h * 0.72 : h, rng));
    const prop = PROPS[room.type];
    if (prop) fl += `<g filter="url(#${uid}-wobble2)">${prop(x, y, w, h)}</g>`;
    if (style === 'cavern') fl += stalagmites(x, y, w, h, rng);
    fl += `</g>`;
    const { lx, anchor, lines, dy } = labelPlans.get(id);
    const ly = y + dy;
    const labelAttrs = `font-size="${+(15 * ls).toFixed(1)}" fill="${K}" font-family="${FONT}" text-anchor="${anchor}" paint-order="stroke" stroke="${PALETTE.bg}" stroke-width="${+(3.5 * ls).toFixed(1)}" stroke-linejoin="round"`;
    if (lines.length === 2) {
      fl += `<text x="${lx}" y="${ly - 4 * ls}" ${labelAttrs}>${esc(lines[0])}</text>`;
      fl += `<text x="${lx}" y="${ly + 12 * ls}" ${labelAttrs}>${esc(lines[1])}</text>`;
    } else {
      fl += `<text x="${lx}" y="${ly + 4 * ls}" ${labelAttrs}>${esc(lines[0])}</text>`;
    }
    const tag = room.type[0].toUpperCase() + room.type.slice(1);
    fl += `<text x="${lx}" y="${ly + (lines.length === 2 ? 26 : 18) * ls}" font-size="${+(8.5 * ls).toFixed(1)}" letter-spacing="${+(1.2 * ls).toFixed(2)}" fill="${RED}" font-family="${FONT}" font-style="italic" text-anchor="${anchor}">${esc(tag)}</text>`;
    roomFloors += fl + `</g>`;
  }

  return casings + walls + edgeFloors + roomFloors;
}
