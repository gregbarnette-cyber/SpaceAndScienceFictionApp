# -*- coding: utf-8 -*-
"""Generator for the Phase O visualization-expansion mockups.
Emits mockups/phase-o/o<NN>-<slug>.html — one interactive HTML mockup per O-item.
Run:  python mockups/phase-o/_gen.py
Re-run any time the look needs adjusting; the HTML files are the deliverable.
"""
import os

OUT = os.path.dirname(os.path.abspath(__file__))

CSS = r"""
:root{
  --bg:#f0f0f0;--panel:#fff;--border:#b8b8b8;--soft:#d8d8d8;--text:#222;--muted:#6a6a6a;
  --accent:#4a90d9;--accent-d:#3a73ad;--head:#e9eef5;--zebra:#f7f9fc;
  --good:#2e8b57;--warn:#b8860b;--bad:#b03030;--space:#0b1020;--ring:#22345a;--ringlbl:#3a5a8a;
}
*{box-sizing:border-box}
html,body{margin:0}
body{font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;font-size:13px;color:var(--text);background:var(--bg)}
.topbar{background:#2b2b2b;color:#eee;padding:8px 14px;font-weight:600;display:flex;align-items:center;gap:10px}
.topbar .sub{color:#9aa3ad;font-weight:400}
.topbar .tag{background:var(--accent);color:#fff;border-radius:3px;padding:1px 7px;font-size:11px}
.notice{background:#fff6da;border-bottom:1px solid #e7d28a;color:#6b5a14;padding:7px 14px;font-size:12px;line-height:1.5}
.notice b{color:#4d4109}.notice code{background:#f4ead0;padding:0 4px;border-radius:3px}
.wrap{max-width:1000px;margin:0 auto;padding:14px 20px 40px}
.hostbar{font-size:12px;color:#41566f;background:#eef4fb;border:1px solid #cfe0f4;border-radius:5px;padding:6px 11px;margin-bottom:12px}
.hostbar b{color:#13314e}.hostbar code{background:#dde9f7;padding:0 4px;border-radius:3px}
.hostbar .tab{display:inline-block;background:#fff;border:1px solid #cfe0f4;border-bottom:2px solid var(--accent);border-radius:4px 4px 0 0;padding:1px 8px;margin-left:4px;font-weight:600;color:#13314e}
h2.title{margin:0 0 2px;font-size:18px}
p.sub{color:var(--muted);margin:4px 0 12px;font-size:12.5px;line-height:1.5}
details.spec{margin:0 0 14px;font-size:12px;color:#555;background:#f5f7fa;border:1px solid var(--soft);border-radius:5px;padding:6px 10px}
details.spec summary{cursor:pointer;font-weight:600;color:#3a73ad}
details.spec code{background:#e9edf2;padding:0 4px;border-radius:3px}
details.spec ul{margin:8px 0 4px;padding-left:18px;line-height:1.6}
.card{background:var(--panel);border:1px solid var(--border);border-radius:6px;padding:11px 13px;margin-bottom:12px}
.card h3{margin:0 0 9px;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:#777}
.ctl{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-bottom:10px}
.ctl .field{display:flex;flex-direction:column;gap:3px}
.ctl label{font-size:11.5px;color:#444;font-weight:600}
.ctl input,.ctl select{height:28px;border:1px solid var(--border);border-radius:4px;padding:0 7px;font-size:12.5px;background:#fff}
.ctl input[type=range]{padding:0;width:260px}
button.btn{height:28px;padding:0 14px;border:1px solid var(--accent-d);background:var(--accent);color:#fff;border-radius:4px;font-size:12.5px;font-weight:600;cursor:pointer}
button.btn:hover{background:var(--accent-d)}
button.ghost{background:#fff;color:#444;border:1px solid var(--border)}
label.chk{font-size:12.5px;color:#333;display:flex;align-items:center;gap:6px;font-weight:600}
.tabstrip{display:flex;gap:2px;margin-bottom:0}
.tabstrip .t{background:#e7ecf2;border:1px solid var(--border);border-bottom:none;border-radius:5px 5px 0 0;padding:5px 12px;font-size:12px;cursor:pointer;color:#555}
.tabstrip .t.active{background:#fff;color:#13314e;font-weight:600;position:relative;top:1px}
.tabbody{background:#fff;border:1px solid var(--border);border-radius:0 6px 6px 6px;padding:12px}
.tabpane{display:none}.tabpane.active{display:block}
svg.diagram{width:100%;display:block;background:#f5f5f5;border:1px solid #ddd;border-radius:5px}
svg.dark{background:var(--space);border:1px solid #233}
.legend{font-size:11px;color:#777;margin-top:7px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.legend i{display:inline-block;width:13px;height:13px;border-radius:50%;vertical-align:middle;margin-right:4px}
.legend i.line{height:0;width:18px;border-top-width:2px;border-radius:0}
.foot{font-size:11px;color:var(--warn);font-style:italic;margin-top:6px}
.readout{font-size:12.5px;font-weight:600;color:var(--accent-d);margin:4px 0}
table{border-collapse:collapse;width:100%;font-size:12px}
th{background:var(--head);text-align:left;padding:5px 8px;border-bottom:1px solid var(--border);font-size:11px;white-space:nowrap}
td{padding:4px 8px;border-bottom:1px solid #eee;white-space:nowrap}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tr:nth-child(even) td{background:var(--zebra)}
tr.sel td{background:#fff3c4 !important}
.mocknote{background:#f3f0fa;border:1px solid #d9cdf0;color:#5b478a;padding:8px 11px;border-radius:5px;font-size:12px;margin-top:14px;line-height:1.5}
.mocknote code{background:#e7ddf5;padding:0 4px;border-radius:3px}
.tip{position:fixed;pointer-events:none;background:#11203a;color:#cfe3ff;border:1px solid #2a4a72;font-size:11px;padding:3px 7px;border-radius:4px;display:none;z-index:9}
.modal{position:fixed;inset:0;background:rgba(10,14,25,.55);display:none;align-items:center;justify-content:center;z-index:50}
.modal.open{display:flex}
.modalbox{background:#fff;max-width:680px;max-height:84vh;overflow:auto;border-radius:8px;border:1px solid #b8b8b8;box-shadow:0 12px 44px rgba(0,0,0,.32);padding:18px 22px}
.modalbox h3{margin:0 0 2px;font-size:16px}
.modalbox h4{margin:14px 0 3px;font-size:11.5px;color:#3a73ad;text-transform:uppercase;letter-spacing:.4px}
.modalbox p{margin:5px 0;line-height:1.55;font-size:12.5px}
.modalbox table{margin:8px 0}
.modalbox .x{float:right;cursor:pointer;color:#999;font-size:20px;font-weight:700;line-height:.8}
.modalbox code{background:#eef;padding:0 4px;border-radius:3px}
"""

PRELUDE = r"""
const SPC={O:"#9bb0ff",B:"#aabfff",A:"#cad7ff",F:"#f8f7ff",G:"#fff4c2",K:"#ffd2a1",M:"#ff9d6c",D:"#dfe6ff","?":"#cccccc"};
const $=id=>document.getElementById(id);
const f=(v,d)=>Number(v).toFixed(d);
const lin=(v,a,b,p,q)=>p+(v-a)/(b-a)*(q-p);
const L10=Math.log10;
function setsvg(id,inner,vb){const e=$(id);if(vb)e.setAttribute('viewBox',vb);e.innerHTML=inner;}
function tip(){let t=$('__tip');if(!t){t=document.createElement('div');t.id='__tip';t.className='tip';document.body.appendChild(t);}return t;}
function bindTip(svgId){const s=$(svgId);s.addEventListener('mousemove',e=>{const el=document.elementFromPoint(e.clientX,e.clientY);const tt=el&&el.getAttribute&&el.getAttribute('data-tip');const t=tip();if(tt){t.textContent=tt;t.style.display='block';t.style.left=(e.clientX+12)+'px';t.style.top=(e.clientY+12)+'px';}else t.style.display='none';});s.addEventListener('mouseleave',()=>tip().style.display='none');}
function tabs(){document.querySelectorAll('.tabstrip .t').forEach(t=>t.onclick=()=>{const g=t.dataset.group,n=t.dataset.tab;document.querySelectorAll('.tabstrip .t[data-group="'+g+'"]').forEach(x=>x.classList.toggle('active',x===t));document.querySelectorAll('.tabpane[data-group="'+g+'"]').forEach(p=>p.classList.toggle('active',p.dataset.tab===n));window.dispatchEvent(new Event('resize'));});}
const star=(cx,cy,r,fill,t)=>`<path d="M${cx},${cy-r} L${cx+r*0.3},${cy-r*0.3} L${cx+r},${cy-r*0.3} L${cx+r*0.42},${cy+r*0.12} L${cx+r*0.62},${cy+r*0.9} L${cx},${cy+r*0.4} L${cx-r*0.62},${cy+r*0.9} L${cx-r*0.42},${cy+r*0.12} L${cx-r},${cy-r*0.3} L${cx-r*0.3},${cy-r*0.3} Z" fill="${fill}" stroke="#7a5c00" stroke-width="0.5"${t?` data-tip="${t}"`:''}/>`;
"""

CATJS = r"""
/* nearby-star catalog (approx heliocentric ly) + V mag + parsecs for vantage/HR maths */
const CAT=[
 {name:"Sol",x:0,y:0,z:0,cls:"G",mag:-26.74,pc:0},
 {name:"Proxima Cen",x:-1.53,y:-1.20,z:-3.77,cls:"M",mag:11.13,pc:1.30},
 {name:"Alpha Cen A",x:-1.61,y:-1.31,z:-3.81,cls:"G",mag:-0.01,pc:1.34},
 {name:"Alpha Cen B",x:-1.62,y:-1.30,z:-3.80,cls:"K",mag:1.33,pc:1.34},
 {name:"Barnard's Star",x:-0.06,y:5.94,z:0.49,cls:"M",mag:9.53,pc:1.83},
 {name:"Wolf 359",x:-7.42,y:2.10,z:1.02,cls:"M",mag:13.44,pc:2.41},
 {name:"Lalande 21185",x:-6.28,y:1.72,z:4.78,cls:"M",mag:7.52,pc:2.55},
 {name:"Sirius",x:-1.61,y:8.07,z:-2.45,cls:"A",mag:-1.46,pc:2.64},
 {name:"Luyten 726-8",x:7.20,y:3.02,z:-2.88,cls:"M",mag:12.10,pc:2.68},
 {name:"Ross 154",x:1.87,y:-8.46,z:-1.70,cls:"M",mag:10.44,pc:2.98},
 {name:"Epsilon Eridani",x:7.20,y:-6.48,z:-2.51,cls:"K",mag:3.73,pc:3.21},
 {name:"Procyon",x:-0.46,y:11.40,z:1.10,cls:"F",mag:0.34,pc:3.51},
 {name:"61 Cygni A",x:6.50,y:6.13,z:7.13,cls:"K",mag:5.21,pc:3.50},
 {name:"Tau Ceti",x:10.22,y:-4.97,z:-3.27,cls:"G",mag:3.50,pc:3.65},
 {name:"Epsilon Indi",x:5.74,y:-3.07,z:-10.28,cls:"K",mag:4.69,pc:3.62},
 {name:"Gliese 581",x:-15.1,y:8.3,z:-6.2,cls:"M",mag:10.57,pc:6.30},
 {name:"Vega",x:5.0,y:24.3,z:7.9,cls:"A",mag:0.03,pc:7.68},
 {name:"Altair",x:8.6,y:13.8,z:2.8,cls:"A",mag:0.76,pc:5.13},
];
CAT.forEach(s=>s.color=SPC[s.cls]||SPC["?"]);
"""

