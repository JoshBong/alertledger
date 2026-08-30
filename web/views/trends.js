import { el } from '../lib/dom.js';
import { store, sumBy } from '../lib/store.js';
import { money, money0, monthLabel, shortMonth, MONTHS, ym } from '../lib/format.js';
import { Segmented } from '../components/segmented.js';
import { BarChart } from '../components/barChart.js';
import { Table } from '../components/table.js';

const panel = (title, ...kids) => el('section', { class: 'panel' }, el('h3', {}, title), ...kids);

export function TrendsView({ rerender }) {
  const mode = store.state.trend;
  const months = store.months.slice(0, 12).reverse();
  const key = mode === 'cat' ? (t => t.cat) : mode === 'acct' ? (t => t.card) : (() => 'total');
  const colorFor = k => mode === 'total' ? 'var(--s1)' : store.colorFor(mode, k);
  const columns = months.map(m => ({ label: shortMonth(m), title: monthLabel(m), values: sumBy(store.inMonth(m), key), current: m === store.months[0] }));
  const keys = [...new Set(columns.flatMap(c => Object.keys(c.values)))]
    .sort((a, b) => mode === 'cat' ? store.categories.indexOf(a) - store.categories.indexOf(b) : a.localeCompare(b));

  const rec = store.data.recurring;
  const last6 = store.months.slice(0, 6).reverse();
  const momRows = store.categories.map(c => [c, ...last6.map(m => store.inMonth(m).filter(t => t.cat === c).reduce((s, t) => s - t.amount, 0))])
    .filter(r => r.slice(1).some(v => v)).map(r => [r[0], ...r.slice(1).map(v => v ? money0(v) : '·')]);

  return el('div', {},
    panel('Monthly spend · last 12 months',
      el('div', { class: 'row', style: { marginBottom: '8px' } },
        Segmented({ options: [{ value: 'total', label: 'total' }, { value: 'cat', label: 'by category' }, { value: 'acct', label: 'by account' }], value: mode, onChange: v => { store.state.trend = v; rerender(); } })),
      BarChart({ columns, keys, colorFor })),
    panel('Recurring charges',
      Table({ columns: [{ title: 'merchant' }, { title: 'category' }, { title: 'last' }, { title: 'per month', numeric: true }],
        rows: rec.map(r => [r.merchant, r.cat, r.last, money(r.amount)]), empty: 'nothing recurring detected yet — needs two charges about a month apart' }),
      rec.length ? el('div', { class: 'muted', style: { marginTop: '6px' } }, `${money(rec.reduce((s, r) => s + r.amount, 0))} / month total`) : null),
    panel('Category · month over month',
      Table({ columns: [{ title: 'category' }, ...last6.map(m => ({ title: MONTHS[+m.slice(5, 7) - 1], numeric: true }))], rows: momRows, empty: 'no spending yet' })),
  );
}
