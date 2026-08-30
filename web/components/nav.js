import { el, clear } from '../lib/dom.js';

const TABS = [
  { id: 'spending', label: 'Spending', glyph: '◔' },
  { id: 'transactions', label: 'Transactions', glyph: '≡' },
  { id: 'trends', label: 'Trends', glyph: '⟋' },
  { id: 'data', label: 'Data', glyph: '⚙' },
];

export function Nav(root, active, onSelect) {
  clear(root).append(
    el('a', { class: 'brand', href: '#spending', onclick: e => { e.preventDefault(); onSelect('spending'); } }, 'alertledger'),
    ...TABS.map(t => el('a', { href: '#' + t.id, class: t.id === active ? 'on' : '', 'data-tab': t.id,
      onclick: e => { e.preventDefault(); onSelect(t.id); } }, el('span', { class: 'glyph' }, t.glyph), t.label)),
  );
}
