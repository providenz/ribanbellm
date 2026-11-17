import { describe, expect, it } from 'vitest';
import {
  candidatePairs, chooseStep, findMeeting, findPath, freeNeighbors, isWalkable, lineDuration, pairKey,
  pickMeetingSpot, pickSpawnTiles, pickSplitTargets, tileKey,
} from './sim.js';

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

describe('findMeeting', () => {
  const rules = { maxConcurrent: 1, globalGapMs: 20000 };
  const state = (over = {}) => ({ now: 100000, inFlight: 0, lastEndedAt: -Infinity, pairCooldownUntil: new Map(), ...over });
  const w = (id, col, row, s = 'idle') => ({ id, col, row, state: s });

  it('pairs two idle neighbours', () => {
    const [a, b] = findMeeting([w(1, 0, 0), w(2, 5, 5), w(3, 0, 1)], state(), rules);
    expect([a.id, b.id]).toEqual([1, 3]);
  });

  it('ignores diagonal or distant characters', () => {
    expect(findMeeting([w(1, 0, 0), w(2, 1, 1), w(3, 4, 4)], state(), rules)).toBeNull();
  });

  it('ignores characters that are moving or talking', () => {
    expect(findMeeting([w(1, 0, 0, 'moving'), w(2, 0, 1)], state(), rules)).toBeNull();
    expect(findMeeting([w(1, 0, 0), w(2, 0, 1, 'talking')], state(), rules)).toBeNull();
  });

  it('respects the concurrency limit and the global gap', () => {
    const pair = [w(1, 0, 0), w(2, 0, 1)];
    expect(findMeeting(pair, state({ inFlight: 1 }), rules)).toBeNull();
    expect(findMeeting(pair, state({ lastEndedAt: 90000 }), rules)).toBeNull();
    expect(findMeeting(pair, state({ lastEndedAt: 80000 }), rules)).not.toBeNull();
  });

  it('respects the pair cooldown in both orders', () => {
    const cooldown = new Map([[pairKey(2, 1), 150000]]);
    expect(findMeeting([w(1, 0, 0), w(2, 0, 1)], state({ pairCooldownUntil: cooldown }), rules)).toBeNull();
    expect(findMeeting([w(1, 0, 0), w(2, 0, 1)], state({ now: 150000, pairCooldownUntil: cooldown }), rules)).not.toBeNull();
  });
});

describe('lineDuration', () => {
  it('grows with the text length', () => {
    expect(lineDuration('')).toBe(1500);
    expect(lineDuration('abcd')).toBe(1700);
  });
});

const t = (col, row) => ({ col, row });
const open = (n) => Array.from({ length: n }, () => Array(n).fill(0));
const steps = (a, b) => Math.abs(a.col - b.col) + Math.abs(a.row - b.row);
const seq = (...values) => { let i = 0; return () => values[i++ % values.length]; };

describe('candidatePairs', () => {
  const rules = { maxConcurrent: 1, globalGapMs: 20000 };
  const state = (over = {}) => ({ now: 100000, inFlight: 0, lastEndedAt: -Infinity, pairCooldownUntil: new Map(), ...over });
  const w = (id, s = 'idle') => ({ id, col: id, row: 0, state: s });
  const ids = (pairs) => pairs.map(([a, b]) => pairKey(a.id, b.id)).sort();

  it('pairs idle and moving walkers, wherever they are', () => {
    expect(ids(candidatePairs([w(1), w(2, 'moving'), w(3, 'talking')], state(), rules, Math.random))).toEqual(['1-2']);
  });

  it('skips walkers busy with a meeting', () => {
    const busy = ['approaching', 'talking', 'leaving'].map((s, i) => w(i + 3, s));
    expect(candidatePairs([w(1), ...busy], state(), rules, Math.random)).toEqual([]);
  });

  it('returns nothing while a conversation is in flight or the gap has not passed', () => {
    const walkers = [w(1), w(2)];
    expect(candidatePairs(walkers, state({ inFlight: 1 }), rules, Math.random)).toEqual([]);
    expect(candidatePairs(walkers, state({ lastEndedAt: 90000 }), rules, Math.random)).toEqual([]);
    expect(candidatePairs(walkers, state({ lastEndedAt: 80000 }), rules, Math.random)).toHaveLength(1);
  });

  it('excludes pairs on cooldown in either id order', () => {
    const cooldown = new Map([[pairKey(2, 1), 150000]]);
    expect(ids(candidatePairs([w(1), w(2), w(3)], state({ pairCooldownUntil: cooldown }), rules, Math.random))).toEqual(['1-3', '2-3']);
  });
});

