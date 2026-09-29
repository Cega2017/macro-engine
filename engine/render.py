import json, os, pandas as pd
from plotly.offline import get_plotlyjs
PLOTLY = get_plotlyjs().replace("\ufffd", "\\uFFFD")
from . import config as C

CSS = """
*{box-sizing:border-box} :root{color-scheme:dark;background:#000} body{margin:0;background:#000;color:#d0d0d0;font:12px Menlo,Consolas,'DejaVu Sans Mono',monospace}
.top{display:flex;align-items:center;gap:16px;padding:6px 16px;background:#0a0a0a;border-bottom:1px solid #f28c28;position:sticky;top:env(safe-area-inset-top,0px);z-index:10;flex-wrap:wrap}
.tbl,.mos{overflow-x:auto}
.logo{color:#000;background:#f28c28;font-weight:bold;padding:2px 8px}.asof{color:#888;font-size:11px}
.tabs{display:flex;gap:2px;flex-wrap:wrap}.tabs button{background:#1a1a1a;color:#f28c28;border:1px solid #333;padding:4px 10px;font:inherit;cursor:pointer}
.tabs button.on{background:#f28c28;color:#000}.tabs button span{color:#888;margin-right:4px}.tabs button.on span{color:#000}
.pane{display:none;padding-block:10px;padding-inline:16px}.pane.on{display:block}
.read{border:1px solid #333;border-left:3px solid #f28c28;background:#080808;padding:6px 12px;margin-bottom:10px}.read ul{margin:4px 0;padding-left:18px}.read li{margin:3px 0;line-height:1.5}
.tt{color:#f28c28;font-weight:bold;letter-spacing:.5px;margin:4px 0}
.card{border:1px solid #222;margin-bottom:12px;background:#000}.ch{padding:6px 10px;border-bottom:1px solid #1c1c1c}.ch .t{color:#fff;font-weight:bold}.ch .s{color:#888;font-size:11px;margin-left:10px}
.cb{display:flex;gap:8px}.plot{flex:1;min-width:0}.ss{width:250px;padding:8px;border-left:1px solid #1c1c1c}.sst{color:#fff;font-size:14px;text-align:center;margin-bottom:6px}
.ss table{width:100%;border-collapse:collapse}.ss td,.ss th{padding:2px 3px;font-size:11px}.ss th{color:#888;text-align:right}
td.a{color:#f28c28}td.w,.w{color:#fff}td.n{text-align:right}.g{color:#4caf50}.r{color:#e05252}.hz{color:#000;background:#e0b64a}.mz{color:#e0b64a}
.tbl table,.mos table{border-collapse:collapse;width:100%}.tbl{margin:10px 0}.tbl th{color:#888;text-align:right;padding:3px 6px;border-bottom:1px solid #333;font-weight:normal}
.tbl th:first-child{text-align:left}.tbl td{padding:3px 6px;border-bottom:1px solid #111;text-align:right}.tbl td.nm,.tbl td.txt{text-align:left}.tbl tr:hover td{background:#111}td.nm{color:#f28c28}td.txt{color:#999;font-size:11px}
.t50{display:none} body.tl .t50{display:inline} body.tl .t21{display:none} #tt{background:#1a1a1a;color:#f28c28;border:1px solid #333;padding:3px 8px;font:inherit;cursor:pointer}
.rb{float:right;display:flex;gap:2px}.rb button{background:#1a1a1a;color:#f28c28;border:1px solid #333;padding:1px 6px;font:inherit;font-size:10px;cursor:pointer}.rb button.on{background:#f28c28;color:#000}
.ss{overflow-x:auto}
@media (max-width:700px){.top{position:static}.rb{float:none;margin-top:4px}}
#hk{background:#1a1a1a;color:#f28c28;border:1px solid #333;padding:3px 8px;font:inherit;cursor:pointer}td.sp{text-align:center;padding:0 4px!important}td.sp svg{vertical-align:middle}
#help{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:50}#help .hb{max-width:520px;margin:12vh auto;background:#0a0a0a;border:1px solid #f28c28;padding:12px 16px}#help td{padding:3px 8px}
.stale{color:#000;background:#e05252;font-size:10px;padding:0 3px}.warn{color:#000;background:#e0b64a;padding:0 3px}
.brief{border:1px solid #333;border-left:3px solid #f28c28;padding:6px 12px;margin-bottom:10px}.brief li{margin:5px 0;line-height:1.5}
.mosaic{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:8px;margin-bottom:10px}.mos{border:1px solid #222;padding:6px 8px}.mos td{padding:2px 4px}
.alerts{border:1px solid #333;padding:6px 12px}.alerts li{margin:2px 0}
@media (max-width:900px){.cb{flex-direction:column}.ss{width:100%;border-left:none;border-top:1px solid #1c1c1c}}
"""

