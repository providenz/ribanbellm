import { describe, expect, it } from 'vitest';
import { EXPRESSIONS, characterKey, expressionFor, hopOffset } from './sprites.js';

describe('expressionFor', () => {
  it('gives each emotion its own face', () => {
    for (const emotion of ['neutral', 'happy', 'annoyed', 'sad', 'surprised', 'smug', 'scared']) {
      expect(expressionFor(emotion)).toBe(emotion);
      expect(EXPRESSIONS).toContain(emotion);
    }
  });

  it('falls back to neutral for anything else', () => {
    expect(expressionFor('angry')).toBe('neutral');
    expect(expressionFor(undefined)).toBe('neutral');
  });

  it('includes a blink', () => {
    expect(EXPRESSIONS).toContain('blink');
  });
});

describe('characterKey', () => {
  it('names one texture per character and expression', () => {
    expect(characterKey(3, 'happy')).toBe('char-3-happy');
    expect(characterKey(3, 'whatever')).toBe('char-3-neutral');
  });
});

describe('hopOffset', () => {
  it('starts and lands on the ground and peaks mid-step', () => {
    expect(hopOffset(0)).toBeCloseTo(0);
    expect(hopOffset(1)).toBeCloseTo(0);
    expect(hopOffset(0.5)).toBeLessThan(hopOffset(0.25));
    expect(hopOffset(0.5)).toBeCloseTo(-6);
  });
});
