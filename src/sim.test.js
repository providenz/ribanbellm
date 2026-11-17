import { describe, expect, it } from 'vitest';
import { chooseStep, freeNeighbors, isWalkable, pickSpawnTiles, tileKey } from './sim.js';

// 0 = floor, 1 = block
const MAP = [
  [0, 0, 0],
  [0, 1, 0],
  [0, 0, 0],
];

// Deterministic "random": cycles through the given values
const sequence = (...values) => {
  let i = 0;
  return () => values[i++ % values.length];
};

describe('isWalkable', () => {
  it('accepts floor tiles and rejects blocks and out-of-bounds', () => {
    expect(isWalkable(MAP, 0, 0)).toBe(true);
    expect(isWalkable(MAP, 1, 1)).toBe(false);
    expect(isWalkable(MAP, -1, 0)).toBe(false);
    expect(isWalkable(MAP, 3, 0)).toBe(false);
  });
});

describe('freeNeighbors', () => {
  it('returns the walkable, unoccupied 4-neighbours', () => {
    const occupied = new Set([tileKey(2, 1)]);
    // (2,0): left (1,0) ok, down (2,1) occupied, right/up out of bounds
    expect(freeNeighbors(MAP, occupied, 2, 0)).toEqual([{ col: 1, row: 0 }]);
  });

  it('never returns a block', () => {
    const neighbors = freeNeighbors(MAP, new Set(), 1, 0);
    expect(neighbors).not.toContainEqual({ col: 1, row: 1 });
    expect(neighbors).toHaveLength(2);
  });
});

describe('chooseStep', () => {
  it('picks one of the free neighbours using rng', () => {
    const step = chooseStep(MAP, new Set(), 0, 0, sequence(0.99));
    expect([{ col: 1, row: 0 }, { col: 0, row: 1 }]).toContainEqual(step);
  });

  it('returns null when boxed in', () => {
    const occupied = new Set([tileKey(1, 0), tileKey(0, 1)]);
    expect(chooseStep(MAP, occupied, 0, 0, Math.random)).toBeNull();
  });
});

describe('pickSpawnTiles', () => {
  it('returns distinct free floor tiles', () => {
    const occupied = new Set([tileKey(0, 0)]);
    const tiles = pickSpawnTiles(MAP, occupied, 7, Math.random);

    expect(tiles).toHaveLength(7); // 9 tiles - 1 block - 1 occupied
    const keys = tiles.map((t) => tileKey(t.col, t.row));
    expect(new Set(keys).size).toBe(7);
    expect(keys).not.toContain(tileKey(0, 0));
    expect(keys).not.toContain(tileKey(1, 1));
  });

  it('returns fewer tiles when the map is full', () => {
    expect(pickSpawnTiles(MAP, new Set(), 20, Math.random)).toHaveLength(8);
  });
});
