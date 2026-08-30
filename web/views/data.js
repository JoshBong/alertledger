import { el, option } from '../lib/dom.js';
import { store, api } from '../lib/store.js';
import { money } from '../lib/format.js';
import { Table } from '../components/table.js';

const panel = (title, ...kids) => el('section', { class: 'panel' }, el('h3', {}, title), ...kids);

export function DataView() {
  const d = store.data, c = d.last_counts || {};

  const syncBtn = el('button', { class: 'primary', onclick: async () => {
    syncBtn.textContent = 'syncing…'; syncBtn.disabled = true;
    try { await api('/api/sync', { method: 'POST' }); location.reload(); }
    catch (e) { syncBtn.textContent = 'failed: ' + e.message; syncBtn.disabled = false; }
  } }, '⟳ Sync now');

  const acctSel = el('select', { 'aria-label': 'account' }, ...d.accounts.map(a => option(a.name, a.id)));
  const file = el('input', { type: 'file', accept: '.csv,text/csv' });
  const msg = el('div', { class: 'muted', style: { marginTop: '6px' } });
  const importBtn = el('button', { onclick: async () => {
    const f = file.files[0];
    if (!f) { msg.textContent = 'choose a CSV first'; return; }
    msg.textContent = 'importing…';
    try {
      const j = await api('/api/import?account=' + encodeURIComponent(acctSel.value), { method: 'POST', body: await f.text() });
      msg.textContent = `imported: ${j.new} new · ${j.upgraded} alert rows upgraded to posted · ${j.dup} already there. Reloading…`;
      setTimeout(() => location.reload(), 1200);
    } catch (e) { msg.textContent = 'failed: ' + e.message; }
  } }, 'Import');

  return el('div', {},
    panel('Sync', el('div', { class: 'row' },
      el('div', { class: 'kv grow' }, el('b', {}, 'last sync'), el('span', {}, d.last_sync ? d.last_sync.replace('T', ' ') : 'never'),
        el('b', {}, 'last run'), el('span', {}, Object.keys(c).length ? `${c.txn} transactions · ${c.statement} statements · ${c.skip} skipped · ${c.unparsed} unparsed` : '—')),
      syncBtn)),
    panel('Accounts', el('div', { class: 'kv' }, ...d.accounts.flatMap(a =>
      [el('b', {}, a.name), el('span', {}, `${d.tx.filter(t => t.acct === a.id).length} transactions · id `, el('code', {}, a.id))]))),
    panel('Import a bank CSV',
      el('p', { class: 'muted', style: { margin: '0 0 8px' } }, 'Backfills history and upgrades alert rows to the bank\'s posted amounts. Download activity as CSV from the bank for ', el('b', {}, 'one account'), ', pick that account, choose the file.'),
      el('div', { class: 'row' }, acctSel, file, importBtn), msg),
    panel(el('span', {}, 'Statement checksum ', el('span', { class: 'muted' }, 'bank balance vs. what we have, per cycle')),
      Table({ columns: [{ title: 'card' }, { title: 'statement' }, { title: 'bank', numeric: true }, { title: 'ours', numeric: true }, { title: 'gap', numeric: true }],
        rows: d.checksum.slice(0, 12).map(r => [r.card, r.date, money(r.bank), money(r.ours), el('span', { class: Math.abs(r.gap) < 1 ? 'down' : 'up' }, money(r.gap))]),
        empty: 'no statement emails yet' })),
    panel(el('span', {}, 'Unparsed emails ', el('span', { class: 'muted' }, 'last 50')),
      Table({ columns: [{ title: 'date' }, { title: 'bank' }, { title: 'subject' }], rows: d.failures.map(f => [f.date, f.bank, f.subject]), empty: 'none — every bank email was recognised' })),
  );
}
