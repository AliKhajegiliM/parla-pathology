#!/usr/bin/env python3
"""Build a self-contained, no-GPU demo page (demo/index.html) for PaRLA from the
committed judge records + generations. Embeds a handful of verified cases so a
reviewer can click through: original report -> base Llama vs PaRLA -> judge verdict.
"""
import json, glob, html, os

BASE = "/Users/ali/claude_content/Report Eval"
OUT = f"{BASE}/parla-pathology/demo/index.html"

CASES = [
    ("TCGA-V7-A7HQ", "Breast", "invasive ductal carcinoma, mastectomy + sentinel nodes"),
    ("TCGA-DK-A1AC", "Bladder", "cystoprostatectomy, high-grade urothelial carcinoma"),
    ("TCGA-A4-7584", "Kidney", "partial nephrectomy + prostatectomy, dual primary"),
    ("TCGA-DX-A3U8", "Sarcoma", "radical orchiectomy, high-grade leiomyosarcoma"),
]

def load(arm):
    d = {}
    for f in glob.glob(f"{BASE}/genrated_token_original_prompt/gen_chandra_{arm}_shard*of3.jsonl"):
        for line in open(f):
            r = json.loads(line); d[r["report_id"]] = r.get("text", "")
    return d

before, after = load("before"), load("after")
J = {x["report_id"]: x for x in (json.loads(l) for l in open(f"{BASE}/model_comparison_500/judgments.jsonl"))}

data = []
for rid, organ, blurb in CASES:
    j = J[rid]
    data.append({
        "id": rid, "organ": organ, "blurb": blurb,
        "base": before[rid], "parla": after[rid],
        "winner": j["winner"], "confidence": j["confidence"],
        "reason": j["reason"],
        "base_omissions": j.get("before_major_omissions", []),
        "parla_omissions": j.get("after_major_omissions", []),
        "base_halluc": j.get("before_hallucinations", []),
        "parla_halluc": j.get("after_hallucinations", []),
    })

DATA_JS = json.dumps(data)

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PaRLA demo — base Llama vs PaRLA on pathology reports</title>
<style>
:root{--blue:#0072B2;--gray:#C9C9C9;--ink:#111;--muted:#555;--line:#e3e3e3;--bg:#f7f8fa}
*{box-sizing:border-box}
body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:var(--ink);margin:0;background:var(--bg);line-height:1.5}
.wrap{max-width:1100px;margin:0 auto;padding:24px 18px 60px}
h1{font-size:1.7rem;margin:.2rem 0}
.sub{color:var(--muted);margin:0 0 18px}
.pills button{font:inherit;border:1px solid var(--line);background:#fff;color:var(--ink);padding:8px 14px;border-radius:999px;margin:4px 6px 4px 0;cursor:pointer}
.pills button.active{background:var(--blue);color:#fff;border-color:var(--blue)}
.meta{margin:14px 0;color:var(--muted);font-size:.95rem}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.cols{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:16px;overflow-x:auto}
.card h3{margin:.1rem 0 .5rem;font-size:1rem}
.card.base h3{color:var(--muted)}
.card.parla{border-color:var(--blue)}
.card.parla h3{color:var(--blue)}
.card pre{white-space:pre-wrap;font-family:inherit;font-size:.92rem;margin:0}
.verdict{margin-top:16px;background:#fff;border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:10px;padding:14px 16px}
.verdict b{color:var(--blue)}
.tag{display:inline-block;background:#eef4fb;color:var(--blue);border-radius:6px;padding:2px 8px;font-size:.8rem;font-weight:600;margin-left:6px}
ul{margin:.4rem 0 .2rem 1.1rem;padding:0}
li{margin:.15rem 0}
.foot{color:var(--muted);font-size:.85rem;margin-top:26px;border-top:1px solid var(--line);padding-top:12px}
a{color:var(--blue)}
</style></head><body><div class="wrap">
<h1>PaRLA: base Llama&nbsp;70B vs&nbsp;PaRLA</h1>
<p class="sub">Real pathology reports abstracted by the base model and by PaRLA, with the GPT-5.5 (Codex) judge's verdict. Precomputed from committed records &mdash; no GPU or download needed. Model: <a href="https://huggingface.co/AliKhajegiliM/PaRLA">huggingface.co/AliKhajegiliM/PaRLA</a></p>
<div class="pills" id="pills"></div>
<div class="meta" id="meta"></div>
<div class="cols">
  <div class="card base"><h3>Base Llama 70B</h3><pre id="base"></pre></div>
  <div class="card parla"><h3>PaRLA</h3><pre id="parla"></pre></div>
</div>
<div class="verdict" id="verdict"></div>
<p class="foot">Cases are drawn from the released <a href="../data/judgments.jsonl">judgments.jsonl</a> (500 TCGA reports). "Major facts missed" are the judge's recorded omissions for each output. Reproduce the aggregate statistics with <a href="../src/analyze_judgments.py">analyze_judgments.py</a>.</p>
</div>
<script>
const DATA = __DATA__;
const esc = s => s;
function li(items){return items.length? '<ul>'+items.map(x=>'<li>'+x+'</li>').join('')+'</ul>' : '<p style="margin:.3rem 0;color:#555">None recorded.</p>';}
function render(i){
  const d = DATA[i];
  document.querySelectorAll('#pills button').forEach((b,k)=>b.classList.toggle('active',k===i));
  document.getElementById('meta').innerHTML = '<b>'+d.organ+'</b> &nbsp;·&nbsp; '+d.blurb+' &nbsp;·&nbsp; <code>'+d.id+'</code>';
  document.getElementById('base').textContent = d.base;
  document.getElementById('parla').textContent = d.parla;
  const winner = d.winner==='after' ? 'PaRLA' : (d.winner==='before'?'Base Llama 70B':'Tie');
  document.getElementById('verdict').innerHTML =
    'Judge verdict: <b>'+winner+' wins</b> <span class="tag">confidence '+d.confidence+'/5</span><br>'+
    '<span style="color:#555">'+d.reason+'</span>'+
    '<div class="cols" style="margin-top:12px"><div><b>Major facts the base model missed ('+d.base_omissions.length+')</b>'+li(d.base_omissions)+'</div>'+
    '<div><b>Major facts PaRLA missed ('+d.parla_omissions.length+')</b>'+li(d.parla_omissions)+
    '<div style="margin-top:6px;color:#555">Unsupported statements &mdash; base: '+d.base_halluc.length+', PaRLA: '+d.parla_halluc.length+'</div></div></div>';
}
const pills = document.getElementById('pills');
DATA.forEach((d,i)=>{const b=document.createElement('button');b.textContent=d.organ;b.onclick=()=>render(i);pills.appendChild(b);});
render(0);
</script></body></html>
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w").write(PAGE.replace("__DATA__", DATA_JS))
print("wrote", OUT, os.path.getsize(OUT), "bytes;", len(data), "cases")
