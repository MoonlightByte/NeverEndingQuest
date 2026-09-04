// Named palettes. `day` is the original parchment look and must stay
// byte-identical (goldens); `night` is ink on a dark ground for the game's
// dark UI. Hosts may pass a palette name or a partial object merged over day.
export const PALETTES = {
  day: {
    bg: '#e7d6ac', ink: '#3b2b17', accent: '#8e1f10', floor: '#e0cc9e',
    grainPaper: [0.72, 0.62, 0.45, 0.55], grainBlotch: [0.35, 0.25, 0.1, 0.28],
    blend: 'multiply', paperOpacity: 0.5, blotchOpacity: 0.35,
    vig: ['rgba(60,40,10,0)', 'rgba(60,40,10,0.34)']
  },
  night: {
    bg: '#0f1922', ink: '#d6c39a', accent: '#e2b253', floor: '#182530',
    grainPaper: [0.85, 0.78, 0.6, 0.1], grainBlotch: null,
    blend: 'screen', paperOpacity: 0.6, blotchOpacity: 0,
    vig: ['rgba(0,0,0,0)', 'rgba(0,0,0,0.55)']
  }
};
export function resolvePalette(opt) {
  if (!opt || opt === 'day') return PALETTES.day;
  if (typeof opt === 'string') {
    if (PALETTES[opt]) return PALETTES[opt];
    console.warn(`mapper: unknown palette "${opt}", using day`);
    return PALETTES.day;
  }
  return { ...PALETTES.day, ...opt, red: opt.accent || PALETTES.day.accent };
}
// Backward-compatible alias (red === accent).
export const PALETTE = { bg: PALETTES.day.bg, ink: PALETTES.day.ink, red: PALETTES.day.accent };
PALETTES.day.red = PALETTES.day.accent; PALETTES.night.red = PALETTES.night.accent;

export const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

export const edgeKey = (a, b) => `${encodeURIComponent(a)}|${encodeURIComponent(b)}`;

export function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function hashSeed(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h;
}

export function chaikin(pts, iters) {
  let p = pts;
  for (let k = 0; k < iters; k++) {
    const q = [p[0]];
    for (let i = 0; i < p.length - 1; i++) {
      const a = p[i], b = p[i + 1];
      q.push([a[0] * 0.72 + b[0] * 0.28, a[1] * 0.72 + b[1] * 0.28]);
      q.push([a[0] * 0.28 + b[0] * 0.72, a[1] * 0.28 + b[1] * 0.72]);
    }
    q.push(p[p.length - 1]);
    p = q;
  }
  return p;
}

export function jitterPts(pts, amt, rng) {
  return pts.map(([x, y]) => [x + (rng() - 0.5) * amt, y + (rng() - 0.5) * amt]);
}

