export const TILE_W = 64; // diamond width
export const TILE_H = 32; // diamond height (2:1 isometric)
export const BLOCK_H = 24; // height of a raised block's side faces

// 0 = floor, 1 = raised block
export const MAP = [
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0],
  [0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0],
  [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0],
  [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0],
  [0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
  [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0],
  [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
];

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
