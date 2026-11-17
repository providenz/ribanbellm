# Village scene: short design

Date: 2026-11-17.

- **Intent:** make the map nicer and richer than a 12x12 checkerboard with grey cubes.
- **Picked by the user:** "a little village". Not picked: height and relief, ambient animations, camera controls.
- **Goals:**
  - An 18x18 map with varied ground: grass (a few shades), flowery grass, dirt paths, sand, a pond.
  - Obstacles that read as things: leafy trees and pines, bushes, rocks, small houses, a well on a central square, benches, lamp posts.
  - The map looks like a floating island, with earth side faces along its front edges.
  - Everything is still drawn in code (no image files).
- **Non-goals:** no animation, no relief, no camera, no change to movement or meetings.
- **How:** the layout is a list of strings in `map.js`, one character per tile. `MAP` (0 walkable, 1 blocked) is derived from it, so `sim.js` is unchanged. Ground tiles are drawn under everything; objects and characters share the existing `col + row` depth rule. Variants (grass shade, tree kind, roof colour) come from a deterministic per-tile hash, so the village looks the same on each load.
- **Approaches:** a layout of strings with derived walkability (picked: readable, editable by hand, sim untouched), versus a tile-map editor format such as Tiled (heavier, needs image assets), versus procedural generation (less control over a pleasant village).
- **Checked by tests:** square layout, known symbols only, every walkable tile reachable from every other, enough room for the whole cast.
- **Left to the builder:** exact layout, colours, shapes, canvas size.
