import { edgeKey } from './primitives.js';

export function edgeState(edge, revealed) {
  const a = revealed.has(edge.a), b = revealed.has(edge.b);
  if (a && b) return 'full';
  if (a) return 'stub-a';
  if (b) return 'stub-b';
  return 'hidden';
}

export function createFog(svgEl, graph, opts = {}) {
  const trailMs = opts.trailMs ?? 900, fadeMs = opts.fadeMs ?? 700;
  const reduced = opts.instant || (typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches);
  const dur = reduced ? 0 : 1;
  const revealed = new Set();
  const pendingTimeouts = new Set();
  const activeAnimations = new Set();

  function trackAnimation(anim) {
    activeAnimations.add(anim);
    if (anim && anim.finished && typeof anim.finished.then === 'function') {
      anim.finished.then(() => activeAnimations.delete(anim)).catch(() => activeAnimations.delete(anim));
    }
    return anim;
  }
  // a room or edge may own several groups sharing one data attribute
  // (interior mode splits walls and floors into layers)
  const roomEls = id => [...svgEl.querySelectorAll(`[data-room="${CSS.escape(id)}"]`)];
  const edgeEls = e => [...svgEl.querySelectorAll(`[data-edge="${CSS.escape(edgeKey(e.a, e.b))}"]`)];
  const edgePaths = els => els.flatMap(el => [...el.querySelectorAll('path.edge-line')]);

  for (const el of svgEl.querySelectorAll('.fog-room, .fog-edge')) el.style.opacity = '0';

  function stubDash(path, from) {
    const L = path.getTotalLength();
    const dashes = [8, 4, 7, 4, 6, 5, 5, 5, 4, 6, 3, 7, 2, 8];
    const arr = [];
    let covered = 0;
    for (let i = 0; i < dashes.length && covered < Math.min(60, L * 0.35); i += 2) {
      arr.push(dashes[i], dashes[i + 1]);
      covered += dashes[i] + dashes[i + 1];
    }
    arr.push(0, Math.ceil(L));
    path.style.strokeDasharray = arr.join(' ');
    path.style.strokeDashoffset = from === 'a' ? '0' : (-(L - covered)).toFixed(1);
  }

  function applyEdge(e, animate) {
    const els = edgeEls(e); if (!els.length) return;
    const paths = edgePaths(els);
    const st = edgeState(e, revealed);
    if (st === 'hidden') { for (const el of els) el.style.opacity = '0'; return; }
    if (st === 'full') {
      for (const path of paths) { path.style.strokeDasharray = ''; path.style.strokeDashoffset = ''; }
      for (const el of els) el.style.opacity = '1';
      if (animate && dur) for (const path of paths) {
        const L = path.getTotalLength();
        path.style.strokeDasharray = `${L} ${L}`;
        const anim = trackAnimation(path.animate([{ strokeDashoffset: L }, { strokeDashoffset: 0 }], { duration: trailMs, easing: 'ease-out' }));
        anim.finished.then(() => { path.style.strokeDasharray = ''; }).catch(() => {});
      }
    } else {
      for (const path of paths) stubDash(path, st === 'stub-a' ? 'a' : 'b');
      for (const el of els) {
        el.style.opacity = '0.55';
        if (animate && dur) trackAnimation(el.animate([{ opacity: 0 }, { opacity: 0.55 }], { duration: fadeMs }));
      }
    }
  }

  function applyRoom(id, animate) {
    const els = roomEls(id); if (!els.length) return;
    for (const el of els) {
      el.style.opacity = '1';
      if (animate && dur) {
        const kids = el.children;
        for (let i = 0; i < kids.length; i++) {
          trackAnimation(kids[i].animate([{ opacity: 0 }, { opacity: 1 }], { duration: fadeMs, delay: i * 40, fill: 'backwards' }));
        }
      }
    }
  }

  function reveal(id) {
    if (!graph.rooms.has(id)) { console.warn(`fog: unknown room "${id}"`); return; }
    if (revealed.has(id)) return;
    revealed.add(id);
    const touching = graph.edges.filter(e => e.a === id || e.b === id);
    const fullNow = touching.filter(e => edgeState(e, revealed) === 'full');
    for (const e of fullNow) applyEdge(e, true);
    const delay = dur && fullNow.length ? trailMs * 0.6 : 0;
    const timeoutId = setTimeout(() => {
      pendingTimeouts.delete(timeoutId);
      if (!revealed.has(id)) return;
      applyRoom(id, true);
      for (const e of touching) if (edgeState(e, revealed).startsWith('stub')) applyEdge(e, true);
    }, delay);
    pendingTimeouts.add(timeoutId);
  }

  function setRevealed(ids) {
    revealed.clear();
    for (const el of svgEl.querySelectorAll('.fog-room, .fog-edge')) el.style.opacity = '0';
    for (const id of ids) if (graph.rooms.has(id)) revealed.add(id);
    for (const id of revealed) applyRoom(id, false);
    for (const e of graph.edges) applyEdge(e, false);
  }

  function revealAll() { setRevealed([...graph.rooms.keys()]); }

  function dispose() {
    for (const id of pendingTimeouts) clearTimeout(id);
    pendingTimeouts.clear();
    for (const anim of activeAnimations) anim.cancel();
    activeAnimations.clear();
  }

  return { reveal, revealAll, setRevealed, revealed: () => [...revealed], dispose };
}
