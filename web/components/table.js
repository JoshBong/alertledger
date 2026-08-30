import { el } from '../lib/dom.js';

// Table({ columns: [{title, numeric}], rows: [[cell, ...]], empty })
export function Table({ columns, rows, empty = 'nothing yet' }) {
  if (!rows.length) return el('div', { class: 'muted' }, empty);
  return el('div', { class: 'tbl' }, el('table', {},
    el('thead', {}, el('tr', {}, ...columns.map(c => el('th', { class: c.numeric ? 'n' : '' }, c.title)))),
    el('tbody', {}, ...rows.map(r => el('tr', {}, ...r.map((cell, i) => el('td', { class: columns[i].numeric ? 'n num' : '' }, cell))))),
  ));
}
