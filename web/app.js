import { store } from './lib/store.js';
import { clear } from './lib/dom.js';
import { Nav } from './components/nav.js';
import { SpendingView } from './views/spending.js';
import { TransactionsView } from './views/transactions.js';
import { TrendsView } from './views/trends.js';
import { DataView } from './views/data.js';
import { BudgetView } from './views/budget.js';

const VIEWS = { spending: SpendingView, budget: BudgetView, transactions: TransactionsView, trends: TrendsView, data: DataView };
const root = document.getElementById('app');

function render(opts = {}) {
  const tab = store.state.tab;
  Nav(document.getElementById('nav'), tab, goto);
  const view = VIEWS[tab]({ rerender: render, goto });
  clear(root).append(view);
  if (opts.keepFocus) {                                  // re-focus the search box after a rerender triggered by typing
    const inp = root.querySelector('input[placeholder="search merchant…"]');
    if (inp) { inp.focus(); inp.setSelectionRange(inp.value.length, inp.value.length); }
  }
}

function goto(tab) {
  store.state.tab = tab;
  history.replaceState(null, '', '#' + tab);
  window.scrollTo(0, 0);
  render();
}

store.state.tab = VIEWS[location.hash.slice(1)] ? location.hash.slice(1) : 'spending';
store.load().then(() => render()).catch(e => { root.innerHTML = `<div class="empty">could not load data: ${e.message}</div>`; });

// server pushes an event when a sync records genuinely new purchases; reload without a manual refresh
new EventSource('/api/events').onmessage = () => store.load().then(() => render());