export function toPath(pts, close = false) {
  let d = `M ${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) d += ` L ${pts[i][0].toFixed(1)},${pts[i][1].toFixed(1)}`;
  return close ? d + ' Z' : d;
}

export function blobPts(cx, cy, rx, ry, n, wob, rng) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const rr = 1 + (rng() - 0.5) * wob;
    pts.push([cx + Math.cos(a) * rx * rr, cy + Math.sin(a) * ry * rr]);
  }
  pts.push([...pts[0]]);
  return chaikin(pts, 3);
}

// Chevron cue for a one-way edge, drawn on the quadratic B(t) = (1-t)^2*A + 2(1-t)t*M + t^2*B.
// fromB indicates the connection was listed by the "b" endpoint, so the arrow
// points from b toward a (curve sampled at 1-0.72, tangent flipped).
export function oneWayChevron(A, M, B, fromB, sw, ink) {
  const t = fromB ? 1 - 0.72 : 0.72;
  const mt = 1 - t;
  const px = mt * mt * A[0] + 2 * mt * t * M[0] + t * t * B[0];
  const py = mt * mt * A[1] + 2 * mt * t * M[1] + t * t * B[1];
  let tx = 2 * mt * (M[0] - A[0]) + 2 * t * (B[0] - M[0]);
  let ty = 2 * mt * (M[1] - A[1]) + 2 * t * (B[1] - M[1]);
  const len = Math.hypot(tx, ty) || 1;
  tx /= len; ty /= len;
  if (fromB) { tx = -tx; ty = -ty; }
  const nx = -ty, ny = tx;
  const apexX = px + 6 * tx, apexY = py + 6 * ty;
  const tailX = px - 6 * tx, tailY = py - 6 * ty;
  const w1x = tailX + 5 * nx, w1y = tailY + 5 * ny;
  const w2x = tailX - 5 * nx, w2y = tailY - 5 * ny;
  const f = v => v.toFixed(1);
  return `<g class="one-way">` +
    `<path d="M ${f(apexX)},${f(apexY)} L ${f(w1x)},${f(w1y)}" fill="none" stroke="${ink}" stroke-width="${sw}" stroke-linecap="round"/>` +
    `<path d="M ${f(apexX)},${f(apexY)} L ${f(w2x)},${f(w2y)}" fill="none" stroke="${ink}" stroke-width="${sw}" stroke-linecap="round"/>` +
    `</g>`;
}

export function svgDefs(uid, P = PALETTES.day) {
  const gp = P.grainPaper, gb = P.grainBlotch || [0, 0, 0, 0];
  return `<defs>
    <filter id="${uid}-wobble" filterUnits="userSpaceOnUse" x="-60" y="-60" width="1320" height="1020">
      <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="8" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="4"/>
    </filter>
    <filter id="${uid}-wobble2" filterUnits="userSpaceOnUse" x="-60" y="-60" width="1320" height="1020">
      <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="4" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.5"/>
    </filter>
    <filter id="${uid}-paper">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="3" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 ${gp[0]}  0 0 0 0 ${gp[1]}  0 0 0 0 ${gp[2]}  0 0 0 ${gp[3]} 0"/>
      <feComposite operator="over" in2="SourceGraphic"/>
    </filter>
    <filter id="${uid}-blotch">
      <feTurbulence type="fractalNoise" baseFrequency="0.008" numOctaves="3" seed="15" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 ${gb[0]}  0 0 0 0 ${gb[1]}  0 0 0 0 ${gb[2]}  0 0 0 ${gb[3]} 0"/>
      <feComposite operator="over" in2="SourceGraphic"/>
    </filter>
    <radialGradient id="${uid}-vig" cx="50%" cy="50%" r="72%">
      <stop offset="62%" stop-color="${P.vig[0]}"/>
      <stop offset="100%" stop-color="${P.vig[1]}"/>
    </radialGradient>
  </defs>`;
}

// Balanced two-line split for long labels (same strategy as the cartouche):
// choose the word boundary minimizing the longer line. Returns [name] when
// short enough or unsplittable. Internal/edge whitespace runs are collapsed
// and trimmed first (F3) so a wrapped second line never starts with a
// leading space (splitting raw "Hall  of  Mirrors" on a single ' ' used to
// leave " Mirrors" as line two). esc() is still applied by the caller AFTER
// splitting - this only normalizes whitespace, not markup.
export function splitLabel(name, maxLen = 16) {
  const clean = String(name).trim().replace(/\s+/g, ' ');
  if (clean.length <= maxLen) return [clean];
  const words = clean.split(' ');
  if (words.length < 2) return [clean];
  let best = 1, bd = Infinity;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(' ').length, b = words.slice(i).join(' ').length;
    if (Math.max(a, b) < bd) { bd = Math.max(a, b); best = i; }
  }
  return [words.slice(0, best).join(' '), words.slice(best).join(' ')];
}

// ---------------------------------------------------------------------------
// Label planner. Each entry describes a glyph-anchored
// label: { id, x, y, r, lines, fs } where (x,y) is the glyph centre, r its
// clearance radius, fs the font size. Candidates are tried in order
// right, left, below, above; a candidate is rejected when its box intersects
// another placed label, any glyph clearance box, or comes within 4px of a
// trail sample point. When every candidate fails the right-hand slot is kept
// and the caller draws a leader tick. Returns Map<id, plan> where plan has
// { lx, ly, anchor, lines, box:[x0,y0,x1,y1], tick:boolean, pos }.
export function planLabels(entries, ctx = {}) {
  const { trailPts = [], bounds = { x0: 30, y0: 30, x1: 1170, y1: 870 } } = ctx;
  const glyphBoxes = entries.map(e => [e.x - e.r, e.y - e.r, e.x + e.r, e.y + e.r]);
  const placed = [];
  const plans = new Map();
  const hit = (a, b, pad = 0) => a[0] < b[2] + pad && b[0] < a[2] + pad && a[1] < b[3] + pad && b[1] < a[3] + pad;
  const order = entries.slice().sort((a, b) => a.y - b.y || (a.id < b.id ? -1 : 1));
  for (const e of order) {
    const lineH = e.fs * 1.08, tagH = e.fs * 0.75;
    const w = Math.max(...e.lines.map(l => l.length)) * e.fs * 0.5;
    const h = e.lines.length * lineH + tagH;
    const gap = 8;
    const cands = [
      { pos: 'right', anchor: 'start', lx: e.x + e.r + gap, ly: e.y, box: [e.x + e.r + gap, e.y - lineH * 0.55, e.x + e.r + gap + w, e.y - lineH * 0.55 + h] },
      { pos: 'left', anchor: 'end', lx: e.x - e.r - gap, ly: e.y, box: [e.x - e.r - gap - w, e.y - lineH * 0.55, e.x - e.r - gap, e.y - lineH * 0.55 + h] },
      { pos: 'below', anchor: 'middle', lx: e.x, ly: e.y + e.r + gap + lineH * 0.8, box: [e.x - w / 2, e.y + e.r + gap, e.x + w / 2, e.y + e.r + gap + h] },
      { pos: 'above', anchor: 'middle', lx: e.x, ly: e.y - e.r - gap - h + lineH * 0.8, box: [e.x - w / 2, e.y - e.r - gap - h, e.x + w / 2, e.y - e.r - gap] }
    ];
    let chosen = null;
    for (const c of cands) {
      const b = c.box;
      if (b[0] < bounds.x0 || b[1] < bounds.y0 || b[2] > bounds.x1 || b[3] > bounds.y1) continue;
      if (placed.some(pb => hit(b, pb, 2))) continue;
      if (glyphBoxes.some((gb, i) => entries[i] !== e && hit(b, gb, 2))) continue;
      if (trailPts.some(([tx, ty]) => tx > b[0] - 4 && tx < b[2] + 4 && ty > b[1] - 4 && ty < b[3] + 4)) continue;
      chosen = c; break;
    }
    let tick = false;
    if (!chosen) {
      // fall back: nudge the right-hand slot downward until it clears placed labels
      chosen = cands[0];
      for (let k = 0; k < 6 && placed.some(pb => hit(chosen.box, pb, 2)) && chosen.box[3] + lineH <= bounds.y1; k++) {
        const dy = lineH;
        chosen = { ...chosen, ly: chosen.ly + dy, box: [chosen.box[0], chosen.box[1] + dy, chosen.box[2], chosen.box[3] + dy] };
      }
      tick = true;
    }
    placed.push(chosen.box);
    plans.set(e.id, { ...chosen, lines: e.lines, tick, lineH, tagH });
  }
  return plans;
}
