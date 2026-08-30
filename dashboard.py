"""Dashboard HTML, rendered from the ledger on each request (served by alertledger.py serve). Vanilla JS + SVG, no deps."""
import json
from datetime import date
from html import escape

import config
import ledger
import report


def collect(con, rules):
    rows = []
    for r in con.execute("SELECT t.*, a.institution, a.last_four FROM transactions t JOIN accounts a ON a.id=t.account_id ORDER BY t.date DESC"):
        cat, ignore = report.classify(r, rules)
        rows.append({"id": r["id"], "date": r["date"], "card": f"{'BofA' if 'America' in r['institution'] else r['institution']} ••{r['last_four'] or '????'}",
                     "merchant": r["description"], "amount": round(r["amount"], 2), "cat": cat,
                     "type": r["type"], "ignore": ignore, "status": r["status"]})
    stmts = [dict(r) for r in con.execute("SELECT s.statement_date AS date, s.balance, a.institution, a.last_four FROM statements s JOIN accounts a ON a.id=s.account_id ORDER BY 1")]
    for s in stmts:
        s["card"] = f"{'BofA' if 'America' in s['institution'] else s['institution']} ••{s['last_four']}"
    return rows, stmts


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>alertledger</title>
<style>
:root{color-scheme:light;--bg:#f6f6f4;--surface:#fcfcfb;--line:#e4e3df;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a8984;
 --s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#4a3aa7;--s8:#e34948;--good:#0ca30c;--bad:#d03b3b;--warn:#fab219}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){color-scheme:dark;--bg:#121211;--surface:#1a1a19;--line:#2e2e2c;--ink:#fff;--ink2:#c3c2b7;--ink3:#7e7d77;
 --s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}
header{display:flex;flex-wrap:wrap;gap:12px;align-items:center;padding:16px 20px;border-bottom:1px solid var(--line);background:var(--surface);position:sticky;top:0;z-index:2}
h1{font-size:16px;margin:0 12px 0 0;font-weight:600}h2{font-size:13px;font-weight:600;color:var(--ink2);margin:0 0 10px;text-transform:uppercase;letter-spacing:.04em}
select,input{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 8px}
.chip{border:1px solid var(--line);border-radius:999px;padding:4px 10px;cursor:pointer;background:var(--bg);color:var(--ink2);display:inline-flex;gap:6px;align-items:center}
.chip.on{background:var(--surface);color:var(--ink);border-color:var(--ink3)}.chip i{width:10px;height:10px;border-radius:2px;display:inline-block}
main{padding:20px;display:grid;gap:20px;grid-template-columns:repeat(12,minmax(0,1fr));max-width:1400px;margin:0 auto}
.card{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;grid-column:span 12;min-width:0}
@media(min-width:900px){.c4{grid-column:span 4}.c6{grid-column:span 6}.c8{grid-column:span 8}}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{padding:12px 14px;border:1px solid var(--line);border-radius:8px}.kpi .l{font-size:12px;color:var(--ink2)}.kpi .v{font-size:24px;font-weight:600;letter-spacing:-.01em;font-variant-numeric:tabular-nums}
.kpi .d{font-size:12px;color:var(--ink3)}.up{color:var(--bad)}.down{color:var(--good)}
svg{width:100%;height:auto;display:block;overflow:visible}text{fill:var(--ink2);font-size:11px}.axis line,.grid line{stroke:var(--line)}.bar{rx:0}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:11px;color:var(--ink2);text-transform:uppercase;letter-spacing:.04em;font-weight:600;position:sticky;top:0;background:var(--surface)}
td.n,th.n{text-align:right}.muted{color:var(--ink3)}.tbl{max-height:520px;overflow:auto}
header>*{flex:0 1 auto}#q{flex:1 1 200px;max-width:320px}
#tip{position:fixed;pointer-events:none;background:var(--ink);color:var(--bg);padding:6px 9px;border-radius:6px;font-size:12px;display:none;z-index:9;white-space:nowrap}
.hbar{display:grid;grid-template-columns:130px 1fr 80px;gap:8px;align-items:center;margin:5px 0}.hbar .t{height:14px;background:var(--s1);border-radius:0 3px 3px 0;min-width:2px}
.hbar .v{text-align:right}.gap{color:var(--bad)}.ok{color:var(--good)}
footer{padding:12px 20px;color:var(--ink3);font-size:12px}
</style></head><body>
<div id="tip"></div>
<header><h1>alertledger</h1>
 <select id="month"></select>
 <span id="cards"></span>
 <input id="q" placeholder="search merchant…">
 <button id="syncbtn" class="chip on" title="pull new alert emails now">⟳ Sync now</button><span id="synced" class="muted" style="font-size:12px">__LAST__</span>
