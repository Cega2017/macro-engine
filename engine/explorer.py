"""F14 EXPLORER: interactive PCA / correlation / attribution on any mix of ETFs and large-cap stocks.
All math runs in the browser on embedded daily returns (3y). Nothing here is fitted in Python except data prep."""
import json, numpy as np, pandas as pd
from . import config as C, data

GROUPS = {
    "Equity index": ["SPY", "QQQ", "IWM", "DIA", "RSP"],
    "Style / factor": ["IWF", "IWD", "MTUM", "SPHB", "SPLV"],
    "Sectors": ["XLK", "XLF", "XLY", "XLV", "XLI", "XLC", "XLE", "XLP", "XLU", "XLB", "XLRE"],
    "Industries": ["SMH", "IYT", "KRE", "XHB", "ITB", "GDX", "COPX", "URA"],
    "International": ["EFA", "EEM", "EWJ", "FXI"],
    "Rates": ["SHY", "IEF", "TLT", "TIP"],
    "Credit": ["LQD", "HYG", "EMB"],
    "Commodities": ["GLD", "SLV", "CPER", "DBC", "USO", "UNG", "DBA"],
    "FX": ["UUP", "FXE", "FXY", "FXA", "FXB", "FXC", "FXF"],
    "Crypto": ["IBIT", "BITO"],
}
PRESETS = {
    "Macro core": ["SPY", "TLT", "HYG", "GLD", "USO", "UUP", "EEM"],
    "Mega caps": ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA"],
    "Sectors": GROUPS["Sectors"],
    "Energy": ["XLE", "USO", "XOM", "CVX", "COP", "SPY"],
    "Rates vs equity": ["TLT", "IEF", "SPY", "QQQ", "XLU", "KRE", "XHB"],
    "Semis / AI": ["SMH", "NVDA", "AVGO", "AMD", "MU", "INTC", "QCOM", "QQQ"],
}
FACTORS = [("SPY", "SPY", "% per 1%"), ("10Y", "US 10Y yield", "% per +10bp"), ("DXY", "Dollar (DXY)", "% per 1%"),
           ("OIL", "Oil (USO)", "% per 1%"), ("HY", "HY spread", "% per +10bp"), ("BE", "10Y breakeven", "% per +10bp")]
DAYS = 756

def payload(X):
    tr = X.tr.copy(); st = data.load("stk_tr")
    px = pd.concat([tr, st], axis=1).sort_index()
    idx = tr.dropna(how="all").index[-DAYS - 1:]
    px = px.reindex(idx)
    r = px.pct_change().iloc[1:]
    dates = [d.strftime("%Y-%m-%d") for d in r.index]
    enc = lambda s, k: [None if not np.isfinite(v) else int(round(v * k)) for v in s.values]
    R = {c: enc(r[c], 1e4) for c in r.columns if r[c].notna().sum() > 60}
    lvl = lambda s: s.reindex(idx.union(s.index)).ffill(limit=3).reindex(idx)
    f = {"SPY": r["SPY"] * 100, "OIL": r["USO"] * 100,
         "10Y": lvl(X.y("US", "10Y")).diff().iloc[1:] * 100 / 10,           # in units of 10bp
         "DXY": lvl(X.t("TVC:DXY")).pct_change().iloc[1:] * 100,
         "HY": lvl(X.f("BAMLH0A0HYM2")).diff().iloc[1:] * 100 / 10,
         "BE": lvl(X.f("T10YIE")).diff().iloc[1:] * 100 / 10}
    F = {k: enc(v.reindex(r.index), 1e3) for k, v in f.items()}
    grp = {t: g for g, ts in GROUPS.items() for t in ts}
    grp.update({t: "Stocks" for t in C.STOCKS})
    names = [n for n in list(GROUPS) + ["Stocks"]]
    return dict(dates=dates, R=R, F=F, grp=grp, groups=names, presets=PRESETS, factors=FACTORS)

