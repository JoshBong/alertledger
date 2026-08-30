import { el } from '../lib/dom.js';
import { store, sumBy, api } from '../lib/store.js';
import { money0, monthLabel, ym, today } from '../lib/format.js';
import { MonthNav } from '../components/monthNav.js';
import { CategoryCards } from '../components/categoryCards.js';

// Budget view: every budgetable category as a card with its bar, whether or not it had spend this month.
export function BudgetView({ rerender }) {
  const { month } = store.state;
  const rows = store.inMonth(month);
  const cur = sumBy(rows, t => t.cat);
  const cats = store.categories;                               // Other = "everything else" budget; total = sum of all
  const budgets = store.budgets;
  const items = cats.map(c => ({ key: c, label: c === store.other ? 'Everything else' : c, value: cur[c] || 0, color: store.categoryColor(c), count: rows.filter(t => t.cat === c).length,
    budget: budgets[c], suggest: store.avg3(c, month), budgetable: true, delta: 0 }));
  const total = items.reduce((s, i) => s + (i.budget || 0), 0);
  const spent = total ? items.reduce((s, i) => s + i.value, 0) : 0;      // all spend counts against the total
  const elapsed = store.elapsed(month);
  const isCurrent = month === ym(today());
  const days = new Date(+month.slice(0, 4), +month.slice(5, 7), 0).getDate();
  const save = async (cat, amount) => {
    try { store.data.budgets = await api('/api/budget', { method: 'POST', body: JSON.stringify({ category: cat, amount }) }); }
    catch (e) { alert('could not save budget: ' + e.message); }
    store.state.editing = null; rerender();
  };
  const overall = total ? el('section', { class: 'panel overall' },
    el('div', { class: 'row' }, el('div', { class: 'grow' }, el('div', { class: 'muted' }, isCurrent ? `day ${+today().slice(8, 10)} of ${days}` : monthLabel(month)),
      el('div', { class: 'big num' }, `${money0(spent)} `, el('span', { class: 'muted' }, `of ${money0(total)} budgeted`))),
      el('div', { class: 'pct num' }, Math.round(100 * spent / total) + '%')),
    el('div', { class: 'budget' }, el('div', { class: 'bar' + (spent > total ? ' over' : spent > total * elapsed * 1.05 ? ' ahead' : '') },
      el('div', { class: 'fill', style: { width: Math.min(100, 100 * spent / total) + '%' } }),
      elapsed > 0 && elapsed < 1 ? el('div', { class: 'tick', style: { left: (elapsed * 100) + '%' } }) : null)),
    el('div', { class: 'muted' }, spent > total ? `over by ${money0(spent - total)}` : `${money0(total - spent)} left` + (elapsed > 0 && elapsed < 1 ? ` · on pace for ${money0(spent / elapsed)}` : '')),
    el('div', { class: 'stack', title: 'spend by category' }, ...items.filter(i => i.value > 0).map(i =>
      el('div', { class: 'seg', style: { width: (100 * i.value / Math.max(total, spent)) + '%', '--c': i.color }, title: `${i.label}: ${money0(i.value)}` }))),
    el('div', { class: 'legend' }, ...items.filter(i => i.value > 0).map(i => el('span', {}, el('i', { class: 'dot', style: { '--c': i.color } }), `${i.label} ${money0(i.value)}`))))
    : el('div', { class: 'empty' }, 'No budgets yet. Tap + budget on a category — "avg" fills in your 3-month average.');
  return el('div', {},
    MonthNav({ months: store.months, month, onChange: m => { store.state.month = m; rerender(); } }),
    overall,
    CategoryCards({ items, total: spent || 1, hasPrev: false, elapsed, selected: null, editing: store.state.editing,
      onSelect: () => {}, onEdit: k => { store.state.editing = k; rerender(); }, onSaveBudget: save }),
  );
}
