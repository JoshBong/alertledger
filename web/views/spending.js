import { el } from '../lib/dom.js';
import { store, sumBy } from '../lib/store.js';
import { money0, monthLabel, ym, today } from '../lib/format.js';
import { MonthNav } from '../components/monthNav.js';
import { Segmented } from '../components/segmented.js';
import { Donut } from '../components/donut.js';
import { CategoryCards } from '../components/categoryCards.js';
import { TxList } from '../components/txList.js';

const MAX_SLICES = 8;

export function SpendingView({ rerender, goto }) {
  const { month, mode } = store.state;
  const rows = store.inMonth(month);
  const prev = store.prevMonth(month);
  const key = store.keyFor(mode);
  const cur = sumBy(rows, key), old = prev ? sumBy(store.inMonth(prev), key) : {};
  const total = Object.values(cur).reduce((a, b) => a + b, 0);

  let items = Object.entries(cur).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  if (mode === 'cat' && items.length > MAX_SLICES) {                       // fold the tail into Other
    const head = items.slice(0, MAX_SLICES - 1), tail = items.slice(MAX_SLICES - 1);
    const other = tail.reduce((s, [, v]) => s + v, 0) + (head.find(([k]) => k === store.other)?.[1] || 0);
    items = [...head.filter(([k]) => k !== store.other), [store.other, other]];
  }
  const shaped = items.map(([k, v]) => ({
    key: k, value: v, color: store.colorFor(mode, k), delta: v - (old[k] || 0),
    count: rows.filter(t => key(t) === k).length,
    label: k === store.other && mode === 'cat' ? `${k} · ${rows.filter(t => t.cat === k).length} uncategorized` : k,
  }));

  const expanded = store.state.expanded;
  const toggle = k => { store.state.expanded = expanded === k ? null : k; rerender(); };
  const detailRows = expanded ? rows.filter(t => key(t) === expanded) : [];
  const detail = expanded && detailRows.length ? el('section', { class: 'panel detail', style: { '--c': store.colorFor(mode, expanded) } },
    el('div', { class: 'row', style: { marginBottom: '8px' } },
      el('h3', { style: { margin: 0 } }, el('i', { class: 'dot' }), ' ', expanded, el('span', { class: 'muted' }, ` · ${detailRows.length} in ${monthLabel(month)}`)),
      el('span', { class: 'grow' }),
      el('a', { href: '#transactions', class: 'muted', onclick: e => { e.preventDefault(); store.state.filter = { q: '', month, account: mode === 'cat' ? '' : expanded, category: mode === 'cat' ? expanded : '' }; goto('transactions'); } }, 'open in Transactions ›'),
      el('button', { class: 'muted', style: { padding: '2px 8px' }, onclick: () => toggle(expanded), 'aria-label': 'close' }, '✕')),
    TxList({ rows: detailRows, colorFor: c => store.categoryColor(c), limit: 60 })) : null;
  const isCurrent = month === ym(today());
  return el('div', {},
    MonthNav({ months: store.months, month, onChange: m => { store.state.month = m; rerender(); } }),
    el('div', { class: 'row', style: { justifyContent: 'center', marginBottom: '6px' } },
      Segmented({ options: [{ value: 'cat', label: 'by category' }, { value: 'acct', label: 'by account' }], value: mode, onChange: v => { store.state.mode = v; rerender(); } })),
    Donut({ items: shaped, total, title: money0(total), onSelect: toggle,
      subtitle: isCurrent ? 'spent so far · as of ' + new Date(today() + 'T00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : 'spent in ' + monthLabel(month) }),
    CategoryCards({ items: shaped, total, hasPrev: !!prev, onSelect: toggle, selected: expanded }),
    detail,
  );
}
