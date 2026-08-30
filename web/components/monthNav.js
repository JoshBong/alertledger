import { el } from '../lib/dom.js';
import { monthLabel } from '../lib/format.js';

// ‹ Aug 2026 › — months is newest-first; onChange(month). Shows a "today" jump when you're not on the current month.
export function MonthNav({ months, month, onChange }) {
  const i = months.indexOf(month);
  return el('div', { class: 'month-nav' },
    el('button', { 'aria-label': 'previous month', disabled: i >= months.length - 1, onclick: () => onChange(months[i + 1]) }, '‹'),
    el('h2', {}, monthLabel(month)),
    el('button', { 'aria-label': 'next month', disabled: i <= 0, onclick: () => onChange(months[i - 1]) }, '›'),
    i > 0 ? el('button', { class: 'today', onclick: () => onChange(months[0]) }, 'today') : null,
  );
}
