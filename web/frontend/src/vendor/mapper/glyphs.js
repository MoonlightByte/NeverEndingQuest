import { mulberry32, PALETTE } from './primitives.js';
const K = PALETTE.ink, BG = PALETTE.bg;
const W = (sw = 1.4) => `fill="none" stroke="${K}" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"`;
const F = () => `fill="${BG}" stroke="${K}" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"`;

// Landmark icons in the style of hand-drawn fantasy-map stamps: front
// elevations with parchment-filled bodies, ~26-34px tall, ground line at y+12.

const ALIAS = {
  'throne room': 'throne', 'treasure room': 'treasure', corridor: 'passage', tunnel: 'passage',
  campsite: 'camp', temple: 'shrine', residence: 'cottage',
  stronghold: 'garrison', room: 'default', location: 'default'
};

export function resolveType(raw) {
  const t = String(raw || 'default').toLowerCase().trim().replace(/\s+/g, ' ');
  return ALIAS[t] || t || 'default';
}

const ROOM = {
  // stacked stone cairn with a grass tuft
  trail: (x, y) => `<circle cx="${x - 5}" cy="${y + 8}" r="4.5" ${F()}/><circle cx="${x + 5}" cy="${y + 8}" r="4.5" ${F()}/><circle cx="${x}" cy="${y + 1}" r="5" ${F()}/><circle cx="${x}" cy="${y - 6.5}" r="3.2" ${F()}/><path d="M ${x + 11},${y + 11} q 0,-4 -1,-5.5 m 1,5.5 q 1,-4 2,-5 M ${x - 12},${y + 12} l 24,0" ${W(1)}/>`,
  // timber watchtower: splayed legs, cross-brace, roofed platform, pennant
  outpost: (x, y) => `<path d="M ${x - 8},${y + 12} L ${x - 4},${y - 4} M ${x + 8},${y + 12} L ${x + 4},${y - 4}" ${W(1.5)}/><path d="M ${x - 6.5},${y + 6} L ${x + 5.5},${y - 1} M ${x + 6.5},${y + 6} L ${x - 5.5},${y - 1}" ${W(1)}/><rect x="${x - 7}" y="${y - 10}" width="14" height="6" ${F()}/><path d="M ${x - 8.5},${y - 10} L ${x},${y - 17} L ${x + 8.5},${y - 10}" ${F()}/><path d="M ${x},${y - 17} l 0,-6 l 7,2.2 l -7,2.2" ${W(1.2)}/>`,
  // stepped temple: columns, entablature, pediment with oculus
  shrine: (x, y) => `<path d="M ${x - 11},${y + 12} L ${x + 11},${y + 12} M ${x - 9.5},${y + 9} L ${x + 9.5},${y + 9}" ${W(1.3)}/><path d="M ${x - 7},${y + 9} L ${x - 7},${y - 4} M ${x - 2.3},${y + 9} L ${x - 2.3},${y - 4} M ${x + 2.3},${y + 9} L ${x + 2.3},${y - 4} M ${x + 7},${y + 9} L ${x + 7},${y - 4}" ${W(1.3)}/><path d="M ${x - 9},${y - 4} L ${x + 9},${y - 4}" ${W(1.3)}/><path d="M ${x - 10.5},${y - 4} L ${x},${y - 13.5} L ${x + 10.5},${y - 4} Z" ${F()}/><circle cx="${x}" cy="${y - 7.5}" r="1.7" fill="${K}"/>`,
  // ring of standing stones around an altar
  ritual: (x, y) => `<ellipse cx="${x}" cy="${y + 3}" rx="12" ry="7.5" stroke-dasharray="3 3.5" ${W(1)}/><path d="M ${x - 11},${y + 2} l 0,-6 M ${x + 11},${y + 2} l 0,-6 M ${x - 6},${y + 10} l 0,-5.5 M ${x + 6},${y + 10} l 0,-5.5 M ${x},${y - 3} l 0,-7" ${W(2.6)}/><circle cx="${x}" cy="${y + 3}" r="1.6" fill="${K}"/>`,
  // tall reeds with cattail heads over water
  marsh: (x, y) => `<path d="M ${x - 7},${y + 8} q -2,-12 -5,-15 M ${x - 3},${y + 8} q -0.5,-13 -1,-17 M ${x + 1},${y + 8} q 0.5,-12 2,-16 M ${x + 5},${y + 8} q 2,-10 5,-13" ${W(1.3)}/><path d="M ${x - 4.2},${y - 8} l 0.3,-3.5 M ${x + 2.4},${y - 7} l 0.8,-3.2" ${W(2.6)}/><path d="M ${x - 11},${y + 10} q 4,2.6 8,0 q 4,-2.6 8,0 q 3,2 6,0" ${W(1.1)}/>`,
  // dashed glade ring around an old stump
  clearing: (x, y) => `<ellipse cx="${x}" cy="${y + 3}" rx="12.5" ry="8.5" stroke-dasharray="4.5 4" ${W(1.2)}/><path d="M ${x - 3},${y} l 0,5.5 q 3,1.6 6,0 l 0,-5.5" ${W(1.2)}/><ellipse cx="${x}" cy="${y}" rx="3" ry="1.5" ${F()}/>`,
  // shingled hut with smoking chimney
  cottage: (x, y) => `<rect x="${x - 9}" y="${y + 2}" width="18" height="10" ${F()}/><path d="M ${x - 11},${y + 2} L ${x},${y - 9} L ${x + 11},${y + 2} Z" ${F()}/><path d="M ${x - 5.5},${y - 1.5} l 11,0 M ${x - 3},${y - 4.5} l 6,0" ${W(0.9)}/><path d="M ${x + 4.5},${y - 5.5} l 0,-4.5 l 3.2,0 l 0,7" ${W(1.2)}/><path d="M ${x + 6},${y - 12} q -1.5,-2 0.5,-3.5" ${W(1)}/><path d="M ${x - 1.6},${y + 12} L ${x - 1.6},${y + 7} Q ${x},${y + 5.5} ${x + 1.6},${y + 7} L ${x + 1.6},${y + 12}" ${W(1.1)}/><rect x="${x - 6.5}" y="${y + 5.5}" width="2.8" height="2.8" ${W(0.9)}/>`,
  // winding dashed footpath
  path: (x, y) => `<path d="M ${x - 14},${y + 9} Q ${x - 5},${y - 1} ${x + 1},${y + 2} Q ${x + 8},${y + 5} ${x + 14},${y - 6}" stroke-dasharray="5 4" ${W(1.8)}/>`,
  // stone arch with keystone and dark passage
  entrance: (x, y) => `<path d="M ${x - 11},${y + 12} L ${x - 11},${y - 1} Q ${x},${y - 14} ${x + 11},${y - 1} L ${x + 11},${y + 12}" ${F()}/><path d="M ${x - 5.5},${y + 12} L ${x - 5.5},${y + 2} Q ${x},${y - 3.5} ${x + 5.5},${y + 2} L ${x + 5.5},${y + 12} Z" fill="${K}" stroke="none"/><path d="M ${x - 8.7},${y - 5.5} l 2.8,2.2 M ${x + 8.7},${y - 5.5} l -2.8,2.2 M ${x - 1.7},${y - 11} l 3.4,0.2" ${W(1)}/>`,
  // paved court with south gate gap and a well
  courtyard: (x, y) => `<path d="M ${x - 3.5},${y + 11} L ${x - 12},${y + 11} L ${x - 12},${y - 9} L ${x + 12},${y - 9} L ${x + 12},${y + 11} L ${x + 3.5},${y + 11}" ${W(1.5)}/><path d="M ${x - 9},${y + 7.5} l 2.5,0 m 2.5,-3 l 2.5,0 m 2.5,3 l 2.5,0 m -11,-7 l 2.5,0 m 5,0 l 2.5,0" ${W(0.8)}/><circle cx="${x}" cy="${y - 3.5}" r="2.6" ${F()}/><path d="M ${x - 2.6},${y - 6.8} l 5.2,0" ${W(1)}/>`,
  // twin crenellated towers over a portcullised arch
  gatehouse: (x, y) => `<rect x="${x - 14}" y="${y - 8}" width="7" height="20" ${F()}/><rect x="${x + 7}" y="${y - 8}" width="7" height="20" ${F()}/><path d="M ${x - 14},${y - 8} l 0,-3 l 2.4,0 l 0,3 m 2.3,0 l 0,-3 l 2.3,0 l 0,3 M ${x + 7},${y - 8} l 0,-3 l 2.4,0 l 0,3 m 2.3,0 l 0,-3 l 2.3,0 l 0,3" ${W(1)}/><path d="M ${x - 7},${y + 12} L ${x - 7},${y - 1} Q ${x},${y - 7.5} ${x + 7},${y - 1} L ${x + 7},${y + 12}" ${W(1.3)}/><path d="M ${x - 3.5},${y - 4.5} l 0,16.5 M ${x},${y - 5.5} l 0,17.5 M ${x + 3.5},${y - 4.5} l 0,16.5 M ${x - 6.5},${y + 3} l 13,0" ${W(0.8)}/>`,
  // nave and spired bell tower
  chapel: (x, y) => `<rect x="${x - 11}" y="${y + 2}" width="15" height="10" ${F()}/><path d="M ${x - 12.5},${y + 2} L ${x - 3.5},${y - 6} L ${x + 5.5},${y + 2}" ${F()}/><rect x="${x + 4}" y="${y - 8}" width="6.5" height="20" ${F()}/><path d="M ${x + 2.8},${y - 8} L ${x + 7.2},${y - 15.5} L ${x + 11.7},${y - 8}" ${F()}/><path d="M ${x + 7.2},${y - 15.5} l 0,-4.5 m -2,1.5 l 4,0" ${W(1.2)}/><circle cx="${x - 4.5}" cy="${y - 0.5}" r="1.8" ${W(1)}/><path d="M ${x - 8},${y + 12} L ${x - 8},${y + 7.5} Q ${x - 6.4},${y + 6} ${x - 4.8},${y + 7.5} L ${x - 4.8},${y + 12}" ${W(1)}/>`,
  // long soldiers' hall with twin doors
  barracks: (x, y) => `<rect x="${x - 15}" y="${y + 2}" width="30" height="10" ${F()}/><path d="M ${x - 16.5},${y + 2} L ${x},${y - 7} L ${x + 16.5},${y + 2} Z" ${F()}/><path d="M ${x - 9},${y - 1} l 18,0" ${W(0.9)}/><path d="M ${x - 7.5},${y + 12} l 0,-5 q 1.6,-1.5 3.2,0 l 0,5 M ${x + 4.3},${y + 12} l 0,-5 q 1.6,-1.5 3.2,0 l 0,5" ${W(1)}/><rect x="${x - 1.4}" y="${y + 5}" width="2.8" height="2.6" ${W(0.9)}/>`,
  // great gabled hall flying a banner
  hall: (x, y) => `<rect x="${x - 12}" y="${y - 2}" width="24" height="14" ${F()}/><path d="M ${x - 14},${y - 2} L ${x},${y - 14} L ${x + 14},${y - 2} Z" ${F()}/><path d="M ${x},${y - 14} l 0,-7 l 6,2.1 l -6,2.1" ${W(1.2)}/><path d="M ${x - 3},${y + 12} L ${x - 3},${y + 5} Q ${x},${y + 3} ${x + 3},${y + 5} L ${x + 3},${y + 12} M ${x},${y + 4} L ${x},${y + 12}" ${W(1.1)}/><rect x="${x - 8.5}" y="${y + 2}" width="3" height="3" ${W(0.9)}/><rect x="${x + 5.5}" y="${y + 2}" width="3" height="3" ${W(0.9)}/>`,
  // lone crenellated watchtower with arrow slits
  tower: (x, y) => `<path d="M ${x - 6},${y + 12} L ${x - 4.5},${y - 12} L ${x + 4.5},${y - 12} L ${x + 6},${y + 12} Z" ${F()}/><path d="M ${x - 4.5},${y - 12} l 0,-3.5 l 3,0 l 0,3.5 m 3,0 l 0,-3.5 l 3,0 l 0,3.5" ${W(1.1)}/><path d="M ${x},${y - 6} l 0,3.5 M ${x},${y + 2} l 0,3.5" ${W(1.3)}/><path d="M ${x},${y - 15.5} l 0,-5 l 6,1.8 l -6,1.8" ${W(1.1)}/><path d="M ${x - 8},${y + 12} l 16,0" ${W(1)}/>`,
  // stepped mausoleum with dark door and cross
  crypt: (x, y) => `<path d="M ${x - 12},${y + 12} L ${x + 12},${y + 12} M ${x - 10.5},${y + 9} L ${x + 10.5},${y + 9}" ${W(1.3)}/><path d="M ${x - 9},${y + 9} L ${x - 9},${y - 3} Q ${x},${y - 11} ${x + 9},${y - 3} L ${x + 9},${y + 9}" ${F()}/><path d="M ${x - 3},${y + 9} L ${x - 3},${y + 2} Q ${x},${y - 1} ${x + 3},${y + 2} L ${x + 3},${y + 9} Z" fill="${K}" stroke="none"/><path d="M ${x},${y - 11} l 0,-4 m -2,1.4 l 4,0" ${W(1.2)}/>`,
  // craggy hill with a dark mouth and a boulder
  cave: (x, y) => `<path d="M ${x - 13},${y + 12} L ${x - 9},${y - 1} L ${x - 5},${y - 8} L ${x + 1},${y - 11} L ${x + 6},${y - 6} L ${x + 10},${y - 8} L ${x + 13},${y + 12} Z" ${F()}/><path d="M ${x - 4},${y + 12} L ${x - 3},${y + 3} Q ${x},${y - 1} ${x + 3},${y + 3} L ${x + 4},${y + 12} Z" fill="${K}" stroke="none"/><circle cx="${x + 9.5}" cy="${y + 10}" r="2.2" ${F()}/>`,
  // pennanted tent beside a campfire
  camp: (x, y) => `<path d="M ${x - 12},${y + 12} L ${x - 2},${y - 9} L ${x + 8},${y + 12} Z" ${F()}/><path d="M ${x - 5},${y + 12} L ${x - 2},${y + 3} L ${x + 1},${y + 12}" ${W(1.1)}/><path d="M ${x - 2},${y - 9} l 0,-4.5 l 5.5,1.7 l -5.5,1.7" ${W(1.1)}/><path d="M ${x + 12},${y + 10} q 1.6,-3 0.2,-5.5 q 3,1.5 2.2,5 M ${x + 10},${y + 12} l 5.5,-1.5 m -5.5,0 l 5.5,1.5" ${W(1)}/>`,
  // cattail reeds over still water with bubbles
  bog: (x, y) => `<path d="M ${x - 5},${y + 4} q -1.5,-10 -4,-12.5 M ${x - 1},${y + 4} q 0,-11 0,-14 M ${x + 3},${y + 4} q 1.5,-9 4,-12" ${W(1.2)}/><path d="M ${x - 1},${y - 7.5} l 0,-3.5 M ${x + 5.6},${y - 6} l 0.8,-3" ${W(2.4)}/><path d="M ${x - 11},${y + 8} q 4,2.6 8,0 q 4,-2.6 8,0 q 3,2 6,0" ${W(1.1)}/><circle cx="${x - 6}" cy="${y + 5.5}" r="0.9" ${W(0.8)}/><circle cx="${x + 8}" cy="${y + 5}" r="0.7" ${W(0.8)}/>`,
  // vaulted room plan: door gap and corner columns
  chamber: (x, y) => `<path d="M ${x - 3.5},${y + 11} L ${x - 11},${y + 11} L ${x - 11},${y - 9} L ${x + 11},${y - 9} L ${x + 11},${y + 11} L ${x + 3.5},${y + 11}" ${W(1.5)}/><circle cx="${x - 7}" cy="${y - 5}" r="1.2" fill="${K}"/><circle cx="${x + 7}" cy="${y - 5}" r="1.2" fill="${K}"/><circle cx="${x - 7}" cy="${y + 7}" r="1.2" fill="${K}"/><circle cx="${x + 7}" cy="${y + 7}" r="1.2" fill="${K}"/>`,
  // crenellated keep flying a banner
  garrison: (x, y) => `<rect x="${x - 11}" y="${y - 6}" width="22" height="18" ${F()}/><path d="M ${x - 11},${y - 6} l 0,-3 l 3.6,0 l 0,3 M ${x - 3.6},${y - 6} l 0,-3 l 3.6,0 l 0,3 M ${x + 4},${y - 6} l 0,-3 l 3.6,0 l 0,3" ${W(1)}/><path d="M ${x + 11},${y - 9} l 0,-6 l -6,2.1 l 6,2.1" ${W(1.1)}/><path d="M ${x - 2},${y + 12} L ${x - 2},${y + 5} Q ${x},${y + 3.5} ${x + 2},${y + 5} L ${x + 2},${y + 12}" ${W(1.1)}/><path d="M ${x - 6.5},${y - 1} l 0,3 M ${x + 6.5},${y - 1} l 0,3" ${W(1.2)}/>`,
  // town gate: posts, twin lintels, doors flung open
  gate: (x, y) => `<path d="M ${x - 10},${y + 12} L ${x - 10},${y - 9} M ${x + 10},${y + 12} L ${x + 10},${y - 9}" ${W(2)}/><path d="M ${x - 12},${y - 9} L ${x + 12},${y - 9} M ${x - 11},${y - 5.5} L ${x + 11},${y - 5.5}" ${W(1.5)}/><path d="M ${x - 10},${y - 5.5} L ${x - 4},${y - 1.5} L ${x - 4},${y + 12} M ${x - 7},${y - 3.5} l 0,13.5" ${W(1)}/><path d="M ${x + 10},${y - 5.5} L ${x + 4},${y - 1.5} L ${x + 4},${y + 12} M ${x + 7},${y - 3.5} l 0,13.5" ${W(1)}/>`,
  // roadside inn with a swinging signboard
  inn: (x, y) => `<rect x="${x - 11}" y="${y + 1}" width="17" height="11" ${F()}/><path d="M ${x - 13},${y + 1} L ${x - 2.5},${y - 9} L ${x + 8},${y + 1} Z" ${F()}/><path d="M ${x - 7.5},${y - 2} l 10,0" ${W(0.9)}/><path d="M ${x + 8},${y - 7} l 8,0 m -2.5,0 l 0,3" ${W(1.2)}/><rect x="${x + 10.6}" y="${y - 4}" width="6" height="5" ${W(1.1)}/><path d="M ${x - 5},${y + 12} L ${x - 5},${y + 6.5} Q ${x - 3.4},${y + 5} ${x - 1.8},${y + 6.5} L ${x - 1.8},${y + 12}" ${W(1)}/><rect x="${x + 1.5}" y="${y + 4.5}" width="3" height="3" ${W(0.9)}/>`,
  // dashed corridor walls with way chevrons
  passage: (x, y) => `<path d="M ${x - 13},${y - 4} q 13,-3 26,0" stroke-dasharray="4.5 3.5" ${W(1.4)}/><path d="M ${x - 13},${y + 6} q 13,-3 26,0" stroke-dasharray="4.5 3.5" ${W(1.4)}/><path d="M ${x - 5},${y - 0.5} l 3,1.4 l -3,1.4 M ${x + 2},${y - 0.8} l 3,1.4 l -3,1.4" ${W(1.1)}/>`,
  // stone gaol: barred window and studded door
  prison: (x, y) => `<rect x="${x - 11}" y="${y - 8}" width="22" height="20" ${F()}/><path d="M ${x - 12.5},${y - 8} l 25,0" ${W(1.6)}/><rect x="${x - 7}" y="${y - 4}" width="9" height="6.5" ${W(1.2)}/><path d="M ${x - 4.2},${y - 4} l 0,6.5 M ${x - 1.2},${y - 4} l 0,6.5 M ${x + 1.8},${y - 4} l 0,6.5" ${W(1)}/><path d="M ${x + 4},${y + 12} L ${x + 4},${y + 5.5} Q ${x + 6.2},${y + 3.5} ${x + 8.4},${y + 5.5} L ${x + 8.4},${y + 12}" ${W(1.1)}/><circle cx="${x + 5.3}" cy="${y + 8.5}" r="0.6" fill="${K}"/>`,
  // broken columns and a fallen drum
  ruins: (x, y) => `<path d="M ${x - 9},${y + 12} L ${x - 9},${y - 3} L ${x - 7.4},${y - 7} L ${x - 5.2},${y - 4} L ${x - 5.2},${y + 12}" ${F()}/><path d="M ${x - 10.4},${y - 2.5} l 6.5,0" ${W(1)}/><path d="M ${x + 0.5},${y + 12} L ${x + 0.5},${y + 1} L ${x + 2},${y - 2.5} L ${x + 4.3},${y + 0.5} L ${x + 4.3},${y + 12}" ${F()}/><ellipse cx="${x + 10}" cy="${y + 9.5}" rx="3.2" ry="2.2" ${F()}/><ellipse cx="${x + 10}" cy="${y + 9.5}" rx="1.2" ry="0.8" ${W(0.8)}/><path d="M ${x - 12},${y + 12} l 25,0" ${W(1)}/>`,
  // market stall with scalloped awning
  shop: (x, y) => `<rect x="${x - 10}" y="${y - 1}" width="20" height="13" ${F()}/><path d="M ${x - 12},${y - 1} L ${x - 9},${y - 8} L ${x + 9},${y - 8} L ${x + 12},${y - 1}" ${F()}/><path d="M ${x - 12},${y - 1} q 3,3.4 6,0 q 3,3.4 6,0 q 3,3.4 6,0 q 3,3.4 6,0" ${W(1)}/><rect x="${x - 6.5}" y="${y + 3.5}" width="7" height="5" ${W(1)}/><path d="M ${x - 3},${y + 3.5} l 0,5 M ${x - 6.5},${y + 6} l 7,0" ${W(0.7)}/><path d="M ${x + 3.5},${y + 12} l 0,-6.5 l 4.5,0 l 0,6.5" ${W(1)}/>`,
  // plaza fountain: basin, bowl, falling water
  square: (x, y) => `<ellipse cx="${x}" cy="${y + 7}" rx="11" ry="4.5" ${F()}/><ellipse cx="${x}" cy="${y + 6}" rx="7.5" ry="2.8" ${W(1)}/><path d="M ${x},${y + 4.5} L ${x},${y - 4}" ${W(1.6)}/><path d="M ${x - 3.5},${y - 4.5} q 3.5,2.8 7,0" ${W(1.2)}/><path d="M ${x - 3},${y - 6.5} q 3,-2.6 6,0" ${W(1)}/><path d="M ${x - 5},${y - 2} q -2.2,3 -1.6,6.5 M ${x + 5},${y - 2} q 2.2,3 1.6,6.5" ${W(0.9)}/>`,
  // cellar barrels and a crate
  storage: (x, y) => `<path d="M ${x - 10.5},${y - 5} q -2.6,8.5 0,17 L ${x - 0.5},${y + 12} q 2.6,-8.5 0,-17 Z" ${F()}/><path d="M ${x - 11.8},${y + 0.5} l 12.3,0 M ${x - 11.8},${y + 6} l 12.3,0" ${W(1)}/><path d="M ${x - 7.5},${y - 4} l -0.4,15 M ${x - 3.5},${y - 4} l 0.4,15" ${W(0.7)}/><rect x="${x + 2.5}" y="${y + 2.5}" width="9.5" height="9.5" ${F()}/><path d="M ${x + 2.5},${y + 2.5} L ${x + 12},${y + 12} M ${x + 12},${y + 2.5} L ${x + 2.5},${y + 12}" ${W(0.8)}/><path d="M ${x + 4.5},${y + 2.5} l 0,-3.5 l 5.5,0 l 0,3.5" ${W(1)}/>`,
  // stacked strapped crates and a sack
  store: (x, y) => `<rect x="${x - 10}" y="${y + 2}" width="12" height="10" ${F()}/><path d="M ${x - 10},${y + 2} L ${x + 2},${y + 12} M ${x + 2},${y + 2} L ${x - 10},${y + 12}" ${W(0.8)}/><rect x="${x - 7.5}" y="${y - 7}" width="9" height="9" ${F()}/><path d="M ${x - 7.5},${y - 2.5} l 9,0" ${W(0.7)}/><path d="M ${x + 5.5},${y + 12} q -2.5,-3.5 -0.5,-7 q 1,-2 3,-2.4 l 0.6,-2.2 l 1.8,1.6 q 2.6,1 2.6,4 q 0.4,3.5 -1.8,6 Z" ${F()}/>`,
  // open tome with a quill
  study: (x, y) => `<path d="M ${x},${y - 3} q -6.5,-4.5 -12,-1.8 L ${x - 12},${y + 6.5} q 5.5,-2.7 12,1.8 q 6.5,-4.5 12,-1.8 L ${x + 12},${y - 4.8} q -5.5,-2.7 -12,1.8 Z" ${F()}/><path d="M ${x},${y - 3} L ${x},${y + 8.3}" ${W(1.1)}/><path d="M ${x - 9},${y - 0.5} q 3.5,-1.4 6.5,0.5 M ${x - 9},${y + 2.5} q 3.5,-1.4 6.5,0.5 M ${x + 2.5},${y} q 3,-1.9 6.5,-0.5 M ${x + 2.5},${y + 3} q 3,-1.9 6.5,-0.5" ${W(0.7)}/><path d="M ${x + 9},${y - 10} q 4.5,-3.5 7,-4 q -1.5,3.5 -4.5,6.5 l -2.5,-2.5" ${W(1.1)}/>`,
  // foaming tankard
  tavern: (x, y) => `<path d="M ${x - 7},${y - 6} L ${x - 5.5},${y + 12} L ${x + 5.5},${y + 12} L ${x + 7},${y - 6}" ${F()}/><path d="M ${x - 6.6},${y - 1} l 13.2,0 M ${x - 6},${y + 6} l 12,0" ${W(0.9)}/><path d="M ${x - 2},${y - 5} l 0.5,16 M ${x + 2},${y - 5} l -0.5,16" ${W(0.7)}/><path d="M ${x + 7},${y - 3} q 6.5,-0.5 5.5,5 q -0.7,4 -4.6,3.4" ${W(1.3)}/><path d="M ${x - 8},${y - 6} q 2.2,-4 4.6,-1.6 q 1.8,-3.4 4.4,-1.4 q 2.6,-1.6 4.6,1 q 1.6,0.6 1.9,2" ${W(1.2)}/><path d="M ${x + 4.6},${y - 8.5} q 1.2,1.8 0.4,3.4" ${W(0.9)}/>`,
  // headstone before a burial mound
  tomb: (x, y) => `<path d="M ${x - 9},${y + 12} L ${x - 9},${y - 4} Q ${x - 4},${y - 10.5} ${x + 1},${y - 4} L ${x + 1},${y + 12}" ${F()}/><path d="M ${x - 4},${y - 4.5} l 0,6 m -2.6,-3.4 l 5.2,0" ${W(1.1)}/><path d="M ${x + 1},${y + 12} Q ${x + 8},${y + 2} ${x + 15},${y + 12}" ${W(1.3)}/><path d="M ${x + 8},${y + 6} q 0,-3 -1,-4 m 1,4 q 1,-3 2,-3.5" ${W(0.9)}/><path d="M ${x - 12},${y + 12} l 28,0" ${W(1)}/>`,
  // two trees in a dashed glade
  grove: (x, y) => `<ellipse cx="${x}" cy="${y + 4}" rx="13" ry="8.5" stroke-dasharray="4.5 4" ${W(1.1)}/><path d="M ${x - 9},${y + 3} a 3.5,3.5 0 0 1 3,-5 a 3,3 0 0 1 3.5,1 a 3.2,3.2 0 0 1 1,4 Z" ${F()}/><path d="M ${x - 5.5},${y + 3} l 0,3.5" ${W(1)}/><path d="M ${x + 2},${y + 1} a 3.5,3.5 0 0 1 3,-5 a 3,3 0 0 1 3.5,1 a 3.2,3.2 0 0 1 1,4 Z" ${F()}/><path d="M ${x + 5.5},${y + 1} l 0,3.5" ${W(1)}/>`,
  // jagged gorge with hatched depth
  ravine: (x, y) => `<path d="M ${x - 13},${y - 7} L ${x - 8},${y - 3} L ${x - 10},${y + 2} L ${x - 5},${y + 6} L ${x - 7},${y + 11}" ${W(1.4)}/><path d="M ${x + 13},${y - 9} L ${x + 8},${y - 4} L ${x + 10},${y + 1} L ${x + 5},${y + 5} L ${x + 7},${y + 10}" ${W(1.4)}/><path d="M ${x - 6},${y - 2} l 4,3 M ${x - 3},${y + 3} l 4,3 M ${x - 1},${y - 5} l 4,3" ${W(0.8)}/>`,
  // stacked contours with a summit flag
  hilltop: (x, y) => `<path d="M ${x - 13},${y + 10} Q ${x},${y - 2} ${x + 13},${y + 10}" ${W(1.4)}/><path d="M ${x - 8},${y + 5} Q ${x},${y - 5} ${x + 8},${y + 5}" ${W(1.2)}/><path d="M ${x},${y - 4} l 0,-7 l 6,2.1 l -6,2.1" ${W(1.1)}/><path d="M ${x - 4},${y + 8} l 2.5,0 m 3,0 l 2.5,0" ${W(0.8)}/>`,
  // river bend with reeds on the bank
  riverside: (x, y) => `<path d="M ${x - 13},${y - 8} Q ${x - 2},${y - 2} ${x - 4},${y + 4} Q ${x - 5.5},${y + 9} ${x + 2},${y + 12}" ${W(1.3)}/><path d="M ${x - 7},${y - 9} Q ${x + 3},${y - 3} ${x + 1},${y + 3} Q ${x - 0.5},${y + 8} ${x + 7},${y + 11}" ${W(1.3)}/><path d="M ${x - 2},${y - 1} q 1.5,-1.2 3,0" ${W(0.8)}/><path d="M ${x + 7},${y + 2} q -1,-6 -2.5,-7.5 M ${x + 9.5},${y + 2} q 0,-6.5 -0.5,-8.5 M ${x + 12},${y + 2} q 1,-5.5 2,-7" ${W(1.1)}/><path d="M ${x + 5},${y + 2} l 10,0" ${W(0.9)}/>`,
  // signpost where dashed ways cross
  crossroads: (x, y) => `<path d="M ${x - 13},${y + 8} L ${x + 13},${y + 2}" stroke-dasharray="4 3" ${W(1.4)}/><path d="M ${x - 8},${y + 12} L ${x + 6},${y - 2}" stroke-dasharray="4 3" ${W(1.4)}/><path d="M ${x},${y + 6} l 0,-16" ${W(1.5)}/><path d="M ${x},${y - 9} l 8,0 l 2.5,1.8 l -2.5,1.8 l -8,0 Z" ${F()}/><path d="M ${x},${y - 4.5} l -7,0 l -2.5,1.8 l 2.5,1.8 l 7,0 Z" ${F()}/>`,
  // carved obelisk
  landmark: (x, y) => `<path d="M ${x - 4},${y + 8} L ${x - 2.5},${y - 12} L ${x + 2.5},${y - 12} L ${x + 4},${y + 8} Z" ${F()}/><path d="M ${x - 2.5},${y - 12} L ${x},${y - 16} L ${x + 2.5},${y - 12}" ${F()}/><path d="M ${x - 1.5},${y - 8} l 3,0 M ${x - 1.5},${y - 5} l 3,0 M ${x - 1.5},${y - 2} l 3,0" ${W(0.8)}/><path d="M ${x - 7},${y + 8} l 14,0 M ${x - 5.5},${y + 11} l 11,0" ${W(1.1)}/>`,
  // banded strongbox in an arched niche
  vault: (x, y) => `<path d="M ${x - 10},${y + 12} L ${x - 10},${y - 2} Q ${x},${y - 12} ${x + 10},${y - 2} L ${x + 10},${y + 12}" ${W(1.4)}/><rect x="${x - 6}" y="${y + 1}" width="12" height="9" ${F()}/><path d="M ${x - 6},${y + 4.5} l 12,0 M ${x - 2},${y + 1} l 0,9 M ${x + 2},${y + 1} l 0,9" ${W(0.9)}/><circle cx="${x}" cy="${y + 6.8}" r="1" fill="${K}"/>`,
  // alchemist's bench with flasks
  laboratory: (x, y) => `<path d="M ${x - 10},${y + 3} l 20,0 M ${x - 8},${y + 3} l 0,9 M ${x + 8},${y + 3} l 0,9" ${W(1.3)}/><circle cx="${x - 4}" cy="${y - 1}" r="3.4" ${F()}/><path d="M ${x - 4.9},${y - 4} l 1.8,0 l 0,-3 l -1.8,0 Z" ${W(1)}/><path d="M ${x + 3},${y + 3} L ${x + 4},${y - 6} l 2.5,0 L ${x + 8.5},${y + 3}" ${W(1.1)}/><path d="M ${x - 5},${y - 9} q 1,-1.5 0,-3 M ${x - 2.5},${y - 9.5} q 1,-1.5 0,-3" ${W(0.8)}/>`,
  // high-backed throne on a dais
  throne: (x, y) => `<path d="M ${x - 6},${y + 4} L ${x - 6},${y - 9} q 1.5,-2.5 3,0 L ${x - 3},${y - 5} L ${x + 3},${y - 5} L ${x + 3},${y - 9} q 1.5,-2.5 3,0 L ${x + 6},${y + 4} Z" ${F()}/><path d="M ${x - 4},${y + 0.5} l 8,0" ${W(1)}/><path d="M ${x - 9},${y + 7.5} l 18,0 M ${x - 11},${y + 11} l 22,0" ${W(1.2)}/>`,
  // chest thrown open, coins heaped inside
  treasure: (x, y) => `<rect x="${x - 8}" y="${y + 2}" width="16" height="9" ${F()}/><path d="M ${x - 8},${y + 2} L ${x - 10},${y - 5} Q ${x},${y - 11} ${x + 10},${y - 5} L ${x + 8},${y + 2}" ${F()}/><path d="M ${x - 7.2},${y - 1} Q ${x},${y - 6.5} ${x + 7.2},${y - 1}" ${W(0.8)}/><circle cx="${x - 3.5}" cy="${y + 1.5}" r="1.6" ${F()}/><circle cx="${x + 0.5}" cy="${y + 0.8}" r="1.6" ${F()}/><circle cx="${x + 4}" cy="${y + 1.8}" r="1.6" ${F()}/><path d="M ${x},${y + 6.5} l 0,2.5 m -1.6,-1.25 l 3.2,0" ${W(1)}/><path d="M ${x - 12},${y - 8} l 2,0 m -1,-1 l 0,2 M ${x + 12},${y - 9} l 2,0 m -1,-1 l 0,2" ${W(0.8)}/>`,
  // open market stall
  market: (x, y) => `<path d="M ${x - 10},${y + 12} L ${x - 10},${y - 4} M ${x + 10},${y + 12} L ${x + 10},${y - 4}" ${W(1.3)}/><path d="M ${x - 12},${y - 4} Q ${x},${y - 10} ${x + 12},${y - 4} l -2,4 q -10,-5 -20,0 Z" ${F()}/><path d="M ${x - 8},${y + 6} l 16,0 M ${x - 8},${y + 6} l 0,6 M ${x + 8},${y + 6} l 0,6" ${W(1.1)}/><circle cx="${x - 3}" cy="${y + 4}" r="1.4" ${W(0.8)}/><circle cx="${x + 2}" cy="${y + 4}" r="1.4" ${W(0.8)}/>`,
  // broad-roofed storehouse with cart door
  warehouse: (x, y) => `<rect x="${x - 13}" y="${y}" width="26" height="12" ${F()}/><path d="M ${x - 15},${y} L ${x},${y - 9} L ${x + 15},${y} Z" ${F()}/><path d="M ${x - 9},${y + 3} l 18,0" ${W(0.8)}/><path d="M ${x - 4},${y + 12} L ${x - 4},${y + 4} L ${x + 4},${y + 4} L ${x + 4},${y + 12} M ${x},${y + 4} l 0,8" ${W(1.1)}/>`,
  // hall with a shield sign
  guild: (x, y) => `<rect x="${x - 9}" y="${y - 1}" width="18" height="13" ${F()}/><path d="M ${x - 11},${y - 1} L ${x},${y - 10} L ${x + 11},${y - 1} Z" ${F()}/><path d="M ${x},${y - 3} l 0,2" ${W(1)}/><path d="M ${x - 3},${y + 1} l 6,0 l 0,4 q 0,3 -3,4 q -3,-1 -3,-4 Z" ${F()}/><path d="M ${x},${y + 1} l 0,7.5" ${W(0.7)}/><path d="M ${x - 6.5},${y + 12} l 0,-4 q 1.6,-1.5 3.2,0 l 0,4" ${W(1)}/>`
};

