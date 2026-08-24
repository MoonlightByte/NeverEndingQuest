import { mulberry32, hashSeed, PALETTE, svgDefs, esc, edgeKey, oneWayChevron, splitLabel, planLabels } from './primitives.js';
import { isInterior, interiorLayers } from './interior.js';
import { layoutMap } from './layout.js';
import { planFlavor } from './flavor.js';
import { roomGlyph, terrainGlyph, hasGlyph } from './glyphs.js';

const FONT = `'IM Fell English', Georgia, serif`;


function cartouche(name, K, R) {
  const two = name.length > 14;
  let lines;
  if (two) {
    const words = name.split(' ');
    let best = 1, bd = Infinity;
    for (let i = 1; i < words.length; i++) {
      const a = words.slice(0, i).join(' ').length, b = words.slice(i).join(' ').length;
      if (Math.max(a, b) < bd) { bd = Math.max(a, b); best = i; }
    }
    lines = [words.slice(0, best).join(' '), words.slice(best).join(' ')];
  } else lines = [name];
  const L = Math.max(...lines.map(s => s.length));
  let g = `<g data-furniture="cartouche">`;
  g += `<rect x="912" y="46" width="238" height="74" fill="${PALETTE.bg}" stroke="${K}" stroke-width="2.4"/>`;
  g += `<rect x="918" y="52" width="226" height="62" fill="none" stroke="${K}" stroke-width="1"/>`;
  if (lines.length === 2) {
    const fs1 = (19 * Math.min(1, 16 / L)).toFixed(1), fs2 = (16 * Math.min(1, 16 / L)).toFixed(1);
    g += `<text x="1031" y="80" font-size="${fs1}" letter-spacing="1.5" fill="${R}" font-family="${FONT}" text-anchor="middle">${esc(lines[0])}</text>`;
    g += `<text x="1031" y="103" font-size="${fs2}" letter-spacing="1.5" fill="${R}" font-family="${FONT}" text-anchor="middle">${esc(lines[1])}</text>`;
  } else {
    const fs = (20 * Math.min(1, 17 / L)).toFixed(1);
    g += `<text x="1031" y="92" font-size="${fs}" letter-spacing="1.5" fill="${R}" font-family="${FONT}" text-anchor="middle">${esc(lines[0])}</text>`;
  }
  return g + `</g>`;
}

function compassRose(cx, cy, s, K, R) {
  let g = `<g data-furniture="compass" stroke="${K}" fill="none" stroke-width="1.3">`;
  g += `<circle cx="${cx}" cy="${cy}" r="${s}"/><circle cx="${cx}" cy="${cy}" r="${s * 0.72}" stroke-width="0.8"/>`;
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2 - Math.PI / 2;
    const big = i % 2 === 0, len = big ? s * 0.95 : s * 0.6, w = big ? s * 0.16 : s * 0.09;
    const px = cx + Math.cos(a) * len, py = cy + Math.sin(a) * len;
    const ax = cx + Math.cos(a + Math.PI / 2) * w, ay = cy + Math.sin(a + Math.PI / 2) * w;
    const bx = cx + Math.cos(a - Math.PI / 2) * w, by = cy + Math.sin(a - Math.PI / 2) * w;
    g += `<path d="M ${ax.toFixed(1)},${ay.toFixed(1)} L ${px.toFixed(1)},${py.toFixed(1)} L ${bx.toFixed(1)},${by.toFixed(1)}" fill="${big ? K : 'none'}" stroke-width="1"/>`;
  }
  g += `</g><text x="${cx}" y="${cy - s - 8}" text-anchor="middle" font-size="${(s * 0.62).toFixed(1)}" fill="${R}" font-family="${FONT}" data-furniture="compass-n">N</text>`;
  return g;
}

function scaleBar(x, y, K) {
  let g = `<g data-furniture="scale">`;
  for (let i = 0; i < 4; i++) g += `<rect x="${x + i * 40}" y="${y}" width="40" height="6" fill="${i % 2 ? K : 'none'}" stroke="${K}" stroke-width="1.2"/>`;
  g += `<text x="${x}" y="${y - 7}" font-size="13" fill="${K}" font-family="${FONT}">0</text>`;
  g += `<text x="${x + 160}" y="${y - 7}" font-size="13" fill="${K}" font-family="${FONT}" text-anchor="end">1 league</text>`;
  return g + `</g>`;
}

