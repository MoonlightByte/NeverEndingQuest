export const PALETTE = { bg: '#e7d6ac', ink: '#3b2b17', red: '#8e1f10' };

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

export function svgDefs(uid) {
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
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.72  0 0 0 0 0.62  0 0 0 0 0.45  0 0 0 0.55 0"/>
      <feComposite operator="over" in2="SourceGraphic"/>
    </filter>
    <filter id="${uid}-blotch">
      <feTurbulence type="fractalNoise" baseFrequency="0.008" numOctaves="3" seed="15" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0.35  0 0 0 0 0.25  0 0 0 0 0.1  0 0 0 0.28 0"/>
      <feComposite operator="over" in2="SourceGraphic"/>
    </filter>
    <radialGradient id="${uid}-vig" cx="50%" cy="50%" r="72%">
      <stop offset="62%" stop-color="rgba(60,40,10,0)"/>
      <stop offset="100%" stop-color="rgba(60,40,10,0.34)"/>
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

// Shared label-plan + clamped greedy vertical de-collision, used by both the
// overland (render.js) and interior (interior.js) renderers so the two modes
// behave identically at labelScale>1 (F2). At ls<=1 this is a no-op (every
// dy stays 0), which is what keeps the default (labelScale unset/1) output
// byte-identical to the pre-de-collision renderer - required for the golden
// SVG tests.
//
// entries: [{ id, y, lx, anchor, lines }] - lx/anchor are already resolved
// by the caller (the label x-offset differs per renderer: overland uses a
// fixed icon offset, interior uses half the chamber width), y is the room's
// vertical anchor, lines is the (possibly two-line, already-split) label.
//
// Greedy pass: sort blocks top-down (stable, id tiebreak), and for every
// x-overlapping pair that also collides vertically, push the later block
// down just enough to clear the earlier one (F1's original behavior).
// Unlike the original, cap every block's final bottom edge at contentBottom
// (F1 fix): visible-but-tight beats off-canvas-invisible, so on an extremely
// dense/tall map the clamp can leave a residual overlap at the very bottom -
// that is an accepted tradeoff, not a bug.
//
// Returns Map<id, { lx, anchor, lines, dy, x0, x1, top, bot }>.
export function planLabels(entries, ls, contentBottom = 880) {
  const plans = new Map();
  for (const e of entries) {
    const { id, y, lx, anchor, lines } = e;
    const w = Math.max(...lines.map(l => l.length)) * 7.4 * ls;
    const top = y + (lines.length === 2 ? -4 - 15 : 4 - 15) * ls;
    const bot = y + (lines.length === 2 ? 26 : 18) * ls + 4 * ls;
    plans.set(id, {
      lx, anchor, lines, dy: 0,
      x0: anchor === 'end' ? lx - w : lx, x1: anchor === 'end' ? lx : lx + w,
      top, bot
    });
  }
  if (ls > 1) {
    const order = [...plans.entries()].sort((a, b) => a[1].top - b[1].top || (a[0] < b[0] ? -1 : 1));
    for (let i = 0; i < order.length; i++) for (let j = 0; j < i; j++) {
      const p = order[i][1], q = order[j][1];
      const xOverlap = p.x0 < q.x1 - 4 && q.x0 < p.x1 - 4;
      const pTop = p.top + p.dy, pBot = p.bot + p.dy, qTop = q.top + q.dy, qBot = q.bot + q.dy;
      if (xOverlap && pTop < qBot && qTop < pBot) p.dy += qBot - pTop + 2 * ls;
    }
    for (const [, p] of plans) {
      const maxDy = contentBottom - p.bot;
      if (p.dy > maxDy) p.dy = maxDy;
    }
  }
  return plans;
}
