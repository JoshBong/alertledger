import { el } from '../lib/dom.js';
import { money0, pct } from '../lib/format.js';

// CategoryCards({ items: [{key, value, color, count, delta}], total, hasPrev, onSelect })
export function CategoryCards({ items, total, hasPrev, onSelect, selected }) {
  if (!items.length) return el('div', { class: 'empty' }, 'no spending recorded this month');
  return el('div', { class: 'cards' }, ...items.map(it =>
    el('div', { class: 'card' + (it.key === selected ? ' on' : ''), style: { '--c': it.color }, role: 'button', tabindex: 0, 'aria-expanded': it.key === selected, onclick: () => onSelect?.(it.key) },
      el('div', { class: 'name' }, el('i', { class: 'dot' }), it.label ?? it.key),
      el('div', { class: 'value num' }, money0(it.value)),
      el('div', { class: 'sub' },
        el('span', {}, pct(it.value, total) + ' of total'),
        hasPrev
          ? el('span', { class: it.delta > 0 ? 'up' : 'down' }, (it.delta > 0 ? '▲ ' : '▼ ') + money0(it.delta))
          : el('span', {}, it.count + ' txns'),
      ),
    )));
}
