import { describe, expect, it } from 'vitest';
import { LAYOUT, MAP, SYMBOLS, tileVariant } from './map.js';
import { findPath, isWalkable } from './sim.js';

const walkable = [];
MAP.forEach((cells, row) => cells.forEach((_, col) => isWalkable(MAP, col, row) && walkable.push({ col, row })));

describe('village layout', () => {
  it('is square and uses only known symbols', () => {
    expect(LAYOUT.length).toBe(18);
    for (const line of LAYOUT) {
      expect(line.length).toBe(LAYOUT.length);
      for (const symbol of line) expect(SYMBOLS).toHaveProperty(symbol);
    }
  });

  it('derives walkability from the symbols', () => {
    LAYOUT.forEach((line, row) =>
      [...line].forEach((symbol, col) => expect(MAP[row][col]).toBe(SYMBOLS[symbol].walkable ? 0 : 1)),
    );
    expect(SYMBOLS['~'].walkable).toBe(false); // water
    expect(SYMBOLS[':'].walkable).toBe(true); // path
  });

  it('has room for the whole cast', () => {
    expect(walkable.length).toBeGreaterThan(150);
  });

  it('lets every walkable tile reach every other', () => {
    const start = walkable[0];
    const unreachable = walkable.filter((tile) => !findPath(MAP, new Set(), start, tile));
    expect(unreachable).toEqual([]);
  });
});

describe('tileVariant', () => {
  it('is stable and in range', () => {
    expect(tileVariant(3, 7, 4)).toBe(tileVariant(3, 7, 4));
    const seen = new Set(walkable.map(({ col, row }) => tileVariant(col, row, 3)));
    expect([...seen].every((v) => v >= 0 && v < 3)).toBe(true);
    expect(seen.size).toBe(3);
  });
});
