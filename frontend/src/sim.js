// Pure simulation helpers (no Phaser), unit-tested in sim.test.js.
// `occupied` is a Set of tileKey() strings for tiles held by a character.

const DIRECTIONS = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
];

export const tileKey = (col, row) => `${col},${row}`;

export function isWalkable(map, col, row) {
  return map[row]?.[col] === 0;
}

export function freeNeighbors(map, occupied, col, row) {
  return DIRECTIONS.map(([dc, dr]) => ({ col: col + dc, row: row + dr })).filter(
    (t) => isWalkable(map, t.col, t.row) && !occupied.has(tileKey(t.col, t.row)),
  );
}

export function chooseStep(map, occupied, col, row, rng) {
  const options = freeNeighbors(map, occupied, col, row);
  return options.length ? options[Math.floor(rng() * options.length)] : null;
}

export function pickSpawnTiles(map, occupied, count, rng) {
  const free = [];
  map.forEach((cells, row) =>
    cells.forEach((_, col) => {
      if (isWalkable(map, col, row) && !occupied.has(tileKey(col, row))) free.push({ col, row });
    }),
  );
  // Fisher-Yates shuffle, then take the first `count`
  for (let i = free.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [free[i], free[j]] = [free[j], free[i]];
  }
  return free.slice(0, count);
}

export const pairKey = (a, b) => (a < b ? `${a}-${b}` : `${b}-${a}`);

// How long a speech line stays on screen
export const lineDuration = (text) => 1500 + 50 * text.length;

// --- Choreographed meetings ---

const steps = (a, b) => Math.abs(a.col - b.col) + Math.abs(a.row - b.row);

function shuffle(items, rng) {
  for (let i = items.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [items[i], items[j]] = [items[j], items[i]];
  }
  return items;
}

// Every pair of available walkers ({ id, state }) allowed to meet now, in random order.
export function candidatePairs(walkers, { now, inFlight, lastEndedAt, pairCooldownUntil }, { maxConcurrent, globalGapMs }, rng) {
  if (inFlight >= maxConcurrent || now - lastEndedAt < globalGapMs) return [];
  const free = walkers.filter((w) => w.state === 'idle' || w.state === 'moving');
  const pairs = [];
  for (let i = 0; i < free.length; i++) {
    for (let j = i + 1; j < free.length; j++) {
      const cooldown = pairCooldownUntil.get(pairKey(free[i].id, free[j].id)) ?? -Infinity;
      if (cooldown <= now) pairs.push([free[i], free[j]]);
    }
  }
  return shuffle(pairs, rng);
}

const isFree = (map, blocked, { col, row }) => isWalkable(map, col, row) && !blocked.has(tileKey(col, row));

// Shortest 4-neighbour path from `from` to `to` (excluding `from`, including `to`), or null.
export function findPath(map, blocked, from, to) {
  if (!isFree(map, blocked, to)) return null;
  if (from.col === to.col && from.row === to.row) return [];
  const cameFrom = new Map([[tileKey(from.col, from.row), null]]);
  const queue = [from];
  while (queue.length) {
    const current = queue.shift();
    for (const [dc, dr] of DIRECTIONS) {
      const next = { col: current.col + dc, row: current.row + dr };
      const key = tileKey(next.col, next.row);
      if (cameFrom.has(key) || !isFree(map, blocked, next)) continue;
      cameFrom.set(key, current);
      if (next.col === to.col && next.row === to.row) {
        const path = [];
        for (let tile = next; tile !== from; tile = cameFrom.get(tileKey(tile.col, tile.row))) path.unshift(tile);
        return path;
      }
      queue.push(next);
    }
  }
  return null;
}

// Two adjacent free tiles near the midpoint of `a` and `b`, each reachable by its character.
// `blocked` must not contain a's and b's own tiles.
export function pickMeetingSpot(map, blocked, a, b) {
  const mid = { col: (a.col + b.col) / 2, row: (a.row + b.row) / 2 };
  const spots = [];
  map.forEach((cells, row) =>
    cells.forEach((_, col) => {
      const tile = { col, row };
      if (!isFree(map, blocked, tile)) return;
      for (const next of [{ col: col + 1, row }, { col, row: row + 1 }]) {
        if (isFree(map, blocked, next)) spots.push([tile, next]);
      }
    }),
  );
  spots.sort(([p, q], [r, s]) => steps(p, mid) + steps(q, mid) - (steps(r, mid) + steps(s, mid)));
  for (const [p, q] of spots) {
    const [forA, forB] = steps(a, p) + steps(b, q) <= steps(a, q) + steps(b, p) ? [p, q] : [q, p];
    if (findPath(map, blocked, a, forA) && findPath(map, blocked, b, forB)) return { a: forA, b: forB };
  }
  return null;
}

// After a chat: for each character, a reachable free tile 3 to 5 steps away, farther from the partner.
export function pickSplitTargets(map, blocked, a, b, rng) {
  const pick = (me, partner, taken) => {
    const around = new Set([...blocked, tileKey(partner.col, partner.row), ...taken]);
    const options = [];
    map.forEach((cells, row) =>
      cells.forEach((_, col) => {
        const tile = { col, row };
        const distance = steps(me, tile);
        if (distance < 3 || distance > 5 || steps(partner, tile) <= steps(partner, me)) return;
        if (findPath(map, around, me, tile)) options.push(tile);
      }),
    );
    return options.length ? options[Math.floor(rng() * options.length)] : null;
  };
  const targetA = pick(a, b, []);
  const targetB = pick(b, a, targetA ? [tileKey(targetA.col, targetA.row)] : []);
  return { a: targetA, b: targetB };
}

// Tiles a walker must avoid: everyone's tiles plus reserved meeting tiles, except its own tile and
// its own destination.
export function blockedFor(occupied, reserved, own = null, dest = null) {
  const blocked = new Set([...occupied, ...reserved]);
  if (own) blocked.delete(tileKey(own.col, own.row));
  if (dest) blocked.delete(tileKey(dest.col, dest.row));
  return blocked;
}
