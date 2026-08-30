import { el } from '../lib/dom.js';

// Staged upload: tall drop area → "Choose files · N chosen" → Import / Clear. onImport(files) runs only on Import.
export function DropZone({ accept = '.csv,.pdf', onImport, hint = 'Drop PDF or CSV files here' }) {
  let staged = [];
  const input = el('input', { type: 'file', accept, multiple: true, style: { display: 'none' }, onchange: e => { add([...e.target.files]); e.target.value = ''; } });
  const chosen = el('span', { class: 'dz-chosen' }, 'No files chosen');
  const list = el('ul', { class: 'dz-list' });
  const importBtn = el('button', { class: 'primary', disabled: true, onclick: () => { const f = staged; clear(); onImport(f); } }, 'Import');
  const clearBtn = el('button', { disabled: true, onclick: () => clear() }, 'Clear');

  function refresh() {
    chosen.textContent = staged.length ? `${staged.length} file${staged.length > 1 ? 's' : ''} chosen` : 'No files chosen';
    list.replaceChildren(...staged.map((f, i) => el('li', {}, el('span', { class: 'grow' }, f.name), el('span', { class: 'muted' }, Math.round(f.size / 1024) + ' KB'),
      el('button', { class: 'dz-x', 'aria-label': 'remove', onclick: () => { staged.splice(i, 1); refresh(); } }, '✕'))));
    importBtn.disabled = clearBtn.disabled = !staged.length;
    importBtn.textContent = staged.length > 1 ? `Import ${staged.length} files` : 'Import';
  }
  function add(files) {
    for (const f of files) if (!staged.some(s => s.name === f.name && s.size === f.size)) staged.push(f);
    refresh();
  }
  function clear() { staged = []; refresh(); }

  const area = el('div', { class: 'dropzone', role: 'button', tabindex: 0, onclick: () => input.click(),
    onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') input.click(); },
    ondragover: e => { e.preventDefault(); area.classList.add('over'); },
    ondragleave: () => area.classList.remove('over'),
    ondrop: e => { e.preventDefault(); area.classList.remove('over'); add([...e.dataTransfer.files]); } },
    el('div', { class: 'dz-hint' }, hint));

  return el('div', { class: 'uploader' },
    area,
    el('div', { class: 'dz-choose' }, el('button', { onclick: () => input.click() }, 'Choose files'), chosen, input),
    list,
    el('div', { class: 'dz-actions' }, importBtn, clearBtn));
}
