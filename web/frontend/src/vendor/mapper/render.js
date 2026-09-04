import { hashSeed, PALETTE, resolvePalette, svgDefs, esc, edgeKey, oneWayChevron, splitLabel, planLabels } from './primitives.js';
import { isInterior, interiorLayers, setInteriorPalette } from './interior.js';
import { layoutMap } from './layout.js';
import { planFlavor } from './flavor.js';
import { roomGlyph, terrainGlyph, hasGlyph, setGlyphPalette } from './glyphs.js';

const FONT = `'IM Fell English', Georgia, serif`;


function cartouche(name, K, R, BG = PALETTE.bg) {
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
  g += `<rect x="912" y="46" width="238" height="74" fill="${BG}" stroke="${K}" stroke-width="2.4"/>`;
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

// Adaptive mark scale: small areas get larger glyphs, labels and
// trail weight so a 6-room town does not float in empty parchment.
export function adaptiveScale(graph) {
  const extent = Math.max(graph.cols || 0, graph.rows || 0, 3);
  return Math.max(1, Math.min(1.6, 4.8 / extent));
}

// Trail style by area/endpoint kind.
function trailStyle(graph, t) {
  const ra = graph.rooms.get(t.a), rb = graph.rooms.get(t.b);
  const secret = /^(passage|tunnel|secret)$/.test(ra.type) || /^(passage|tunnel|secret)$/.test(rb.type);
  if (secret) return 'dotted';
  if (/town|settlement|city|village/.test(String(graph.area.areaType).toLowerCase())) return 'street';
  return 'trail';
}

function samplePts(A, mid, B, n) {
  const pts = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n, u = 1 - t;
    pts.push([u * u * A.x + 2 * u * t * mid[0] + t * t * B.x, u * u * A.y + 2 * u * t * mid[1] + t * t * B.y]);
  }
  return pts;
}

