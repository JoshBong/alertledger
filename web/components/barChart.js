import { el, svg } from '../lib/dom.js';
import { money, money0 } from '../lib/format.js';
import { attach } from '../lib/tooltip.js';

// Stacked bars. BarChart({ columns: [{label, title, values: {key: v}}], keys, colorFor, legend })
export function BarChart({ columns, keys, colorFor, legend = true }) {
  const W = 640, H = 200, PL = 44, PB = 22, PT = 6;
  const max = Math.max(1, ...columns.map(c => Object.values(c.values).filter(v => v > 0).reduce((a, b) => a + b, 0)));
  const y = v => PT + (H - PT - PB) * (1 - v / max);
  const chart = svg('svg', { viewBox: `0 0 ${W} ${H}` });
  const grid = svg('g', { class: 'grid' });
  for (const f of [0, .5, 1]) {
    grid.append(svg('line', { x1: PL, x2: W, y1: y(max * f), y2: y(max * f) }));
    grid.append(svg('text', { x: PL - 6, y: y(max * f) + 4, 'text-anchor': 'end' }, money0(max * f)));
  }
  chart.append(grid);
  const bw = (W - PL) / columns.length;
  columns.forEach((c, i) => {
    let acc = 0;
    const x = PL + i * bw + bw * .2, w = bw * .6;
    for (const k of keys) {
      const v = c.values[k];
      if (!(v > 0)) continue;
      const rect = svg('rect', { x, y: y(acc + v), width: w, height: Math.max(0, y(acc) - y(acc + v) - 1.5), fill: colorFor(k), rx: 1 });
      attach(rect, () => `<b>${c.title}</b>${keys.length > 1 || k !== 'total' ? ' · ' + k : ''}<br>${money(v)}`);
      chart.append(rect);
      acc += v;
    }
    chart.append(svg('text', { x: x + w / 2, y: H - 6, 'text-anchor': 'middle' }, c.label));
  });
  const root = el('div', { class: 'bars' }, chart);
  if (legend && keys.length > 1) root.append(el('div', { class: 'legend' }, ...keys.map(k => el('span', {}, el('i', { class: 'dot', style: { '--c': colorFor(k) } }), k))));
  return root;
}