MSJS = r"""
const MS=[
 {c:"O5",teff:42000,M:-5.7},{c:"B0",teff:30000,M:-4.1},{c:"B5",teff:15200,M:-1.1},
 {c:"A0",teff:9790,M:0.7},{c:"A5",teff:8180,M:2.0},{c:"F0",teff:7300,M:2.6},
 {c:"F5",teff:6650,M:3.4},{c:"G0",teff:5940,M:4.4},{c:"G2",teff:5780,M:4.83},
 {c:"G5",teff:5560,M:5.1},{c:"K0",teff:5150,M:5.9},{c:"K5",teff:4410,M:7.4},
 {c:"M0",teff:3840,M:8.8},{c:"M2",teff:3520,M:10.1},{c:"M5",teff:3170,M:12.3},{c:"M8",teff:2600,M:16.0}
];
"""

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>%%CSS%%</style></head>
<body>
<div class="topbar">Space &amp; Science Fiction App <span class="sub">— GUI mockup</span>
  <span class="tag">Phase O · %%TAG%%</span></div>
<div class="notice"><b>Interactive viz mockup — not the real app.</b> %%LEAD%%
  This page renders the proposed diagram client-side over representative data so the look can be reviewed; the real app draws it with matplotlib via the noted helpers.</div>
<div class="wrap">
  <div class="hostbar">%%HOST%%</div>
  <h2 class="title">%%H2%%</h2>
  <p class="sub">%%SUB%%</p>
  <details class="spec"><summary>Plan details (from <code>future_phases.md</code>)</summary><ul>%%SPEC%%</ul></details>
  %%BODY%%
  <div class="mocknote">%%NOTE%%</div>
