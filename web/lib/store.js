// Loads /api/data once and exposes derived views + UI state. Views subscribe to `state` changes via render().
import { ym, today, monthRange } from './format.js';

const SLOTS = ['--s1', '--s2', '--s3', '--s4', '--s5', '--s6', '--s7', '--s8'];
const CATEGORY_COLORS = {
  'Food & Dining': 'var(--s2)', Groceries: 'var(--s3)', Shopping: 'var(--s5)', Travel: 'var(--s1)', Transport: 'var(--s4)',
  'Bills & Subscriptions': 'var(--s7)', Health: 'var(--s6)', People: 'var(--s8)', Other: 'var(--gray)',
};

export const store = {
  data: null,
  spend: [],            // rows that count as spending (purchases, refunds, zelle out) — excludes transfers/ignored
  months: [],           // continuous 'YYYY-MM' list, newest first
  accountColor: {},
  state: { tab: 'spending', month: ym(today()), mode: 'cat', trend: 'total', filter: { q: '', month: '', account: '', category: '' } },

  async load() {
    const r = await fetch('/api/data');
    if (!r.ok) throw new Error('data ' + r.status);
    this.data = await r.json();
    this.spend = this.data.tx.filter(t => !t.ignore && t.type !== 'transfer');
    const seen = new Set(this.spend.map(t => ym(t.date)));
    seen.add(ym(today()));
    const sorted = [...seen].sort();
    this.months = monthRange(sorted[0], sorted[sorted.length - 1]);
    this.accountColor = Object.fromEntries(this.data.accounts.map((a, i) => [a.name, `var(${SLOTS[i % 8]})`]));
    return this;
  },

  get categories() { return this.data.categories; },
  get other() { return this.data.categories[this.data.categories.length - 1]; },
  categoryColor(c) { return CATEGORY_COLORS[c] || 'var(--gray)'; },
  colorFor(mode, key) { return mode === 'cat' ? this.categoryColor(key) : this.accountColor[key] || 'var(--gray)'; },
  keyFor(mode) { return mode === 'cat' ? (t => t.cat) : (t => t.card); },

  inMonth(m) { return this.spend.filter(t => ym(t.date) === m); },
  prevMonth(m) { const i = this.months.indexOf(m); return i >= 0 ? this.months[i + 1] : undefined; },
};

// Sum of spend (positive = money out) grouped by key.
export function sumBy(rows, key) {
  const out = {};
  for (const t of rows) out[key(t)] = (out[key(t)] || 0) - t.amount;
  return out;
}

export async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok || j.error) throw new Error(j.error || r.status);
  return j;
}