HTML = r"""
<style>
#ex .ctl{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
#ex button,#ex select,#ex input{background:#1a1a1a;color:#f28c28;border:1px solid #333;padding:4px 8px;font:inherit}
#ex button.on{background:#f28c28;color:#000}
#ex .chip{display:inline-block;background:#111;border:1px solid #f28c28;color:#fff;padding:2px 6px;margin:2px;cursor:pointer}
#ex .chip:after{content:' ×';color:#f28c28}
#ex .pick{border:1px solid #222;padding:6px 8px;max-height:260px;overflow:auto;display:none}
#ex .pick.open{display:block}
#ex .pick .g{color:#888;margin-top:4px}
#ex .pick label{display:inline-block;min-width:74px;color:#d0d0d0;cursor:pointer}
#ex .lab{color:#888}
#ex .out{margin-top:8px}
#ex .note{border:1px solid #333;border-left:3px solid #f28c28;background:#080808;padding:6px 12px;margin:8px 0;line-height:1.5}
</style>
<div id="ex">
 <div class="ctl"><span class="lab">NAMES</span><span id="chips"></span>
  <button id="pk">+ add / remove</button><input id="q" placeholder="type ticker, Enter" size="12"><span id="qm" class="lab"></span>
  <span class="lab">presets</span><span id="pre"></span><button id="clr">clear</button></div>
 <div class="pick" id="pl"></div>
 <div class="ctl"><span class="lab">VIEW</span><span id="modes"></span>
  <span class="lab">window</span><select id="win"><option value="63">63d (3M)</option><option value="126" selected>126d (6M)</option><option value="252">252d (1Y)</option></select>
  <span class="lab">history</span><select id="hist"><option value="252">1Y</option><option value="504">2Y</option><option value="755" selected>3Y</option></select>
  <span id="anc" class="lab"></span></div>
 <div class="out" id="exo"></div>
</div>
<script>
(function(){
const D=__DATA__; const N=D.dates.length; const FK=D.factors.map(f=>f[0]);
const all=Object.keys(D.R); let sel=["SPY","TLT","HYG","GLD","USO","UUP","NVDA","XOM"].filter(x=>D.R[x]); let mode="corr"; let anchor="SPY";
try{const s=JSON.parse(localStorage.getItem("ex_sel")||"null"); if(s&&s.length) sel=s.filter(x=>D.R[x]);}catch(e){}
const $=id=>document.getElementById(id);
const L={paper_bgcolor:"#000",plot_bgcolor:"#000",font:{family:"Menlo,Consolas,monospace",size:11,color:"#d0d0d0"},margin:{l:60,r:20,t:30,b:40},
 xaxis:{gridcolor:"#2a2a2a",griddash:"dot",zeroline:false},yaxis:{gridcolor:"#2a2a2a",griddash:"dot",zeroline:false},legend:{orientation:"h",y:1.12,font:{size:10}},hovermode:"closest"};
const PAL=["#ffffff","#f28c28","#5fa8ff","#c77dff","#4ecdc4","#e0b64a","#ff6b6b","#9be15d","#aaaaaa","#ff9ff3","#54a0ff","#feca57"];
const cfg={displaylogo:false,responsive:false,showSendToCloud:false,showLink:false,modeBarButtonsToRemove:["lasso2d","select2d","toImage","sendDataToCloud"]};
function NP(id,data,layout){const el=document.getElementById(id);layout.autosize=false;layout.width=el.clientWidth||900;el.style.height=(layout.height||400)+"px";
 return Plotly.newPlot(el,data,layout,cfg).then(gd=>{if(window.hookPlot)window.hookPlot(gd);return gd})}
function lay(o){return Object.assign(JSON.parse(JSON.stringify(L)),o||{})}
function ser(t){return D.R[t].map(v=>v==null?null:v/1e4)}
function fac(k){return D.F[k].map(v=>v==null?null:v/1e3)}
// ---------- math ----------
function cols(names,a,b){ // rows a..b-1 with all present
 const S=names.map(ser), rows=[]; for(let i=a;i<b;i++){let ok=true;for(const s of S){if(s[i]==null){ok=false;break}} if(ok) rows.push(i)} return {S,rows}}
function corrM(names,a,b){const {S,rows}=cols(names,a,b); const n=names.length, m=rows.length;
 const Z=S.map(s=>{const x=rows.map(i=>s[i]);const mu=x.reduce((p,q)=>p+q,0)/m;const sd=Math.sqrt(x.reduce((p,q)=>p+(q-mu)**2,0)/(m-1))||1;return x.map(v=>(v-mu)/sd)});
 const C=[...Array(n)].map(()=>Array(n).fill(0)); for(let i=0;i<n;i++)for(let j=i;j<n;j++){let s=0;for(let k=0;k<m;k++)s+=Z[i][k]*Z[j][k];C[i][j]=C[j][i]=s/(m-1)} return {C,Z,m,rows}}
function jacobi(A){const n=A.length; const a=A.map(r=>r.slice()); const V=[...Array(n)].map((_,i)=>[...Array(n)].map((_,j)=>i==j?1:0));
 for(let sw=0;sw<100;sw++){let off=0;for(let i=0;i<n;i++)for(let j=i+1;j<n;j++)off+=a[i][j]**2; if(off<1e-12)break;
  for(let p=0;p<n;p++)for(let q=p+1;q<n;q++){if(Math.abs(a[p][q])<1e-15)continue;const th=(a[q][q]-a[p][p])/(2*a[p][q]);
   const t=Math.sign(th||1)/(Math.abs(th)+Math.sqrt(th*th+1)); const c=1/Math.sqrt(t*t+1), s=t*c;
   for(let k=0;k<n;k++){const akp=a[k][p],akq=a[k][q];a[k][p]=c*akp-s*akq;a[k][q]=s*akp+c*akq}
   for(let k=0;k<n;k++){const apk=a[p][k],aqk=a[q][k];a[p][k]=c*apk-s*aqk;a[q][k]=s*apk+c*aqk}
   for(let k=0;k<n;k++){const vkp=V[k][p],vkq=V[k][q];V[k][p]=c*vkp-s*vkq;V[k][q]=s*vkp+c*vkq}}}
 const ev=a.map((r,i)=>r[i]); const ord=ev.map((v,i)=>i).sort((x,y)=>ev[y]-ev[x]);
 return {val:ord.map(i=>ev[i]),vec:ord.map(i=>V.map(r=>r[i]))}}
function pca(names,a,b){const {C,Z,m}=corrM(names,a,b); const e=jacobi(C); const tot=e.val.reduce((p,q)=>p+q,0);
 e.vec.forEach((v,k)=>{ // sign: PC1 net positive; others largest |loading| positive
  const flip=k==0?v.reduce((p,q)=>p+q,0)<0:v[v.map(Math.abs).indexOf(Math.max(...v.map(Math.abs)))]<0; if(flip)for(let i=0;i<v.length;i++)v[i]=-v[i]});
 return {share:e.val.map(v=>v/tot),vec:e.vec,val:e.val,m}}
function solve(A,y){const n=A.length;const M=A.map((r,i)=>r.concat([y[i]]));for(let c=0;c<n;c++){let p=c;for(let r=c+1;r<n;r++)if(Math.abs(M[r][c])>Math.abs(M[p][c]))p=r;[M[c],M[p]]=[M[p],M[c]];
 if(Math.abs(M[c][c])<1e-14)return null;for(let r=0;r<n;r++){if(r==c)continue;const f=M[r][c]/M[c][c];for(let k=c;k<=n;k++)M[r][k]-=f*M[c][k]}}return M.map((r,i)=>r[n]/r[i])}
function inv(A){const n=A.length;return [...Array(n)].map((_,j)=>solve(A,[...Array(n)].map((_,i)=>i==j?1:0))).reduce((acc,col,j)=>{col.forEach((v,i)=>{acc[i][j]=v});return acc},[...Array(n)].map(()=>Array(n).fill(0)))}
function ols(t,a,b,keys){const y=ser(t).map(v=>v==null?null:v*100); const Fs=keys.map(fac); const rows=[];
 for(let i=a;i<b;i++){if(y[i]==null)continue;let ok=true;for(const f of Fs)if(f[i]==null){ok=false;break} if(ok)rows.push(i)}
 const k=keys.length+1, m=rows.length; if(m<k+10)return null; const XtX=[...Array(k)].map(()=>Array(k).fill(0)), Xty=Array(k).fill(0);
 const xr=i=>[1].concat(Fs.map(f=>f[i]));
 for(const i of rows){const x=xr(i);for(let p=0;p<k;p++){Xty[p]+=x[p]*y[i];for(let q=0;q<k;q++)XtX[p][q]+=x[p]*x[q]}}
 const bta=solve(XtX,Xty); if(!bta)return null; let sse=0,sst=0; const my=rows.reduce((p,i)=>p+y[i],0)/m;
 for(const i of rows){const x=xr(i);const f=x.reduce((p,v,j)=>p+v*bta[j],0);sse+=(y[i]-f)**2;sst+=(y[i]-my)**2}
 const s2=sse/(m-k); const Ii=inv(XtX); const se=Ii.map((r,i)=>Math.sqrt(Math.max(r[i]*s2,0)));
 const contrib=keys.map((_,j)=>bta[j+1]*rows.reduce((p,i)=>p+Fs[j][i],0)); const tot=rows.reduce((p,i)=>p+y[i],0);
 return {b:bta,t:bta.map((v,i)=>v/se[i]),r2:1-sse/sst,m,contrib,alpha:tot-contrib.reduce((p,q)=>p+q,0),tot}}
function rcorr(x,y,w,a){const out=[];for(let e=a;e<N;e++){let n=0,sx=0,sy=0,sxx=0,syy=0,sxy=0;for(let i=e-w+1;i<=e;i++){if(i<0||x[i]==null||y[i]==null)continue;n++;sx+=x[i];sy+=y[i];sxx+=x[i]*x[i];syy+=y[i]*y[i];sxy+=x[i]*y[i]}
 out.push(n>w*0.8?(n*sxy-sx*sy)/Math.sqrt((n*sxx-sx*sx)*(n*syy-sy*sy)):null)}return out}
// ---------- views ----------
const W=()=>+$("win").value, H=()=>+$("hist").value;
function note(h){return `<div class='note'>${h}</div>`}
function vCorr(o){const n=sel.length,{C,m}=corrM(sel,N-W(),N); const p=pca(sel,N-W(),N); const ord=sel.map((s,i)=>i).sort((a,b)=>p.vec[0][b]-p.vec[0][a]);
 const lab=ord.map(i=>sel[i]); const z=ord.map(i=>ord.map(j=>C[i][j]));
 const {C:C2}=corrM(sel,N-W()-252,N-252); const dz=ord.map(i=>ord.map(j=>C[i][j]-C2[i][j]));
 o.innerHTML=note(`Correlation of daily returns over the last <b>${W()}</b> sessions (${m} common days). Names are ordered by their PC1 loading, so blocks that move together cluster. Right panel = change vs the same window one year earlier: green = more correlated now.`)+"<div class='cb'><div class='plot' id='e1'></div><div class='plot' id='e2'></div></div>";
 const hm=(id,zz,t,lo,hi)=>NP(id,[{type:"heatmap",z:zz,x:lab,y:lab,zmin:lo,zmax:hi,colorscale:[[0,"#a82626"],[0.5,"#000"],[1,"#3a8a2a"]],text:zz.map(r=>r.map(v=>v.toFixed(2))),texttemplate:n<=16?"%{text}":"",hovertemplate:"%{y} / %{x}: %{z:.2f}<extra></extra>"}],
  lay({title:{text:t,font:{color:"#f28c28",size:12}},height:Math.max(360,26*n+120),yaxis:{autorange:"reversed"},xaxis:{tickangle:-45}}),cfg);
 hm("e1",z,`Correlation, ${W()}d`,-1,1); hm("e2",dz,`Change vs 1y ago`,-0.8,0.8)}
function vRoll(o){const a=D.R[anchor]?anchor:sel[0]; const st=N-H(); const x=ser(a); const others=sel.filter(s=>s!=a);
 o.innerHTML=note(`Rolling ${W()}-day correlation of each selected name against <b>${a}</b> (change the anchor above). A line crossing zero means the relationship flipped: e.g. TLT vs SPY above zero = bonds no longer hedge stocks.`)+"<div class='plot' id='e1'></div>";
 NP("e1",others.map((s,k)=>({x:D.dates.slice(st),y:rcorr(x,ser(s),W(),st),name:s,mode:"lines",line:{color:PAL[k%PAL.length],width:1.5}})),
  lay({height:460,yaxis:{range:[-1,1],gridcolor:"#2a2a2a",griddash:"dot",zeroline:true,zerolinecolor:"#666"},hovermode:"x unified"}),cfg)}
function vPerf(o){const st=N-H(); o.innerHTML=note(`Total return rebased to 100 at the start of the ${H()>=755?"3Y":H()/252+"Y"} history (dividends included).`)+"<div class='plot' id='e1'></div>";
 NP("e1",sel.map((s,k)=>{const r=ser(s);let v=null;const y=[];for(let i=st;i<N;i++){if(r[i]!=null)v=(v==null?100:v*(1+r[i]));y.push(v)}return{x:D.dates.slice(st),y,name:s,mode:"lines",line:{color:PAL[k%PAL.length],width:1.5}}}),
  lay({height:460,yaxis:{type:"log",gridcolor:"#2a2a2a",griddash:"dot"},hovermode:"x unified"}),cfg)}
function vPCA(o){if(sel.length<3){o.innerHTML=note("Pick at least 3 names for PCA.");return}
 const p=pca(sel,N-W(),N); const k=Math.min(3,sel.length); const pcs=[...Array(k)].map((_,i)=>"PC"+(i+1));
 // communality: share of each name's variance explained by first k PCs
 const comm=sel.map((s,i)=>pcs.reduce((acc,_,j)=>acc+p.val[j]*p.vec[j][i]**2,0));
 const desc=pcs.map((pc,j)=>{const v=p.vec[j];const o2=sel.map((s,i)=>[s,v[i]]).sort((a,b)=>b[1]-a[1]);const pos=o2.filter(x=>x[1]>0.2).map(x=>x[0]),neg=o2.filter(x=>x[1]<-0.2).map(x=>x[0]).reverse();
  const same=v.every(x=>x>=0)||v.every(x=>x<=0);
  return `<li><b>${pc} (${(p.share[j]*100).toFixed(0)}%)</b>: ${same&&j==0?"every name loads the same way: this is the <b>common factor</b> (the market or macro tide) that moves them all together.":`<span class='g'>${pos.join(", ")||"—"}</span> move opposite to <span class='r'>${neg.join(", ")||"—"}</span>. Read it as a <b>spread</b>: the left group vs the right group.`}</li>`}).join("");
 // rolling PC1 share
 const st=N-H(), xs=[], ys=[]; for(let e=Math.max(st,W());e<=N;e+=5){try{const q=pca(sel,e-W(),e);xs.push(D.dates[e-1]);ys.push(q.share[0]*100)}catch(err){}}
 o.innerHTML=note(`PCA on <b>${sel.length}</b> names, standardized daily returns, last ${W()} sessions (${p.m} common days). With ${sel.length} names, an equal split would give each PC ${(100/sel.length).toFixed(0)}%; PC1 far above that = one driver runs the group.<ul>${desc}</ul>The table's <b>explained</b> column is how much of each name's own daily variance the top ${k} PCs capture. Low = the name trades on its own story (idiosyncratic), high = it is mostly a factor ride.`)+
  "<div class='cb'><div class='plot' id='e1'></div><div class='plot' id='e2'></div></div><div class='plot' id='e3'></div><div class='tbl' id='e4'></div>";
 NP("e1",[{type:"bar",x:p.share.slice(0,Math.min(8,sel.length)).map((_,i)=>"PC"+(i+1)),y:p.share.slice(0,8).map(v=>v*100),marker:{color:"#f28c28"},text:p.share.slice(0,8).map(v=>(v*100).toFixed(0)+"%"),textposition:"outside"}],
  lay({title:{text:"Variance explained",font:{color:"#f28c28",size:12}},height:360,yaxis:{ticksuffix:"%",gridcolor:"#2a2a2a"}}),cfg);
 const ord=sel.map((s,i)=>i).sort((a,b)=>p.vec[0][a]-p.vec[0][b]);
 NP("e2",pcs.map((pc,j)=>({type:"bar",orientation:"h",y:ord.map(i=>sel[i]),x:ord.map(i=>p.vec[j][i]),name:pc,marker:{color:PAL[j+1]}})),
  lay({title:{text:"Loadings",font:{color:"#f28c28",size:12}},height:Math.max(360,22*sel.length+100),barmode:"group",margin:{l:60,r:20,t:50,b:40}}),cfg);
 NP("e3",[{x:xs,y:ys,mode:"lines",line:{color:"#fff"},name:"PC1 share"}],lay({title:{text:`Rolling PC1 share (${W()}d window, every 5 days): rising = the group is moving as one block`,font:{color:"#f28c28",size:12}},height:300,yaxis:{ticksuffix:"%",gridcolor:"#2a2a2a",griddash:"dot"}}),cfg);
 $("e4").innerHTML="<table><tr><th>Name</th>"+pcs.map(x=>`<th>${x}</th>`).join("")+`<th>explained by top ${k}</th></tr>`+ord.slice().reverse().map(i=>`<tr><td class='nm'>${sel[i]}</td>`+pcs.map((_,j)=>`<td class='${p.vec[j][i]>0?"g":"r"}'>${p.vec[j][i].toFixed(2)}</td>`).join("")+`<td>${(comm[i]*100).toFixed(0)}%</td></tr>`).join("")+"</table>"}
function vAttr(o){const a=N-W(); const res=sel.map(s=>[s,ols(s,a,N,FK)]).filter(x=>x[1]);
 o.innerHTML=note(`Multi-factor regression of each name's daily return (%) on six macro factors over the last ${W()} sessions. <b>Beta</b> units are in the header (e.g. 10Y: % move per +10bp in the yield). Bold = |t| &gt; 2 (statistically meaningful). <b>R²</b> = share of daily moves the six factors explain. The chart splits each name's total return over the window into what each factor contributed (beta × factor move) and the unexplained remainder (<b>alpha</b>). Factors overlap (SPY and HY move together), so read the betas as a set, not one at a time. A factor proxy regressed on itself (SPY on SPY, USO on oil) shows beta 1 and R² near 100% by construction.`)+
  "<div class='tbl' id='e4'></div><div class='plot' id='e1'></div>";
 $("e4").innerHTML="<table><tr><th>Name</th>"+D.factors.map(f=>`<th>${f[1]}<br><span class='lab'>${f[2]}</span></th>`).join("")+"<th>R²</th><th>total %</th><th>alpha %</th></tr>"+
  res.map(([s,r])=>`<tr><td class='nm'>${s}</td>`+FK.map((_,j)=>{const b=r.b[j+1],t=r.t[j+1];return `<td class='${Math.abs(t)>2?(b>0?"g":"r"):""}'>${Math.abs(t)>2?"<b>":""}${b.toFixed(2)}${Math.abs(t)>2?"</b>":""}</td>`}).join("")+
  `<td>${(r.r2*100).toFixed(0)}%</td><td>${r.tot.toFixed(1)}</td><td class='${r.alpha>0?"g":"r"}'>${r.alpha.toFixed(1)}</td></tr>`).join("")+"</table>";
 const tr=D.factors.map((f,j)=>({type:"bar",name:f[1],x:res.map(x=>x[0]),y:res.map(x=>x[1].contrib[j]),marker:{color:PAL[(j+1)%PAL.length]}}));
 tr.push({type:"bar",name:"alpha",x:res.map(x=>x[0]),y:res.map(x=>x[1].alpha),marker:{color:"#555"}});
 tr.push({type:"scatter",mode:"markers",name:"total",x:res.map(x=>x[0]),y:res.map(x=>x[1].tot),marker:{color:"#fff",symbol:"diamond",size:9}});
 NP("e1",tr,lay({title:{text:`Return attribution over ${W()}d (sum of daily %)`,font:{color:"#f28c28",size:12}},barmode:"relative",height:460,legend:{orientation:"h",y:-0.12,font:{size:10}},yaxis:{ticksuffix:"%",gridcolor:"#2a2a2a",griddash:"dot",zeroline:true,zerolinecolor:"#666"}}),cfg)}
const MODES=[["corr","CORRELATION",vCorr],["roll","ROLLING CORR",vRoll],["pca","PCA",vPCA],["attr","ATTRIBUTION",vAttr],["perf","PERFORMANCE",vPerf]];
// ---------- UI ----------
function draw(){try{localStorage.setItem("ex_sel",JSON.stringify(sel))}catch(e){}
 $("chips").innerHTML=sel.map(s=>`<span class='chip' data-s='${s}'>${s}</span>`).join("");
 document.querySelectorAll("#chips .chip").forEach(c=>c.onclick=()=>{sel=sel.filter(x=>x!=c.dataset.s);sync();draw()});
 $("modes").innerHTML=MODES.map(m=>`<button data-m='${m[0]}' class='${m[0]==mode?"on":""}'>${m[1]}</button>`).join("");
 document.querySelectorAll("#modes button").forEach(b=>b.onclick=()=>{mode=b.dataset.m;draw()});
 $("anc").innerHTML=mode=="roll"?`anchor <select id='ancs'>${sel.map(s=>`<option ${s==anchor?"selected":""}>${s}</option>`).join("")}</select>`:"";
 if($("ancs"))$("ancs").onchange=e=>{anchor=e.target.value;draw()};
 if(!sel.includes(anchor))anchor=sel[0]; const o=$("exo"); if(sel.length<2){o.innerHTML=note("Pick at least 2 names.");return}
 try{MODES.find(m=>m[0]==mode)[2](o)}catch(e){o.innerHTML=note("Could not compute: "+e.message)}}
function sync(){document.querySelectorAll("#pl input").forEach(i=>i.checked=sel.includes(i.value))}
$("pl").innerHTML=D.groups.map(g=>`<div class='g'>${g}</div>`+all.filter(t=>D.grp[t]==g).map(t=>`<label><input type='checkbox' value='${t}'> ${t}</label>`).join("")).join("");
document.querySelectorAll("#pl input").forEach(i=>i.onchange=()=>{sel=i.checked?[...new Set(sel.concat([i.value]))]:sel.filter(x=>x!=i.value);draw()});
$("pk").onclick=()=>$("pl").classList.toggle("open");
$("q").onkeydown=e=>{if(e.key=="Enter"){const t=e.target.value.trim().toUpperCase();if(!t)return;if(D.R[t]&&!sel.includes(t)){sel.push(t);sync();draw();$("qm").textContent=""}else{$("qm").textContent=D.R[t]?t+" already added":t+" not in data"}e.target.value=""}};
$("pre").innerHTML=Object.keys(D.presets).map(k=>`<button data-p='${k}'>${k}</button>`).join(" ");
document.querySelectorAll("#pre button").forEach(b=>b.onclick=()=>{sel=D.presets[b.dataset.p].filter(x=>D.R[x]);sync();draw()});
$("clr").onclick=()=>{sel=[];sync();draw()}; $("win").onchange=draw; $("hist").onchange=draw;
sync(); let done=false; const go=()=>{const p=document.getElementById("explorer");if(!done&&p.classList.contains("on")){if(p.clientWidth<80){setTimeout(go,60);return}done=true;draw()}};
new MutationObserver(go).observe(document.getElementById("explorer"),{attributes:true}); go();
})();
</script>
"""

def tab_explorer(X):
    P = payload(X)
    js = json.dumps(P, separators=(",", ":")).replace("</", "<\\/")
    read = ["Pick any mix of ETFs and the 45 large-cap stocks; switch views between correlation matrix, rolling correlation vs an anchor, PCA on just those names, "
            "six-factor attribution (SPY, 10Y, dollar, oil, HY spread, breakevens) and rebased performance. Window and history toggles apply to every view.",
            f"Data: daily total returns, last {len(P['dates'])} sessions to {P['dates'][-1]}. Everything is computed in your browser; selections are remembered on this device."]
    return dict(key="explorer", title="EXPLORER", read=read, cards=[], html=HTML.replace("__DATA__", js))
