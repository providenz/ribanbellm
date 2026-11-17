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

export const isAdjacent = (a, b) => Math.abs(a.col - b.col) + Math.abs(a.row - b.row) === 1;

// First pair of idle walkers ({ id, col, row, state }) allowed to start a conversation, or null.
// `pairCooldownUntil` maps pairKey -> time before which that pair may not talk again.
export function findMeeting(walkers, { now, inFlight, lastEndedAt, pairCooldownUntil }, { maxConcurrent, globalGapMs }) {
  if (inFlight >= maxConcurrent || now - lastEndedAt < globalGapMs) return null;
  const idle = walkers.filter((w) => w.state === 'idle');
  for (let i = 0; i < idle.length; i++) {
    for (let j = i + 1; j < idle.length; j++) {
      const [a, b] = [idle[i], idle[j]];
      if (isAdjacent(a, b) && (pairCooldownUntil.get(pairKey(a.id, b.id)) ?? -Infinity) <= now) return [a, b];
    }
  }
  return null;
}

// How long a speech line stays on screen
export const lineDuration = (text) => 1500 + 50 * text.length;
