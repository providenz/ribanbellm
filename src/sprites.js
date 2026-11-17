import { EDGE_H, TILE_H, TILE_W } from './map.js';

export const CHAR_W = 32;
export const CHAR_H = 46;

// Small seeded generator, so textures come out the same on every load
function seeded(seed) {
  return () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
}

const HW = TILE_W / 2;
const HH = TILE_H / 2;
const DIAMOND = [
  { x: HW, y: 0 }, { x: TILE_W, y: HH }, { x: HW, y: TILE_H }, { x: 0, y: HH },
];

// A random point well inside the tile diamond
function insideDiamond(rand, margin = 0.75) {
  for (;;) {
    const x = rand() * TILE_W;
    const y = rand() * TILE_H;
    if (Math.abs(x - HW) / HW + Math.abs(y - HH) / HH < margin) return { x, y };
  }
}

function groundTile(g, base, stroke, speckles, rand) {
  g.fillStyle(base).fillPoints(DIAMOND, true);
  g.lineStyle(1, stroke, 0.6).strokePoints(DIAMOND, true);
  for (const [color, count, size] of speckles) {
    for (let i = 0; i < count; i++) {
      const { x, y } = insideDiamond(rand);
      g.fillStyle(color).fillRect(x, y, size, size);
    }
  }
}

function grassTufts(g, color, count, rand) {
  g.lineStyle(1, color);
  for (let i = 0; i < count; i++) {
    const { x, y } = insideDiamond(rand);
    g.lineBetween(x, y, x - 1, y - 3).lineBetween(x, y, x + 1.5, y - 3);
  }
}

// Ground tiles: grass0-2, flowers0-1, path0-1, sand, water, island edges, hover outline
export function makeGroundTextures(scene) {
  const g = scene.make.graphics({}, false);
  const rand = seeded(7);
  const save = (key, h = TILE_H) => {
    g.generateTexture(key, TILE_W, h);
    g.clear();
  };

  [0x5d9a4f, 0x66a356, 0x579349].forEach((base, i) => {
    groundTile(g, base, 0x467a3c, [[0x78b866, 10, 2]], rand);
    grassTufts(g, 0x3f7335, 5, rand);
    save(`grass${i}`);
  });
  [[0xf2f0e6, 0xf5d547], [0xe86a8a, 0xb38be8]].forEach((petals, i) => {
    groundTile(g, 0x62a053, 0x467a3c, [[0x78b866, 8, 2]], rand);
    for (let k = 0; k < 7; k++) {
      const { x, y } = insideDiamond(rand, 0.65);
      g.fillStyle(petals[k % 2]).fillCircle(x, y, 2);
      g.fillStyle(0xffe36e).fillRect(x - 0.5, y - 0.5, 1, 1);
    }
    save(`flowers${i}`);
  });
  [0, 1].forEach((i) => {
    groundTile(g, 0xc9a46c, 0xa8854f, [[0xb08e5a, 9, 2], [0xe0c48e, 6, 2], [0x8f7650, 3, 3]], rand);
    save(`path${i}`);
  });
  groundTile(g, 0xe8d6a0, 0xcdb97f, [[0xd4c088, 12, 1], [0xf6e9c2, 8, 1]], rand);
  save('sand');

  g.fillStyle(0x3f86b8).fillPoints(DIAMOND, true);
  g.fillStyle(0x5aa2d0).fillPoints(DIAMOND.map((p) => ({ x: HW + (p.x - HW) * 0.7, y: HH + (p.y - HH) * 0.7 })), true);
  g.lineStyle(1, 0xbfe3f5, 0.8).lineBetween(20, 15, 30, 15).lineBetween(36, 20, 44, 20);
  save('water');

  // Earth faces under the island's front edges: soil with a darker band of rock below
  const face = (points) => {
    g.fillStyle(0x7a5536).fillPoints(points, true);
  };
  face([{ x: 0, y: HH }, { x: HW, y: TILE_H }, { x: HW, y: TILE_H + EDGE_H }, { x: 0, y: HH + EDGE_H }]);
  g.fillStyle(0x5f4129).fillPoints([{ x: 0, y: HH + 10 }, { x: HW, y: TILE_H + 10 }, { x: HW, y: TILE_H + EDGE_H }, { x: 0, y: HH + EDGE_H }], true);
  save('edgeLeft', TILE_H + EDGE_H);
  face([{ x: TILE_W, y: HH }, { x: HW, y: TILE_H }, { x: HW, y: TILE_H + EDGE_H }, { x: TILE_W, y: HH + EDGE_H }]);
  g.fillStyle(0x4c3420).fillPoints([{ x: TILE_W, y: HH + 10 }, { x: HW, y: TILE_H + 10 }, { x: HW, y: TILE_H + EDGE_H }, { x: TILE_W, y: HH + EDGE_H }], true);
  save('edgeRight', TILE_H + EDGE_H);

  g.lineStyle(2, 0xffe36e).strokePoints([
    { x: HW, y: 1 }, { x: TILE_W - 1, y: HH }, { x: HW, y: TILE_H - 1 }, { x: 1, y: HH },
  ], true);
  save('hover');
  g.destroy();
}

