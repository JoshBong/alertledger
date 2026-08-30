export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const money = n => (n < 0 ? '−' : '') + '$' + Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const money0 = n => '$' + Math.round(Math.abs(n)).toLocaleString();
export const pct = (v, total) => (total ? Math.round(100 * v / total) : 0) + '%';

export const ym = iso => iso.slice(0, 7);                                  // '2026-08-03' → '2026-08'
export const monthLabel = m => MONTHS[+m.slice(5, 7) - 1] + ' ' + m.slice(0, 4);
export const shortMonth = m => MONTHS[+m.slice(5, 7) - 1] + (m.endsWith('-01') ? ' ' + m.slice(2, 4) : '');
export const today = () => new Date().toISOString().slice(0, 10);
export const dayLabel = iso => new Date(iso + 'T00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

// Continuous list of 'YYYY-MM' from `to` back to `from`, newest first.
export function monthRange(from, to) {
  const out = [];
  let [y, m] = to.split('-').map(Number);
  const [fy, fm] = from.split('-').map(Number);
  while (y > fy || (y === fy && m >= fm)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    if (--m === 0) { m = 12; y--; }
  }
  return out;
}