export function renderMap(graph, opts = {}) {
  const uid = opts.uid || 'map';
  // labelScale multiplies room-name/type-tag text only (not map furniture);
  // 1 must produce byte-identical output to the pre-option renderer.
  const ls = Math.max(0.5, Math.min(3, Number(opts.labelScale) || 1));
  const P = resolvePalette(opts.palette);
  setGlyphPalette(P); setInteriorPalette(P);
  const K = P.ink, R = P.accent || P.red, BG = P.bg;
  const sc = adaptiveScale(graph);
  const layout = layoutMap(graph);
  let mode = opts.mode ? String(opts.mode).toLowerCase() : null;
  if (mode && mode !== 'interior' && mode !== 'overland') { console.warn(`renderMap: unknown mode "${opts.mode}", using automatic detection`); mode = null; }
  const interior = mode ? mode === 'interior' : isInterior(graph.area);

  let s = `<svg viewBox="0 0 1200 900" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" data-mapper="${uid}">`;
  if (opts.fontCss !== false) s += `<style>@import url('https://fonts.googleapis.com/css2?family=IM+Fell+English:ital@0;1&amp;display=swap');</style>`;
  s += svgDefs(uid, P);
  s += `<rect width="1200" height="900" fill="${BG}"/>`;

  if (interior) s += interiorLayers(graph, layout, uid, ls, sc);

  // rooms: terrain + glyph + label, sorted by id for stable output
  const roomIds = interior ? [] : [...layout.rooms.keys()].sort();

  // Label plan: four candidate slots per glyph with glyph, trail and label
  // avoidance; a leader tick marks a label that had to be displaced.
  const fsl = 15 * ls * Math.min(sc, 1.3);
  const glyphR = 16 * 1.35 * sc;
  const trailPts = layout.trails.flatMap(t => samplePts(layout.rooms.get(t.a), t.mid, layout.rooms.get(t.b), 20));
  const plans = planLabels(roomIds.map(id => {
    const { x, y, room } = layout.rooms.get(id);
    return { id, x, y, r: glyphR, lines: splitLabel(room.name, 18), fs: fsl };
  }), { trailPts });
  const labelBoxes = [...plans.values()].map(p => p.box);

  const decos = interior ? [] : planFlavor(graph, layout, { scale: sc, labelBoxes });
  const byRoom = new Map([...graph.rooms.keys()].map(k => [k, []]));
  for (const d of decos) byRoom.get(d.nearRoom).push(d);

  // edges (under rooms)
  if (!interior) for (const t of layout.trails) {
    const dk = esc(edgeKey(t.a, t.b));
    const A = layout.rooms.get(t.a), B = layout.rooms.get(t.b);
    s += `<g data-edge="${dk}" class="fog-edge" data-mid="${t.mid[0]},${t.mid[1]}">`;
    {
      const style = trailStyle(graph, t), sw = (2 * Math.sqrt(sc)).toFixed(2);
      if (style === 'street') {
        // two parallel lines offset along the chord normal
        const dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy) || 1, nx = -dy / L * 2.3, ny = dx / L * 2.3;
        for (const sgn of [1, -1]) {
          const d = `M ${(A.x + nx * sgn).toFixed(1)},${(A.y + ny * sgn).toFixed(1)} Q ${(t.mid[0] + nx * sgn).toFixed(1)},${(t.mid[1] + ny * sgn).toFixed(1)} ${(B.x + nx * sgn).toFixed(1)},${(B.y + ny * sgn).toFixed(1)}`;
          s += `<path d="${d}" class="edge-line" fill="none" stroke="${K}" stroke-width="1.2" stroke-linecap="round" filter="url(#${uid}-wobble2)"/>`;
        }
      } else if (style === 'dotted') {
        s += `<path d="${t.path}" class="edge-line" fill="none" stroke="${K}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="2 5" filter="url(#${uid}-wobble2)"/>`;
      } else {
        s += `<path d="${t.path}" class="edge-line" fill="none" stroke="${K}" stroke-width="${sw}" stroke-linecap="round" stroke-dasharray="7 4" filter="url(#${uid}-wobble2)"/>`;
      }
    }
    if (t.twoWay === false) {
      s += oneWayChevron([A.x, A.y], t.mid, [B.x, B.y], t.from === t.b, 1.6, K);
    }
    s += `</g>`;
  }

  for (const id of roomIds) {
    const { x, y, room } = layout.rooms.get(id);
    s += `<g data-room="${esc(id)}" class="fog-room" data-anchor="${x},${y}">`;
    s += `<g filter="url(#${uid}-wobble2)">`;
    // masses draw back-to-front (by y) so nearer canopies overlap farther ones
    const ds = byRoom.get(id).slice().sort((p, q) => p.y - q.y || p.x - q.x);
    for (const d of ds) s += terrainGlyph(d);
    s += `</g>`;
    s += `<g filter="url(#${uid}-wobble)" transform="translate(${x},${y}) scale(${(1.35 * sc).toFixed(3)}) translate(${-x},${-y})">`;
    s += roomGlyph(room.type, x, y, hashSeed(graph.mapId + ':' + id));
    s += `</g>`;
    const { lx, ly, anchor, lines, tick, lineH, tagH } = plans.get(id);
    const la = `font-size="${fsl.toFixed(1)}" fill="${K}" font-family="${FONT}" text-anchor="${anchor}" paint-order="stroke" stroke="${BG}" stroke-width="${(3.5 * ls).toFixed(1)}" stroke-linejoin="round"`;
    lines.forEach((ln, i) => { s += `<text x="${lx.toFixed(1)}" y="${(ly + i * lineH).toFixed(1)}" ${la}>${esc(ln)}</text>`; });
    if (hasGlyph(room.type)) {
      const tag = room.type[0].toUpperCase() + room.type.slice(1);
      s += `<text x="${lx.toFixed(1)}" y="${(ly + (lines.length - 1) * lineH + tagH + 2).toFixed(1)}" font-size="${(fsl * 0.57).toFixed(1)}" letter-spacing="${(1.2 * ls).toFixed(2)}" fill="${R}" font-family="${FONT}" font-style="italic" text-anchor="${anchor}">${esc(tag)}</text>`;
    }
    if (tick) s += `<path d="M ${(x + glyphR * 0.7).toFixed(1)},${y.toFixed(1)} L ${(lx - 3).toFixed(1)},${(ly - lineH * 0.3).toFixed(1)}" fill="none" stroke="${K}" stroke-width="0.8" stroke-dasharray="2 2"/>`;
    s += `</g>`;
  }

  // furniture
  s += `<g data-furniture="frame" fill="none" stroke="${K}"><rect x="14" y="14" width="1172" height="872" stroke-width="3"/><rect x="22" y="22" width="1156" height="856" stroke-width="1.2"/></g>`;
  s += cartouche(graph.mapName, K, R, BG);
  s += compassRose(120, 130, 44, K, R);
  s += scaleBar(880, 856, K);

  // texture overlays
  s += `<rect width="1200" height="900" filter="url(#${uid}-paper)" fill="none" style="mix-blend-mode:${P.blend}" opacity="${P.paperOpacity}"/>`;
  if (P.grainBlotch) s += `<rect width="1200" height="900" filter="url(#${uid}-blotch)" fill="none" style="mix-blend-mode:${P.blend}" opacity="${P.blotchOpacity}"/>`;
  s += `<rect width="1200" height="900" fill="url(#${uid}-vig)"/>`;
  return s + `</svg>`;
}