JS = r"""
function yfit(gd,ev){ // rescale y axes to the visible x window after a lookback button / zoom
 const keys=Object.keys(ev||{}); if(!keys.some(k=>/^xaxis\d*\.(range|autorange)/.test(k)))return;
 const L=gd._fullLayout, acc={}, auto={};
 gd._fullData.forEach(t=>{if(t.visible===false||t.visible==="legendonly"||t.orientation==="h")return;
  const xa="xaxis"+(t.xaxis||"x").slice(1), ya="yaxis"+(t.yaxis||"y").slice(1), X=L[xa], Y=L[ya]; if(!X||!Y||X.type!=="date"||!t.x||!(t.y||t.close))return;
  if(X.autorange){auto[ya]=1;return}
  const lo=String(X.range[0]).slice(0,10), hi=String(X.range[1]).slice(0,10); const a=acc[ya]||(acc[ya]={mn:Infinity,mx:-Infinity,log:Y.type==="log"});
  const Ys=t.type==="candlestick"?[t.low,t.high]:[t.y];
  for(let i=0;i<t.x.length;i++){const x=String(t.x[i]).slice(0,10);if(x<lo||x>hi)continue;for(const yy of Ys){const v=yy&&yy[i];if(v==null||!isFinite(v))continue;if(v<a.mn)a.mn=v;if(v>a.mx)a.mx=v}}
  if(t.type==="bar"||t.fill==="tozeroy"){a.mn=Math.min(a.mn,0);a.mx=Math.max(a.mx,0)}});
 const upd={}; Object.keys(auto).forEach(k=>upd[k+".autorange"]=true);
 Object.entries(acc).forEach(([k,a])=>{if(!isFinite(a.mn))return;let mn=a.mn,mx=a.mx;if(a.log){if(mn<=0)return;mn=Math.log10(mn);mx=Math.log10(mx)}
  const p=(mx-mn)*0.06||Math.abs(mx)*0.05||1; upd[k+".range"]=[mn-p,mx+p]});
 if(Object.keys(upd).length)Plotly.relayout(gd,upd)}
const T=%s; const drawn={};
const CFG={displaylogo:false,responsive:false,showSendToCloud:false,showLink:false,modeBarButtonsToRemove:['lasso2d','select2d','toImage','sendDataToCloud']};
const WIN=[['1M',1],['3M',3],['6M',6],['YTD','ytd'],['1Y',12],['3Y',36],['All','all']];
function iso(d){return d.toISOString().slice(0,10)}
function span(gd){let mn='9999',mx='0000';gd._fullData.forEach(t=>{const X=gd._fullLayout['xaxis'+(t.xaxis||'x').slice(1)];if(!X||X.type!=='date'||!t.x)return;
 for(let i=0;i<t.x.length;i++){const s=String(t.x[i]).slice(0,10);if(s<mn)mn=s;if(s>mx)mx=s}});return mn<mx?[mn,mx]:null}
function setWin(gd,w){const sp=span(gd);if(!sp)return;let s=sp[0];const e=new Date(sp[1]+'T00:00:00Z');
 if(w==='ytd'){s=e.getUTCFullYear()+'-01-01';if(s<sp[0])s=sp[0]}else if(w!=='all'){const y=e.getUTCFullYear(),m=e.getUTCMonth()-w,dd=e.getUTCDate();
  const last=new Date(Date.UTC(y,m+1,0)).getUTCDate();s=iso(new Date(Date.UTC(y,m,Math.min(dd,last))));if(s<sp[0])s=sp[0]}
 const upd={};Object.keys(gd._fullLayout).forEach(k=>{if(/^xaxis\d*$/.test(k)&&gd._fullLayout[k].type==='date'){upd[k+'.range']=[s,sp[1]];upd[k+'.autorange']=false}});
 gd._win=w;gd._setting=1;Plotly.relayout(gd,upd).then(()=>{gd._setting=0});markWin(gd)}
function markWin(gd){if(gd._bar)gd._bar.querySelectorAll('button').forEach(b=>b.classList.toggle('on',String(b.dataset.w)===String(gd._win)))}
function rangeBar(gd){const card=gd.closest('.card');if(!card||!gd.layout.meta||!gd.layout.meta.range)return;const ch=card.querySelector('.ch');
 const bar=document.createElement('span');bar.className='rb';WIN.forEach(([l,w])=>{const b=document.createElement('button');b.textContent=l;b.dataset.w=w;
  b.addEventListener('click',()=>setWin(gd,w));bar.appendChild(b)});ch.appendChild(bar);gd._bar=bar;gd._win=gd.layout.meta.win||'all';markWin(gd)}
function hook(el){ setTimeout(()=>fitLeg(el),0); // fixed-height, explicit-width plots that re-fit y on every view change and re-size only when visible
 el.on('plotly_relayout',ev=>{const k=Object.keys(ev||{});if(k.some(x=>/^xaxis\d*\.autorange/.test(x)&&ev[x]===true)){el._win='all';markWin(el)}
  else if(!el._setting&&k.some(x=>/^xaxis\d*\.range/.test(x))){el._win=null;markWin(el)}yfit(el,ev)});
 el.on('plotly_restyle',()=>yfit(el,{'xaxis.range[0]':1}));
 if(window.ResizeObserver)new ResizeObserver(()=>fitW(el)).observe(el)}
function fitW(el){if(!el._fullLayout||el.offsetParent===null)return;const w=el.clientWidth;if(w>=80&&Math.abs(w-el._fullLayout.width)>2)Plotly.relayout(el,{width:w}).then(()=>fitLeg(el));}
function fitLeg(el){const L=el._fullLayout;if(!L||!L.showlegend||!L.legend||!L.legend._height)return;const need=Math.ceil(L.legend._height)+8;
 if(Math.abs(need-L.margin.t)>4)Plotly.relayout(el,{'margin.t':Math.max(need,20),height:(el.layout._h0||(el.layout._h0=L.height))+Math.max(0,need-28)}).then(()=>{el.style.height=el._fullLayout.height+'px'})}
window.hookPlot=function(el){el.style.height=(el.layout.height||420)+'px';hook(el)};
function draw(c,n){const el=document.getElementById(c.id); if(!el)return;
 if(el.clientWidth<80&&n<200){setTimeout(()=>draw(c,n+1),50);return}   // viewer frame not laid out yet: wait instead of drawing at zero width
 const f=c.fig; f.layout.autosize=false; f.layout.width=el.clientWidth; el.style.height=(f.layout.height||420)+'px';
 Plotly.newPlot(el,f.data,f.layout,CFG).then(gd=>{hook(gd);rangeBar(gd);if(gd.layout.meta&&gd.layout.meta.win&&gd.layout.meta.win!=='all')setWin(gd,gd.layout.meta.win);
  else if(gd.layout.xaxis&&gd.layout.xaxis.range)yfit(gd,{'xaxis.range[0]':1})})}
function show(k){document.querySelectorAll('.pane').forEach(p=>p.classList.toggle('on',p.id==k));document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('on',b.dataset.k==k));
 if(!drawn[k]){(T[k]||[]).forEach(c=>draw(c,0));drawn[k]=1} else requestAnimationFrame(()=>document.querySelectorAll('#'+k+' .js-plotly-plot').forEach(fitW));
 try{localStorage.setItem('mt_tab',k)}catch(e){} window.scrollTo(0,0)}
let kb='',kt=null; const TB=()=>[...document.querySelectorAll('.tabs button')];
function help(on){const h=document.getElementById('help');h.style.display=(on===undefined?h.style.display!=='block':on)?'block':'none'}
document.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)||e.metaKey||e.ctrlKey||e.altKey)return;const b=TB();const i=b.findIndex(x=>x.classList.contains('on'));
 if(e.key=='ArrowRight'&&i<b.length-1)show(b[i+1].dataset.k);else if(e.key=='ArrowLeft'&&i>0)show(b[i-1].dataset.k);
 else if(/^[0-9]$/.test(e.key)){kb+=e.key;clearTimeout(kt);const go=()=>{const n=+kb;kb='';if(b[n])show(b[n].dataset.k)};if(kb.length>=2||+kb>1)go();else kt=setTimeout(go,600)}
 else if(e.key=='t'||e.key=='T')tog();else if(e.key=='?')help();else if(e.key=='Escape')help(false);else if(e.key=='g')window.scrollTo(0,0)});
function tog(on){const b=document.body;if(on===undefined){on=!b.classList.contains('tl')}b.classList.toggle('tl',on);document.getElementById('tt').textContent='TREND: '+(on?'50/200 SMA':'21 EMA');try{localStorage.setItem('mt_tl',on?'1':'0')}catch(e){}}
try{if(localStorage.getItem('mt_tl')==='1')tog(true)}catch(e){}
document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>show(b.dataset.k)));
document.getElementById('tt').addEventListener('click',()=>tog());document.getElementById('hk').addEventListener('click',()=>help());
document.getElementById('help').addEventListener('click',()=>help(false));
let s='brief';try{s=localStorage.getItem('mt_tab')||'brief'}catch(e){} if(!document.getElementById(s))s='brief'; show(s);
"""