export function hasGlyph(type) { return Object.hasOwn(ROOM, type); }

export function roomGlyph(type, x, y, seed) {
  const fn = ROOM[type];
  if (fn) return fn(x, y, mulberry32(seed));
  return `<path d="M ${x - 3.5},${y + 9} L ${x - 4.5},${y - 4} Q ${x},${y - 10} ${x + 4.5},${y - 4} L ${x + 3.5},${y + 9} Z" ${F()}/><path d="M ${x - 2},${y - 2} l 4,0 M ${x - 2},${y + 1.5} l 4,0" ${W(0.9)}/><path d="M ${x - 8},${y + 9} l 16,0" ${W(1.1)}/>`;
}

export function terrainGlyph(d) {
  const { x, y, s, kind } = d;
  const r = mulberry32(d.seed);
  if (kind === 'tree') {
    const p = `M ${x - s},${y} a ${s * 0.55},${s * 0.55} 0 0 1 ${s * 0.5},-${s * 0.75} a ${s * 0.5},${s * 0.5} 0 0 1 ${s * 0.55},-${s * 0.28} a ${s * 0.55},${s * 0.55} 0 0 1 ${s * 0.6},${s * 0.35} a ${s * 0.5},${s * 0.5} 0 0 1 ${s * 0.35},${s * 0.68} Z`;
    return `<path d="${p}" fill="${BG}" stroke="${K}" stroke-width="1.1" stroke-linejoin="round"/><path d="M ${x},${y} l 0,${s * 0.5}" stroke="${K}" stroke-width="1.1"/>`;
  }
  if (kind === 'reed') return `<path d="M ${x - 3},${y} q -1,-${s} -2,-${s + 2} M ${x},${y} q 0,-${s + 2} 0,-${s + 4} M ${x + 3},${y} q 1,-${s} 2,-${s + 3}" ${W(1)}/>`;
  if (kind === 'pool') {
    const w = s + 3;
    return `<path d="M ${x - w},${y} q ${w * 0.5},-${w * 0.42} ${w},-${w * 0.1} q ${w * 0.55},${w * 0.15} ${w},${w * 0.1} q -${w * 0.5},${w * 0.45} -${w},${w * 0.12} q -${w * 0.55},-${w * 0.1} -${w},-${w * 0.12} Z" fill="${BG}" stroke="${K}" stroke-width="1.1" stroke-linejoin="round"/><path d="M ${x - w * 0.4},${y + 1} q ${w * 0.4},${w * 0.22} ${w * 0.8},0" ${W(0.8)}/><path d="M ${x - w - 3},${y + 2} l -3,1 M ${x + w + 3},${y + 2} l 3,1" ${W(0.8)}/>`;
  }
  if (kind === 'peak') {
    const h = s * 1.6;
    return `<path d="M ${x - s},${y} Q ${x - s * 0.45},${y - h * 0.62} ${x - s * 0.08},${y - h} Q ${x + s * 0.4},${y - h * 0.5} ${x + s},${y}" fill="${BG}" stroke="${K}" stroke-width="1.4" stroke-linejoin="round"/><path d="M ${x - s * 0.08},${y - h} Q ${x + s * 0.05},${y - h * 0.45} ${x + s * 0.16},${y}" ${W(1)}/>`;
  }
  if (kind === 'rubble') return `<path d="M ${x - s * 0.6},${y} l ${s * 0.35},-${s * 0.4} l ${s * 0.35},${s * 0.4} Z M ${x + s * 0.2},${y + 2} l ${s * 0.3},-${s * 0.3} l ${s * 0.3},${s * 0.3} Z" ${W(1)}/>`;
  if (kind === 'stone') {
    // flagstone cracks + a pebble
    return `<path d="M ${x - s * 0.5},${y} l ${s * 0.32},-${s * 0.2} l ${s * 0.34},${s * 0.16} M ${x - s * 0.1},${y + 2.5} l ${s * 0.4},-${s * 0.1}" ${W(0.9)}/><circle cx="${x + s * 0.45}" cy="${y + 1}" r="0.9" fill="${K}"/>`;
  }
  // grass tufts
  return `<path d="M ${x - 3},${y} q 0,-4 -1,-5 M ${x},${y} q 0,-5 0,-6 M ${x + 3},${y} q 0,-4 1,-5" ${W(0.9)}/>`;
}
