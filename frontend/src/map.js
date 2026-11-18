export const TILE_W = 64; // diamond width
export const TILE_H = 32; // diamond height (2:1 isometric)
export const EDGE_H = 18; // height of the island's earth side faces

// What each layout character stands for. `ground` is the floor drawn under it, `object` what stands on it.
export const SYMBOLS = {
  '.': { walkable: true, ground: 'grass' },
  ',': { walkable: true, ground: 'flowers' },
  ':': { walkable: true, ground: 'path' },
  s: { walkable: true, ground: 'sand' },
  '~': { walkable: false, ground: 'water' },
  T: { walkable: false, ground: 'grass', object: 'tree' },
  b: { walkable: false, ground: 'grass', object: 'bush' },
  r: { walkable: false, ground: 'grass', object: 'rock' },
  H: { walkable: false, ground: 'grass', object: 'house' },
  w: { walkable: false, ground: 'path', object: 'well' },
  n: { walkable: false, ground: 'path', object: 'bench' },
  l: { walkable: false, ground: 'path', object: 'lamp' },
};

// The village, one character per tile (row by row, columns left to right)
export const LAYOUT = [
  'TTT...,.....b.TTTT',
  'T.H...:..,....H.TT',
  'T.....:........:.T',
  '..,...:...b....:..',
  'b.....:..H.....:..',
  '......::::::::::::',
  '.,....:...,.....r.',
  '......l:::::l.....',
  '::::::::::w:::::..',
  '......:::::::.....',
  '..H...:.n...n.:...',
  '......:.......:...',
  '..b...:..,..ss:ss.',
  'T.....:....ss~~~ss',
  'TT....:,...s~~~~s.',
  'TTr...:....ss~~ss.',
  'TTT.H.:..,...ssss,',
  'TTTT..:.....b..TTT',
];

// 0 = walkable, 1 = blocked (what sim.js works with)
export const MAP = LAYOUT.map((line) => [...line].map((symbol) => (SYMBOLS[symbol].walkable ? 0 : 1)));

export const symbolAt = (col, row) => SYMBOLS[LAYOUT[row]?.[col]];

// A stable pseudo-random pick in [0, n) per tile, so the village looks the same on every load
export function tileVariant(col, row, n) {
  let h = (col * 374761393 + row * 668265263) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  return ((h ^ (h >>> 16)) >>> 0) % n;
}

// Grid (col, row) -> screen position of the tile's top-center point. Accepts fractional coordinates.
export function gridToScreen(col, row) {
  return { x: (col - row) * (TILE_W / 2), y: (col + row) * (TILE_H / 2) };
}

// Screen position -> grid (col, row), inverse of gridToScreen
export function screenToGrid(x, y) {
  const col = Math.floor(x / TILE_W + y / TILE_H);
  const row = Math.floor(y / TILE_H - x / TILE_W);
  return { col, row };
}
