import { describe, expect, it } from 'vitest';
import { feelingNotes, isNearBottom } from './chat.js';

describe('feelingNotes', () => {
  it('describes each changed feeling from its owner toward the other', () => {
    const feelings = { Grillon: { before: 0, after: 2 }, 'Gérard': { before: 1, after: -1 } };
    expect(feelingNotes(feelings)).toEqual(['Grillon ❤️ Gérard', 'Gérard 😕 Grillon']);
  });

  it('skips unchanged feelings', () => {
    expect(feelingNotes({ A: { before: 3, after: 3 }, B: { before: 0, after: 1 } })).toEqual(['B ❤️ A']);
  });
});

describe('isNearBottom', () => {
  it('is true when scrolled to the end, false when the viewer scrolled up', () => {
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 600, clientHeight: 390 })).toBe(true);
    expect(isNearBottom({ scrollHeight: 1000, scrollTop: 200, clientHeight: 390 })).toBe(false);
  });
});
