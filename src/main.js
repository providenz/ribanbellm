import Phaser from 'phaser';

const TILE_W = 64; // diamond width
const TILE_H = 32; // diamond height (2:1 isometric)
const BLOCK_H = 24; // height of a raised block's side faces

// 0 = floor, 1 = raised block
const MAP = [
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

// Grid (col, row) -> screen position of the tile's top-center point
function gridToScreen(col, row) {
  return { x: (col - row) * (TILE_W / 2), y: (col + row) * (TILE_H / 2) };
}

// Screen position -> grid (col, row), inverse of gridToScreen
function screenToGrid(x, y) {
  const col = Math.floor(x / TILE_W + y / TILE_H);
  const row = Math.floor(y / TILE_H - x / TILE_W);
  return { col, row };
}

class IsoScene extends Phaser.Scene {
  constructor() {
    super('iso');
  }

  create() {
    this.makeTextures();

    const rows = MAP.length;
    const cols = MAP[0].length;
    this.world = this.add.container(this.scale.width / 2, 80);

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        const { x, y } = gridToScreen(col, row);
        const key = MAP[row][col] === 1 ? 'block' : (col + row) % 2 ? 'floorA' : 'floorB';
        // Blocks are drawn raised: their top face starts BLOCK_H above the floor
        const img = this.add.image(x, key === 'block' ? y - BLOCK_H : y, key).setOrigin(0.5, 0);
        img.depth = col + row + (key === 'block' ? 0.5 : 0);
        this.world.add(img);
      }
    }

    this.hover = this.add.image(0, 0, 'hover').setOrigin(0.5, 0).setVisible(false);
    this.hover.depth = 1000;
    this.world.add(this.hover);

    this.player = { col: 0, row: 0, sprite: this.add.image(0, 0, 'player').setOrigin(0.5, 1) };
    this.world.add(this.player.sprite);
    this.placePlayer();

    this.input.on('pointermove', (p) => {
      const g = screenToGrid(p.x - this.world.x, p.y - this.world.y);
      const inside = g.col >= 0 && g.row >= 0 && g.col < cols && g.row < rows;
      this.hover.setVisible(inside);
      if (inside) {
        const { x, y } = gridToScreen(g.col, g.row);
        this.hover.setPosition(x, y);
      }
    });

    const moves = { LEFT: [-1, 0], RIGHT: [1, 0], UP: [0, -1], DOWN: [0, 1] };
    for (const [key, [dc, dr]] of Object.entries(moves)) {
      this.input.keyboard.on(`keydown-${key}`, () => this.tryMove(dc, dr));
    }

    this.add.text(12, 12, 'Arrow keys: move  |  Mouse: hover tiles', { fontFamily: 'monospace', fontSize: '14px', color: '#c8ccd8' });
  }

  tryMove(dc, dr) {
    const col = this.player.col + dc;
    const row = this.player.row + dr;
    if (MAP[row]?.[col] !== 0) return; // out of bounds or blocked
    this.player.col = col;
    this.player.row = row;
    this.placePlayer();
  }

  placePlayer() {
    const { col, row, sprite } = this.player;
    const { x, y } = gridToScreen(col, row);
    sprite.setPosition(x, y + TILE_H / 2 + 4);
    // Same depth rule as tiles, slightly above the floor and blocks of its own cell
    sprite.depth = col + row + 0.6;
    this.world.sort('depth');
  }

  makeTextures() {
    const hw = TILE_W / 2;
    const hh = TILE_H / 2;
    const diamond = (g, ox, oy, color, stroke) => {
      const pts = [
        { x: ox + hw, y: oy },
        { x: ox + TILE_W, y: oy + hh },
        { x: ox + hw, y: oy + TILE_H },
        { x: ox, y: oy + hh },
      ];
      g.fillStyle(color).fillPoints(pts, true);
      if (stroke !== undefined) g.lineStyle(1, stroke).strokePoints(pts, true);
    };

    const g = this.make.graphics({}, false);

    diamond(g, 0, 0, 0x4f7a4a, 0x3d5f39);
    g.generateTexture('floorA', TILE_W, TILE_H);
    g.clear();
    diamond(g, 0, 0, 0x5a8a54, 0x3d5f39);
    g.generateTexture('floorB', TILE_W, TILE_H);
    g.clear();

    // Raised block: top face + left and right side faces
    diamond(g, 0, 0, 0xa8a29a);
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
    g.clear();

    // Player: simple capsule-ish figure
    g.fillStyle(0x000000, 0.25).fillEllipse(12, 34, 20, 8);
    g.fillStyle(0xe0604a).fillRoundedRect(4, 8, 16, 24, 6);
    g.fillStyle(0xf2d0b0).fillCircle(12, 8, 7);
    g.generateTexture('player', 24, 38);

    g.destroy();
  }
}

new Phaser.Game({
  type: Phaser.AUTO,
  width: 960,
  height: 640,
  backgroundColor: '#1b1d26',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  scene: IsoScene,
});