</div>
<script>%%PRELUDE%%
%%SCRIPT%%</script>
</body></html>
"""

def emit(num, slug, **k):
    spec = "".join("<li>%s</li>" % s for s in k["spec"])
    prelude = PRELUDE
    if k.get("cat"): prelude += CATJS
    if k.get("ms"): prelude += MSJS
    html = (TEMPLATE
        .replace("%%CSS%%", CSS)
        .replace("%%TITLE%%", "O%d — %s (Phase O mockup)" % (num, k["h2"]))
        .replace("%%TAG%%", k["tag"])
        .replace("%%LEAD%%", k["lead"])
        .replace("%%HOST%%", k["host"])
        .replace("%%H2%%", "O%d · %s" % (num, k["h2"]))
        .replace("%%SUB%%", k["sub"])
        .replace("%%SPEC%%", spec)
        .replace("%%BODY%%", k["body"])
        .replace("%%NOTE%%", k["note"])
        .replace("%%PRELUDE%%", prelude)
        .replace("%%SCRIPT%%", k["script"]))
    path = os.path.join(OUT, "o%02d-%s.html" % (num, slug))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
    print("wrote", os.path.basename(path), len(html), "bytes")

# ------------------------------------------------------------------ O1
emit(1, "night-sky",
 tag="O1 · Night Sky", ms=False, cat=True,
 lead="A celestial-sphere view of the sky <i>as seen from</i> the queried star.",
 host='Adds a <span class="tab">Night Sky</span> viz tab to <b>opt 19 — Stars within a Certain Distance of a Star</b> (<code>StarsWithinDistanceStarPanel</code>).',
 h2="Night Sky From Another Star",
 sub="Each catalog star is re-projected onto the sky of the chosen vantage star; apparent magnitude is recomputed from that vantage. Sol appears pointing back home (M_V 4.83).",
 spec=[
  "<code>core.viz.prepare_sky_from_star(result, mag_limit=6.5)</code> — RA/Dec from the vantage vector; <code>m' = M − 5 + 5·log₁₀(d_ly/3.26156)</code>.",
  "Stars with NULL V mag are <b>skipped &amp; counted</b> (<code>skipped_no_mag</code>) — never given a fabricated magnitude.",
  "Prereq: thread <code>app_magnitude</code>/<code>parsecs</code> through the opts-18/19 rows (shared with O2b).",
  "<code>make_sky_canvas</code> — Aitoff (or rectangular RA/Dec fallback); marker size by brightness; dark-navy palette."],
 body='''
  <div class="card">
   <div class="ctl">
     <div class="field"><label>Vantage star</label><select id="van"></select></div>
     <div class="field"><label>Limiting magnitude m'</label><input id="mag" value="6.5" style="width:80px"></div>
     <button class="btn" onclick="draw()">Apply</button>
   </div>
   <svg class="diagram dark" id="sky" viewBox="0 0 640 360" style="height:360px"></svg>
   <div class="legend"><span>○ size ∝ brightness</span><span><i style="background:#fff4c2"></i>G</span><span><i style="background:#ffd2a1"></i>K</span><span><i style="background:#ff9d6c"></i>M</span><span><i style="background:#cad7ff"></i>A/F</span></div>
   <div class="foot" id="foot"></div>
  </div>''',
 note='Real app: a <b>Night Sky</b> tab on opt 19 with a mag-limit field that re-runs <code>prepare_sky_from_star</code> on the cached result (no new query). The view only holds stars within the queried distance limit — querying ≥ 50 ly gives a fuller sky.',
 script=r'''
const sel=$('van');CAT.filter(s=>s.name!=="Sol").forEach(s=>sel.add(new Option(s.name,s.name)));sel.value="Alpha Cen A";
bindTip('sky');
function draw(){
 const v=CAT.find(s=>s.name===sel.value);const lim=parseFloat($('mag').value)||6.5;
 const others=CAT.filter(s=>s!==v);let skipped=0;const sky=[];
 others.forEach(s=>{
   const dx=s.x-v.x,dy=s.y-v.y,dz=s.z-v.z,d=Math.hypot(dx,dy,dz);if(d<1e-6)return;
   if(s.mag==null||s.name==="Sol"&&false){skipped++;return;}
   const ra=(Math.atan2(dy,dx)*180/Math.PI+360)%360, dec=Math.asin(dz/d)*180/Math.PI;
   const absM = (s.name==="Sol")?4.83 : s.mag - 5 + 5*L10(Math.max(s.pc,1e-3));
   const m = absM - 5 + 5*L10(d/3.26156);
   if(m>lim){return;}
   sky.push({name:s.name,ra,dec,m,cls:s.cls,d});
 });
 // rectangular RA/Dec (clear hover maths); RA reversed
 const x0=44,x1=624,y0=20,y1=320, sx=ra=>lin(ra,360,0,x0,x1), sy=de=>lin(de,90,-90,y0,y1);
 let g='';
 for(let ra=0;ra<=360;ra+=60){const X=sx(ra);g+=`<line x1="${X}" y1="${y0}" x2="${X}" y2="${y1}" stroke="#1a2448"/><text x="${X}" y="${y1+13}" fill="#5b78a8" font-size="9" text-anchor="middle">${ra}°</text>`;}
 for(let de=-90;de<=90;de+=30){const Y=sy(de);g+=`<line x1="${x0}" y1="${Y}" x2="${x1}" y2="${Y}" stroke="#1a2448"/><text x="${x0-5}" y="${Y+3}" fill="#5b78a8" font-size="9" text-anchor="end">${de>0?'+':''}${de}°</text>`;}
 const mmin=Math.min(...sky.map(s=>s.m));
 let dots='';sky.forEach(s=>{const r=Math.max(1.6,Math.min(9,3.2*Math.pow(10,-0.4*(s.m-mmin))));
   dots+=`<circle cx="${sx(s.ra)}" cy="${sy(s.dec)}" r="${r}" fill="${SPC[s.cls]}" stroke="#05080d" stroke-opacity="0.4" data-tip="${s.name} — m'=${f(s.m,2)} · ${f(s.d,2)} ly"/>`;
   if(r>4) dots+=`<text x="${sx(s.ra)+r+2}" y="${sy(s.dec)+3}" fill="#9fb8d8" font-size="8.5">${s.name}</text>`;});
 setsvg('sky',`<text x="${(x0+x1)/2}" y="13" fill="#cfe3ff" font-size="11" text-anchor="middle">Night sky from ${v.name} (to m=${f(lim,1)})</text>${g}${dots}`);
 $('foot').textContent = skipped? `${skipped} star(s) omitted (no V magnitude).` : `${sky.length} stars shown · RA reversed (sky convention).`;
}
draw();''')

# ------------------------------------------------------------------ O2
emit(2, "hr-diagram",
 tag="O2 · HR Diagram", ms=True, cat=True,
 lead="The app's first HR / colour–magnitude diagram.",
 host='New <span class="tab">HR Diagram</span> tab on <b>opt 12 (Main Sequence)</b> and result overlay on <b>opts 18/19</b>.',
 h2="HR / Colour–Magnitude Diagram",
 sub="O2a: the main-sequence reference line from the main_sequence_stars table. O2b: result stars (opts 18/19) overlaid as scatter, Teff from the spectral-class ceiling-rule lookup.",
 spec=[
  "<code>prepare_hr_main_sequence()</code> → connected, labelled MS line; <code>make_hr_canvas(parent,data,overlay_points)</code>.",
  "x = Teff (K), <b>log scale, inverted</b> (hot left); y = absolute visual mag, <b>inverted</b> (bright top).",
  "O2b: per-result-star <code>M_V = app_magnitude + 5 − 5·log₁₀(parsecs)</code>; missing mag / non-OBAFGKM class → skipped + counted."],
 body='''
  <div class="card">
   <label class="chk"><input type="checkbox" id="ov" checked onchange="draw()"> Overlay opt-19 result stars (O2b)</label>
   <svg class="diagram" id="hr" viewBox="0 0 640 400" style="height:400px;margin-top:8px"></svg>
   <div class="legend"><span><i class="line" style="border-top:2px solid #4a6"></i>main sequence (ref)</span><span><i style="background:#b03030"></i>result star</span><span>top axis: spectral class</span></div>
  </div>''',
 note='Real app: <code>MainSequencePanel</code> gains <code>DiagramToggleMixin</code> + an <b>HR Diagram</b> tab; opts 18/19 add the same canvas with <code>overlay_points</code>. The GCNS BP−RP CMD is a separate Phase M extension, not duplicated here.',
 script=r'''
bindTip('hr');
const x0=52,x1=612,y0=28,y1=360;
const tmin=2400,tmax=45000, mmin=-7,mmax=17;
const sx=t=>lin(L10(t),L10(tmax),L10(tmin),x0,x1), sy=m=>lin(m,mmin,mmax,y0,y1);
const RES=[{name:"Sirius",cls:"A",teff:9790,M:1.42},{name:"Procyon",cls:"F",teff:6530,M:2.66},
 {name:"Alpha Cen A",cls:"G",teff:5790,M:4.38},{name:"Epsilon Eri",cls:"K",teff:5080,M:6.19},
 {name:"Barnard's",cls:"M",teff:3130,M:13.2},{name:"Tau Ceti",cls:"G",teff:5340,M:5.69}];
function draw(){
 let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 for(const t of [40000,20000,10000,7000,5000,4000,3000]){const X=sx(t);g+=`<line x1="${X}" y1="${y0}" x2="${X}" y2="${y1}" stroke="#eee"/><text x="${X}" y="${y1+14}" fill="#555" font-size="9" text-anchor="middle">${t}</text>`;}
 for(let m=-5;m<=15;m+=5){const Y=sy(m);g+=`<line x1="${x0}" y1="${Y}" x2="${x1}" y2="${Y}" stroke="#eee"/><text x="${x0-5}" y="${Y+3}" fill="#555" font-size="9" text-anchor="end">${m}</text>`;}
 // top spectral-class axis
 for(const r of MS.filter(r=>["O5","B0","A0","F0","G0","K0","M0","M8"].includes(r.c))){const X=sx(r.teff);g+=`<text x="${X}" y="${y0-6}" fill="#3a73ad" font-size="9" text-anchor="middle">${r.c[0]}</text>`;}
 // MS line
 let path=MS.map((r,i)=>`${i?'L':'M'}${f(sx(r.teff),1)},${f(sy(r.M),1)}`).join(' ');
 g+=`<path d="${path}" fill="none" stroke="#4a6a55" stroke-width="2"/>`;
 MS.forEach((r,i)=>{const X=sx(r.teff),Y=sy(r.M);g+=`<circle cx="${X}" cy="${Y}" r="2.6" fill="#4a6a55" data-tip="${r.c} · ${r.teff} K · M=${r.M}"/>`;if(i%2===0)g+=`<text x="${X+4}" y="${Y-3}" fill="#789" font-size="8">${r.c}</text>`;});
 if($('ov').checked) RES.forEach(s=>{const X=sx(s.teff),Y=sy(s.M);g+=`<circle cx="${X}" cy="${Y}" r="5" fill="#b03030" stroke="#fff" stroke-width="1" data-tip="${s.name} · ${s.teff} K · M_V=${s.M}"/><text x="${X+7}" y="${Y+3}" fill="#7a1414" font-size="9">${s.name}</text>`;});
 g+=`<text x="${(x0+x1)/2}" y="${y1+30}" fill="#444" font-size="10" text-anchor="middle">Effective temperature (K) — hot left, log scale</text>`;
 g+=`<text x="14" y="${(y0+y1)/2}" fill="#444" font-size="10" text-anchor="middle" transform="rotate(-90 14 ${(y0+y1)/2})">Absolute visual magnitude — bright up</text>`;
 setsvg('hr',g);
}
draw();''')

# ------------------------------------------------------------------ O3
emit(3, "mass-radius",
 tag="O3 · Mass–Radius", cat=False,
 lead="A planet mass–radius diagram with composition reference curves.",
 host='New <span class="tab">Mass–Radius</span> tab on <b>opts 3, 6</b> and the Map panel.',
 h2="Mass–Radius Diagram",
 sub="Log–log scatter of system planets against constant-density composition curves and the eight Solar-System reference points.",
 spec=[
  "<code>prepare_mass_radius(planets, mass_key, radius_key, name_key)</code> — generic over NASA (<code>pl_bmasse/pl_rade</code>) &amp; HWC (<code>P_MASS/P_RADIUS</code>); filters to planets with both values.",
  "Curves: <code>R = (M/(ρ/ρ⊕))^(1/3)</code>, ρ⊕=5.51 — iron 7.9, rock 5.51, water 1.0, Jupiter 1.33. Deliberately constant-density, <b>not</b> Zeng models.",
  "Tab added only when ≥ 1 planet has both mass &amp; radius."],
 body='''
  <div class="card">
   <svg class="diagram" id="mr" viewBox="0 0 640 420" style="height:420px"></svg>
   <div class="legend"><span><i class="line" style="border-top:2px dashed #999"></i>density curves</span><span><i style="background:#9aa"></i>Solar System</span><span><i style="background:#4a90d9"></i>system planet</span></div>
  </div>''',
 note='Real app: <code>make_mass_radius_canvas</code>; the curve set is labelled "constant density" in the legend so it is not mistaken for an interior model.',
 script=r'''
bindTip('mr');
const x0=54,x1=620,y0=20,y1=372;
const mmin=0.05,mmax=4000,rmin=0.3,rmax=25;
const sx=m=>lin(L10(m),L10(mmin),L10(mmax),x0,x1), sy=r=>lin(L10(r),L10(rmin),L10(rmax),y1,y0);
const SS=[["Mercury",0.055,0.383],["Mars",0.107,0.532],["Venus",0.815,0.95],["Earth",1,1],["Uranus",14.5,4.01],["Neptune",17.1,3.88],["Saturn",95.2,9.45],["Jupiter",317.8,11.21]];
const SYS=[["b",4.8,1.9],["c",2.0,1.25],["d",11.0,3.1],["e",0.9,0.98],["f",46,4.6]];
const curves=[["iron",7.9,"#b06a4a"],["rock",5.51,"#7a8a55"],["water",1.0,"#4a7fa8"],["Jupiter ρ",1.33,"#a08a4a"]];
function draw(){
 let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 for(const m of [0.1,1,10,100,1000]){const X=sx(m);g+=`<line x1="${X}" y1="${y0}" x2="${X}" y2="${y1}" stroke="#f0f0f0"/><text x="${X}" y="${y1+14}" fill="#555" font-size="9" text-anchor="middle">${m}</text>`;}
 for(const r of [0.5,1,2,5,10,20]){const Y=sy(r);g+=`<line x1="${x0}" y1="${Y}" x2="${x1}" y2="${Y}" stroke="#f0f0f0"/><text x="${x0-5}" y="${Y+3}" fill="#555" font-size="9" text-anchor="end">${r}</text>`;}
 curves.forEach(([nm,rho,col])=>{let p='';for(let i=0;i<=60;i++){const m=mmin*Math.pow(mmax/mmin,i/60);const r=Math.pow(m/(rho/5.51),1/3);if(r<rmin||r>rmax)continue;p+=`${p?'L':'M'}${f(sx(m),1)},${f(sy(r),1)} `;}g+=`<path d="${p}" fill="none" stroke="${col}" stroke-width="1.3" stroke-dasharray="5 4" opacity="0.8"/>`;const lm=2000,lr=Math.pow(lm/(rho/5.51),1/3);if(lr<=rmax)g+=`<text x="${sx(lm)}" y="${sy(lr)-2}" fill="${col}" font-size="8.5">${nm}</text>`;});
 SS.forEach(([nm,m,r])=>{g+=`<circle cx="${sx(m)}" cy="${sy(r)}" r="3" fill="#9aa" data-tip="${nm} (Solar System)"/><text x="${sx(m)+4}" y="${sy(r)+3}" fill="#778" font-size="8">${nm}</text>`;});
 SYS.forEach(([nm,m,r])=>{g+=`<circle cx="${sx(m)}" cy="${sy(r)}" r="5" fill="#4a90d9" stroke="#fff" data-tip="planet ${nm}: ${m} M⊕, ${r} R⊕"/><text x="${sx(m)+6}" y="${sy(r)+3}" fill="#26537d" font-size="9">${nm}</text>`;});
 g+=`<text x="${(x0+x1)/2}" y="${y1+30}" fill="#444" font-size="10" text-anchor="middle">Mass (M⊕, log)</text>`;
 g+=`<text x="14" y="${(y0+y1)/2}" fill="#444" font-size="10" text-anchor="middle" transform="rotate(-90 14 ${(y0+y1)/2})">Radius (R⊕, log)</text>`;
 setsvg('mr',g);
}
draw();''')

# ------------------------------------------------------------------ O4
emit(4, "solar-overlay",
 tag="O4 · Solar Overlay", cat=False,
 lead="An optional Solar-System reference overlay on the orbital diagrams.",
 host='Adds a checkbox above the <b>Orbital Diagram</b> on <b>opts 3, 6</b> and the Map panel.',
 h2="Solar System Reference Overlay",
 sub="Toggles dashed grey circles at the Solar planets' SMAs over the existing exoplanet orbital diagram. Off by default — existing renders unchanged.",
 spec=[
  "<code>make_orbits_canvas()</code> gains <code>solar_overlay: bool = False</code>; draws dashed circles at <code>_PLANET_SMAS</code> for planets with SMA ≤ max_au×1.1.",
  "A <i>“Show Solar System reference”</i> checkbox rebuilds the canvas (cheap — same data).",
  "Default unchecked → byte-identical to today."],
 body='''
  <div class="card">
   <label class="chk"><input type="checkbox" id="ov" onchange="draw()"> Show Solar System reference</label>
   <svg class="diagram" id="orb" viewBox="0 0 560 460" style="height:460px;margin-top:8px"></svg>
   <div class="legend"><span><i class="line" style="border-top:2px solid #4a90d9"></i>exoplanet orbit</span><span><i style="background:#bfe3bf"></i>HZ annulus</span><span><i class="line" style="border-top:2px dashed #999"></i>Solar planet (overlay)</span></div>
  </div>''',
 note='Real app: additive <code>solar_overlay</code> param; the dashed circles get a small end-of-orbit label (Mercury…Neptune).',
 script=r'''
const cx=280,cy=235,maxAU=5.5,sc=190/maxAU;
const PL=[["Mercury",0.39],["Venus",0.72],["Earth",1.0],["Mars",1.52],["Jupiter",5.2]];
const EXO=[["b",0.45,0.05],["c",1.1,0.12],["d",2.4,0.30]];
const HZ=[0.95,1.67];
function draw(){
 let g=`<circle cx="${cx}" cy="${cy}" r="${HZ[1]*sc}" fill="#bfe3bf" opacity="0.5"/><circle cx="${cx}" cy="${cy}" r="${HZ[0]*sc}" fill="#f5f5f5"/>`;
 if($('ov').checked) PL.forEach(([nm,a])=>{if(a>maxAU*1.1)return;g+=`<circle cx="${cx}" cy="${cy}" r="${a*sc}" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="5 4"/><text x="${cx+a*sc*0.7071}" y="${cy-a*sc*0.7071}" fill="#888" font-size="8">${nm}</text>`;});
 EXO.forEach(([nm,a,e])=>{const rx=a*sc,ry=a*Math.sqrt(1-e*e)*sc;g+=`<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="none" stroke="#4a90d9" stroke-width="1.6"/>`;const px=cx+rx,py=cy;g+=`<circle cx="${px}" cy="${py}" r="5" fill="#2e6cb0"/><text x="${px+6}" y="${py+3}" fill="#26537d" font-size="9">planet ${nm}</text>`;});
 g+=star(cx,cy,8,"#FFD700","host star")+`<text x="${cx+10}" y="${cy+12}" fill="#7a5c00" font-size="9">host</text>`;
 setsvg('orb',g);
}
draw();''')

# ------------------------------------------------------------------ O5
emit(5, "date-scrubber",
 tag="O5 · Date Scrubber", cat=False,
 lead="A date slider / animation over the System Map.",
 host='Adds a slider + Play/Pause below the <b>System Map</b> on <code>NasaPlanetarySystemsMapPanel</code>; an approximate propagated mode on opts 22–23.',
 h2="Date Scrubber / Orbital Animation",
 sub="The System Map already solves Kepler offline for any date — this drives it with a slider so planets sweep their orbits. Only marker offsets move; orbits and star are static artists.",
 spec=[
  "Slider spans <code>[date − span, date + span]</code>, span = min(2× longest period, 50 yr); throttled 50 ms recompute via <code>prepare_exoplanet_system_diagram</code>.",
  "Play steps at ~10 fps; updates <code>PathCollection.set_offsets</code> + <code>draw_idle()</code> only.",
  "<code>epoch_known=False</code> planets stay pinned at periastron (open-ring overlay) — the scrubber invents no motion for them.",
  "Opts 22/23: approximate <i>propagation</i> along circular reference orbits with a persistent “approximate positions” label."],
 body='''
  <div class="card">
   <svg class="diagram dark" id="sys" viewBox="0 0 560 440" style="height:440px"></svg>
   <div class="ctl" style="margin-top:10px">
     <button class="btn" id="play" onclick="toggle()">▶ Play</button>
     <input type="range" id="slider" min="0" max="365" value="0" oninput="frame()">
     <div class="readout" id="ro"></div>
   </div>
   <div class="legend"><span>● planet (date-resolved)</span><span>○ open ring = no epoch (pinned at periastron)</span></div>
  </div>''',
 note='Real app: orbits/star drawn once; only planet markers re-offset per frame — smooth, no Horizons calls during scrubbing.',
 script=r'''
const cx=280,cy=225,maxAU=3.2,sc=170/maxAU;
const P=[{nm:"b",a:0.4,e:0.04,per:36,ep:true,ph:0.1},{nm:"c",a:1.0,e:0.10,per:150,ep:true,ph:1.2},{nm:"d",a:1.9,e:0.22,per:380,ep:true,ph:2.6},{nm:"e",a:2.6,e:0.05,per:600,ep:false,ph:0}];
function kepler(M,e){let E=M;for(let i=0;i<6;i++)E=E-(E-e*Math.sin(E)-M)/(1-e*Math.cos(E));return E;}
function pos(p,day){const M=p.ph+2*Math.PI*day/p.per;const E=kepler(M,p.e);const xv=p.a*(Math.cos(E)-p.e),yv=p.a*Math.sqrt(1-p.e*p.e)*Math.sin(E);return[cx+xv*sc,cy-yv*sc];}
let baseOrbits='';
P.forEach(p=>{const rx=p.a*sc,ry=p.a*Math.sqrt(1-p.e*p.e)*sc;baseOrbits+=`<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="none" stroke="#2a3f66" stroke-width="1"/>`;});
function frame(){
 const day=parseInt($('slider').value,10);
 let m='';P.forEach((p,i)=>{const[x,y]=p.ep?pos(p,day):[cx+p.a*(1-p.e)*sc,cy];const col=["#9bd","#fff4c2","#ff9d6c","#ad8"][i];
   m+= p.ep? `<circle cx="${x}" cy="${y}" r="5.5" fill="${col}" data-tip="planet ${p.nm}"/>` : `<circle cx="${x}" cy="${y}" r="5.5" fill="none" stroke="${col}" stroke-width="2" data-tip="planet ${p.nm} — no epoch (pinned)"/>`;
   m+=`<text x="${x+7}" y="${y+3}" fill="#9fb8d8" font-size="8.5">${p.nm}</text>`;});
 setsvg('sys',`<text x="${cx}" y="16" fill="#cfe3ff" font-size="11" text-anchor="middle">System map — day +${day}</text>${baseOrbits}${star(cx,cy,8,"#FFD700","host")}${m}`);
 const d=new Date(2026,5,14);d.setDate(d.getDate()+day);$('ro').textContent="Map date: "+d.toISOString().slice(0,10);
}
let timer=null;
function toggle(){if(timer){clearInterval(timer);timer=null;$('play').textContent="▶ Play";}else{$('play').textContent="⏸ Pause";timer=setInterval(()=>{let v=(parseInt($('slider').value,10)+4)%366;$('slider').value=v;frame();},80);}}
bindTip('sys');frame();''')

# ------------------------------------------------------------------ O6
emit(6, "sol-regions-parity",
 tag="O6 · Sol Regions Parity", cat=False,
 lead="Diagram parity for opt 13 — it computes the same regions dict as opts 8–10 but has no diagrams.",
 host='Adds the three ring-diagram tabs opts 9/10 already have to <b>opt 13 — Sol Solar System Regions</b>.',
 h2="Diagram Parity for Sol Regions",
 sub="opt 13 → DiagramToggleMixin + HZ Diagram / System Regions Diagram / Alternate HZ Diagram, reusing the existing prepare_*_diagram pipeline. Seven data tabs unchanged.",
 spec=[
  "Pass the <code>compute_sol_regions()</code> dict through <code>prepare_hz_diagram</code> / <code>prepare_system_regions_diagram</code> / <code>prepare_alt_hz_diagram</code> — no new core code.",
  "opt 13 renders at construction (no Run button) → give it a minimal Show-Diagrams flow or refactor to the render pattern. Data-tab behaviour must not change."],
 body='''
  <div class="tabstrip">
    <div class="t active" data-group="o6" data-tab="hz">HZ Diagram</div>
    <div class="t" data-group="o6" data-tab="reg">System Regions</div>
    <div class="t" data-group="o6" data-tab="alt">Alternate HZ</div>
  </div>
  <div class="tabbody">
    <div class="tabpane active" data-group="o6" data-tab="hz"><svg class="diagram" id="hz" viewBox="0 0 480 360" style="height:360px"></svg></div>
    <div class="tabpane" data-group="o6" data-tab="reg"><svg class="diagram" id="reg" viewBox="0 0 480 360" style="height:360px"></svg></div>
    <div class="tabpane" data-group="o6" data-tab="alt"><svg class="diagram" id="alt" viewBox="0 0 480 360" style="height:360px"></svg></div>
  </div>''',
 note='Real app: identical concentric-ring canvases to opts 8–10, just fed the Sun\'s region dict (G2V, 5778 K, L=1).',
 script=r'''
tabs();
function rings(id,zones,scale,unit){const cx=240,cy=180;let mx=Math.max(...zones.map(z=>z.au));const R=150/Math.pow(mx,scale);
 let g='';zones.slice().reverse().forEach(z=>{const r=Math.pow(z.au,scale)*R;g+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="${z.fill||'none'}" stroke="${z.c}" stroke-width="2" ${z.dash?'stroke-dasharray="5 4"':''}/>`;});
 zones.forEach(z=>{const r=Math.pow(z.au,scale)*R;g+=`<text x="${cx}" y="${cy-r-2}" fill="#444" font-size="8.5" text-anchor="middle">${z.label} ${f(z.au,2)}</text>`;});
 g+=star(cx,cy,7,"#FFD700","Sun");setsvg(id,g);}
rings('hz',[{label:"Recent Venus",au:0.75,c:"#cc7a00"},{label:"Runaway GH",au:0.95,c:"#2e8b57"},{label:"Max GH",au:1.67,c:"#2e8b57"},{label:"Early Mars",au:1.77,c:"#cc7a00"}],0.5);
rings('reg',[{label:"Grav",au:0.2,c:"#888"},{label:"HZ in",au:0.95,c:"#2e8b57"},{label:"HZ out",au:1.37,c:"#2e8b57"},{label:"Snow",au:5.0,c:"#4a7fa8"},{label:"LH2",au:20,c:"#6a6acc"},{label:"Outer",au:40,c:"#888"}],0.5);
rings('alt',[{label:"FF",au:0.14,c:"#a05"},{label:"FS",au:0.56,c:"#a50"},{label:"PrW",au:1.12,c:"#2e8b57"},{label:"PrA",au:2.0,c:"#08a"},{label:"PM",au:9,c:"#582"},{label:"PH",au:20,c:"#55a"}],0.25);''')

# ------------------------------------------------------------------ O7
emit(7, "solar-orbits",
 tag="O7 · Solar Orbits", cat=False,
 lead="Orbital diagrams for the Solar-System data (opt 11 shows orbital elements as text only).",
 host='Adds <span class="tab">Orbital Diagram</span> + <span class="tab">Moon Systems</span> tabs to <b>opt 11</b>.',
 h2="Solar System Orbital Diagrams",
 sub="Reuses make_orbits_canvas (no HZ zones). A combo box switches the Moon Systems view between planets.",
 spec=[
  "<code>prepare_solar_system_orbits(kind)</code> — kind ∈ planets / dwarfs+asteroids / moons:&lt;planet&gt; (moon SMA-km → AU via /1.496e8).",
  "Returns the same <code>{orbits,max_au,star_name}</code> shape make_orbits_canvas consumes, hz_zones=[].",
  "Moon view axis labelled in both AU and km."],
 body='''
  <div class="tabstrip">
    <div class="t active" data-group="o7" data-tab="pl">Planets &amp; Dwarfs</div>
    <div class="t" data-group="o7" data-tab="mo">Moon Systems</div>
  </div>
  <div class="tabbody">
    <div class="tabpane active" data-group="o7" data-tab="pl"><svg class="diagram" id="pl" viewBox="0 0 560 460" style="height:460px"></svg></div>
    <div class="tabpane" data-group="o7" data-tab="mo">
      <div class="ctl"><div class="field"><label>Planet</label><select id="msel" onchange="moons()"><option>Jupiter</option><option>Saturn</option><option>Earth</option></select></div></div>
      <svg class="diagram" id="mo" viewBox="0 0 560 420" style="height:420px"></svg>
    </div>
  </div>''',
 note='Real app: a <code>SolarSystemPanel</code> with DiagramToggleMixin; the moon combo rebuilds the canvas per planet.',
 script=r'''
tabs();
const cx=280,cy=235;
const PLAN=[["Mercury",0.39,0.21,"#b9a"],["Venus",0.72,0.01,"#cb8"],["Earth",1.0,0.02,"#4a90d9"],["Mars",1.52,0.09,"#c64"],["Jupiter",5.2,0.05,"#c92"],["Saturn",9.5,0.06,"#cb6"]];
function planets(){const mx=10.5,sc=195/mx;let g='';PLAN.forEach(([nm,a,e,col])=>{const rx=a*sc,ry=a*Math.sqrt(1-e*e)*sc;g+=`<ellipse cx="${cx}" cy="${cy}" rx="${rx}" ry="${ry}" fill="none" stroke="${col}" stroke-width="1.5" data-tip="${nm}: a=${a} AU"/><circle cx="${cx+rx}" cy="${cy}" r="4" fill="${col}"/><text x="${cx+rx+5}" y="${cy+3}" fill="#555" font-size="8.5">${nm}</text>`;});g+=star(cx,cy,8,"#FFD700","Sun");setsvg('pl',g);}
const MOONS={Jupiter:[["Io",0.0028],["Europa",0.0045],["Ganymede",0.0072],["Callisto",0.0126]],Saturn:[["Mimas",0.0012],["Enceladus",0.0016],["Titan",0.0082],["Iapetus",0.0238]],Earth:[["Moon",0.00257]]};
function moons(){const p=$('msel').value,ms=MOONS[p];const mx=Math.max(...ms.map(m=>m[1]))*1.1,sc=185/mx;let g='';ms.forEach(([nm,a],i)=>{const r=a*sc;g+=`<circle cx="280" cy="210" r="${r}" fill="none" stroke="#4a90d9" stroke-width="1.3"/><circle cx="${280+r}" cy="210" r="3.5" fill="#2e6cb0" data-tip="${nm}: ${a} AU = ${Math.round(a*1.496e8).toLocaleString()} km"/><text x="${280+r+4}" y="213" fill="#555" font-size="8.5">${nm}</text>`;});g+=`<circle cx="280" cy="210" r="9" fill="#caa"/><text x="280" y="245" fill="#555" font-size="9" text-anchor="middle">${p}</text>`;g+=`<text x="280" y="405" fill="#777" font-size="9" text-anchor="middle">orbit radius in AU (1 AU = 1.496×10⁸ km)</text>`;setsvg('mo',g);}
planets();moons();bindTip('pl');bindTip('mo');''')

# ------------------------------------------------------------------ O8
emit(8, "two-star-map",
 tag="O8 · Two-Star Map", cat=True,
 lead="A map for the distance / travel-time panels, which currently render text only.",
 host='Adds a <span class="tab">Map</span> tab to <b>opts 17, 20, 21</b>.',
 h2="Two-Star Map (Distance / Travel-Time)",
 sub="Dark-navy star chart with the two endpoints (+ Sol reference when neither is Sol), a dashed labelled connector. Reuses Phase I's routes= overlay.",
 spec=[
  "<b>Shares the <code>routes=</code> param with Phase I</b> — whichever ships first implements it; the other reuses it (Phase I already did).",
  "Opts 20/21 label the connector with distance + travel time (e.g. <code>11.4 ly — 4 Months @ 100×c</code>).",
  "Endpoints already return <code>(name,ra,dec,ly)</code> — same Cartesian math as opt 17; no new lookups."],
 body='''
  <div class="card">
   <div class="ctl">
     <div class="field"><label>Origin</label><input id="a" value="Sol"></div>
     <div class="field"><label>Destination</label><input id="b" value="61 Cygni A"></div>
     <div class="field"><label>Velocity (×c)</label><input id="v" value="100" style="width:90px"></div>
     <button class="btn" onclick="draw()">Map</button>
   </div>
   <svg class="diagram dark" id="map" viewBox="0 0 640 380" style="height:380px"></svg>
   <div class="legend"><span><i class="line" style="border-top:2px dashed #7fd3ff"></i>route (distance + time)</span><span>★ origin · ● destination · ◦ Sol ref</span></div>
  </div>''',
 note='Real app: the existing <code>make_star_chart_canvas</code>/<code>_3d</code> with <code>routes=[{...}]</code>; the connector follows the chart\'s zoom-driven label decluttering.',
 script=r'''
const HRS=8765.8128,YR=8765.82,MO=YR/12;
function fmt(h){let r=h,p=[];const y=Math.floor(r/YR);r-=y*YR;const mo=Math.floor(r/MO);r-=mo*MO;const d=Math.floor(r/24);if(y)p.push(y+"y");if(mo)p.push(mo+"mo");if(d&&p.length<2)p.push(d+"d");return p.join(" ")||"<1d";}
function find(n){return CAT.find(s=>s.name.toLowerCase()===n.trim().toLowerCase());}
function draw(){
 const a=find($('a').value),b=find($('b').value);if(!a||!b){setsvg('map','<text x="20" y="30" fill="#f88" font-size="12">star not in demo catalog</text>');return;}
 const v=parseFloat($('v').value)||100;const d=Math.hypot(a.x-b.x,a.y-b.y,a.z-b.z);const hrs=d/(v/HRS);
 const nodes=[a,b];if(a.name!=="Sol"&&b.name!=="Sol")nodes.push(CAT[0]);
 const cx=320,cy=190,ox=a.x,oy=a.y;let R=0.5;nodes.forEach(n=>R=Math.max(R,Math.hypot(n.x-ox,n.y-oy)));const sc=150/R;
 const sx=x=>cx+(x-ox)*sc,sy=y=>cy-(y-oy)*sc;const step=R>16?5:R>8?2:1;
 let g='';for(let rr=Math.ceil(R/step)*step;rr>0;rr-=step){if(rr*sc<8)continue;g+=`<circle cx="${cx}" cy="${cy}" r="${rr*sc}" fill="none" stroke="#22345a"/><text x="${cx+3}" y="${cy-rr*sc+11}" fill="#3a5a8a" font-size="8">${rr} ly</text>`;}
 const ax=sx(a.x),ay=sy(a.y),bx=sx(b.x),by=sy(b.y);
 g+=`<line x1="${ax}" y1="${ay}" x2="${bx}" y2="${by}" stroke="#7fd3ff" stroke-width="2" stroke-dasharray="6 4"/>`;
 const mx=(ax+bx)/2,my=(ay+by)/2,lbl=`${f(d,2)} ly — ${fmt(hrs)} @ ${v}×c`;
 g+=`<rect x="${mx-58}" y="${my-9}" width="116" height="15" rx="3" fill="#0b1020" opacity="0.8"/><text x="${mx}" y="${my+2}" fill="#cfe3ff" font-size="9" text-anchor="middle">${lbl}</text>`;
 nodes.forEach(n=>{if(n===a)return;const X=sx(n.x),Y=sy(n.y);if(n.name==="Sol")g+=`<circle cx="${X}" cy="${Y}" r="4" fill="none" stroke="#889" stroke-width="1.5"/><text x="${X+6}" y="${Y+3}" fill="#99a" font-size="9">Sol (ref)</text>`;else g+=`<circle cx="${X}" cy="${Y}" r="5.5" fill="${n.color}"/><text x="${X+7}" y="${Y+3}" fill="#9fb8d8" font-size="9">${n.name}</text>`;});
 g+=star(ax,ay,8,"#FFD700",a.name)+`<text x="${ax+9}" y="${ay+3}" fill="#FFD700" font-size="9" font-weight="bold">${a.name}</text>`;
 setsvg('map',g);
}
bindTip('map');draw();''')

# ------------------------------------------------------------------ O9
emit(9, "brachistochrone-profiles",
 tag="O9 · Brachistochrone", cat=False,
 lead="The three brachistochrone profiles are ideal line charts — currently tables only.",
 host='Adds <span class="tab">Acceleration Profiles</span> to <b>opts 22, 23, 24, 29, 30</b>.',
 h2="Brachistochrone Profile Charts",
 sub="Reconstructs v(t)/d(t) for each profile from accel_g + total time + profile type. Two stacked subplots sharing the time axis.",
 spec=[
  "<code>prepare_brachistochrone_profiles(result)</code> — piecewise segments from the formulas in docs/calculators.md; ~200 samples/profile.",
  "Returns <code>{profiles:[{label,color,t_hours,v_kms,d_au}],accel_g}</code>; colours fixed per profile index.",
  "<code>make_profile_canvas</code> — top velocity (km/s, 2nd axis %c), bottom cumulative distance (AU, 2nd axis LM)."],
 body='''
  <div class="card">
   <div class="ctl"><div class="field"><label>Acceleration (g)</label><input id="g" value="1.0" style="width:80px"></div>
     <div class="field"><label>Distance (AU)</label><input id="d" value="5.2" style="width:90px"></div>
     <button class="btn" onclick="draw()">Plot</button></div>
   <svg class="diagram" id="v" viewBox="0 0 640 220" style="height:220px"></svg>
   <svg class="diagram" id="dd" viewBox="0 0 640 220" style="height:220px;margin-top:8px"></svg>
   <div class="legend"><span><i class="line" style="border-top:2px solid #c0392b"></i>P1 to-halfway</span><span><i class="line" style="border-top:2px solid #2980b9"></i>P2 accel/coast/decel</span><span><i class="line" style="border-top:2px solid #27ae60"></i>P3 to 3% c</span></div>
  </div>''',
 note='Real app: light-theme two-subplot chart added as a viz tab on 24/29/30 and to the existing tabs of 22/23 (opt 23 plots its single custom-thrust profile).',
 script=r'''
const G=9.80665,C=299792458,AU=1.495978707e11,VCAP=0.03*C;
function profile(kind,a,D){ // returns {t:[h],v:[km/s],d:[AU]}
 let T;if(kind===1)T=2*Math.sqrt(D/a);else if(kind===2)T=Math.sqrt(16*D/(3*a));else{const tc=VCAP/a;T=(a*tc*tc>=D)?2*Math.sqrt(D/a):2*tc+(D-a*tc*tc)/VCAP;}
 const t=[],v=[],d=[];for(let i=0;i<=160;i++){const tt=T*i/160;let vv,dd;
  if(kind===1){if(tt<T/2){vv=a*tt;dd=0.5*a*tt*tt;}else{const td=tt-T/2,vmax=a*T/2;vv=vmax-a*td;dd=0.5*a*(T/2)*(T/2)+vmax*td-0.5*a*td*td;}}
  else if(kind===2){const q=T/4;const vmax=a*q;if(tt<q){vv=a*tt;dd=0.5*a*tt*tt;}else if(tt<3*q){vv=vmax;dd=0.5*a*q*q+vmax*(tt-q);}else{const td=tt-3*q;vv=vmax-a*td;dd=0.5*a*q*q+vmax*2*q+vmax*td-0.5*a*td*td;}}
  else{const tc=Math.min(VCAP/a,T/2);const vmax=a*tc;if(tt<tc){vv=a*tt;dd=0.5*a*tt*tt;}else if(tt<T-tc){vv=vmax;dd=0.5*a*tc*tc+vmax*(tt-tc);}else{const td=tt-(T-tc);vv=vmax-a*td;dd=0.5*a*tc*tc+vmax*(T-2*tc)+vmax*td-0.5*a*td*td;}}
  t.push(tt/3600);v.push(vv/1000);d.push(dd/AU);}
 return {t,v,d,T};
}
function axis(id,series,key,ylab){const x0=52,x1=626,y0=16,y1=186;const tmax=Math.max(...series.map(s=>s.t[s.t.length-1]));const ymax=Math.max(...series.flatMap(s=>s[key]))*1.05;
 const sx=t=>lin(t,0,tmax,x0,x1),sy=y=>lin(y,0,ymax,y1,y0);let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 for(let i=0;i<=4;i++){const Y=lin(i,0,4,y1,y0),val=ymax*i/4;g+=`<line x1="${x0}" y1="${Y}" x2="${x1}" y2="${Y}" stroke="#f0f0f0"/><text x="${x0-4}" y="${Y+3}" fill="#555" font-size="8" text-anchor="end">${val<10?val.toFixed(1):Math.round(val)}</text>`;}
 const cols=["#c0392b","#2980b9","#27ae60"];series.forEach((s,i)=>{let p=s.t.map((tt,j)=>`${j?'L':'M'}${f(sx(tt),1)},${f(sy(s[key][j]),1)}`).join(' ');g+=`<path d="${p}" fill="none" stroke="${cols[i]}" stroke-width="1.8"/>`;});
 g+=`<text x="${x0-44}" y="${(y0+y1)/2}" fill="#444" font-size="9" transform="rotate(-90 ${x0-40} ${(y0+y1)/2})" text-anchor="middle">${ylab}</text>`;
 g+=`<text x="${(x0+x1)/2}" y="${y1+18}" fill="#444" font-size="9" text-anchor="middle">time (hours)</text>`;setsvg(id,g);}
function draw(){const a=(parseFloat($('g').value)||1)*G,D=(parseFloat($('d').value)||5.2)*AU;const S=[profile(1,a,D),profile(2,a,D),profile(3,a,D)];axis('v',S,'v','velocity (km/s)');axis('dd',S,'d','distance (AU)');}
draw();''')

# ------------------------------------------------------------------ O10
emit(10, "honorverse",
 tag="O10 · Honorverse", cat=False,
 lead="Visualizing the Honorverse hyper-limit table + a hyper-limit ring on the regions diagram.",
 host='Bar chart on <b>opt 14</b>; a dashed red ring on the <b>System Regions Diagram</b> of opts 8–10.',
 h2="Honorverse Visualization",
 sub="O10a: hyper limit per spectral class as a horizontal bar chart. O10b: the star's hyper limit appended to the regions diagram as a clearly-fictional dashed red ring.",
 spec=[
  "O10a: <code>prepare_hyper_limits()</code> over the loaded honorverse_hyper table; bars in LM (2nd axis AU via /8.3167), coloured by class.",
  "O10b: <code>prepare_system_regions_diagram</code> resolves the type's hyper limit (ceiling rule) → region entry <code>{label:'Honorverse Hyper Limit',au,color:'#cc2222',style:'dashed'}</code>; no match → omitted (opt 10 manual has no type)."],
 body='''
  <div class="tabstrip">
    <div class="t active" data-group="o10" data-tab="bar">O10a · Hyper Limits (opt 14)</div>
    <div class="t" data-group="o10" data-tab="ring">O10b · Ring on Regions (opts 8–10)</div>
  </div>
  <div class="tabbody">
    <div class="tabpane active" data-group="o10" data-tab="bar"><svg class="diagram" id="bar" viewBox="0 0 640 360" style="height:360px"></svg></div>
    <div class="tabpane" data-group="o10" data-tab="ring"><svg class="diagram" id="ring" viewBox="0 0 480 380" style="height:380px"></svg>
      <div class="legend"><span><i class="line" style="border-top:2px solid #2e8b57"></i>physical zones</span><span><i class="line" style="border-top:2px dashed #cc2222"></i>Honorverse Hyper Limit (fiction)</span></div></div>
  </div>''',
 note='Real app: the ring is styled distinctly (dashed red) so it reads as fiction next to the physical zones; documented in star-system-regions.md + science-and-scifi.md.',
 script=r'''
tabs();
const HL=[["O","#9bb0ff",1800],["B","#aabfff",1100],["A","#cad7ff",560],["F","#f8f7ff",330],["G","#fff4c2",210],["K","#ffd2a1",120],["M","#ff9d6c",55]];
function bar(){const x0=120,x1=600,y0=20;const mx=Math.max(...HL.map(h=>h[2]));let g='';HL.forEach((h,i)=>{const y=y0+i*46,w=(h[2]/mx)*(x1-x0);g+=`<text x="${x0-8}" y="${y+20}" fill="#444" font-size="11" text-anchor="end">${h[0]} class</text><rect x="${x0}" y="${y+6}" width="${w}" height="26" fill="${h[2]>500?'#9bb0ff':h[1]}" stroke="#999" data-tip="${h[0]}: ${h[2]} LM = ${f(h[2]/8.3167,2)} AU"/><text x="${x0+w+5}" y="${y+24}" fill="#555" font-size="10">${h[2]} LM (${f(h[2]/8.3167,1)} AU)</text>`;});g+=`<text x="${(x0+x1)/2}" y="${y0+7*46+14}" fill="#444" font-size="10" text-anchor="middle">Hyper limit — light-minutes (secondary: AU)</text>`;setsvg('bar',g);}
function ring(){const cx=240,cy=185,R=150;const zones=[{l:"Recent Venus",au:0.75,c:"#cc7a00"},{l:"HZ inner",au:0.95,c:"#2e8b57"},{l:"HZ outer",au:1.67,c:"#2e8b57"},{l:"Snow line",au:4.9,c:"#4a7fa8"}];const hyper={l:"Hyper Limit",au:3.2,c:"#cc2222"};const all=zones.concat([hyper]);const mx=Math.max(...all.map(z=>z.au));const s=R/Math.sqrt(mx);let g='';all.slice().sort((a,b)=>b.au-a.au).forEach(z=>{const r=Math.sqrt(z.au)*s;g+=`<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${z.c}" stroke-width="2" ${z===hyper?'stroke-dasharray="6 4"':''}/>`;});all.forEach(z=>{const r=Math.sqrt(z.au)*s;g+=`<text x="${cx}" y="${cy-r-2}" fill="${z===hyper?'#cc2222':'#444'}" font-size="8.5" text-anchor="middle">${z.l} ${f(z.au,2)}</text>`;});g+=star(cx,cy,7,"#FFD700","star (G2V)");setsvg('ring',g);}
bar();ring();bindTip('bar');''')

# ------------------------------------------------------------------ O11
emit(11, "toomre-kinematics",
 tag="O11 · Toomre", cat=False,
 lead="Hypatia U/V/W velocities are fetched on every lookup but shown only as numbers.",
 host='Adds a <span class="tab">Kinematics</span> tab wherever the Hypatia Abundance Profile tab appears (opts 1, 3–6, 8).',
 h2="Toomre / Galactic Kinematics Diagram",
 sub="V vs √(U²+W²) with iso-velocity arcs and heuristic disk/halo regions. The star is a gold ★; Hypatia's own disk classification annotates it.",
 spec=[
  "<code>prepare_toomre(hypatia_result)</code> → <code>{v, uw:√(U²+W²), disk, star_name}</code> or <code>{error}</code> when any of U/V/W is null.",
  "<code>make_toomre_canvas</code> — dashed quarter-circles at 50/100/180 km/s; regions thin disk &lt;50, thick ≈70–180, halo &gt;180 (labelled heuristic).",
  "Tab shown only when U, V, W are all non-null."],
 body='''
  <div class="card">
   <div class="ctl" style="margin-bottom:8px"><button class="ghost btn" onclick="openHelp()">&#8505; What is this? (Toomre diagram)</button></div>
   <svg class="diagram" id="t" viewBox="0 0 560 420" style="height:420px"></svg>
   <div class="legend"><span>★ this star</span><span><i class="line" style="border-top:2px dashed #999"></i>constant total v (50/100/180)</span></div>
  </div>
  <div class="modal" id="helpModal" onclick="if(event.target===this)closeHelp()">
    <div class="modalbox">
      <span class="x" onclick="closeHelp()">&times;</span>
      <h3>Toomre / Galactic Kinematics Diagram</h3>
      <h4>What it is</h4>
      <p>The standard plot for reading a star's Galactic motion. It turns the three space-velocity
         components Hypatia returns &mdash; <code>U</code> (toward the Galactic centre), <code>V</code>
         (along Galactic rotation) and <code>W</code> (toward the north Galactic pole) &mdash; into a 2-D
         view that reveals which stellar <b>population</b> the star belongs to.</p>
      <h4>The axes</h4>
      <p><b>x = V</b> (rotational velocity). <b>y = &#8730;(U&#178; + W&#178;)</b> &mdash; the two
         non-rotational components combined into one &ldquo;perpendicular speed&rdquo;. A star's total
         space velocity is &#8730;(U&#178;+V&#178;+W&#178;), so <b>lines of constant total speed are
         circles</b> on this plot.</p>
      <h4>What the rings mean</h4>
      <p>The dashed quarter-circles (50, 100, 180 km/s) are contours of constant total velocity. The
         Galaxy's populations separate mostly by total speed, so the ring a star sits inside tells you
         its population:</p>
      <table><thead><tr><th>Population</th><th>Total speed</th><th>Character</th></tr></thead><tbody>
        <tr><td>Thin disk</td><td>&#8818; 50 km/s</td><td>young, metal-rich, near-circular orbits</td></tr>
        <tr><td>Thick disk</td><td>&#8776; 70&#8211;180</td><td>older, more eccentric / inclined</td></tr>
        <tr><td>Halo</td><td>&#8819; 180</td><td>ancient, metal-poor, plunging orbits</td></tr>
      </tbody></table>
      <h4>The marker</h4>
      <p>The gold &#9733; is this star at its (V, &#8730;(U&#178;+W&#178;)) position; the subtitle shows
         Hypatia's own <code>disk</code> classification so the geometric reading can be cross-checked.
         The boundaries are <b>heuristic</b> &mdash; a probabilistic continuum, not hard cuts.</p>
      <p style="text-align:right;margin-top:12px"><button class="btn" onclick="closeHelp()">Close</button></p>
    </div>
  </div>''',
 note='Real app: subtitle shows Hypatia\'s <code>disk</code> classification when present; region boundaries are labelled as heuristic. An <b>&#8505; What is this?</b> button opens this explanation as a dialog (a small reusable help-dialog helper) in every host panel (opts 1, 3&#8211;6, 8).',
 script=r'''
bindTip('t');
const x0=54,x1=540,y0=20,y1=372;const vmin=-300,vmax=120,umax=300;
const sx=v=>lin(v,vmin,vmax,x0,x1),sy=u=>lin(u,0,umax,y1,y0);
const STAR={v:-38,uw:46,name:"Tau Ceti",disk:"thin"};
function draw(){let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 for(let v=-300;v<=100;v+=100){const X=sx(v);g+=`<line x1="${X}" y1="${y0}" x2="${X}" y2="${y1}" stroke="#f3f3f3"/><text x="${X}" y="${y1+14}" fill="#555" font-size="9" text-anchor="middle">${v}</text>`;}
 for(let u=0;u<=300;u+=100){const Y=sy(u);g+=`<line x1="${x0}" y1="${Y}" x2="${x1}" y2="${Y}" stroke="#f3f3f3"/><text x="${x0-4}" y="${Y+3}" fill="#555" font-size="9" text-anchor="end">${u}</text>`;}
 // arcs centered at LSR ~ (-232,0) approx; use origin v=-232 for visual
 const v0=-232;[50,100,180].forEach(rad=>{let p='';for(let a=0;a<=90;a+=3){const vv=v0+rad*Math.cos(a*Math.PI/180),uu=rad*Math.sin(a*Math.PI/180);if(vv<vmin||uu>umax)continue;p+=`${p?'L':'M'}${f(sx(vv),1)},${f(sy(uu),1)} `;}g+=`<path d="${p}" fill="none" stroke="#999" stroke-width="1" stroke-dasharray="5 4"/><text x="${sx(v0+rad*0.5)}" y="${sy(rad*0.87)}" fill="#888" font-size="8">${rad}</text>`;});
 g+=`<text x="${sx(-232)}" y="${y0+14}" fill="#2e8b57" font-size="9" text-anchor="middle">thin disk &lt;50 · thick ≈70–180 · halo &gt;180 (heuristic)</text>`;
 const X=sx(STAR.v),Y=sy(STAR.uw);g+=star(X,Y,7,"#FFD700",`${STAR.name} · disk: ${STAR.disk}`)+`<text x="${X+9}" y="${Y+3}" fill="#7a5c00" font-size="9.5">${STAR.name}</text>`;
 g+=`<text x="${(x0+x1)/2}" y="${y1+30}" fill="#444" font-size="10" text-anchor="middle">V (km/s)</text>`;
 g+=`<text x="14" y="${(y0+y1)/2}" fill="#444" font-size="10" text-anchor="middle" transform="rotate(-90 14 ${(y0+y1)/2})">√(U² + W²) (km/s)</text>`;
 setsvg('t',g);}
function openHelp(){$('helpModal').classList.add('open');}
function closeHelp(){$('helpModal').classList.remove('open');}
draw();''')

# ------------------------------------------------------------------ O12
emit(12, "hwc-habitability",
 tag="O12 · HWC Visuals", cat=False,
 lead="HWC flux/temperature/ESI columns are tabled, never drawn.",
 host='Adds <span class="tab">Temperature Ranges</span> + <span class="tab">ESI vs Orbit</span> tabs to <b>opt 6 (HWC)</b>.',
 h2="HWC Habitability Visuals",
 sub="Per-system temperature range bars (with the liquid-water band) and an ESI-vs-orbit scatter with the star's HZ shaded.",
 spec=[
  "<code>prepare_hwc_temps(planet_rows)</code> — per planet equilibrium &amp; surface min→max bars; dashed lines at 273 / 373 K.",
  "<code>prepare_hwc_esi(star_row, planet_rows)</code> — SMA (log if span &gt;10×) vs ESI; HZ shaded from S_HZ_OPT/CON; points coloured by P_HABITABLE.",
  "Per-system only — no overlap with L2's cross-catalog ESI ranking table."],
 body='''
  <div class="tabstrip">
    <div class="t active" data-group="o12" data-tab="temp">Temperature Ranges</div>
    <div class="t" data-group="o12" data-tab="esi">ESI vs Orbit</div>
  </div>
  <div class="tabbody">
    <div class="tabpane active" data-group="o12" data-tab="temp"><svg class="diagram" id="temp" viewBox="0 0 640 320" style="height:320px"></svg></div>
    <div class="tabpane" data-group="o12" data-tab="esi"><svg class="diagram" id="esi" viewBox="0 0 640 360" style="height:360px"></svg></div>
  </div>''',
 note='Real app: two HwcPanel viz tabs; the 273–373 K band is labelled "liquid water".',
 script=r'''
tabs();bindTip('temp');bindTip('esi');
const PLN=[{n:"b",eqmin:240,eqmax:290,smin:255,smax:305,esi:0.92,a:0.7,hab:1},{n:"c",eqmin:180,eqmax:220,smin:195,smax:240,esi:0.64,a:1.4,hab:0},{n:"d",eqmin:330,eqmax:400,smin:360,smax:440,esi:0.41,a:0.3,hab:0},{n:"e",eqmin:250,eqmax:300,smin:268,smax:318,esi:0.88,a:1.0,hab:1}];
function temps(){const x0=120,x1=620,y0=20;const tmin=150,tmax=460;const sx=t=>lin(t,tmin,tmax,x0,x1);let g='';
 [273,373].forEach(t=>{g+=`<line x1="${sx(t)}" y1="${y0}" x2="${sx(t)}" y2="${y0+PLN.length*58}" stroke="#4a7fa8" stroke-dasharray="4 4"/><text x="${sx(t)}" y="${y0-4}" fill="#4a7fa8" font-size="8" text-anchor="middle">${t}K</text>`;});
 g+=`<rect x="${sx(273)}" y="${y0}" width="${sx(373)-sx(273)}" height="${PLN.length*58}" fill="#bfe3bf" opacity="0.25"/>`;
 PLN.forEach((p,i)=>{const y=y0+i*58;g+=`<text x="${x0-8}" y="${y+30}" fill="#444" font-size="11" text-anchor="end">planet ${p.n}</text>`;
   g+=`<rect x="${sx(p.eqmin)}" y="${y+8}" width="${sx(p.eqmax)-sx(p.eqmin)}" height="14" fill="#e08a3c" opacity="0.8" data-tip="equilibrium ${p.eqmin}–${p.eqmax} K"/>`;
   g+=`<rect x="${sx(p.smin)}" y="${y+26}" width="${sx(p.smax)-sx(p.smin)}" height="14" fill="#c0392b" opacity="0.8" data-tip="surface ${p.smin}–${p.smax} K"/>`;});
 for(let t=150;t<=450;t+=50){g+=`<text x="${sx(t)}" y="${y0+PLN.length*58+14}" fill="#555" font-size="8" text-anchor="middle">${t}</text>`;}
 g+=`<text x="${(x0+x1)/2}" y="${y0+PLN.length*58+30}" fill="#444" font-size="9" text-anchor="middle">Temperature (K) — eq (orange) / surface (red); green band = liquid water</text>`;setsvg('temp',g);}
function esi(){const x0=54,x1=620,y0=20,y1=300;const amin=0.2,amax=2.0;const sx=a=>lin(L10(a),L10(amin),L10(amax),x0,x1),sy=e=>lin(e,0,1,y1,y0);
 let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 g+=`<rect x="${sx(0.75)}" y="${y0}" width="${sx(1.77)-sx(0.75)}" height="${y1-y0}" fill="#bfe3bf" opacity="0.3"/><rect x="${sx(0.95)}" y="${y0}" width="${sx(1.67)-sx(0.95)}" height="${y1-y0}" fill="#7cbf7c" opacity="0.3"/>`;
 for(const a of [0.2,0.5,1,2]){g+=`<text x="${sx(a)}" y="${y1+13}" fill="#555" font-size="8" text-anchor="middle">${a}</text>`;}
 for(let e=0;e<=1;e+=0.25){g+=`<line x1="${x0}" y1="${sy(e)}" x2="${x1}" y2="${sy(e)}" stroke="#f0f0f0"/><text x="${x0-4}" y="${sy(e)+3}" fill="#555" font-size="8" text-anchor="end">${e}</text>`;}
 PLN.forEach(p=>{g+=`<circle cx="${sx(p.a)}" cy="${sy(p.esi)}" r="6" fill="${p.hab?'#2e8b57':'#999'}" stroke="#fff" data-tip="planet ${p.n}: a=${p.a} AU, ESI=${p.esi}"/><text x="${sx(p.a)+8}" y="${sy(p.esi)+3}" fill="#444" font-size="9">${p.n}</text>`;});
 g+=`<text x="${(x0+x1)/2}" y="${y1+28}" fill="#444" font-size="9" text-anchor="middle">Semi-major axis (AU, log) — green bands = optimistic/conservative HZ · green dot = habitable</text>`;
 g+=`<text x="16" y="${(y0+y1)/2}" fill="#444" font-size="9" transform="rotate(-90 16 ${(y0+y1)/2})" text-anchor="middle">ESI</text>`;setsvg('esi',g);}
temps();esi();''')

# ------------------------------------------------------------------ O13
emit(13, "transit-geometry",
 tag="O13 · Transit Geometry", cat=False,
 lead="pl_orbincl is fetched then explicitly ignored by both orbit-prep functions.",
 host='Adds a <span class="tab">Transit Geometry</span> tab to <b>opt 3</b> and the Map panel.',
 h2="Transit Geometry View",
 sub="Impact parameter b = (a/R★)·cos i per planet — no full 3D needed. The transiting band |b| ≤ 1 is shaded.",
 spec=[
  "<code>prepare_transit_geometry(planets)</code> — needs st_rad + per-planet pl_orbsmax/pl_orbincl; <code>R★ = st_rad×0.00465 AU</code>.",
  "Returns <code>{star_radius_au, planets:[{name,a_au,incl_deg,b}], skipped}</code> or <code>{error}</code> when st_rad / all inclinations missing.",
  "<code>make_transit_canvas</code> — stellar disk left, planets at (log a, b), band |b|≤1 shaded \"transiting\"; caveat: i only, node unknown."],
 body='''
  <div class="card">
   <svg class="diagram" id="tr" viewBox="0 0 640 380" style="height:380px"></svg>
   <div class="legend"><span><i style="background:#bcd6f0"></i>transiting band |b| ≤ 1</span><span>● planet</span></div>
   <div class="foot">geometry from i only; ascending node unknown. Skipped: planet f (no inclination measured).</div>
  </div>''',
 note='Real app: tab shown when ≥1 planet qualifies; a footnote lists planets skipped for missing inclination.',
 script=r'''
bindTip('tr');
const x0=120,x1=620,y0=20,y1=340,cy=180;
const amin=0.02,amax=3;const sx=a=>lin(L10(a),L10(amin),L10(amax),x0,x1),sy=b=>lin(b,-3,3,y1,y0);
const Rstar=1; // in units of R★
const PLN=[{n:"b",a:0.05,i:89.6},{n:"c",a:0.12,i:88.9},{n:"d",a:0.4,i:89.97},{n:"e",a:1.1,i:87.2}];
function bof(a_au,i){const Rstar_au=0.0072;return (a_au/Rstar_au)*Math.cos(i*Math.PI/180);}
function draw(){let g=`<rect x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="#fff" stroke="#c9c9c9"/>`;
 g+=`<rect x="${x0}" y="${sy(1)}" width="${x1-x0}" height="${sy(-1)-sy(1)}" fill="#bcd6f0" opacity="0.4"/><text x="${x1-6}" y="${sy(0)-3}" fill="#3a73ad" font-size="9" text-anchor="end">transiting (|b| ≤ 1)</text>`;
 // stellar disk to scale at left
 const dr=(sy(-1)-sy(1))/2;g+=`<circle cx="${x0-44}" cy="${cy}" r="${dr}" fill="#ffe9a8" stroke="#caa84a"/><text x="${x0-44}" y="${cy+dr+14}" fill="#777" font-size="8" text-anchor="middle">R★</text>`;
 for(const a of [0.02,0.1,0.5,1,3]){g+=`<line x1="${sx(a)}" y1="${y0}" x2="${sx(a)}" y2="${y1}" stroke="#f3f3f3"/><text x="${sx(a)}" y="${y1+13}" fill="#555" font-size="8" text-anchor="middle">${a}</text>`;}
 for(let b=-3;b<=3;b++){g+=`<text x="${x0-4}" y="${sy(b)+3}" fill="#555" font-size="8" text-anchor="end">${b}</text>`;}
 PLN.forEach(p=>{const b=bof(p.a,p.i);const Y=sy(Math.max(-3,Math.min(3,b)));g+=`<circle cx="${sx(p.a)}" cy="${Y}" r="6" fill="${Math.abs(b)<=1?'#2e8b57':'#b03030'}" stroke="#fff" data-tip="planet ${p.n}: a=${p.a} AU, i=${p.i}°, b=${f(b,2)}"/><text x="${sx(p.a)+8}" y="${Y+3}" fill="#444" font-size="9">${p.n}</text>`;});
 g+=`<text x="${(x0+x1)/2}" y="${y1+28}" fill="#444" font-size="9" text-anchor="middle">Semi-major axis (AU, log)</text>`;
 g+=`<text x="16" y="${cy}" fill="#444" font-size="9" transform="rotate(-90 16 ${cy})" text-anchor="middle">impact parameter b (R★)</text>`;setsvg('tr',g);}
draw();''')

# ------------------------------------------------------------------ O14
emit(14, "size-strip",
 tag="O14 · Size Strip", cat=False,
 lead="A to-scale planet size-comparison strip.",
 host='Adds a <span class="tab">Size Comparison</span> tab to <b>opts 3, 6</b> and the Map panel.',
 h2="Planet Size-Comparison Strip",
 sub="A single row of to-scale circles — Earth and Jupiter anchors plus each system planet, labelled with name + radius.",
 spec=[
  "<code>make_size_comparison_canvas(parent, planets, radius_key, name_key)</code> — gray Earth (1 R⊕) &amp; Jupiter (11.21 R⊕) anchors.",
  "Planets without a radius listed in a footnote, not drawn. Equal-aspect, no ticks.",
  "Tab shown when ≥ 1 planet has a radius."],
 body='''
  <div class="card">
   <svg class="diagram" id="sz" viewBox="0 0 640 240" style="height:240px"></svg>
   <div class="foot">No radius: planet g (drawn omitted).</div>
  </div>''',
 note='Real app: one row of to-scale circles; gray silhouettes for Earth/Jupiter anchors.',
 script=r'''
bindTip('sz');
const OBJ=[["Earth",1,"#9aa",true],["b",1.9,"#4a90d9",false],["c",1.25,"#4a90d9",false],["d",3.1,"#4a90d9",false],["e",4.6,"#4a90d9",false],["Jupiter",11.21,"#9aa",true]];
function draw(){const base=200,maxR=Math.max(...OBJ.map(o=>o[1]));const sc=80/maxR;let x=40;let g='';
 OBJ.forEach(([nm,r,col,anc])=>{const rr=r*sc;g+=`<circle cx="${x+rr}" cy="${base-rr}" r="${rr}" fill="${col}" opacity="${anc?0.55:0.95}" stroke="#777" data-tip="${nm}: ${r} R⊕"/><line x1="${x}" y1="${base}" x2="${x+2*rr}" y2="${base}" stroke="#ccc"/><text x="${x+rr}" y="${base+15}" fill="#444" font-size="9.5" text-anchor="middle">${nm}</text><text x="${x+rr}" y="${base+27}" fill="#888" font-size="8" text-anchor="middle">${r} R⊕</text>`;x+=2*rr+26;});
 g+=`<line x1="30" y1="${base}" x2="${x}" y2="${base}" stroke="#bbb"/>`;setsvg('sz',g);}
draw();''')

# ------------------------------------------------------------------ O15
emit(15, "table-map-link",
 tag="O15 · Row↔Map Link", cat=True,
 lead="Selecting a result row does nothing on the maps today, and clicking a map star doesn't select its row.",
 host='Two-way linking on <b>opts 18, 19</b> between the result table and the star charts.',
 h2="Table-Row ↔ Map Linking",
 sub="Click a table row → its star gets a gold ring on the map; click a map star → its row selects and scrolls into view. Try both below.",
 spec=[
  "<code>canvas.highlight_star(name|None)</code> attached to each map/chart helper (attribute — <b>no signature change</b>): a hollow gold ring, or removed for None.",
  "Each helper gains an optional <code>on_star_click(name)</code> callback (default None → current inline info box).",
  "Selection survives switching viz tabs. O18 reuses this highlight function."],
 body='''
  <div class="card">
   <div style="display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start">
     <div style="flex:1;min-width:280px"><div style="max-height:300px;overflow:auto;border:1px solid var(--border);border-radius:5px"><table id="tbl"></table></div></div>
     <div style="flex:1;min-width:300px"><svg class="diagram dark" id="map" viewBox="0 0 380 340" style="height:340px"></svg></div>
   </div>
   <div class="readout" id="ro">Click a row or a star.</div>
  </div>''',
 note='Real app: panels keep refs to all canvases; <code>selectionChanged</code> → <code>highlight_star</code> on every canvas; map click selects + scrolls the row.',
 script=r'''
const pool=CAT.filter(s=>s.name!=="Sol"&&Math.hypot(s.x,s.y,s.z)<6.5).map(s=>({...s,ly:Math.hypot(s.x,s.y,s.z)}));
let selName=null;
function rows(){let r=pool.map(s=>`<tr id="row-${s.name.replace(/\W/g,'')}" onclick="pick('${s.name}')"><td>${s.name}</td><td>${s.cls}</td><td class="num">${f(s.ly,2)}</td></tr>`).join('');
 $('tbl').innerHTML=`<thead><tr><th>Star</th><th>Spec</th><th>LY</th></tr></thead><tbody>${r}</tbody>`;}
function map(){const cx=190,cy=170;let R=0.5;pool.forEach(s=>R=Math.max(R,Math.hypot(s.x,s.y)));const sc=140/R;const sx=x=>cx+x*sc,sy=y=>cy-y*sc;
 let g='';for(let rr=Math.ceil(R/2)*2;rr>0;rr-=2){if(rr*sc<8)continue;g+=`<circle cx="${cx}" cy="${cy}" r="${rr*sc}" fill="none" stroke="#22345a"/>`;}
 pool.forEach(s=>{g+=`<circle cx="${sx(s.x)}" cy="${sy(s.y)}" r="5" fill="${s.color}" onclick="pick('${s.name}')" style="cursor:pointer" data-tip="${s.name}"/>`;if(s.name===selName)g+=`<circle cx="${sx(s.x)}" cy="${sy(s.y)}" r="9" fill="none" stroke="#FFD700" stroke-width="2"/>`;g+=`<text x="${sx(s.x)+7}" y="${sy(s.y)+3}" fill="#9fb8d8" font-size="8">${s.name}</text>`;});
 g+=star(cx,cy,7,"#FFD700","Sol");setsvg('map',g);}
function pick(name){selName=name;document.querySelectorAll('#tbl tr').forEach(t=>t.classList.remove('sel'));const row=$('row-'+name.replace(/\W/g,''));if(row){row.classList.add('sel');row.scrollIntoView({block:'nearest'});}$('ro').textContent="Selected: "+name;map();}
rows();map();bindTip('map');''')

# ------------------------------------------------------------------ O16
emit(16, "legend-filter",
 tag="O16 · Legend Filter", cat=True,
 lead="Spectral-class legends are display-only today.",
 host='Clickable legend on the <b>opts 18, 19</b> maps and charts (2D + 3D).',
 h2="Clickable Legend Filtering",
 sub="Click a spectral class in the legend to hide/show those stars; its legend text dims. Per-star labels follow their star's visibility.",
 spec=[
  "Draw the scatter as <b>one PathCollection per spectral class</b> (prerequisite for toggling); <code>legend_handle.set_picker(5)</code>.",
  "On <code>pick_event</code> toggle that class's collection visibility; legend text → alpha 0.3 when hidden.",
  "Works in both 2D and 3D variants."],
 body='''
  <div class="card">
   <div class="legend" id="leg" style="margin-bottom:8px"></div>
   <svg class="diagram dark" id="map" viewBox="0 0 600 360" style="height:360px"></svg>
  </div>''',
 note='Real app: same behaviour wired through matplotlib pick events on the per-class legend handles.',
 script=r'''
const pool=CAT.filter(s=>s.name!=="Sol").map(s=>({...s,ly:Math.hypot(s.x,s.y,s.z)}));
const classes=[...new Set(pool.map(s=>s.cls))];const hidden=new Set();
function legend(){$('leg').innerHTML=classes.map(c=>`<span style="cursor:pointer;opacity:${hidden.has(c)?0.3:1}" onclick="tog('${c}')"><i style="background:${SPC[c]}"></i>${c}</span>`).join('');}
function tog(c){if(hidden.has(c))hidden.delete(c);else hidden.add(c);legend();map();}
function map(){const cx=300,cy=180;let R=0.5;pool.forEach(s=>R=Math.max(R,Math.hypot(s.x,s.y)));const sc=150/R;const sx=x=>cx+x*sc,sy=y=>cy-y*sc;
 let g='';for(let rr=Math.ceil(R/5)*5;rr>0;rr-=5){if(rr*sc<8)continue;g+=`<circle cx="${cx}" cy="${cy}" r="${rr*sc}" fill="none" stroke="#22345a"/>`;}
 pool.forEach(s=>{if(hidden.has(s.cls))return;g+=`<circle cx="${sx(s.x)}" cy="${sy(s.y)}" r="5" fill="${s.color}" data-tip="${s.name} (${s.cls})"/><text x="${sx(s.x)+7}" y="${sy(s.y)+3}" fill="#9fb8d8" font-size="8">${s.name}</text>`;});
 g+=star(cx,cy,7,"#FFD700","Sol");setsvg('map',g);}
legend();map();bindTip('map');''')

# ------------------------------------------------------------------ O17
emit(17, "isochrone-rings",
 tag="O17 · Isochrone Rings", cat=True,
 lead="The star charts draw distance rings at fixed ly steps — add a travel-time mode.",
 host='Adds an isochrone mode to the <b>opts 18, 19</b> star charts.',
 h2="Travel-Time Isochrone Rings",
 sub="Enter a velocity → rings become travel-time contours (d = v·t) at nice time steps; clear it to restore plain distance rings.",
 spec=[
  "Velocity input + unit (LY/HR | ×c) + Apply above the chart; rings at <code>d = v_lyhr × t</code> for steps chosen so 3–6 fit (week…50 yr).",
  "Labels e.g. <code>6 months @ 0.01 ly/hr</code>; conversion via the canonical 8765.8128.",
  "Param on <code>make_star_chart_canvas</code>/<code>_3d</code>: <code>isochrone={ly_hr,label_unit}|None</code> + panel rebuild on Apply."],
 body='''
  <div class="card">
   <div class="ctl">
     <div class="field"><label>Velocity</label><input id="v" value="0.01" style="width:90px"></div>
     <div class="field"><label>Unit</label><select id="u"><option value="ly">LY/HR</option><option value="c">×c</option></select></div>
     <button class="btn" onclick="draw()">Apply</button>
     <button class="ghost btn" onclick="$('v').value='';draw()">Clear (distance rings)</button>
   </div>
   <svg class="diagram dark" id="map" viewBox="0 0 600 380" style="height:380px"></svg>
  </div>''',
 note='Real app: same chart, rings relabelled as isochrones; clearing the velocity restores the distance rings.',
 script=r'''
const HRS=8765.8128,YR=8765.82,WK=168,MO=YR/12;
const STEPS=[["1 week",WK],["1 month",MO],["3 months",3*MO],["6 months",6*MO],["1 yr",YR],["2 yr",2*YR],["5 yr",5*YR],["10 yr",10*YR],["25 yr",25*YR],["50 yr",50*YR]];
const pool=CAT.filter(s=>Math.hypot(s.x,s.y,s.z)<6.5);
function draw(){const cx=300,cy=190;let R=0.5;pool.forEach(s=>R=Math.max(R,Math.hypot(s.x,s.y)));const sc=160/R;const sx=x=>cx+x*sc,sy=y=>cy-y*sc;
 const raw=$('v').value.trim();let g='';
 if(raw){let v=parseFloat(raw);const ly_hr=$('u').value==='c'? v/HRS : v;
   // pick steps giving rings inside R
   let chosen=STEPS.map(([lbl,hrs])=>[lbl,ly_hr*hrs]).filter(([_,d])=>d<=R*1.02);
   if(chosen.length>6)chosen=chosen.slice(chosen.length-6);
   chosen.forEach(([lbl,d])=>{g+=`<circle cx="${cx}" cy="${cy}" r="${d*sc}" fill="none" stroke="#2e6c8a" stroke-dasharray="4 3"/><text x="${cx+3}" y="${cy-d*sc+11}" fill="#5fb6d8" font-size="8">${lbl} @ ${f(ly_hr,4)} ly/hr</text>`;});
   g+=`<text x="${cx}" y="16" fill="#cfe3ff" font-size="11" text-anchor="middle">Isochrone mode</text>`;
 } else {
   const step=R>16?5:R>8?2:1;for(let rr=Math.ceil(R/step)*step;rr>0;rr-=step){if(rr*sc<8)continue;g+=`<circle cx="${cx}" cy="${cy}" r="${rr*sc}" fill="none" stroke="#22345a"/><text x="${cx+3}" y="${cy-rr*sc+11}" fill="#3a5a8a" font-size="8">${rr} ly</text>`;}
   g+=`<text x="${cx}" y="16" fill="#cfe3ff" font-size="11" text-anchor="middle">Distance rings</text>`;
 }
 pool.forEach(s=>{if(s.name==="Sol")return;g+=`<circle cx="${sx(s.x)}" cy="${sy(s.y)}" r="5" fill="${s.color}" data-tip="${s.name}"/><text x="${sx(s.x)+7}" y="${sy(s.y)+3}" fill="#9fb8d8" font-size="8">${s.name}</text>`;});
 g+=star(cx,cy,7,"#FFD700","Sol");setsvg('map',g);}
draw();bindTip('map');''')

# ------------------------------------------------------------------ O18
emit(18, "find-star",
 tag="O18 · Find Star", cat=True,
 lead="A find-on-map search box (depends on O15's highlight function).",
 host='Adds a Find box above the <b>opts 18, 19</b> chart tabs.',
 h2="Find-Star-on-Map Search Box",
 sub="Substring match on name + designations; on match, centre + gold-ring the star (reuses O15's highlight). Find again cycles multiple matches.",
 spec=[
  "Case-insensitive substring on Star Name &amp; Star Designations of the rendered stars.",
  "On match: centre the view at half-range min(current,15) ly (labels appear), call <code>highlight_star(name)</code>; show <code>1 of N matches</code> when multiple.",
  "<b>Depends on O15's <code>highlight_star</code></b>. No match → status-bar message, no view change."],
 body='''
  <div class="card">
   <div class="ctl"><div class="field"><label>Find star</label><input id="q" value="cen" style="width:160px" onkeydown="if(event.key==='Enter')find()"></div>
     <button class="btn" onclick="find()">Find</button><div class="readout" id="ro"></div></div>
   <svg class="diagram dark" id="map" viewBox="0 0 600 380" style="height:380px"></svg>
  </div>''',
 note='Real app: reuses O15\'s ring; cycling Find steps through matches; no match → status-bar message only.',
 script=r'''
const pool=CAT.filter(s=>s.name!=="Sol").map(s=>({...s,ly:Math.hypot(s.x,s.y,s.z)}));
let matches=[],mi=0,center=null;
function map(){const cx=300,cy=190;const ox=center?center.x:0,oy=center?center.y:0;let R=0.5;pool.forEach(s=>R=Math.max(R,Math.hypot(s.x-ox,s.y-oy)));if(center)R=Math.min(R,15);const sc=160/R;const sx=x=>cx+(x-ox)*sc,sy=y=>cy-(y-oy)*sc;
 let g='';const step=R>16?5:R>8?2:1;for(let rr=Math.ceil(R/step)*step;rr>0;rr-=step){if(rr*sc<8)continue;g+=`<circle cx="${cx}" cy="${cy}" r="${rr*sc}" fill="none" stroke="#22345a"/>`;}
 pool.forEach(s=>{const X=sx(s.x),Y=sy(s.y);g+=`<circle cx="${X}" cy="${Y}" r="5" fill="${s.color}" data-tip="${s.name}"/><text x="${X+7}" y="${Y+3}" fill="#9fb8d8" font-size="8">${s.name}</text>`;if(center&&s.name===center.name)g+=`<circle cx="${X}" cy="${Y}" r="9" fill="none" stroke="#FFD700" stroke-width="2"/>`;});
 const SX=sx(0),SY=sy(0);if(Math.abs(SX-cx)<400)g+=star(SX,SY,6,"#FFD700","Sol");setsvg('map',g);}
function find(){const q=$('q').value.trim().toLowerCase();if(!q){return;}
 const newM=pool.filter(s=>s.name.toLowerCase().includes(q));
 if(newM.length===0){$('ro').textContent="No match — no view change.";return;}
 if(JSON.stringify(newM.map(m=>m.name))!==JSON.stringify(matches.map(m=>m.name))){matches=newM;mi=0;}else{mi=(mi+1)%matches.length;}
 center=matches[mi];$('ro').textContent= matches.length>1? `${mi+1} of ${matches.length} matches — ${center.name}` : `Found: ${center.name}`;map();}
map();find();bindTip('map');''')

print("done.")
