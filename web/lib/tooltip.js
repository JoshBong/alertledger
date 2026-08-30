const node = () => document.getElementById('tooltip');
export function show(ev, html) {
  const t = node();
  t.innerHTML = html;
  t.style.display = 'block';
  t.style.left = Math.min(ev.clientX + 12, innerWidth - 190) + 'px';
  t.style.top = (ev.clientY + 12) + 'px';
}
export function hide() { node().style.display = 'none'; }
// attach(elm, () => 'html') wires hover tooltips on any element
export function attach(elm, html) {
  elm.addEventListener('mousemove', ev => show(ev, html()));
  elm.addEventListener('mouseleave', hide);
  return elm;
}