describe('findPath', () => {
  it('walks around a block', () => {
    const map = [[0, 1, 0], [0, 0, 0]];
    const path = findPath(map, new Set(), t(0, 0), t(2, 0));
    expect(path).toHaveLength(4);
    expect(path.at(-1)).toEqual(t(2, 0));
    expect(path.some((p) => p.col === 1 && p.row === 0)).toBe(false);
    path.reduce((prev, p) => (expect(steps(prev, p)).toBe(1), p), t(0, 0));
  });

  it('returns null when boxed in by another character', () => {
    expect(findPath([[0, 0, 0]], new Set([tileKey(1, 0)]), t(0, 0), t(2, 0))).toBeNull();
  });

  it('returns null when the target is a block or taken', () => {
    expect(findPath([[0, 1]], new Set(), t(0, 0), t(1, 0))).toBeNull();
    expect(findPath([[0, 0]], new Set([tileKey(1, 0)]), t(0, 0), t(1, 0))).toBeNull();
  });

  it('returns an empty path when already there', () => {
    expect(findPath(open(3), new Set(), t(1, 1), t(1, 1))).toEqual([]);
  });
});

describe('pickMeetingSpot', () => {
  it('picks two adjacent free tiles near the middle', () => {
    const spot = pickMeetingSpot(open(5), new Set(), t(0, 0), t(4, 4));
    expect(steps(spot.a, spot.b)).toBe(1);
    expect(steps(spot.a, t(2, 2))).toBeLessThanOrEqual(1);
    expect(steps(spot.b, t(2, 2))).toBeLessThanOrEqual(1);
  });

  it('sends each character to the closer tile of the spot', () => {
    const spot = pickMeetingSpot(open(5), new Set(), t(0, 0), t(4, 4));
    expect(steps(t(0, 0), spot.a)).toBeLessThanOrEqual(steps(t(0, 0), spot.b));
  });

  it('works when the two are already neighbours', () => {
    const spot = pickMeetingSpot(open(3), new Set(), t(0, 0), t(1, 0));
    expect(steps(spot.a, spot.b)).toBe(1);
  });

  it('returns null when one of them cannot get out', () => {
    // b at (4,4) is walled in by blocks
    const map = open(5);
    map[3][4] = 1;
    map[4][3] = 1;
    expect(pickMeetingSpot(map, new Set(), t(0, 0), t(4, 4))).toBeNull();
  });
});

describe('pickSplitTargets', () => {
  it('sends both away from each other, 3 to 5 steps, to distinct free tiles', () => {
    const map = open(10);
    const blocked = new Set([tileKey(5, 2)]);
    const a = t(4, 4);
    const b = t(5, 4);
    for (let i = 0; i < 20; i++) {
      const targets = pickSplitTargets(map, blocked, a, b, Math.random);
      for (const [me, partner, target] of [[a, b, targets.a], [b, a, targets.b]]) {
        expect(steps(me, target)).toBeGreaterThanOrEqual(3);
        expect(steps(me, target)).toBeLessThanOrEqual(5);
        expect(steps(partner, target)).toBeGreaterThan(steps(partner, me));
        expect(blocked.has(tileKey(target.col, target.row))).toBe(false);
      }
      expect(targets.a).not.toEqual(targets.b);
    }
  });

  it('gives null when there is no room', () => {
    const targets = pickSplitTargets([[0, 0]], new Set(), t(0, 0), t(1, 0), seq(0.5));
    expect(targets).toEqual({ a: null, b: null });
  });
});
