// Token and cost totals for the sidebar footer. Same shape as GET /api/usage.

export const EMPTY_USAGE = { conversations: 0, input_tokens: 0, output_tokens: 0, cost_usd: null, unpriced: 0 };

// Add a conversation's usage ({ input_tokens, output_tokens, cost_usd }, cost null when unknown).
// A running conversation reports its totals so far after each line: pass the previous report as
// `previous` to add only what grew since, so the conversation is counted once.
export function addUsage(total, usage, previous = null) {
  const before = previous ?? { input_tokens: 0, output_tokens: 0, cost_usd: 0 };
  const known = usage.cost_usd !== null;
  const newlyUnpriced = !known && (previous === null || previous.cost_usd !== null);
  const addedCost = known ? usage.cost_usd - (before.cost_usd ?? 0) : 0;
  return {
    conversations: total.conversations + (previous === null ? 1 : 0),
    input_tokens: total.input_tokens + usage.input_tokens - before.input_tokens,
    output_tokens: total.output_tokens + usage.output_tokens - before.output_tokens,
    // Rounded to the micro-dollar so float sums stay clean
    cost_usd: known ? Math.round(((total.cost_usd ?? 0) + addedCost) * 1e6) / 1e6 : total.cost_usd,
    unpriced: total.unpriced + (newlyUnpriced ? 1 : 0),
  };
}

const number = new Intl.NumberFormat('fr-FR');

function money(usd) {
  const digits = usd < 1 ? 4 : 2; // small amounts need more decimals to mean anything
  return `${new Intl.NumberFormat('fr-FR', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(usd)} $`;
}

export function formatUsage(u) {
  if (!u.conversations) return 'aucune conversation';
  const tokens = `${number.format(u.input_tokens + u.output_tokens)} tokens`;
  let cost;
  if (u.cost_usd === null) cost = 'coût inconnu';
  else cost = money(u.cost_usd) + (u.unpriced ? ` (+${u.unpriced} sans prix)` : '');
  return `${u.conversations} conv. · ${tokens} · ${cost}`;
}