HELP = """<div id='help'><div class='hb'><div class='tt'>KEYBOARD</div><table>
<tr><td class='a'>0–9</td><td>jump to F0–F9</td></tr><tr><td class='a'>1 then 0–4</td><td>F10–F14 (type both digits quickly)</td></tr>
<tr><td class='a'>← →</td><td>previous / next tab</td></tr><tr><td class='a'>T</td><td>toggle trend: 21 EMA vs 50/200 SMA</td></tr>
<tr><td class='a'>G</td><td>back to top</td></tr><tr><td class='a'>?</td><td>this help (Esc or click to close)</td></tr>
<tr><td class='a'>Charts</td><td>lookback buttons in each chart's title bar; drag to zoom; double-click to reset; click legend items to hide</td></tr></table></div></div>"""

def html(tabs, asof, log, fragment=False):
    nav = "".join(f"<button data-k='{t['key']}'><span>F{i}</span>{t['title']}</button>" for i, t in enumerate(tabs))
    panes, figs = "", {}
    for t in tabs:
        body = ""
        if t.get("read"): body += "<div class='read'><div class='tt'>READ</div><ul>" + "".join(f"<li>{r}</li>" for r in t["read"]) + "</ul></div>"
        if t.get("html"): body += t["html"]
        if t.get("table"): body += t["table"]
        for c in t.get("cards", []):
            side = c["side"] if c.get("side") else "<div class='ss'></div>"
            body += (f"<div class='card'><div class='ch'><span class='t'>{c['title']}</span><span class='s'>{c.get('sub','')}</span></div>"
                     f"<div class='cb'><div class='plot' id='{c['id']}'></div>{side}</div></div>")
        figs[t["key"]] = [dict(id=c["id"], fig=json.loads(c["fig"])) for c in t.get("cards", [])]
        if t.get("html2"): body += t["html2"]
        panes += f"<div class='pane' id='{t['key']}'>{body}</div>"
    head = (f"<title>Macro Terminal</title><style>{CSS}</style><script>{PLOTLY}</script>" if fragment else
            f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Macro Terminal</title>"
            f"<style>{CSS}</style><script>{PLOTLY}</script></head><body>")
    tail = "" if fragment else "</body></html>"
    return (head + f"<div class='top'><span class='logo'>MACRO TERMINAL</span>"
            f"<span class='asof'>tape as of {asof:%Y-%m-%d} · built {pd.Timestamp.now():%Y-%m-%d %H:%M} · data: {log}</span><button id='tt'>TREND: 21 EMA</button><button id='hk' title='keyboard shortcuts'>?</button><div class='tabs'>{nav}</div></div>{panes}{HELP}"
            f"<script>{JS % json.dumps(figs, separators=(',',':'))}</script>" + tail)
