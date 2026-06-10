#!/usr/bin/env python3
"""Build a self-contained HTML review dashboard from batch_run results.json.

Usage: python3 build_dashboard.py [results.json] [dashboard.html]
"""
import sys
import json

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SwePruner Review Dashboard</title>
<style>
  :root {
    --bg:#0f1115; --panel:#171a21; --panel2:#1d212b; --border:#2a2f3a;
    --fg:#e6e8eb; --muted:#9aa3b2; --kept:#16341f; --kept-border:#2f9e57;
    --gold:#3a3413; --accent:#4f9cf9; --good:#2f9e57; --bad:#e0566b; --review:#d9a441;
  }
  * { box-sizing:border-box; }
  body { margin:0; font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
         background:var(--bg); color:var(--fg); }
  code, pre, .mono { font-family:"SF Mono",Menlo,Consolas,monospace; }
  header { position:sticky; top:0; z-index:10; background:var(--panel);
           border-bottom:1px solid var(--border); padding:10px 16px; }
  .hrow { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
  h1 { font-size:16px; margin:0 12px 0 0; }
  .stat { color:var(--muted); font-size:12px; }
  .stat b { color:var(--fg); font-size:13px; }
  input,select,button { background:var(--panel2); color:var(--fg);
    border:1px solid var(--border); border-radius:6px; padding:6px 9px; font-size:13px; }
  button { cursor:pointer; }
  button:hover { border-color:var(--accent); }
  #search { min-width:220px; }
  main { padding:16px; max-width:1200px; margin:0 auto; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px;
          margin-bottom:14px; overflow:hidden; }
  .card.collapsed .body { display:none; }
  .chead { display:flex; gap:12px; align-items:center; padding:10px 14px; cursor:pointer;
           border-bottom:1px solid var(--border); flex-wrap:wrap; }
  .chead:hover { background:var(--panel2); }
  .idx { font-weight:700; color:var(--accent); }
  .badge { font-size:11px; padding:2px 7px; border-radius:20px; border:1px solid var(--border);
           color:var(--muted); white-space:nowrap; }
  .badge.score-hi { color:#7ee2a8; border-color:#2f9e57; }
  .badge.score-lo { color:#f1a3ae; border-color:#e0566b; }
  .badge.neg { color:#f1a3ae; border-color:#e0566b; }
  .q { flex:1; min-width:240px; color:var(--fg); }
  .has-comment { color:var(--accent); }
  .body { padding:12px 14px; }
  .grid { display:grid; grid-template-columns:1fr; gap:14px; }
  @media(min-width:980px){ .grid { grid-template-columns:1fr 360px; } }
  .legend { font-size:12px; color:var(--muted); margin-bottom:6px; }
  .swatch { display:inline-block; width:11px; height:11px; border-radius:2px; vertical-align:middle; margin:0 4px 0 10px; }
  pre.code { background:#0b0d11; border:1px solid var(--border); border-radius:8px;
             margin:0; padding:4px 0; overflow:auto; max-height:1600px; font-size:11px; line-height:1.32; min-width:0; }
  .codepair { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }
  @media(max-width:880px){ .codepair { grid-template-columns:1fr; } }
  .pane { min-width:0; }  /* allow the inner <pre> to scroll instead of the column expanding */
  .pane h4 { margin:0 0 6px; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .reveal { width:100%; min-height:120px; border:1px dashed var(--border); border-radius:8px;
            background:#0b0d11; color:var(--muted); cursor:pointer; font-size:14px;
            display:flex; flex-direction:column; align-items:center; justify-content:center; gap:6px; }
  .reveal small { font-size:11px; color:#5a6273; text-transform:none; letter-spacing:0; }
  .reveal:hover { color:var(--fg); border-color:var(--accent); }
  .ln { display:flex; white-space:pre; width:max-content; min-width:100%; }
  .ln .g { width:46px; text-align:right; padding-right:6px; color:#5a6273; user-select:none; flex:none; }
  .ln .m { width:16px; text-align:center; color:var(--review); user-select:none; flex:none; }
  .ln .t { padding-right:14px; flex:none; }
  .ln.kept { background:var(--kept); }
  .ln.kept .g { color:#7ee2a8; }
  .ln.goldline { box-shadow:inset 3px 0 0 var(--review); }
  /* python syntax tokens (left pane) */
  .tk-kw  { color:#c678dd; }
  .tk-str { color:#98c379; }
  .tk-com { color:#5c6370; font-style:italic; }
  .tk-num { color:#d19a66; }
  .tk-fn  { color:#61afef; }
  .tk-bi  { color:#56b6c2; }
  .tk-dec { color:#e5c07b; }
  .tk-op  { color:#abb2bf; }
  .side h4 { margin:0 0 6px; font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
  .pruned { background:#0b0d11; border:1px solid var(--border); border-radius:8px; padding:8px 10px;
            white-space:pre-wrap; max-height:260px; overflow:auto; font-size:12px; }
  textarea { width:100%; min-height:60px; resize:vertical; background:#0b0d11; color:var(--fg);
             border:1px solid var(--border); border-radius:8px; padding:8px; font-size:13px; }
  .clabel { display:block; font-size:11px; color:var(--muted); margin:8px 0 3px; text-transform:uppercase; letter-spacing:.04em; }
  .meta-line { font-size:12px; color:var(--muted); margin:6px 0; }
  .eval { font-size:12px; color:var(--muted); background:var(--panel2); border:1px solid var(--border);
          border-radius:8px; padding:8px; margin-top:8px; }
  .saved { font-size:11px; color:var(--good); margin-left:8px; opacity:0; transition:opacity .3s; }
  .saved.show { opacity:1; }
  details summary { cursor:pointer; color:var(--muted); font-size:12px; margin-top:8px; }
</style>
</head>
<body>
<header>
  <div class="hrow">
    <h1>SwePruner Review</h1>
    <span class="stat">rows <b id="s-range"></b></span>
    <span class="stat">thr <b id="s-thr"></b></span>
    <span class="stat">avg score <b id="s-score"></b></span>
    <span class="stat">avg token cut <b id="s-cut"></b></span>
    <span class="stat">commented <b id="s-reviewed"></b></span>
    <span class="stat" id="s-store"></span>
  </div>
  <div class="hrow" style="margin-top:8px">
    <input id="search" placeholder="filter by query / index…">
    <select id="filter">
      <option value="all">All</option>
      <option value="commented">Has comment</option>
      <option value="uncommented">No comment</option>
      <option value="lowscore">score &lt; 0.5</option>
      <option value="negative">is_negative</option>
    </select>
    <button id="expand">Expand all</button>
    <button id="collapse">Collapse all</button>
    <span style="flex:1"></span>
    <button id="export">⬇ Export review</button>
    <label class="badge" style="cursor:pointer">⬆ Import<input id="import" type="file" accept="application/json" style="display:none"></label>
  </div>
</header>
<main id="app"></main>

<script>
const DATA = __DATA__;
const STORE_KEY = "swepruner_review_" + DATA.meta.start;

function loadReview(){ try { return JSON.parse(localStorage.getItem(STORE_KEY)) || {}; } catch(e){ return {}; } }
function saveReview(r){ localStorage.setItem(STORE_KEY, JSON.stringify(r)); }
let review = loadReview();
const revealed = new Set();   // right-window reveals; in-memory so reload re-hides (blind-first)

// Persistence: when opened via the local server (http://), auto-save to a JSON
// file on disk through /api/review/<start>; always mirror to localStorage too.
const SERVER = location.protocol.startsWith("http");
const API = "/api/review/" + DATA.meta.start;
let saveTimer=null;
function setStore(msg){ const el=document.getElementById("s-store"); if(el) el.textContent=msg; }
function persistNow(){
  if(!SERVER) return;
  fetch(API,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(review)})
    .then(r=>setStore(r.ok ? "💾 saved → review_"+DATA.meta.start+".json" : "⚠ save error"))
    .catch(()=>setStore("⚠ offline — localStorage only"));
}
function persist(){ saveReview(review); if(SERVER){ clearTimeout(saveTimer); saveTimer=setTimeout(persistNow, 400); } }
async function init(){
  if(SERVER){
    let serverData={};
    try { const r=await fetch(API); if(r.ok) serverData=await r.json()||{}; } catch(e){}
    const local=loadReview();
    if(Object.keys(serverData).length===0 && Object.keys(local).length>0){
      review=local; setStore("⤴ migrating localStorage → file…"); persistNow();
    } else {
      review=serverData; setStore("💾 saving to review_"+DATA.meta.start+".json");
    }
  } else {
    review=loadReview();
    setStore("⚠ localStorage only — run serve_dashboard.py & open via http://localhost");
  }
  render();
}

const esc = s => (s==null?"":String(s)).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const pct = (a,b) => b>0 ? Math.round(100*(b-a)/b) : 0;
const hasAny = rv => !!(rv && ((rv.query&&rv.query.trim())||(rv.gold&&rv.gold.trim())||(rv.pred&&rv.pred.trim())));

// --- tiny self-contained Python syntax highlighter (left pane only) ---
const PY_KW = new Set("False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield match case".split(" "));
const PY_BI = new Set("print len range int str float list dict set tuple bool bytes open isinstance issubclass enumerate zip map filter sum min max abs sorted reversed any all type object super hasattr getattr setattr repr format input self cls None".split(" "));
function highlightCode(code){
  const lines = code.split("\n");
  const isId = c => /[A-Za-z0-9_]/.test(c);
  const DQ3 = '"'.repeat(3), SQ3 = "'".repeat(3);   // triple-quotes w/o source literals
  let triple = null;            // open multiline-string delimiter, or null
  const out = [];
  for(const line of lines){
    let html="", i=0, prev="", n=line.length;
    while(i<n){
      if(triple){
        const idx=line.indexOf(triple,i);
        if(idx===-1){ html+=`<span class="tk-str">${esc(line.slice(i))}</span>`; i=n; break; }
        html+=`<span class="tk-str">${esc(line.slice(i,idx+3))}</span>`; i=idx+3; triple=null; continue;
      }
      const c=line[i];
      if(c===" "||c==="\t"){ let j=i; while(j<n&&(line[j]===" "||line[j]==="\t"))j++; html+=esc(line.slice(i,j)); i=j; continue; }
      if(c==="#"){ html+=`<span class="tk-com">${esc(line.slice(i))}</span>`; i=n; break; }
      if(line.startsWith(DQ3,i)||line.startsWith(SQ3,i)){
        const q=line.substr(i,3), close=line.indexOf(q,i+3);
        if(close===-1){ html+=`<span class="tk-str">${esc(line.slice(i))}</span>`; triple=q; i=n; break; }
        html+=`<span class="tk-str">${esc(line.slice(i,close+3))}</span>`; i=close+3; continue;
      }
      if(c==='"'||c==="'"){ let j=i+1; while(j<n){ if(line[j]==="\\"){j+=2;continue;} if(line[j]===c){j++;break;} j++; }
        html+=`<span class="tk-str">${esc(line.slice(i,j))}</span>`; i=j; continue; }
      if(c>="0"&&c<="9"){ let j=i; while(j<n&&/[0-9a-fA-F_xXoObBeE.]/.test(line[j]))j++;
        html+=`<span class="tk-num">${esc(line.slice(i,j))}</span>`; i=j; continue; }
      if(c==="@"){ let j=i+1; while(j<n&&/[A-Za-z0-9_.]/.test(line[j]))j++;
        html+=`<span class="tk-dec">${esc(line.slice(i,j))}</span>`; i=j; continue; }
      if(/[A-Za-z_]/.test(c)){ let j=i; while(j<n&&isId(line[j]))j++; const w=line.slice(i,j);
        let cls = PY_KW.has(w) ? "tk-kw"
          : (prev==="def"||prev==="class") ? "tk-fn"
          : PY_BI.has(w) ? "tk-bi"
          : (j<n && line[j]==="(") ? "tk-fn" : "";
        html += cls ? `<span class="${cls}">${esc(w)}</span>` : esc(w);
        prev=w; i=j; continue; }
      html+=`<span class="tk-op">${esc(c)}</span>`; i++;
    }
    out.push(html||" ");
  }
  return out;
}

function codeHtml(code, kept, gold, labeled, hl){
  const keptS = new Set(kept), goldS = new Set(gold);
  const lines = code.split("\n");
  let out = "";
  for(let i=0;i<lines.length;i++){
    const n=i+1;
    const isKept = labeled && keptS.has(n);
    const isGold = labeled && goldS.has(n);
    const cls = "ln" + (isKept?" kept":"") + (isGold?" goldline":"");
    const text = hl ? (hl[i]||" ") : (esc(lines[i])||" ");
    out += `<div class="${cls}"><span class="g">${n}</span><span class="m">${isGold?"g":""}</span><span class="t">${text}</span></div>`;
  }
  return out;
}

function card(r){
  const rv = review[r.idx] || {};
  const scoreCls = r.score>=0.5 ? "score-hi":"score-lo";
  const cut = pct(r.left_token_cnt, r.origin_token_cnt);
  const hasComment = hasAny(rv);
  const evalHtml = r.evaluation ? `<div class="eval"><b>dataset eval</b> · quality:${esc(r.evaluation.overall_quality)} · deletion:${esc(r.evaluation.deletion_relevance)} · semantic:${esc(r.evaluation.semantic_preservation)}<br>${esc(r.evaluation.reasoning)}</div>` : "";
  return `<div class="card collapsed" data-idx="${r.idx}">
    <div class="chead">
      <span class="idx">#${r.idx}</span>
      <span class="badge ${scoreCls}">score ${r.score.toFixed(3)}</span>
      <span class="badge">${r.origin_token_cnt}→${r.left_token_cnt} (-${cut}%)</span>
      ${r.is_negative? '<span class="badge neg">negative</span>':''}
      ${hasComment? '<span class="badge has-comment">✓ commented</span>':''}
      <span class="q">${esc(r.query)}</span>
    </div>
    <div class="body">
      ${r.error_msg? '<div class="meta-line" style="color:var(--bad)">'+esc(r.error_msg)+'</div>':''}
      <div class="legend">left: original code &nbsp;|&nbsp; right:<span class="swatch" style="background:var(--kept-border)"></span>predicted-kept<span class="swatch" style="background:var(--review)"></span>gold-kept (g)</div>
      <div class="codepair">
        <div class="pane"><h4>Original</h4><pre class="code">${codeHtml(r.code, [], [], false, highlightCode(r.code))}</pre></div>
        <div class="pane"><h4>Gold + predicted labels</h4>${revealed.has(r.idx)
          ? `<pre class="code">${codeHtml(r.code, r.predicted_kept_frags||[], r.gold_kept_frags||[], true)}</pre>`
          : `<button class="reveal" data-idx="${r.idx}">👁 Reveal labels<small>read the original first, then compare</small></button>`}</div>
      </div>
      <div class="grid">
        <div>
          <details><summary>show pruned_code (model output)</summary><div class="pruned">${esc(r.pruned_code)}</div></details>
          ${evalHtml}
        </div>
        <div class="side">
          <h4>Comments <span class="saved">saved ✓</span></h4>
          <label class="clabel">Query</label>
          <textarea data-field="query" placeholder="notes on the query…">${esc(rv.query||"")}</textarea>
          <label class="clabel">Gold labels</label>
          <textarea data-field="gold" placeholder="notes on the gold labels…">${esc(rv.gold||"")}</textarea>
          <label class="clabel">Pred labels</label>
          <textarea data-field="pred" placeholder="notes on the predicted labels…">${esc(rv.pred||"")}</textarea>
        </div>
      </div>
    </div>
  </div>`;
}

function recomputeStats(){
  const rs = DATA.results;
  const avg = a => a.length? (a.reduce((x,y)=>x+y,0)/a.length):0;
  document.getElementById("s-range").textContent = DATA.meta.start+"–"+(DATA.meta.start+DATA.meta.count-1);
  document.getElementById("s-thr").textContent = DATA.meta.threshold;
  document.getElementById("s-score").textContent = avg(rs.map(r=>r.score)).toFixed(3);
  document.getElementById("s-cut").textContent = Math.round(avg(rs.map(r=>pct(r.left_token_cnt,r.origin_token_cnt))))+"%";
  let reviewed=0;
  for(const r of rs){ if(hasAny(review[r.idx])) reviewed++; }
  document.getElementById("s-reviewed").textContent=reviewed+"/"+rs.length;
}

function visible(r){
  const f=document.getElementById("filter").value;
  const q=document.getElementById("search").value.toLowerCase().trim();
  const rv=review[r.idx]||{};
  if(q && !(String(r.idx).includes(q) || r.query.toLowerCase().includes(q))) return false;
  switch(f){
    case "commented": return hasAny(rv);
    case "uncommented": return !hasAny(rv);
    case "lowscore": return r.score<0.5;
    case "negative": return !!r.is_negative;
    default: return true;
  }
}

function render(){
  const app=document.getElementById("app");
  app.innerHTML = DATA.results.filter(visible).map(card).join("") || '<p class="stat">no matches</p>';
  recomputeStats();
}

document.addEventListener("click", e=>{
  const rb=e.target.closest(".reveal");
  if(rb){
    const idx=+rb.dataset.idx; revealed.add(idx);
    const r=DATA.results.find(x=>x.idx===idx);
    rb.insertAdjacentHTML("afterend", `<pre class="code">${codeHtml(r.code, r.predicted_kept_frags||[], r.gold_kept_frags||[], true)}</pre>`);
    rb.remove();
    return;
  }
  const head=e.target.closest(".chead");
  if(head){ head.parentElement.classList.toggle("collapsed"); }
});

document.addEventListener("input", e=>{
  if(e.target.tagName==="TEXTAREA"){
    const idx=+e.target.closest(".card").dataset.idx;
    const field=e.target.dataset.field||"query";
    review[idx]=review[idx]||{}; review[idx][field]=e.target.value;
    persist(); recomputeStats();
    const s=e.target.closest(".side").querySelector(".saved");
    s.classList.add("show"); clearTimeout(s._t); s._t=setTimeout(()=>s.classList.remove("show"),800);
  }
});

// keep the two code windows of a card scrolled in lockstep
let syncing=false;
document.addEventListener("scroll", e=>{
  const pre=e.target;
  if(syncing || !pre.classList || !pre.classList.contains("code")) return;
  const pair=pre.closest(".codepair"); if(!pair) return;
  syncing=true;
  pair.querySelectorAll(".code").forEach(o=>{ if(o!==pre){ o.scrollTop=pre.scrollTop; o.scrollLeft=pre.scrollLeft; }});
  syncing=false;
}, true);

document.getElementById("search").addEventListener("input", render);
document.getElementById("filter").addEventListener("change", render);
document.getElementById("expand").onclick=()=>document.querySelectorAll(".card").forEach(c=>c.classList.remove("collapsed"));
document.getElementById("collapse").onclick=()=>document.querySelectorAll(".card").forEach(c=>c.classList.add("collapsed"));

document.getElementById("export").onclick=()=>{
  const rows = DATA.results.map(r=>{ const v=review[r.idx]||{}; return {idx:r.idx, query:r.query, score:r.score,
     origin_token_cnt:r.origin_token_cnt, left_token_cnt:r.left_token_cnt,
     gold_kept_frags:r.gold_kept_frags, predicted_kept_frags:r.predicted_kept_frags,
     query_comment:v.query||"", gold_comment:v.gold||"", pred_comment:v.pred||""}; });
  const blob=new Blob([JSON.stringify({meta:DATA.meta, review:rows},null,2)],{type:"application/json"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob);
  a.download="swepruner_review_"+DATA.meta.start+".json"; a.click();
};
document.getElementById("import").onchange=ev=>{
  const file=ev.target.files[0]; if(!file) return;
  const fr=new FileReader();
  fr.onload=()=>{ try{ const j=JSON.parse(fr.result); const arr=j.review||j;
    for(const r of arr){ if(r.idx!=null){ review[r.idx]={query:r.query_comment||"", gold:r.gold_comment||"", pred:r.pred_comment||""}; } }
    persist(); render(); alert("Imported review for "+arr.length+" rows."); }
    catch(e){ alert("Import failed: "+e); } };
  fr.readAsText(file);
};

init();
</script>
</body>
</html>
"""


def main() -> None:
    src = sys.argv[1] if len(sys.argv) > 1 else "results.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "dashboard.html"
    with open(src) as f:
        data = json.load(f)
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", payload)
    with open(out, "w") as f:
        f.write(html)
    print(f"wrote {out} ({len(html)} bytes, {len(data['results'])} rows)")


if __name__ == "__main__":
    main()
