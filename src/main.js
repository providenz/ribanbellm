import Phaser from 'phaser';
import { BLOCK_H, MAP, TILE_H, gridToScreen, screenToGrid } from './map.js';
import { chooseStep, pickSpawnTiles, tileKey } from './sim.js';
import { makeCharacterTexture, makeTileTextures } from './sprites.js';

const STEP_DELAY_MS = [1000, 3000]; // idle time between two steps
const STEP_DURATION_MS = 600;
const FOOT_OFFSET = TILE_H / 2 + 4; // from a tile's top point to where a character stands

class IsoScene extends Phaser.Scene {
  constructor() {
    super('iso');
  }

  create() {
    makeTileTextures(this);
    this.world = this.add.container(this.scale.width / 2, 80);
    this.drawMap();
    this.setupHover();
    // Name labels live above the whole map so floor tiles never hide them
    this.overlay = this.add.container(this.world.x, this.world.y);

    this.cast = []; // all active characters from the API, in stable order
    this.walkers = new Map(); // character id -> walker on screen
    this.occupied = new Set(); // tileKey of tiles held by a walker

    this.status = this.add.text(12, 12, 'Chargement...', {
      fontFamily: 'monospace', fontSize: '14px', color: '#c8ccd8',
    });

    const slider = document.getElementById('population');
    const count = document.getElementById('population-count');
    slider.addEventListener('input', () => {
      count.textContent = slider.value;
      this.setPopulation(Number(slider.value));
    });
    this.loadCast(Number(slider.value));
  }

  drawMap() {
    MAP.forEach((cells, row) =>
      cells.forEach((cell, col) => {
        const { x, y } = gridToScreen(col, row);
        const key = cell === 1 ? 'block' : (col + row) % 2 ? 'floorA' : 'floorB';
        // Blocks are drawn raised: their top face starts BLOCK_H above the floor
        const img = this.add.image(x, cell === 1 ? y - BLOCK_H : y, key).setOrigin(0.5, 0);
        img.depth = col + row + (cell === 1 ? 0.5 : 0);
        this.world.add(img);
      }),
    );
  }

  setupHover() {
    this.hover = this.add.image(0, 0, 'hover').setOrigin(0.5, 0).setVisible(false);
    this.hover.depth = 1000;
    this.world.add(this.hover);
    this.input.on('pointermove', (p) => {
      const g = screenToGrid(p.x - this.world.x, p.y - this.world.y);
      const inside = MAP[g.row]?.[g.col] !== undefined;
      this.hover.setVisible(inside);
      if (inside) {
        const { x, y } = gridToScreen(g.col, g.row);
        this.hover.setPosition(x, y);
      }
    });
  }

  async loadCast(population) {
    try {
      const response = await fetch('/api/characters');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      this.cast = await response.json();
    } catch (error) {
      this.status.setText(`Backend injoignable (${error.message}).\nLancez: cd backend && uv run python manage.py runserver`);
      return;
    }
    this.status.setText('');
    this.setPopulation(population);
  }

  // Keep the first `n` characters of the cast on screen (stable order, so the same ones leave first).
  setPopulation(n) {
    const wanted = new Set(this.cast.slice(0, n).map((c) => c.id));
    for (const [id, walker] of this.walkers) if (!wanted.has(id)) this.removeWalker(walker);

    const missing = this.cast.slice(0, n).filter((c) => !this.walkers.has(c.id));
    const tiles = pickSpawnTiles(MAP, this.occupied, missing.length, Math.random);
    missing.forEach((character, i) => tiles[i] && this.addWalker(character, tiles[i]));
  }

  addWalker(character, { col, row }) {
    const sprite = this.add.image(0, 0, makeCharacterTexture(this, character)).setOrigin(0.5, 1);
    const label = this.add
      .text(0, 0, character.name, { fontFamily: 'sans-serif', fontSize: '11px', color: '#ffffff' })
      .setOrigin(0.5, 0)
      .setStroke('#1b1d26', 3);
    this.world.add(sprite);
    this.overlay.add(label);

    const walker = { character, col, row, pos: { col, row }, sprite, label, timer: null };
    this.walkers.set(character.id, walker);
    this.occupied.add(tileKey(col, row));
    this.place(walker, col + row);
    this.scheduleStep(walker);
  }

  removeWalker(walker) {
    walker.timer?.remove();
    this.tweens.killTweensOf(walker.pos);
    this.occupied.delete(tileKey(walker.col, walker.row));
    if (walker.target) this.occupied.delete(tileKey(walker.target.col, walker.target.row));
    walker.sprite.destroy();
    walker.label.destroy();
    this.walkers.delete(walker.character.id);
  }

  scheduleStep(walker) {
    walker.timer = this.time.delayedCall(Phaser.Math.Between(...STEP_DELAY_MS), () => this.step(walker));
  }

  step(walker) {
    const next = chooseStep(MAP, this.occupied, walker.col, walker.row, Math.random);
    if (!next) return this.scheduleStep(walker);

    // Hold both tiles during the move so nobody walks into us
    walker.target = next;
    this.occupied.add(tileKey(next.col, next.row));
    const goingRight = gridToScreen(next.col, next.row).x > gridToScreen(walker.col, walker.row).x;
    walker.sprite.setFlipX(!goingRight);
    // Draw at the depth of the nearer tile for the whole move, so blocks never cut through us
    const depthSum = Math.max(walker.col + walker.row, next.col + next.row);

    this.tweens.add({
      targets: walker.pos,
      col: next.col,
      row: next.row,
      duration: STEP_DURATION_MS,
      ease: 'Sine.easeInOut',
      onUpdate: () => this.place(walker, depthSum),
      onComplete: () => {
        this.occupied.delete(tileKey(walker.col, walker.row));
        walker.col = next.col;
        walker.row = next.row;
        walker.target = null;
        this.place(walker, next.col + next.row);
        this.scheduleStep(walker);
      },
    });
  }

  place(walker, depthSum) {
    const { x, y } = gridToScreen(walker.pos.col, walker.pos.row);
    walker.sprite.setPosition(x, y + FOOT_OFFSET);
    walker.label.setPosition(x, y + FOOT_OFFSET + 1);
    // Same depth rule as tiles, slightly above the floor and blocks of its own cell
    walker.sprite.depth = depthSum + 0.6;
    this.world.sort('depth');
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
