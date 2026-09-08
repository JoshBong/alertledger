// Drag a transaction into the category it belongs in. The gesture (drag.js) and the chrome (catRail.js)
// meet here: this is the bit that talks to the server and reloads.
import { store, api } from './store.js';
import { showRail, hideRail, askScope, toast } from '../components/catRail.js';

export function recatOptions(rerender) {
  return {
    onStart: tx => showRail(store.categories, c => store.categoryColor(c), tx.cat),
    onEnd: () => hideRail(),
    onDrop: async (tx, cat) => {
      if (tx.cat === cat) return;
      const count = store.data.tx.filter(t => t.mkey === tx.mkey).length;
      const scope = count > 1 ? await askScope({ merchant: tx.merchant, category: cat, count }) : 'one';
      if (!scope) return;
      let r;
      try {
        r = await api('/api/category', { method: 'POST', body: JSON.stringify({ id: tx.id, category: cat, scope }) });
      } catch (e) {
        return toast('could not move it: ' + e.message);
      }
      await store.load(); rerender();
      toast(`${r.changed > 1 ? r.changed + ' charges' : tx.merchant} → ${cat}`, {
        label: 'Undo',
        onClick: async () => {
          await api('/api/category/revert', { method: 'POST', body: JSON.stringify(r.revert) }).catch(() => {});
          await store.load(); rerender();
        },
      });
    },
  };
}
