import { BLOCK_H, TILE_H, TILE_W } from './map.js';

export const CHAR_W = 32;
export const CHAR_H = 46;

export function makeTileTextures(scene) {
  const hw = TILE_W / 2;
  const hh = TILE_H / 2;
  const diamond = (g, color, stroke) => {
    const pts = [
      { x: hw, y: 0 },
      { x: TILE_W, y: hh },
      { x: hw, y: TILE_H },
      { x: 0, y: hh },
    ];
    g.fillStyle(color).fillPoints(pts, true);
    if (stroke !== undefined) g.lineStyle(1, stroke).strokePoints(pts, true);
  };

  const g = scene.make.graphics({}, false);

  diamond(g, 0x4f7a4a, 0x3d5f39);
  g.generateTexture('floorA', TILE_W, TILE_H);
  g.clear();
  diamond(g, 0x5a8a54, 0x3d5f39);
  g.generateTexture('floorB', TILE_W, TILE_H);
  g.clear();

  // Raised block: top face + left and right side faces
  diamond(g, 0xa8a29a);
  g.fillStyle(0x7d7770).fillPoints([
    { x: 0, y: hh }, { x: hw, y: TILE_H }, { x: hw, y: TILE_H + BLOCK_H }, { x: 0, y: hh + BLOCK_H },
  ], true);
  g.fillStyle(0x625d57).fillPoints([
    { x: TILE_W, y: hh }, { x: hw, y: TILE_H }, { x: hw, y: TILE_H + BLOCK_H }, { x: TILE_W, y: hh + BLOCK_H },
  ], true);
  g.generateTexture('block', TILE_W, TILE_H + BLOCK_H);
  g.clear();

  g.lineStyle(2, 0xffe36e).strokePoints([
    { x: hw, y: 1 }, { x: TILE_W - 1, y: hh }, { x: hw, y: TILE_H - 1 }, { x: 1, y: hh },
  ], true);
  g.generateTexture('hover', TILE_W, TILE_H);

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