// Objects are drawn with their foot at (HW, h - HH): placed with origin (0.5, 1) at the tile's
// bottom point, the foot lands on the tile's center.
const OBJECTS = {
  tree0: [72, (g, fy) => leafyTree(g, fy, [0x3f7d3a, 0x4f9545, 0x68ad58])],
  tree1: [72, (g, fy) => leafyTree(g, fy, [0x5e7d2e, 0x76963a, 0x93b04e], [0xe8584a, 4])],
  pine: [76, (g, fy) => {
    shadow(g, fy, 30);
    g.fillStyle(0x6b4a2f).fillRect(HW - 3, fy - 12, 6, 12);
    [[0x2f6b46, 0], [0x3a7d52, 14], [0x4a9262, 26]].forEach(([color, up], i) => {
      const half = 20 - i * 4;
      g.fillStyle(color).fillTriangle(HW - half, fy - 10 - up, HW + half, fy - 10 - up, HW, fy - 34 - up);
    });
  }],
  bush: [44, (g, fy) => {
    shadow(g, fy, 30);
    g.fillStyle(0x3f7d3a).fillCircle(HW - 8, fy - 6, 9).fillCircle(HW + 8, fy - 6, 9);
    g.fillStyle(0x55994a).fillCircle(HW, fy - 11, 11);
    g.fillStyle(0x76b664).fillCircle(HW - 3, fy - 15, 4);
    g.fillStyle(0xd94f6a).fillCircle(HW + 6, fy - 8, 2).fillCircle(HW - 7, fy - 4, 2);
  }],
  rock: [40, (g, fy) => {
    shadow(g, fy, 30);
    g.fillStyle(0x8a8f96).fillPoints([
      { x: HW - 16, y: fy }, { x: HW - 12, y: fy - 12 }, { x: HW - 2, y: fy - 18 },
      { x: HW + 12, y: fy - 13 }, { x: HW + 16, y: fy }, { x: HW, y: fy + 4 },
    ], true);
    g.fillStyle(0xb0b5bb).fillPoints([
      { x: HW - 12, y: fy - 12 }, { x: HW - 2, y: fy - 18 }, { x: HW + 12, y: fy - 13 }, { x: HW, y: fy - 8 },
    ], true);
    g.fillStyle(0x6f9a4a).fillEllipse(HW - 9, fy - 2, 7, 3);
  }],
  house0: [84, (g, fy) => house(g, fy, 0xb5523b, 0x8f3e2c)],
  house1: [84, (g, fy) => house(g, fy, 0x4f6fa8, 0x3c5788)],
  house2: [84, (g, fy) => house(g, fy, 0x7f9a46, 0x637a35)],
  well: [70, (g, fy) => {
    shadow(g, fy, 34);
    g.fillStyle(0x8f8a84).fillRect(HW - 14, fy - 14, 28, 14).fillEllipse(HW, fy, 28, 10);
    g.fillStyle(0xa8a39c).fillEllipse(HW, fy - 14, 28, 10);
    g.fillStyle(0x2c4f6b).fillEllipse(HW, fy - 14, 20, 6);
    g.fillStyle(0x6b4a2f).fillRect(HW - 13, fy - 40, 3, 26).fillRect(HW + 10, fy - 40, 3, 26);
    g.lineStyle(1, 0x3a2a1a).lineBetween(HW, fy - 38, HW, fy - 20);
    g.fillStyle(0x8a5a3a).fillRect(HW - 3, fy - 22, 6, 5);
    g.fillStyle(0xa8483a).fillTriangle(HW - 19, fy - 38, HW + 19, fy - 38, HW, fy - 54);
  }],
  bench: [40, (g, fy) => {
    shadow(g, fy, 34);
    // Along the tile's left-to-right axis, seen from the front
    g.fillStyle(0x5a3d26).fillRect(HW - 13, fy - 6, 2, 8).fillRect(HW + 11, fy - 6, 2, 8);
    g.fillStyle(0x9a6b42).fillPoints([
      { x: HW - 16, y: fy - 7 }, { x: HW + 16, y: fy - 7 }, { x: HW + 14, y: fy - 3 }, { x: HW - 18, y: fy - 3 },
    ], true);
    g.fillStyle(0x84593a).fillRect(HW - 16, fy - 18, 32, 4).fillRect(HW - 16, fy - 13, 32, 3);
    g.fillStyle(0x5a3d26).fillRect(HW - 15, fy - 18, 2, 12).fillRect(HW + 13, fy - 18, 2, 12);
  }],
  lamp: [76, (g, fy) => {
    shadow(g, fy, 16);
    g.fillStyle(0xffe9a0, 0.18).fillCircle(HW, fy - 50, 16);
    g.fillStyle(0x2f3136).fillRect(HW - 4, fy - 4, 8, 4).fillRect(HW - 1.5, fy - 44, 3, 42);
    g.fillStyle(0x2f3136).fillRect(HW - 6, fy - 58, 12, 3).fillRect(HW - 5, fy - 45, 10, 2);
    g.fillStyle(0xffe08a).fillRect(HW - 4, fy - 55, 8, 10);
    g.fillStyle(0x2f3136).fillTriangle(HW - 7, fy - 58, HW + 7, fy - 58, HW, fy - 64);
  }],
};