export function renderMap(graph, opts = {}) {
  const uid = opts.uid || 'map';
  // labelScale multiplies room-name/type-tag text only (not map furniture);
  // 1 must produce byte-identical output to the pre-option renderer.
  const ls = Math.max(0.5, Math.min(3, Number(opts.labelScale) || 1));
  const K = PALETTE.ink, R = PALETTE.red, BG = PALETTE.bg;
  const layout = layoutMap(graph);
  let mode = opts.mode ? String(opts.mode).toLowerCase() : null;
  if (mode && mode !== 'interior' && mode !== 'overland') { console.warn(`renderMap: unknown mode "${opts.mode}", using automatic detection`); mode = null; }
  const interior = mode ? mode === 'interior' : isInterior(graph.area);
  const decos = interior ? [] : planFlavor(graph, layout);
  const byRoom = new Map([...graph.rooms.keys()].map(k => [k, []]));
  for (const d of decos) byRoom.get(d.nearRoom).push(d);

  let s = `<svg viewBox="0 0 1200 900" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" data-mapper="${uid}">`;
  if (opts.fontCss !== false) s += `<style>@import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&amp;display=swap');</style>`;
  s += svgDefs(uid);
  s += `<rect width="1200" height="900" fill="${BG}"/>`;

  if (interior) s += interiorLayers(graph, layout, uid, ls);

  // edges (under rooms)
  if (!interior) for (const t of layout.trails) {
    const dk = esc(edgeKey(t.a, t.b));
    s += `<g data-edge="${dk}" class="fog-edge">`;
    s += `<path d="${t.path}" class="edge-line" fill="none" stroke="${K}" stroke-width="2" stroke-linecap="round" stroke-dasharray="7 4" filter="url(#${uid}-wobble2)"/>`;
    if (t.twoWay === false) {
      const A = layout.rooms.get(t.a), B = layout.rooms.get(t.b);
      s += oneWayChevron([A.x, A.y], t.mid, [B.x, B.y], t.from === t.b, 1.6, K);
    }
    s += `</g>`;
  }

  // rooms: terrain + glyph + label, sorted by id for stable output
  const roomIds = interior ? [] : [...layout.rooms.keys()].sort();

  // Label plan: at embed scales (ls > 1) long names wrap onto two lines and
  // overlapping label blocks are nudged apart vertically, then clamped
  // on-canvas (F1) - see planLabels in primitives.js, shared with interior.js
  // (F2). ls = 1 skips both so pre-option output stays byte-identical.
  const labelEntries = roomIds.map(id => {
    const { x, y, room } = layout.rooms.get(id);
    const flip = x > layout.content.x + layout.content.w - 150 * ls;
    const lx = flip ? x - 27 : x + 27, anchor = flip ? 'end' : 'start';
    const lines = ls > 1 ? splitLabel(room.name) : [room.name];
    return { id, y, lx, anchor, lines };
  });
  const plans = planLabels(labelEntries, ls);

  for (const id of roomIds) {
    const { x, y, room } = layout.rooms.get(id);
    s += `<g data-room="${esc(id)}" class="fog-room">`;
    s += `<g filter="url(#${uid}-wobble2)">`;
    const ds = byRoom.get(id).slice().sort((p, q) => p.y - q.y || p.x - q.x);
    for (const d of ds) s += terrainGlyph(d);
    s += `</g>`;
    s += `<g filter="url(#${uid}-wobble)" transform="translate(${x},${y}) scale(1.35) translate(${-x},${-y})">`;
    s += roomGlyph(room.type, x, y, hashSeed(graph.mapId + ':' + id));
    s += `</g>`;
    const { lx, anchor, lines, dy } = plans.get(id);
    const ly = y + dy;
    const labelAttrs = `font-size="${+(15 * ls).toFixed(1)}" fill="${K}" font-family="${FONT}" text-anchor="${anchor}" paint-order="stroke" stroke="${BG}" stroke-width="${+(3.5 * ls).toFixed(1)}" stroke-linejoin="round"`;
    if (lines.length === 2) {
      s += `<text x="${lx}" y="${ly - 4 * ls}" ${labelAttrs}>${esc(lines[0])}</text>`;
      s += `<text x="${lx}" y="${ly + 12 * ls}" ${labelAttrs}>${esc(lines[1])}</text>`;
    } else {
      s += `<text x="${lx}" y="${ly + 4 * ls}" ${labelAttrs}>${esc(lines[0])}</text>`;
    }
    if (hasGlyph(room.type)) {
      const tag = room.type[0].toUpperCase() + room.type.slice(1);
      s += `<text x="${lx}" y="${ly + (lines.length === 2 ? 26 : 18) * ls}" font-size="${+(8.5 * ls).toFixed(1)}" letter-spacing="${+(1.2 * ls).toFixed(2)}" fill="${R}" font-family="${FONT}" font-style="italic" text-anchor="${anchor}">${esc(tag)}</text>`;
    }
    s += `</g>`;
  }

  // furniture
  s += `<g data-furniture="frame" fill="none" stroke="${K}"><rect x="14" y="14" width="1172" height="872" stroke-width="3"/><rect x="22" y="22" width="1156" height="856" stroke-width="1.2"/></g>`;
  s += cartouche(graph.mapName, K, R);
  s += compassRose(120, 130, 44, K, R);
  s += scaleBar(880, 856, K);

  // texture overlays
  s += `<rect width="1200" height="900" filter="url(#${uid}-paper)" fill="none" style="mix-blend-mode:multiply" opacity="0.5"/>`;
  s += `<rect width="1200" height="900" filter="url(#${uid}-blotch)" fill="none" style="mix-blend-mode:multiply" opacity="0.35"/>`;
  s += `<rect width="1200" height="900" fill="url(#${uid}-vig)"/>`;
  return s + `</svg>`;
}
