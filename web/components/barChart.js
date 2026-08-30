import { el, svg } from '../lib/dom.js';
import { money, money0 } from '../lib/format.js';
import { attach } from '../lib/tooltip.js';

// "Nice" axis: 3–5 round ticks covering max (500 → 0,100,…; 3604 → 0,1000,2000,3000,4000).
function niceTicks(max, count = 4) {
  const raw = max / count, mag = Math.pow(10, Math.floor(Math.log10(raw || 1)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || mag * 10;
  const top = Math.ceil(max / step) * step || step;
  const ticks = [];
  for (let v = 0; v <= top + 1e-9; v += step) ticks.push(v);
  return { top, ticks };
}

// Stacked bars, responsive width, fixed height. BarChart({ columns: [{label, title, values:{key:v}, current?}], keys, colorFor, legend })
export function BarChart({ columns, keys, colorFor, legend = true, height = 240 }) {
  const root = el('div', { class: 'bars' });
  const holder = el('div', { class: 'bars-svg' });
  root.append(holder);
  const totals = columns.map(c => Object.values(c.values).filter(v => v > 0).reduce((a, b) => a + b, 0));
  const { top, ticks } = niceTicks(Math.max(...totals, 1));
  const avg = totals.filter(Boolean).length ? totals.reduce((a, b) => a + b, 0) / totals.filter(Boolean).length : 0;

  function draw() {
    const W = Math.max(320, holder.clientWidth || 640), H = height, PL = 52, PR = 8, PB = 24, PT = 10;
    const y = v => PT + (H - PT - PB) * (1 - v / top);
    const chart = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    const grid = svg('g', { class: 'grid' });
    for (const t of ticks) {
      grid.append(svg('line', { x1: PL, x2: W - PR, y1: y(t), y2: y(t) }));
      grid.append(svg('text', { x: PL - 8, y: y(t) + 4, 'text-anchor': 'end' }, money0(t)));
    }
    chart.append(grid);
    const slot = (W - PL - PR) / columns.length, bw = Math.min(44, slot * .62);
    columns.forEach((c, i) => {
      let acc = 0;
      const x = PL + i * slot + (slot - bw) / 2;
      if (c.current) chart.append(svg('rect', { x: PL + i * slot + 1, y: PT, width: slot - 2, height: H - PT - PB, fill: 'var(--line)', opacity: .35, rx: 4 }));
      for (const k of keys) {
        const v = c.values[k];
        if (!(v > 0)) continue;
        const rect = svg('rect', { x, y: y(acc + v), width: bw, height: Math.max(0, y(acc) - y(acc + v) - 1), fill: colorFor(k), rx: 2 });
        attach(rect, () => `<b>${c.title}</b>${k !== 'total' ? ' · ' + k : ''}<br>${money(v)}${keys.length > 1 ? `<br><span style="opacity:.7">month total ${money(totals[i])}</span>` : ''}`);
        chart.append(rect);
        acc += v;
      }
      chart.append(svg('text', { x: x + bw / 2, y: H - 7, 'text-anchor': 'middle', class: c.current ? 'cur' : '' }, c.label));
    });
    if (avg > 0) {
      chart.append(svg('line', { x1: PL, x2: W - PR, y1: y(avg), y2: y(avg), class: 'avg' }));
      chart.append(svg('text', { x: W - PR, y: y(avg) - 4, 'text-anchor': 'end', class: 'avg-label' }, 'avg ' + money0(avg)));
    }
    holder.replaceChildren(chart);
  }
  requestAnimationFrame(draw);
  if (window.ResizeObserver) new ResizeObserver(draw).observe(holder);
  if (legend && keys.length > 1) root.append(el('div', { class: 'legend' }, ...keys.map(k => el('span', {}, el('i', { class: 'dot', style: { '--c': colorFor(k) } }), k))));
  return root;
}
