import { mulberry32, hashSeed } from './primitives.js';

export function layoutMap(graph) {
  const width = 1200, height = 900;
  const content = { x: 80, y: 175, w: 1040, h: 640 };
  const rng = mulberry32(hashSeed(graph.mapId + ':layout'));
  const cellW = content.w / graph.cols, cellH = content.h / graph.rows;
  const rooms = new Map();
  for (const room of graph.rooms.values()) {
    const cx = content.x + (room.gx - 0.5) * cellW;
    const cy = content.y + (room.gy - 0.5) * cellH;
    const x = Math.min(content.x + content.w, Math.max(content.x, cx + (rng() - 0.5) * 0.44 * cellW));
    const y = Math.min(content.y + content.h, Math.max(content.y, cy + (rng() - 0.5) * 0.44 * cellH));
    rooms.set(room.id, { x: +x.toFixed(1), y: +y.toFixed(1), room });
  }
  const trails = graph.edges.map(e => {
    const A = rooms.get(e.a), B = rooms.get(e.b);
    const dx = B.x - A.x, dy = B.y - A.y;
    const len = Math.hypot(dx, dy) || 1;
    const off = (rng() - 0.5) * 0.28 * len;
    const mx = +((A.x + B.x) / 2 - (dy / len) * off).toFixed(1);
    const my = +((A.y + B.y) / 2 + (dx / len) * off).toFixed(1);
    return { a: e.a, b: e.b, twoWay: e.twoWay, from: e.from, mid: [mx, my], path: `M ${A.x},${A.y} Q ${mx},${my} ${B.x},${B.y}` };
  });
  return { width, height, content, rooms, trails };
}
