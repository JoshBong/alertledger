import { el, svg } from '../lib/dom.js';
import { money, pct } from '../lib/format.js';
import { attach } from '../lib/tooltip.js';

// Donut({ items: [{key, value, color}], total, title, subtitle, onSelect })
export function Donut({ items, total, title, subtitle, onSelect }) {
  const R = 80, r = 58, C = 100, GAP = items.length > 1 ? 0.02 : 0;
  const chart = svg('svg', { viewBox: '0 0 200 200', role: 'img', 'aria-label': title });
  if (!total) chart.append(svg('circle', { cx: C, cy: C, r: (R + r) / 2, fill: 'none', stroke: 'var(--line)', 'stroke-width': R - r }));
  if (items.length === 1) {                                                  // a 360° arc is degenerate in SVG: draw a ring
    const it = items[0];
    const ring = svg('circle', { cx: C, cy: C, r: (R + r) / 2, fill: 'none', stroke: it.color, 'stroke-width': R - r, onclick: () => onSelect?.(it.key) });
    attach(ring, () => `<b>${it.key}</b><br>${money(it.value)} · 100%`);
    chart.append(ring);
  }
  let a0 = -Math.PI / 2;
  for (const it of items.length === 1 ? [] : items) {
    const a1 = a0 + 2 * Math.PI * it.value / total;
    const s = a0 + GAP / 2, e = a1 - GAP / 2;
    a0 = a1;
    if (e <= s) continue;
    const p = (a, rad) => [C + rad * Math.cos(a), C + rad * Math.sin(a)];
    const big = e - s > Math.PI ? 1 : 0;
    const [x1, y1] = p(s, R), [x2, y2] = p(e, R), [x3, y3] = p(e, r), [x4, y4] = p(s, r);
    const d = `M${x1},${y1}A${R},${R},0,${big},1,${x2},${y2}L${x3},${y3}A${r},${r},0,${big},0,${x4},${y4}Z`;
    const path = svg('path', { d, fill: it.color, onclick: () => onSelect?.(it.key) });
    attach(path, () => `<b>${it.key}</b><br>${money(it.value)} · ${pct(it.value, total)}`);
    chart.append(path);
  }
  return el('div', { class: 'donut' }, chart,
    el('div', { class: 'center' }, el('div', { class: 'big num' }, title), el('div', { class: 'sub' }, subtitle)));
}