</header>
<main>
 <section class="card"><div class="kpis" id="kpis"></div></section>
 <section class="card c8"><h2>Monthly spend by card · last 12 months</h2><div id="monthly"></div></section>
 <section class="card c4"><h2>Categories · <span id="mlabel"></span></h2><div id="cats"></div></section>
 <section class="card c6"><h2>Recurring charges</h2><div class="tbl"><table id="recur"></table></div></section>
 <section class="card c6"><h2>Statement checksum <span class="muted">(bank balance vs. our alerts, per cycle)</span></h2><div class="tbl"><table id="chk"></table></div></section>
 <section class="card"><h2>Transactions · <span id="tcount"></span></h2><div class="tbl"><table id="tx"></table></div></section>
</main>
<footer>alerts are authorization-time (amounts may drift on posting) · edit categories in rules.toml</footer>
<script>
const DATA=__DATA__;
const SLOT=['--s1','--s2','--s3','--s4','--s5','--s6','--s7','--s8'];
const cards=[...new Set(DATA.tx.map(t=>t.card))].sort();const cardColor=Object.fromEntries(cards.map((c,i)=>[c,`var(${SLOT[i%8]})`]));
const fmt=n=>(n<0?'−':'')+'$'+Math.abs(n).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
const spend=DATA.tx.filter(t=>t.amount<0&&!t.ignore&&t.type!=='transfer');
const lastM=[...new Set(spend.map(t=>t.date.slice(0,7)))].sort().pop()||new Date().toISOString().slice(0,7);
const firstM=[...new Set(spend.map(t=>t.date.slice(0,7)))].sort()[0]||lastM;
const months=(()=>{const out=[];let [y,m]=lastM.split('-').map(Number);const [fy,fm]=firstM.split('-').map(Number);while(y>fy||(y===fy&&m>=fm)){out.push(`${y}-${String(m).padStart(2,'0')}`);if(--m===0){m=12;y--}}return out})();
const state={month:months[0]||new Date().toISOString().slice(0,7),cards:new Set(cards),q:''};
const tip=document.getElementById('tip');const showTip=(e,h)=>{tip.innerHTML=h;tip.style.display='block';tip.style.left=(e.clientX+12)+'px';tip.style.top=(e.clientY+12)+'px'};const hideTip=()=>tip.style.display='none';
function el(tag,attrs={},...kids){const n=document.createElementNS(tag==='svg'||attrs.ns?'http://www.w3.org/2000/svg':'http://www.w3.org/1999/xhtml',tag);for(const[k,v]of Object.entries(attrs)){if(k==='ns')continue;k.startsWith('on')?n.addEventListener(k.slice(2),v):n.setAttribute(k,v)}for(const k of kids)n.append(k);return n}
const sel=document.getElementById('month');months.forEach(m=>sel.append(new Option(m,m)));sel.value=state.month;sel.onchange=()=>{state.month=sel.value;render()};
const cc=document.getElementById('cards');cards.forEach(c=>{const b=el('span',{class:'chip on',onclick:()=>{state.cards.has(c)?state.cards.delete(c):state.cards.add(c);b.classList.toggle('on');render()}},el('i',{style:`background:${cardColor[c]}`}),c);cc.append(b)});
document.getElementById('q').oninput=e=>{state.q=e.target.value.toLowerCase();renderTx()};
const vis=t=>state.cards.has(t.card);
function render(){
  const inM=spend.filter(t=>vis(t)&&t.date.startsWith(state.month));const prevM=months[months.indexOf(state.month)+1];
  const prev=prevM?spend.filter(t=>vis(t)&&t.date.startsWith(prevM)):[];
  const tot=a=>a.reduce((s,t)=>s-t.amount,0);const T=tot(inM),P=tot(prev);
  const income=DATA.tx.filter(t=>vis(t)&&t.amount>0&&t.type==='transfer'&&t.date.startsWith(state.month)).reduce((s,t)=>s+t.amount,0);
  const k=document.getElementById('kpis');k.innerHTML='';
  const kpi=(l,v,d,cls)=>k.append(el('div',{class:'kpi'},el('div',{class:'l'},l),el('div',{class:'v'},v),el('div',{class:'d '+(cls||'')},d)));
  kpi('Spend · '+state.month,fmt(T),prevM?((T>=P?'▲ ':'▼ ')+fmt(Math.abs(T-P))+' vs '+prevM):'—',T>P?'up':'down');
  kpi('Transactions',inM.length,inM.length?fmt(T/inM.length)+' avg':'');
  kpi('Income · Zelle/deposits',fmt(income),'');
  const byCard={};inM.forEach(t=>byCard[t.card]=(byCard[t.card]||0)-t.amount);Object.entries(byCard).sort((a,b)=>b[1]-a[1]).forEach(([c,v])=>kpi(c,fmt(v),Math.round(100*v/T)+'% of month'));
  renderMonthly();renderCats(inM);renderTx();document.getElementById('mlabel').textContent=state.month;
}
function renderMonthly(){
  const ms=months.slice(0,12).reverse();const W=700,H=220,pl=44,pb=24,pt=8;const box=document.getElementById('monthly');box.innerHTML='';
  const agg=ms.map(m=>{const o={};spend.filter(t=>vis(t)&&t.date.startsWith(m)).forEach(t=>o[t.card]=(o[t.card]||0)-t.amount);return o});
  const max=Math.max(1,...agg.map(o=>Object.values(o).reduce((a,b)=>a+b,0)));const y=v=>pt+(H-pt-pb)*(1-v/max);
  const s=el('svg',{viewBox:`0 0 ${W} ${H}`});const g=el('g',{class:'grid',ns:1});
  [0,.25,.5,.75,1].forEach(f=>{g.append(el('line',{ns:1,x1:pl,x2:W,y1:y(max*f),y2:y(max*f)}));g.append(el('text',{ns:1,x:pl-6,y:y(max*f)+4,'text-anchor':'end'},'$'+Math.round(max*f).toLocaleString()))});s.append(g);
  const bw=(W-pl)/ms.length;ms.forEach((m,i)=>{let acc=0;const x=pl+i*bw+bw*.18,w=bw*.64;
    cards.filter(c=>agg[i][c]).forEach(c=>{const v=agg[i][c];const r=el('rect',{ns:1,x,y:y(acc+v),width:w,height:Math.max(0,y(acc)-y(acc+v)-2),fill:cardColor[c],
      onmousemove:e=>showTip(e,`<b>${m}</b> · ${c}<br>${fmt(v)}`),onmouseleave:hideTip});s.append(r);acc+=v});
    if(m===state.month)s.append(el('rect',{ns:1,x:pl+i*bw+2,y:pt,width:bw-4,height:H-pt-pb,fill:'none',stroke:'var(--ink3)','stroke-dasharray':'3 3',rx:4}));
    s.append(el('text',{ns:1,x:x+w/2,y:H-6,'text-anchor':'middle'},m.slice(2)))});
  box.append(s);
}
function renderCats(inM){
  const o={};inM.forEach(t=>o[t.cat]=(o[t.cat]||0)-t.amount);const rows=Object.entries(o).sort((a,b)=>b[1]-a[1]);const max=rows[0]?.[1]||1;
  const box=document.getElementById('cats');box.innerHTML='';if(!rows.length)box.append(el('div',{class:'muted'},'no spend this month'));
  rows.forEach(([c,v])=>box.append(el('div',{class:'hbar'},el('span',{},c),el('div',{},el('div',{class:'t',style:`width:${100*v/max}%`})),el('span',{class:'v'},fmt(v)))));
}
function table(id,head,rows){const t=document.getElementById(id);t.innerHTML='';t.append(el('thead',{},el('tr',{},...head.map(h=>el('th',{class:h.n?'n':''},h.t)))));
  const b=el('tbody');rows.forEach(r=>b.append(el('tr',{},...r.map((c,i)=>el('td',{class:head[i].n?'n':''},c)))));t.append(b)}
