import { describe, expect, it } from 'vitest';
import { EMPTY_USAGE, addUsage, formatUsage } from './usage.js';

const plain = (text) => text.replace(/\s/g, ' '); // French formatting uses narrow no-break spaces

describe('addUsage', () => {
  it('sums tokens and known costs, and counts conversations', () => {
    const total = addUsage(addUsage(EMPTY_USAGE, { input_tokens: 100, output_tokens: 10, cost_usd: 0.01 }), {
      input_tokens: 50, output_tokens: 5, cost_usd: 0.002,
    });
    expect(total).toEqual({ conversations: 2, input_tokens: 150, output_tokens: 15, cost_usd: 0.012, unpriced: 0 });
  });

  it('counts conversations without a known price apart', () => {
    const total = addUsage(EMPTY_USAGE, { input_tokens: 100, output_tokens: 10, cost_usd: null });
    expect(total).toEqual({ conversations: 1, input_tokens: 100, output_tokens: 10, cost_usd: null, unpriced: 1 });
  });

  it('adds only the growth of a running conversation, and counts it once', () => {
    const first = { input_tokens: 100, output_tokens: 10, cost_usd: 0.01 };
    const later = { input_tokens: 250, output_tokens: 30, cost_usd: 0.025 };
    const total = addUsage(addUsage(EMPTY_USAGE, first), later, first);
    expect(total).toEqual({ conversations: 1, input_tokens: 250, output_tokens: 30, cost_usd: 0.025, unpriced: 0 });
  });

  it('counts a running conversation without a price once', () => {
    const first = { input_tokens: 100, output_tokens: 10, cost_usd: null };
    const later = { input_tokens: 250, output_tokens: 30, cost_usd: null };
    const total = addUsage(addUsage(EMPTY_USAGE, first), later, first);
    expect(total).toEqual({ conversations: 1, input_tokens: 250, output_tokens: 30, cost_usd: null, unpriced: 1 });
  });
});

describe('formatUsage', () => {
  it('shows conversations, tokens and cost', () => {
    const text = plain(formatUsage({ conversations: 3, input_tokens: 12000, output_tokens: 345, cost_usd: 0.0125, unpriced: 0 }));
    expect(text).toBe('3 conv. · 12 345 tokens · 0,0125 $');
  });

  it('says when there is nothing yet', () => {
    expect(formatUsage(EMPTY_USAGE)).toBe('aucune conversation');
  });

  it('says the cost is unknown when no price is known', () => {
    const text = plain(formatUsage({ conversations: 1, input_tokens: 100, output_tokens: 10, cost_usd: null, unpriced: 1 }));
    expect(text).toBe('1 conv. · 110 tokens · coût inconnu');
  });

  it('flags a partial cost', () => {
    const text = plain(formatUsage({ conversations: 3, input_tokens: 100, output_tokens: 10, cost_usd: 1.5, unpriced: 2 }));
    expect(text).toBe('3 conv. · 110 tokens · 1,50 $ (+2 sans prix)');
  });
});
