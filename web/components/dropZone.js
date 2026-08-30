import { el } from '../lib/dom.js';

// DropZone({ accept, onFiles(files) }) — click or drag-and-drop, multi-file.
export function DropZone({ accept = '.csv,.pdf', onFiles, label = 'Drop bank CSV or statement PDF files here — or click to choose' }) {
  const input = el('input', { type: 'file', accept, multiple: true, style: { display: 'none' }, onchange: e => { onFiles([...e.target.files]); e.target.value = ''; } });
  const zone = el('div', { class: 'dropzone', role: 'button', tabindex: 0, onclick: () => input.click(),
    onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') input.click(); },
    ondragover: e => { e.preventDefault(); zone.classList.add('over'); },
    ondragleave: () => zone.classList.remove('over'),
    ondrop: e => { e.preventDefault(); zone.classList.remove('over'); onFiles([...e.dataTransfer.files]); } },
    el('div', { class: 'dz-glyph' }, '⬇'), el('div', {}, label), el('div', { class: 'muted' }, 'Chase: statements PDF (account + date detected from the filename) or activity CSV · BofA: activity CSV'), input);
  return zone;
}