table('recur',[{t:'merchant'},{t:'card'},{t:'last'},{t:'hits',n:1},{t:'$/mo',n:1}],DATA.recurring.map(r=>[r.merchant,r.card,r.last,r.hits,fmt(r.amount)]));
table('chk',[{t:'card'},{t:'statement'},{t:'bank',n:1},{t:'ours',n:1},{t:'gap',n:1}],DATA.checksum.map(r=>[r.card,r.date,fmt(r.bank),fmt(r.ours),el('span',{class:Math.abs(r.gap)<1?'ok':'gap'},fmt(r.gap))]));
function renderTx(){const rows=DATA.tx.filter(t=>vis(t)&&t.date.startsWith(state.month)&&(!state.q||(t.merchant+' '+t.cat).toLowerCase().includes(state.q)));
  document.getElementById('tcount').textContent=rows.length+' rows';
  table('tx',[{t:'date'},{t:'card'},{t:'merchant'},{t:'category'},{t:'amount',n:1}],rows.map(t=>[t.date,el('span',{},el('i',{class:'chip',style:`padding:0;border:0;width:10px;height:10px;background:${cardColor[t.card]};display:inline-block;border-radius:2px;margin-right:6px`}),t.card),
    t.merchant,el('span',{class:t.ignore?'muted':''},t.ignore?'ignored':t.type==='transfer'?'income':t.cat),el('span',{class:t.amount>0?'ok':''},fmt(t.amount))]))}
