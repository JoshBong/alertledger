// Tiny DOM helpers. el('div', {class:'x', onclick: fn}, ...children) — pass ns:true for SVG.
const SVG = 'http://www.w3.org/2000/svg';

export function el(tag, attrs = {}, ...children) {
  const { ns, ...rest } = attrs;
  const node = ns ? document.createElementNS(SVG, tag) : document.createElement(tag);
  for (const [k, v] of Object.entries(rest)) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
    else if (k === 'html') node.innerHTML = v;
    else if (k === 'style' && typeof v === 'object') for (const [prop, val] of Object.entries(v)) prop.startsWith('--') ? node.style.setProperty(prop, val) : (node.style[prop] = val);
    else node.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null && c !== false) node.append(c);
  return node;
}

export const svg = (tag, attrs = {}, ...children) => el(tag, { ns: true, ...attrs }, ...children);

export function clear(node) { node.replaceChildren(); return node; }

export function option(label, value = label) { return new Option(label, value); }
