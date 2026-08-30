import { el } from '../lib/dom.js';

// Segmented({ options: [{value, label}], value, onChange })
export function Segmented({ options, value, onChange }) {
  return el('div', { class: 'seg', role: 'tablist' },
    ...options.map(o => el('button', { role: 'tab', class: o.value === value ? 'on' : '', 'aria-selected': o.value === value, onclick: () => onChange(o.value) }, o.label)));
}