document.getElementById('syncbtn').onclick=async()=>{const b=document.getElementById('syncbtn');b.textContent='syncing…';b.disabled=true;
  try{const r=await fetch('/api/sync',{method:'POST'});const j=await r.json();if(j.error)throw new Error(j.error);location.reload()}catch(e){b.textContent='sync failed: '+e.message;b.disabled=false}};
render();
</script></body></html>"""


def recurring_data(con, rules):
    from datetime import datetime
    from collections import defaultdict
    groups = defaultdict(list)
    for row, cat in report.spend_rows(con, rules):
        groups[report.merchant_key(row)].append((datetime.fromisoformat(row["date"]).date(), -row["amount"], row["last_four"], row["institution"]))
    out = []
    for k, items in groups.items():
        items.sort(); hits = set()
        for (d0, a0, *_), (d1, a1, *_) in zip(items, items[1:]):
            if 26 <= (d1 - d0).days <= 35 and abs(a1 - a0) <= max(1.0, 0.05 * a0):
                hits.update({(d0, a0), (d1, a1)})
        if len(hits) >= 2:
            last = items[-1]
            out.append({"merchant": k, "amount": last[1], "last": last[0].isoformat(), "hits": len(hits),
                        "card": f"{'BofA' if 'America' in last[3] else last[3]} ••{last[2]}"})
    return sorted(out, key=lambda r: -r["amount"])


def checksum_data(con):
    from datetime import timedelta
    rows = con.execute("SELECT s.*, a.institution, a.last_four FROM statements s JOIN accounts a ON a.id=s.account_id ORDER BY s.account_id, s.statement_date").fetchall()
    prev, out = {}, []
    for r in rows:
        p = prev.get(r["account_id"]); prev[r["account_id"]] = r
        since = p["statement_date"] if p else (date.fromisoformat(r["statement_date"]) - timedelta(days=31)).isoformat()
        ours = con.execute("SELECT COALESCE(SUM(-amount),0) FROM transactions WHERE account_id=? AND date>? AND date<=? AND type NOT IN ('transfer')",
                           (r["account_id"], since, r["statement_date"])).fetchone()[0]
        out.append({"card": f"{'BofA' if 'America' in r['institution'] else r['institution']} ••{r['last_four']}", "date": r["statement_date"],
                    "bank": r["balance"], "ours": ours, "gap": r["balance"] - ours})
    return sorted(out, key=lambda r: r["date"], reverse=True)


def render(con) -> str:
    rules = report.load_rules()
    tx, stmts = collect(con, rules)
    data = {"tx": tx, "statements": stmts, "recurring": recurring_data(con, rules), "checksum": checksum_data(con)}
    last = ledger.get_meta(con, "last_sync")
    return (PAGE.replace("__DATA__", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
                .replace("__LAST__", escape("last sync " + last.replace("T", " ")) if last else "never synced"))


if __name__ == "__main__":
    print(render(ledger.connect(str(config.DB))))