function shadow(g, fy, width) {
  g.fillStyle(0x000000, 0.22).fillEllipse(HW, fy + 1, width, width * 0.4);
}

function leafyTree(g, fy, [dark, mid, light], fruit) {
  shadow(g, fy, 40);
  g.fillStyle(0x6b4a2f).fillRect(HW - 3, fy - 20, 6, 20);
  g.fillStyle(dark).fillCircle(HW - 11, fy - 30, 13).fillCircle(HW + 11, fy - 30, 13);
  g.fillStyle(mid).fillCircle(HW, fy - 38, 16);
  g.fillStyle(light).fillCircle(HW - 5, fy - 44, 6);
  if (fruit) {
    const [color, count] = fruit;
    [[-10, -28], [8, -34], [2, -24], [-3, -40]].slice(0, count).forEach(([dx, dy]) => g.fillStyle(color).fillCircle(HW + dx, fy + dy, 2.5));
  }
}

// A small isometric house: two walls and a pyramid roof
function house(g, fy, roof, roofShade) {
  const w = 24;
  const d = w / 2;
  const wall = 26;
  const L = { x: HW - w, y: fy };
  const F = { x: HW, y: fy + d };
  const R = { x: HW + w, y: fy };
  const up = (p, h) => ({ x: p.x, y: p.y - h });
  const along = (a, b, t) => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
  g.fillStyle(0x000000, 0.22).fillPoints([{ x: L.x - 4, y: L.y }, { x: F.x, y: F.y + 4 }, { x: R.x + 4, y: R.y }, { x: HW, y: fy - d }], true);
  g.fillStyle(0xeadfc8).fillPoints([L, F, up(F, wall), up(L, wall)], true);
  g.fillStyle(0xcbbd9f).fillPoints([F, R, up(R, wall), up(F, wall)], true);
  // Door on the left wall, window on the right wall
  const d0 = along(L, F, 0.4);
  const d1 = along(L, F, 0.72);
  g.fillStyle(0x6b4a2f).fillPoints([d0, d1, up(d1, 16), up(d0, 16)], true);
  const w0 = along(F, R, 0.35);
  const w1 = along(F, R, 0.68);
  g.fillStyle(0x7fc4e8).fillPoints([up(w0, 10), up(w1, 10), up(w1, 19), up(w0, 19)], true);
  g.lineStyle(1, 0x8a7a5e).strokePoints([up(w0, 10), up(w1, 10), up(w1, 19), up(w0, 19)], true);
  // Roof overhangs the walls a little
  const apex = { x: HW, y: fy - wall - 30 };
  const rl = { x: L.x - 4, y: L.y - wall + 1 };
  const rf = { x: F.x, y: F.y - wall + 4 };
  const rr = { x: R.x + 4, y: R.y - wall + 1 };
  g.fillStyle(roof).fillTriangle(rl.x, rl.y, rf.x, rf.y, apex.x, apex.y);
  g.fillStyle(roofShade).fillTriangle(rf.x, rf.y, rr.x, rr.y, apex.x, apex.y);
  g.fillStyle(0x8a8580).fillRect(HW + 8, fy - wall - 22, 5, 10);
}

