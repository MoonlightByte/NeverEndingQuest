import { resolveType } from './glyphs.js';

const COORD_RE = /^X(\d+)Y(\d+)$/;

export function parseMap(mapJson, areaJson = null) {
  if (!mapJson) throw new Error('parseMap: rooms[] missing');
  if (!mapJson.mapId) throw new Error('parseMap: mapId missing');
  if (!Array.isArray(mapJson.rooms)) throw new Error('parseMap: rooms[] missing');
  const warnings = [];
  const rooms = new Map();
  const badRooms = [];
  for (const r of mapJson.rooms) {
    if (!r.id) throw new Error('parseMap: room without id');
    const m = COORD_RE.exec(r.coordinates || '');
    if (!m) {
      badRooms.push(r);
      rooms.set(r.id, {
        id: r.id, name: r.name || r.id, type: resolveType(r.type),
        connections: r.connections || [], gx: null, gy: null
      });
      continue;
    }
    rooms.set(r.id, {
      id: r.id, name: r.name || r.id, type: resolveType(r.type),
      connections: r.connections || [], gx: parseInt(m[1], 10), gy: parseInt(m[2], 10)
    });
  }
  const seen = new Map(); // "A|B" -> {a,b,fromA,fromB}
  for (const r of rooms.values()) {
    for (const c of r.connections) {
      if (!rooms.has(c)) { warnings.push(`room ${r.id} connects to unknown room ${c} (skipped)`); continue; }
      const [a, b] = r.id < c ? [r.id, c] : [c, r.id];
      const key = `${a}|${b}`;
      const e = seen.get(key) || { a, b, fromA: false, fromB: false };
      if (r.id === a) e.fromA = true; else e.fromB = true;
      seen.set(key, e);
    }
  }
  const edges = [...seen.values()].map(e => {
    const twoWay = e.fromA && e.fromB;
    if (!twoWay) warnings.push(`edge ${e.a}-${e.b} is one-way in source data`);
    const edge = { a: e.a, b: e.b, twoWay };
    if (!twoWay) edge.from = e.fromA ? e.a : e.b;
    return edge;
  }).sort((x, y) => (x.a + x.b).localeCompare(y.a + y.b));
  // Some modules emit 0-based coordinates (e.g. "X1Y0"); normalize so the
  // minimum is 1 on each axis and the layout never clamps rooms to the border.
  const goodRooms = [...rooms.values()].filter(r => r.gx !== null);
  let minGx = Infinity, minGy = Infinity;
  for (const r of goodRooms) { minGx = Math.min(minGx, r.gx); minGy = Math.min(minGy, r.gy); }
  const dx = goodRooms.length ? 1 - minGx : 0, dy = goodRooms.length ? 1 - minGy : 0;
  if (dx || dy) {
    for (const r of goodRooms) { r.gx += dx; r.gy += dy; }
    warnings.push(`normalized: coordinates shifted by X${dx >= 0 ? '+' : ''}${dx} Y${dy >= 0 ? '+' : ''}${dy} so the grid starts at X1Y1`);
  }
  let cols = 0, rows = 0;
  for (const r of goodRooms) { cols = Math.max(cols, r.gx); rows = Math.max(rows, r.gy); }

  // Rooms with unparseable coordinates: keep the map usable by auto-placing
  // them instead of aborting the whole parse.
  if (badRooms.length) {
    if (!goodRooms.length) {
      const n = badRooms.length;
      const width = Math.max(1, Math.ceil(Math.sqrt(n)));
      badRooms.forEach((r, i) => {
        const room = rooms.get(r.id);
        room.gx = (i % width) + 1;
        room.gy = Math.floor(i / width) + 1;
      });
      cols = width;
      rows = Math.max(1, Math.ceil(n / width));
      warnings.push('all coordinates unparseable; auto-layout applied');
    } else {
      let col = cols + 1, row = 1;
      const maxRow = Math.max(rows, 1);
      for (const r of badRooms) {
        const room = rooms.get(r.id);
        room.gx = col;
        room.gy = row;
        warnings.push(`room ${r.id} has unparseable coordinates "${r.coordinates}" (auto-placed)`);
        row++;
        if (row > maxRow) { row = 1; col++; }
      }
      cols = 0; rows = 0;
      for (const r of rooms.values()) { cols = Math.max(cols, r.gx); rows = Math.max(rows, r.gy); }
    }
  }

  const area = {
    areaType: (areaJson && areaJson.areaType) || 'wilderness',
    terrain: (areaJson && areaJson.terrain) || '',
    climate: (areaJson && areaJson.climate) || '',
    description: (areaJson && areaJson.areaDescription) || '',
    nameHint: areaJson ? '' : (mapJson.mapName || '')
  };
  return { mapId: mapJson.mapId, mapName: mapJson.mapName || mapJson.mapId, rooms, edges, cols, rows, area, warnings };
}
