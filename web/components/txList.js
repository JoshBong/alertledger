import { el } from '../lib/dom.js';
import { money, dayLabel } from '../lib/format.js';

// TxList({ rows, colorFor(cat), limit }) — rows newest first; grouped by day.
export function TxList({ rows, colorFor, limit = 400 }) {
  if (!rows.length) return el('div', { class: 'list' }, el('div', { class: 'empty' }, 'nothing here'));
  const list = el('div', { class: 'list' });
  let day = '';
  for (const t of rows.slice(0, limit)) {
    if (t.date !== day) { day = t.date; list.append(el('div', { class: 'day' }, dayLabel(t.date))); }
    const income = t.type === 'transfer' || t.amount > 0;
    const cat = t.ignore ? 'ignored' : t.type === 'transfer' ? 'income' : t.cat;
    list.append(el('div', { class: 'tx' },
      el('div', { class: 'merchant', title: t.merchant }, t.merchant),
      el('div', { class: 'amount num' + (income ? ' in' : '') }, money(t.amount)),
      el('div', { class: 'meta', style: { '--c': colorFor(t.cat) } }, el('i', { class: 'dot' }), cat, '·', t.card, t.status === 'pending' ? '· pending' : null),
    ));
  }
  if (rows.length > limit) list.append(el('div', { class: 'empty' }, `showing ${limit} of ${rows.length} — narrow the filters`));
  return list;
}