export function makeObjectTextures(scene) {
  const g = scene.make.graphics({}, false);
  for (const [key, [h, draw]] of Object.entries(OBJECTS)) {
    draw(g, h - HH);
    g.generateTexture(key, TILE_W, h);
    g.clear();
  }
  g.destroy();
}

const ACCESSORIES = {
  none() {},
  hat(g) {
    g.fillStyle(0x2b2b2b).fillRect(5, 12, 22, 3).fillRect(9, 2, 14, 11);
    g.fillStyle(0xc04040).fillRect(9, 10, 14, 2);
  },
  crown(g) {
    g.fillStyle(0xf2c94c).fillPoints([
      { x: 8, y: 14 }, { x: 8, y: 5 }, { x: 12, y: 9 }, { x: 16, y: 2 },
      { x: 20, y: 9 }, { x: 24, y: 5 }, { x: 24, y: 14 },
    ], true);
  },
  antenna(g) {
    g.lineStyle(2, 0x333333).lineBetween(16, 15, 16, 5);
    g.fillStyle(0xff5050).fillCircle(16, 5, 3);
  },
  bow(g) {
    g.fillStyle(0xff6fa8)
      .fillTriangle(22, 13, 17, 8, 17, 18)
      .fillTriangle(22, 13, 27, 8, 27, 18)
      .fillCircle(22, 13, 2);
  },
  glasses(g) {
    g.lineStyle(2, 0x222222).strokeCircle(13, 24, 5).strokeCircle(22, 24, 5).lineBetween(18, 24, 17, 24);
  },
  mustache(g) {
    g.fillStyle(0x3a2a1a).fillEllipse(13, 32, 9, 4).fillEllipse(20, 32, 9, 4);
  },
};

// A colored blob with eyes looking right (flipX makes it look left) and its accessory.
// Returns the texture key.
export function makeCharacterTexture(scene, character) {
  const key = `char-${character.id}`;
  if (scene.textures.exists(key)) return key;

  const g = scene.make.graphics({}, false);
  g.fillStyle(0x000000, 0.25).fillEllipse(16, 42, 24, 8);
  g.fillStyle(parseInt(character.color.slice(1), 16)).fillRoundedRect(4, 14, 24, 29, 11);
  g.fillStyle(0xffffff).fillCircle(13, 24, 4).fillCircle(22, 24, 4);
  g.fillStyle(0x111111).fillCircle(14.5, 24.5, 2).fillCircle(23.5, 24.5, 2);
  (ACCESSORIES[character.accessory] ?? ACCESSORIES.none)(g);
  g.generateTexture(key, CHAR_W, CHAR_H);
  g.destroy();
  return key;
}
