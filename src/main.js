import Phaser from 'phaser';
import { BLOCK_H, MAP, TILE_H, gridToScreen, screenToGrid } from './map.js';
import {
  candidatePairs, chooseStep, findPath, lineDuration, pairKey, pickMeetingSpot, pickSpawnTiles, pickSplitTargets, tileKey,
} from './sim.js';
import { CHAR_H, makeCharacterTexture, makeTileTextures } from './sprites.js';
import { readEvents } from './stream.js';

const STEP_DELAY_MS = [1000, 3000]; // idle time between two steps
const STEP_DURATION_MS = 600;
const FOOT_OFFSET = TILE_H / 2 + 4; // from a tile's top point to where a character stands
const MEETING = { maxConcurrent: 1, globalGapMs: 20000, pairCooldownMs: 60000 };
const MEETING_CHECK_MS = 250;
const PATH_RETRIES = 3; // a walker whose way is blocked waits and retries this many times
const PATH_RETRY_MS = 500;
const EMOJI = { neutral: '', happy: '😄', annoyed: '😤', sad: '😢', surprised: '😮', smug: '😏', scared: '😱' };

// Walker states: idle (waiting between steps), moving (wandering step), approaching (walking to a
// meeting), talking, leaving (walking away after a meeting).

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
    this.inFlight = 0; // conversations in progress
    this.lastEndedAt = -Infinity;
    this.pairCooldownUntil = new Map(); // pairKey -> scene time
    // Phaser freezes timers and tweens while the tab is hidden, so the world pauses with it
    this.time.addEvent({ delay: MEETING_CHECK_MS, loop: true, callback: () => this.checkMeetings() });

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

    const walker = {
      id: character.id, character, col, row, pos: { col, row }, sprite, label,
      timer: null, state: 'idle', target: null, moving: null, onRemoved: null, conversation: null,
    };
    this.walkers.set(character.id, walker);
    this.occupied.add(tileKey(col, row));
    this.place(walker, col + row);
    this.scheduleStep(walker);
  }

  removeWalker(walker) {
    const convo = walker.conversation;
    if (convo) {
      convo.cancelled = true;
      convo.abort.abort();
      this.clearBubbles(convo);
      convo.wake?.();
    }
    walker.timer?.remove();
    this.tweens.killTweensOf(walker.pos);
    this.occupied.delete(tileKey(walker.col, walker.row));
    if (walker.target) this.occupied.delete(tileKey(walker.target.col, walker.target.row));
    walker.sprite.destroy();
    walker.label.destroy();
    this.walkers.delete(walker.character.id);
    walker.onRemoved?.(); // unblock anything waiting for its current step
  }

  isPresent(walker) {
    return this.walkers.get(walker.id) === walker;
  }

  scheduleStep(walker) {
    walker.timer = this.time.delayedCall(Phaser.Math.Between(...STEP_DELAY_MS), () => this.wander(walker));
  }

  async wander(walker) {
    const next = chooseStep(MAP, this.occupied, walker.col, walker.row, Math.random);
    if (!next) return this.scheduleStep(walker);
    walker.state = 'moving';
    await this.moveStep(walker, next);
    // A meeting may have claimed this walker during the step
    if (walker.state === 'moving' && this.isPresent(walker)) {
      walker.state = 'idle';
      this.scheduleStep(walker);
    }
  }

  // Move one tile; resolves when the step is done (or the walker is removed).
  moveStep(walker, next) {
    // Hold both tiles during the move so nobody walks into us
    walker.target = next;
    this.occupied.add(tileKey(next.col, next.row));
    const goingRight = gridToScreen(next.col, next.row).x > gridToScreen(walker.col, walker.row).x;
    walker.sprite.setFlipX(!goingRight);
    // Draw at the depth of the nearer tile for the whole move, so blocks never cut through us
    const depthSum = Math.max(walker.col + walker.row, next.col + next.row);

    walker.moving = new Promise((resolve) => {
      walker.onRemoved = resolve;
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
          walker.moving = null;
          walker.onRemoved = null;
          this.place(walker, next.col + next.row);
          resolve();
        },
      });
    });
    return walker.moving;
  }

  // Walk along a shortest path, re-planning when someone is in the way. Resolves to true on arrival.
  async walkTo(walker, dest, shouldStop = () => false) {
    if (walker.moving) await walker.moving;
    let failures = 0;
    while (this.isPresent(walker) && !shouldStop()) {
      if (walker.col === dest.col && walker.row === dest.row) return true;
      const blocked = new Set(this.occupied);
      blocked.delete(tileKey(walker.col, walker.row));
      const path = findPath(MAP, blocked, walker, dest);
      if (!path) {
        if (++failures > PATH_RETRIES) return false;
        await this.wait(PATH_RETRY_MS);
        continue;
      }
      await this.moveStep(walker, path[0]);
    }
    return false;
  }

  // Where a walker stands, or will stand once its current step ends
  standingTile(walker) {
    return walker.target ?? { col: walker.col, row: walker.row };
  }

  checkMeetings() {
    const pairs = candidatePairs(
      [...this.walkers.values()],
      { now: this.time.now, inFlight: this.inFlight, lastEndedAt: this.lastEndedAt, pairCooldownUntil: this.pairCooldownUntil },
      MEETING,
      Math.random,
    );
    for (const [a, b] of pairs) {
      const blocked = new Set(this.occupied);
      for (const w of [a, b]) {
        blocked.delete(tileKey(w.col, w.row));
        if (w.target) blocked.delete(tileKey(w.target.col, w.target.row));
      }
      const spot = pickMeetingSpot(MAP, blocked, this.standingTile(a), this.standingTile(b));
      if (spot) return this.meet(a, b, spot);
    }
  }

  async meet(a, b, spot) {
    const convo = { cancelled: false, bubbles: new Set(), queue: [], wake: null, abort: new AbortController() };
    for (const w of [a, b]) {
      w.timer?.remove();
      w.state = 'approaching';
      w.conversation = convo;
    }
    this.inFlight++;
    this.listen(a, b, convo); // the first line is written while they walk
    try {
      const stop = () => convo.cancelled;
      const arrived = await Promise.all([this.walkTo(a, spot.a, stop), this.walkTo(b, spot.b, stop)]);
      if (convo.cancelled) return;
      if (!arrived.every(Boolean)) {
        convo.abort.abort();
        await this.shrug(convo, a, b);
        return;
      }
      this.face(a, b);
      this.face(b, a);
      a.state = b.state = 'talking';
      await this.play(convo, a, b);
    } finally {
      this.clearBubbles(convo);
      convo.abort.abort();
      this.inFlight--;
      this.lastEndedAt = this.time.now;
      this.pairCooldownUntil.set(pairKey(a.id, b.id), this.time.now + MEETING.pairCooldownMs);
      this.split(a, b);
    }
  }

  // Fetch the conversation and queue its events as they arrive.
  async listen(a, b, convo) {
    const push = (event) => {
      convo.queue.push(event);
      convo.wake?.();
    };
    try {
      const response = await fetch('/api/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ a_id: a.id, b_id: b.id }),
        signal: convo.abort.signal,
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await readEvents(response, push);
    } catch (error) {
      if (error.name !== 'AbortError') console.warn('Conversation failed:', error.message);
      push({ type: 'error', message: error.message });
    }
    push({ type: 'closed' });
  }

  async nextEvent(convo) {
    while (!convo.queue.length && !convo.cancelled) await new Promise((resolve) => (convo.wake = resolve));
    convo.wake = null;
    return convo.queue.shift();
  }

  // Play queued events: "..." while a character thinks, one line at a time, then the feelings.
  async play(convo, a, b) {
    const byName = { [a.character.name]: a, [b.character.name]: b };
    for (;;) {
      const event = await this.nextEvent(convo);
      if (convo.cancelled || !event) return;
      if (event.type === 'thinking') {
        this.clearBubbles(convo);
        if (byName[event.speaker]) this.showBubble(convo, byName[event.speaker], '...');
      } else if (event.type === 'line') {
        const speaker = byName[event.speaker] ?? a;
        this.clearBubbles(convo);
        this.react(speaker, event.emotion);
        this.showBubble(convo, speaker, `${EMOJI[event.emotion] ?? ''} ${event.text}`.trim());
        await this.wait(lineDuration(event.text));
        this.clearBubbles(convo);
      } else if (event.type === 'end') {
        for (const [name, { before, after }] of Object.entries(event.feelings)) {
          if (after !== before && byName[name]) this.floatIcon(byName[name], after > before ? '❤️' : '😕');
        }
        await this.wait(1200);
        return;
      } else {
        // error, or the stream closed without an end
        await this.shrug(convo, a, b);
        return;
      }
    }
  }

  async shrug(convo, a, b) {
    this.clearBubbles(convo);
    for (const w of [a, b]) if (this.isPresent(w)) this.showBubble(convo, w, '🤷 bof...');
    await this.wait(2000);
  }

  // Both walk a few tiles away from each other, then go back to wandering.
  split(a, b) {
    const blocked = new Set(this.occupied);
    for (const w of [a, b]) blocked.delete(tileKey(w.col, w.row));
    const targets = pickSplitTargets(MAP, blocked, a, b, Math.random);
    for (const [walker, target] of [[a, targets.a], [b, targets.b]]) {
      if (!this.isPresent(walker)) continue;
      walker.conversation = null;
      walker.state = 'leaving';
      const done = () => {
        if (!this.isPresent(walker)) return;
        walker.state = 'idle';
        this.scheduleStep(walker);
      };
      if (target) this.walkTo(walker, target).then(done);
      else done();
    }
  }

  wait(ms) {
    return new Promise((resolve) => this.time.delayedCall(ms, resolve));
  }

  face(walker, other) {
    walker.sprite.setFlipX(gridToScreen(other.col, other.row).x < gridToScreen(walker.col, walker.row).x);
  }

  // Point just above a standing walker's head
  headPoint(walker) {
    const { x, y } = gridToScreen(walker.col, walker.row);
    return { x, y: y + FOOT_OFFSET - CHAR_H - 2 };
  }

  showBubble(convo, walker, text) {
    const pad = 6;
    const tail = 6;
    const label = this.add
      .text(0, 0, text, { fontFamily: 'sans-serif', fontSize: '12px', color: '#1b1d26', wordWrap: { width: 170 } })
      .setOrigin(0.5, 1);
    const w = label.width + pad * 2;
    const h = label.height + pad * 2;
    const bg = this.add.graphics();
    bg.fillStyle(0xffffff, 0.95).fillRoundedRect(-w / 2, -h - tail, w, h, 8).fillTriangle(-5, -tail - 1, 5, -tail - 1, 0, 0);
    label.setPosition(0, -tail - pad);
    const { x, y } = this.headPoint(walker);
    const bubble = this.add.container(x, y, [bg, label]);
    this.overlay.add(bubble);
    convo.bubbles.add(bubble);
  }

  clearBubbles(convo) {
    convo.bubbles.forEach((bubble) => bubble.destroy());
    convo.bubbles.clear();
  }

  // Small body reaction to the line's emotion (the emoji in the bubble covers the rest)
  react(walker, emotion) {
    const { sprite } = walker;
    if (emotion === 'happy' || emotion === 'surprised') {
      this.tweens.add({ targets: sprite, y: sprite.y - 8, duration: 150, yoyo: true, repeat: 1, ease: 'Sine.easeOut' });
    } else if (emotion === 'annoyed' || emotion === 'scared') {
      this.tweens.add({ targets: sprite, x: sprite.x + 3, duration: 50, yoyo: true, repeat: 3 });
    }
  }

  floatIcon(walker, icon) {
    const { x, y } = this.headPoint(walker);
    const text = this.add.text(x, y, icon, { fontSize: '20px' }).setOrigin(0.5, 1);
    this.overlay.add(text);
    this.tweens.add({ targets: text, y: y - 30, alpha: 0, duration: 1200, onComplete: () => text.destroy() });
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
