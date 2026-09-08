// Everything the drag-to-recategorize gesture needs on screen: the category rail that slides up while you
// drag, the "just this one / all of them" prompt on drop, and the undo toast afterwards.
import { el, clear } from '../lib/dom.js';

let railEl = null, toastEl = null, toastTimer = null, raf = 0;

function mount(id, cls) {
  const n = el('div', { id, class: cls });
  document.body.append(n);
  return n;
}

// The rail. Category chips are the drop targets ([data-drop-cat]); the one the row is already in is dimmed.
export function showRail(cats, colorFor, current) {
  toastEl?.classList.remove('up');                  // an undo toast must not sit on top of the rail
  railEl = railEl || mount('rail', 'rail');
  clear(railEl).append(el('div', { class: 'rail-label' }, 'drop into'),
    ...cats.map(c => el('div', {
      class: 'chip' + (c === current ? ' current' : ''), 'data-drop-cat': c === current ? null : c,
      style: { '--c': colorFor(c) },
    }, el('i', { class: 'dot' }), c)));
  cancelAnimationFrame(raf);                       // a frame queued by an earlier drag must not raise it again
  raf = requestAnimationFrame(() => railEl.classList.add('up'));
}

export function hideRail() {
  cancelAnimationFrame(raf);
  railEl?.classList.remove('up');
}

// "just this one" vs "all from this merchant" → resolves to 'one' | 'merchant' | null (cancelled).
export function askScope({ merchant, category, count }) {
  return new Promise(resolve => {
    const done = v => { back.remove(); resolve(v); };
    const card = el('div', { class: 'panel ask' },
      el('h3', {}, merchant),
      el('div', { class: 'muted' }, '→ ' + category),
      el('div', { class: 'ask-actions' },
        el('button', { class: 'primary', onclick: () => done('one') }, 'Just this one'),
        el('button', { onclick: () => done('merchant') }, `All ${count} · and future ones`),
        el('button', { class: 'muted', onclick: () => done(null) }, 'Cancel')));
    const back = el('div', { class: 'backdrop', onclick: e => { if (e.target === back) done(null); } }, card);
    document.body.append(back);
    document.addEventListener('keydown', function esc(e) {
      if (e.key === 'Escape') { done(null); document.removeEventListener('keydown', esc); }
    });
  });
}

// toast('moved 14 charges…', { label: 'Undo', onClick })
export function toast(text, action) {
  toastEl = toastEl || mount('toast', 'toast');
  clearTimeout(toastTimer);
  clear(toastEl).append(el('span', {}, text),
    action ? el('button', { onclick: () => { toastEl.classList.remove('up'); action.onClick(); } }, action.label) : null);
  requestAnimationFrame(() => toastEl.classList.add('up'));   // its own frame: a toast is never hidden by a racing call
  toastTimer = setTimeout(() => toastEl.classList.remove('up'), action ? 9000 : 3500);
}
