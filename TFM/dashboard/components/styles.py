from __future__ import annotations

"""Hoja de estilos de la aplicación.

Todo el CSS vive aquí en lugar de estar embebido en ``streamlit_app.py``. El
tema de ``.streamlit/config.toml`` solo gobierna de facto el color primario de
los widgets: el resto lo define esta hoja.
"""

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
:root {
    --tui-red:#D40E14;
    --tui-red-soft:rgba(212,14,20,.12);
    --tui-red-deep:#B80B10;
    --tui-dark:#111827;
    --tui-digital:#4B5563;
    --tui-blue:#D1D5DB;
    --tui-blue-strong:#9CA3AF;
    --tui-blue50:#F5F5F5;
    --tui-blue25:#FAFAFA;
    --bg:#FFFFFF;
    --paper:#FFFFFF;
    --text:#111827;
    --muted:#667085;
    --border:#D0D5DD;
    --border-strong:#98A2B3;
    --success:#19865E;
    --warning:#B7791F;
    --error:#C73535;
    --shadow:0 18px 46px rgba(17,24,39,.08);
    --shadow-soft:0 10px 28px rgba(17,24,39,.06);
}
html, body, [class*="css"] { font-family:'Inter', Arial, sans-serif; }
.stApp {
    color:var(--text);
    background-color:#EAF4FB;
    background-image:
      url("data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A//www.w3.org/2000/svg%27%20viewBox%3D%270%200%201600%20960%27%3E%0A%3Crect%20width%3D%271600%27%20height%3D%27960%27%20fill%3D%27none%27/%3E%0A%3Cg%20fill%3D%27none%27%20stroke-linecap%3D%27round%27%3E%0A%20%20%3Cpath%20d%3D%27M-80%20120%20C%20160%2040%20320%20220%20560%20150%20S%201020%2040%201680%20120%27%20stroke%3D%27%23111827%27%20stroke-opacity%3D%27.12%27%20stroke-width%3D%273%27/%3E%0A%20%20%3Cpath%20d%3D%27M-90%20210%20C%20220%20110%20410%20320%20700%20235%20S%201120%20120%201690%20210%27%20stroke%3D%27%236B7280%27%20stroke-opacity%3D%27.11%27%20stroke-width%3D%273.2%27/%3E%0A%20%20%3Cpath%20d%3D%27M-60%20340%20C%20180%20250%20430%20420%20760%20340%20S%201220%20250%201660%20340%27%20stroke%3D%27%231F2937%27%20stroke-opacity%3D%27.09%27%20stroke-width%3D%272.6%27/%3E%0A%20%20%3Cpath%20d%3D%27M-60%20500%20C%20260%20430%20420%20650%20760%20560%20S%201180%20430%201660%20530%27%20stroke%3D%27%236B7280%27%20stroke-opacity%3D%27.10%27%20stroke-width%3D%273%27/%3E%0A%20%20%3Cpath%20d%3D%27M-40%20650%20C%20280%20560%20520%20790%20900%20690%20S%201280%20600%201660%20710%27%20stroke%3D%27%23111827%27%20stroke-opacity%3D%27.08%27%20stroke-width%3D%273.6%27/%3E%0A%20%20%3Cpath%20d%3D%27M-30%20810%20C%20240%20720%20420%20910%20760%20840%20S%201180%20760%201650%20850%27%20stroke%3D%27%239CA3AF%27%20stroke-opacity%3D%27.12%27%20stroke-width%3D%273%27/%3E%0A%20%20%3Ccircle%20cx%3D%271360%27%20cy%3D%27160%27%20r%3D%27140%27%20stroke%3D%27%23111827%27%20stroke-opacity%3D%27.05%27%20stroke-width%3D%277%27/%3E%0A%20%20%3Ccircle%20cx%3D%271490%27%20cy%3D%27220%27%20r%3D%27220%27%20stroke%3D%27%236B7280%27%20stroke-opacity%3D%27.04%27%20stroke-width%3D%2711%27/%3E%0A%20%20%3Ccircle%20cx%3D%27180%27%20cy%3D%27760%27%20r%3D%27220%27%20stroke%3D%27%239CA3AF%27%20stroke-opacity%3D%27.05%27%20stroke-width%3D%279%27/%3E%0A%3C/g%3E%0A%3C/svg%3E"),
      radial-gradient(circle at 50% 10%, rgba(255,255,255,.84), transparent 18%),
      radial-gradient(circle at 55% 80%, rgba(255,255,255,.74), transparent 16%),
      repeating-linear-gradient(0deg, rgba(17,24,39,.030) 0 1px, transparent 1px 38px),
      repeating-linear-gradient(90deg, rgba(17,24,39,.030) 0 1px, transparent 1px 38px),
      linear-gradient(180deg,#EDF6FC 0%,#E5F1F9 100%);
    background-size:cover, auto, auto, auto, auto, auto;
    background-position:center center, center top, center bottom, center center, center center, center center;
    background-repeat:no-repeat, no-repeat, no-repeat, repeat, repeat, no-repeat;
    background-attachment:fixed;
}
/* Fondo principal claro e iluminado con trama neutra. */
[data-testid="stAppViewContainer"] > .main .block-container {
    position:relative;
    background:linear-gradient(180deg,rgba(234,244,251,.46) 0%,rgba(241,247,251,.40) 100%);
    border:1px solid rgba(17,24,39,.06);
    border-radius:24px;
    box-shadow:
      0 16px 38px rgba(17,24,39,.04),
      inset 0 1px 0 rgba(255,255,255,.50);
    padding-left:1.8rem;
    padding-right:1.8rem;
    z-index:1;
    backdrop-filter:blur(2px);
}

[data-testid="stAppViewContainer"] > .main .block-container > * { position:relative; z-index:1; }
[data-testid="stHeader"] { background:rgba(236,244,250,.82); backdrop-filter:blur(12px); }
.block-container { padding-top:1.15rem; padding-bottom:4rem; max-width:1580px; }
h1,h2,h3,h4 { color:var(--tui-dark); letter-spacing:-.03em; }
h1 { font-size:2.05rem !important; font-weight:900 !important; }
h2 { font-size:1.3rem !important; font-weight:900 !important; }
h3 { font-size:1.03rem !important; font-weight:850 !important; }
p,label,span,div { text-rendering:optimizeLegibility; }

/* SIDEBAR */
[data-testid="stSidebar"] {
    background:linear-gradient(180deg,rgba(224,239,248,.56) 0%,rgba(232,244,251,.52) 100%);
    border-right:1px solid rgba(17,24,39,.08);
    box-shadow:10px 0 28px rgba(17,24,39,.035);
    backdrop-filter:blur(6px);
}

[data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
[data-testid="stSidebar"] .block-container { padding-top:.8rem; }
.tui-brand { display:flex; gap:.78rem; align-items:center; padding:.15rem .05rem .9rem .05rem; animation:fadeSlide .45s ease both; }
.tui-logo-wrap { display:flex; align-items:center; justify-content:center; padding:.42rem .5rem; border-radius:20px; background:rgba(255,255,255,.62); border:1px solid rgba(17,24,39,.08); box-shadow:var(--shadow-soft); backdrop-filter:blur(5px); }
.tui-logo-img { width:130px; height:auto; display:block; }
.tui-brand-title { font-size:.98rem; color:var(--tui-dark); font-weight:900; line-height:1.05; }
.tui-brand-sub { color:var(--muted); font-size:.68rem; font-weight:750; margin-top:.17rem; }
.sidebar-status { border:1px solid rgba(17,24,39,.09); border-radius:16px; padding:.72rem .8rem; margin:.15rem 0 .85rem 0; background:linear-gradient(180deg,rgba(234,244,251,.52),rgba(247,251,253,.48)); box-shadow:var(--shadow-soft); backdrop-filter:blur(5px); }
.sidebar-status-row { display:flex; align-items:center; gap:.45rem; color:var(--tui-dark); font-size:.79rem; font-weight:850; }
.status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.dot-ok{background:var(--success);box-shadow:0 0 0 4px rgba(25,134,94,.09)} .dot-warning{background:var(--warning)} .dot-critical{background:var(--error)}
.sidebar-time { color:var(--muted); font-size:.68rem; margin-top:.32rem; }
.sidebar-filter-intro { margin:.65rem 0 .35rem; border-radius:16px; padding:.7rem .76rem; background:linear-gradient(180deg,rgba(234,244,251,.48),rgba(247,251,253,.44)); color:var(--tui-dark); border:1px solid rgba(17,24,39,.09); box-shadow:var(--shadow-soft); backdrop-filter:blur(5px); }
.sidebar-filter-intro strong{color:var(--tui-dark);font-size:.78rem}.sidebar-filter-intro span{display:block;color:#667085;font-size:.65rem;line-height:1.35;margin-top:.18rem}

/* radio Vista / Escenario */
[data-testid="stSidebar"] div[data-testid="stRadio"] > label { color:var(--tui-dark)!important; font-weight:900; font-size:.78rem; margin-bottom:.2rem; }
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] { gap:.04rem; }
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label {
    padding:.26rem .25rem; border-radius:10px; transition:.18s ease; font-weight:700;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:hover { background:rgba(17,24,39,.05); }

/* expanders de filtros */
[data-testid="stSidebar"] [data-testid="stExpander"] { background:linear-gradient(180deg,rgba(234,244,251,.50),rgba(247,251,253,.46)); border:1px solid rgba(17,24,39,.09); border-radius:16px; box-shadow:var(--shadow-soft); margin:.42rem 0; overflow:hidden; backdrop-filter:blur(5px); }
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color:var(--tui-dark); font-weight:850; }
[data-testid="stSidebar"] [data-testid="stSlider"] { margin-bottom:.35rem; }
[data-testid="stSidebar"] [data-testid="stSlider"] label, [data-testid="stSidebar"] [data-testid="stSelectbox"] label { color:#334155!important; font-weight:750; font-size:.80rem; }

/* HERO y contenedores principales */
.hero { position:relative; overflow:hidden; padding:1.5rem 1.65rem; border-radius:24px; margin-bottom:1rem; background:linear-gradient(180deg,rgba(255,255,255,.96) 0%,rgba(247,247,248,.95) 100%); color:var(--tui-dark); box-shadow:var(--shadow); animation:fadeUp .42s ease both; border:1px solid rgba(17,24,39,.10); }
.hero:before { content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-88px; top:-115px; border:24px solid rgba(17,24,39,.04); animation:floatOrb 8s ease-in-out infinite; }
.hero:after { content:""; position:absolute; width:180px; height:180px; border-radius:50%; left:-95px; bottom:-110px; background:radial-gradient(circle,rgba(17,24,39,.08),rgba(17,24,39,.01) 65%,transparent 70%); }
.hero h1 { color:var(--tui-dark) !important; margin:0 0 .3rem 0; position:relative; z-index:2; }
.hero p { margin:0; color:#475467; font-size:.93rem; max-width:900px; position:relative; z-index:2; }
.hero-kicker { text-transform:uppercase; letter-spacing:.11em; font-weight:900; font-size:.66rem; color:#6B7280; margin-bottom:.42rem; position:relative; z-index:2; }
.hero-status { display:inline-flex; align-items:center; gap:.45rem; background:rgba(17,24,39,.05); border:1px solid rgba(17,24,39,.08); border-radius:999px; padding:.33rem .65rem; font-size:.72rem; font-weight:850; margin-top:.85rem; position:relative; z-index:2; color:var(--tui-dark); }

.section-card,[data-testid="stMetric"],[data-testid="stDataFrame"] { background:linear-gradient(180deg,rgba(255,255,255,.84),rgba(248,251,253,.78)); border:1px solid rgba(17,24,39,.10); box-shadow:var(--shadow-soft); backdrop-filter:blur(3px); }
.section-card { border-radius:20px; padding:1rem 1.05rem; animation:fadeUp .48s ease both; }
.section-title { color:var(--tui-dark); font-weight:900; font-size:.95rem; margin-bottom:.15rem; }
.section-sub { color:var(--muted); font-size:.76rem; margin-bottom:.8rem; }
[data-testid="stMetric"] { padding:.66rem .82rem; border-radius:16px; min-height:82px; transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-2px); box-shadow:0 18px 36px rgba(17,24,39,.10); border-color:rgba(17,24,39,.18); }
[data-testid="stMetricLabel"] { color:var(--muted); font-size:.66rem; text-transform:uppercase; letter-spacing:.045em; font-weight:900; }
[data-testid="stMetricValue"] { color:var(--tui-dark); font-weight:900; font-size:1.58rem; line-height:1.0; }

.alert-card { border-radius:14px; padding:.82rem .9rem; margin-bottom:.58rem; border:1px solid rgba(17,24,39,.08); background:linear-gradient(180deg,rgba(255,255,255,.80),rgba(244,249,252,.76)); box-shadow:0 10px 24px rgba(17,24,39,.04); backdrop-filter:blur(3px); }
.alert-critical { border-left:4px solid var(--error); background:#FFF8F8; }.alert-warning { border-left:4px solid var(--warning); background:#FFFBF3; }.alert-info { border-left:4px solid #667085; background:#F7F7F8; }.alert-ok { border-left:4px solid var(--success); background:#F5FBF8; }
.alert-head { display:flex; justify-content:space-between; gap:.7rem; align-items:flex-start; }.alert-title { font-weight:900; color:var(--text); font-size:.84rem; }.alert-badge { font-size:.61rem; font-weight:900; letter-spacing:.06em; border-radius:999px; padding:.18rem .45rem; white-space:nowrap; }
.badge-critical{background:#FBE1E1;color:#9C2020}.badge-warning{background:#FFF0CC;color:#8D5D00}.badge-info{background:#EAECF0;color:#344054}.badge-ok{background:#DDF3E9;color:#116947}.alert-message { color:var(--muted); font-size:.76rem; line-height:1.45; margin-top:.28rem; }.alert-action { color:#344054; font-size:.71rem; font-weight:800; margin-top:.35rem; }

[data-testid="stChatMessage"] { background:linear-gradient(180deg,rgba(255,255,255,.78),rgba(246,250,253,.74)); border:1px solid rgba(17,24,39,.10); border-radius:15px; padding:.25rem .35rem; backdrop-filter:blur(3px); }
[data-testid="stChatInput"] { border-color:var(--border); }
div.stButton > button { min-height:3rem; padding:.58rem 1rem; border-radius:999px; border:1px solid rgba(17,24,39,.16); background:linear-gradient(180deg,#FFFFFF 0%,#F2F4F7 100%); color:var(--tui-dark); font-weight:850; transition:.18s ease; box-shadow:inset 0 1px 0 rgba(255,255,255,.92), 0 8px 18px rgba(17,24,39,.06); }
div.stButton > button:hover { border-color:rgba(17,24,39,.32); background:linear-gradient(180deg,#FFFFFF 0%,#ECEFF3 100%); color:var(--tui-dark); transform:translateY(-1px); box-shadow:0 12px 22px rgba(17,24,39,.09); }
div.stButton > button[kind="primary"] { background:linear-gradient(180deg,#111827 0%,#2B3340 100%); color:#fff; border-color:#111827; box-shadow:0 12px 28px rgba(17,24,39,.18), inset 0 1px 0 rgba(255,255,255,.08); }
div.stButton > button[kind="primary"]:hover { background:linear-gradient(180deg,#0F172A 0%,#1F2937 100%); color:#fff; border-color:#0F172A; }
[data-baseweb="select"] > div,[data-baseweb="input"] > div,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,textarea { background:#fff!important; color:var(--text)!important; border-color:rgba(17,24,39,.12)!important; border-radius:12px!important; box-shadow:inset 0 1px 0 rgba(255,255,255,.88); }
[data-baseweb="tab-list"] { gap:.25rem; } [data-baseweb="tab"] { border-radius:999px; padding:.4rem .85rem; background:linear-gradient(180deg,#FFFFFF 0%,#F2F4F7 100%); border:1px solid rgba(17,24,39,.10); box-shadow:0 6px 16px rgba(17,24,39,.05); }
[data-baseweb="tab"][aria-selected="true"] { background:linear-gradient(180deg,#111827 0%,#2B3340 100%); color:#fff; border-color:#111827; }
[data-testid="stDataFrame"] { border-radius:16px; overflow:hidden; animation:fadeUp .45s ease both; }
.small-note,.system-strip { color:var(--muted); font-size:.74rem; line-height:1.45; }.system-strip{display:flex;align-items:center;gap:.5rem;margin:.2rem 0 .9rem}.status-chip{display:inline-flex;border-radius:999px;padding:.22rem .55rem;font-size:.68rem;font-weight:900}.chip-ok{background:#DDF3E9;color:#116947}.chip-warning{background:#FFF0CC;color:#8D5D00}.chip-critical{background:#FBE1E1;color:#9C2020}

.page-heading{margin:.25rem 0 1rem 0;animation:fadeUp .35s ease both}.page-heading h1{margin:0!important;color:var(--tui-dark)!important;font-size:1.9rem!important}.page-heading p{margin:.28rem 0 0 0;color:var(--muted);font-size:.88rem;max-width:920px}.page-heading .kicker{font-size:.70rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase;color:#4B5563;margin-bottom:.26rem}
hr { border-color:rgba(17,24,39,.10)!important; }

@keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeSlide { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }
@keyframes floatOrb { 0%,100%{transform:translateY(0) rotate(0deg)} 50%{transform:translateY(10px) rotate(8deg)} }
@media(max-width:800px){.block-container{padding-left:1rem;padding-right:1rem}.hero{padding:1.15rem}.hero h1{font-size:1.5rem!important}.tui-logo-img{width:104px}}

/* Ranking premium: podium superior */
.podium-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:.65rem 0 1.15rem}
.podium-card{position:relative;overflow:hidden;border-radius:22px;padding:1.05rem 1.1rem;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,250,252,.96));border:1px solid rgba(17,24,39,.10);box-shadow:var(--shadow-soft);min-height:150px;transition:.18s ease}
.podium-card:hover{transform:translateY(-3px);box-shadow:0 20px 42px rgba(17,24,39,.10)}
.podium-card.first{border:1px solid rgba(17,24,39,.18);box-shadow:0 18px 40px rgba(17,24,39,.09)}
.podium-image{width:calc(100% + 2.2rem);height:150px;object-fit:cover;display:block;margin:-1.05rem -1.1rem .9rem -1.1rem;border-bottom:1px solid rgba(17,24,39,.10);background:#F1F5F9}
.podium-image-fallback{width:calc(100% + 2.2rem);height:150px;margin:-1.05rem -1.1rem .9rem -1.1rem;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#FFFFFF,#F3F4F6);color:var(--tui-dark);font-weight:900;border-bottom:1px solid rgba(17,24,39,.10)}
.podium-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-top:.05rem}.podium-head-main{min-width:0;flex:1}.podium-rank{font-size:.72rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.podium-name{font-size:1.35rem;font-weight:900;color:var(--tui-dark);margin:.22rem 0 0}.podium-price{font-size:2rem;font-weight:900;color:var(--tui-red);line-height:1;white-space:nowrap;text-align:right;margin-top:.05rem}.podium-meta{margin-top:.75rem;font-size:.74rem;color:var(--muted);line-height:1.45}
.podium-rank-icon{width:24px;height:24px;object-fit:contain;vertical-align:middle;margin-right:.35rem;border-radius:5px}.scenario-icon-wrap{height:52px;display:flex;align-items:center;justify-content:center;margin:.05rem 0 .28rem}.scenario-icon{width:44px;height:44px;object-fit:contain;border-radius:10px}.scenario-active-icon{width:22px;height:22px;object-fit:contain;vertical-align:middle;margin-right:.28rem;border-radius:5px}.assistant-summary{margin:.45rem 0 .15rem;padding:.55rem .65rem;border-radius:12px;background:rgba(255,255,255,.72);border:1px solid rgba(17,24,39,.08);font-size:.70rem;color:#475467;line-height:1.45}
.alerts-top{margin:.2rem 0 .75rem}.alerts-top-title{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900;color:var(--tui-dark);margin-bottom:.35rem}
@media(max-width:900px){.podium-grid{grid-template-columns:1fr}}

.scenario-card{margin:.28rem 0 .65rem;padding:.68rem .72rem;border-radius:14px;background:linear-gradient(180deg,#FFFFFF,#F7F7F8);border:1px solid rgba(17,24,39,.10);box-shadow:0 8px 18px rgba(17,24,39,.04)}
.scenario-title{font-size:.80rem;font-weight:900;color:var(--tui-dark)}.scenario-desc{font-size:.66rem;color:var(--muted);line-height:1.35;margin-top:.16rem}
.chat-main{margin:.35rem 0 .75rem}.chat-main-title{font-size:.96rem;font-weight:900;color:var(--tui-dark);margin-bottom:.15rem}.chat-main-sub{font-size:.74rem;color:var(--muted);margin-bottom:.45rem}
.map-note{font-size:.70rem;color:var(--muted);margin:.25rem 0 .6rem}.map-kpi{font-weight:900;color:var(--tui-dark)}
.selector-title{font-size:.98rem;font-weight:900;color:var(--tui-dark);margin-bottom:.15rem}.selector-sub{font-size:.74rem;color:var(--muted);margin-bottom:.55rem}.selector-active{font-size:.72rem;color:var(--muted);margin-top:.35rem}.selector-active strong{color:var(--tui-dark)}

/* Recomendador externo (API de destinos de España) */
.reco-card{position:relative;overflow:hidden;border-radius:22px;padding:1.05rem 1.15rem;background:linear-gradient(180deg,rgba(255,255,255,.98),rgba(248,250,252,.96));border:1px solid rgba(17,24,39,.10);box-shadow:var(--shadow-soft);height:100%;transition:.18s ease}
.reco-card:hover{transform:translateY(-3px);box-shadow:0 20px 42px rgba(17,24,39,.10)}
.reco-card.first{border:1px solid rgba(17,24,39,.18);box-shadow:0 18px 40px rgba(17,24,39,.09)}
.reco-head{display:flex;align-items:flex-start;justify-content:space-between;gap:.9rem}
.reco-rank{font-size:.70rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.reco-name{font-size:1.3rem;font-weight:900;color:var(--tui-dark);margin:.2rem 0 0;line-height:1.1}
.reco-place{font-size:.72rem;color:var(--muted);margin-top:.2rem}
.reco-score{font-size:1.75rem;font-weight:900;color:var(--tui-red);line-height:1;text-align:right;white-space:nowrap}
.reco-score-label{font-size:.60rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:right;margin-top:.22rem}
.reco-typology{display:inline-block;margin-top:.6rem;font-size:.66rem;font-weight:850;border-radius:999px;padding:.2rem .55rem;background:#EEF2F6;color:#344054}
.reco-headline{font-size:.80rem;color:#475467;line-height:1.45;margin-top:.65rem}
.reco-block{margin-top:.7rem}
.reco-block-title{font-size:.64rem;font-weight:900;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);margin-bottom:.25rem}
.reco-list{margin:0;padding-left:1.05rem;font-size:.74rem;color:#475467;line-height:1.5}
.reco-chips{display:flex;flex-wrap:wrap;gap:.28rem;margin-top:.2rem}
.reco-chip{font-size:.63rem;font-weight:800;border-radius:999px;padding:.18rem .5rem;background:#EEF2F6;color:#344054;border:1px solid rgba(17,24,39,.07)}
.reco-chip.ok{background:#DDF3E9;color:#116947}
.reco-chip.warn{background:#FFF0CC;color:#8D5D00}
.reco-bar-row{display:flex;align-items:center;gap:.5rem;margin-bottom:.28rem}
.reco-bar-label{font-size:.68rem;color:#475467;min-width:118px}
.reco-bar-track{flex:1;height:7px;border-radius:999px;background:#EDF0F4;overflow:hidden}
.reco-bar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,#D40E14,#F2646A)}
.reco-bar-value{font-size:.68rem;font-weight:900;color:var(--tui-dark);min-width:38px;text-align:right}
.reco-meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:.3rem .8rem;margin-top:.2rem}
.reco-meta-item{font-size:.71rem;color:var(--muted)}
.reco-meta-item strong{color:var(--tui-dark);font-weight:850}
.reco-engine{font-size:.70rem;color:var(--muted);margin:.15rem 0 .85rem}
.reco-engine strong{color:var(--tui-dark)}
@media(max-width:900px){.reco-meta-grid{grid-template-columns:1fr}}

/* Recomendacion destacada: la respuesta principal, visible sin buscarla */
.hero-reco{position:relative;overflow:hidden;border-radius:26px;padding:1.6rem 1.8rem;margin:.35rem 0 1.1rem;
  background:linear-gradient(135deg,#111827 0%,#1F2937 62%,#37414F 100%);color:#fff;
  background-size:cover;background-position:center 38%;
  box-shadow:0 22px 52px rgba(17,24,39,.22);animation:fadeUp .45s ease both;min-height:250px;
  display:flex;flex-direction:column;justify-content:flex-end}
.hero-reco.has-photo{padding-top:5rem}
.hero-reco:before{content:"";position:absolute;width:300px;height:300px;border-radius:50%;right:-110px;top:-140px;
  border:26px solid rgba(255,255,255,.05)}
.hero-reco:after{content:"";position:absolute;width:190px;height:190px;border-radius:50%;left:-90px;bottom:-120px;
  background:radial-gradient(circle,rgba(212,14,20,.28),transparent 68%)}
.hero-reco-credit{position:absolute;right:.85rem;bottom:.5rem;z-index:3;font-size:.56rem;
  color:rgba(255,255,255,.42);max-width:46%;text-align:right;line-height:1.3}
.hero-reco-read{position:relative;z-index:2;font-size:.66rem;font-weight:800;letter-spacing:.05em;
  text-transform:uppercase;color:rgba(255,255,255,.6);margin-top:.28rem;text-align:right}
.hero-reco-kicker{position:relative;z-index:2;text-transform:uppercase;letter-spacing:.13em;font-weight:900;
  font-size:.64rem;color:rgba(255,255,255,.62);margin-bottom:.5rem}
.hero-reco-top{position:relative;z-index:2;display:flex;align-items:flex-start;justify-content:space-between;gap:1.5rem}
.hero-reco-name{font-size:2.5rem;font-weight:900;line-height:1.02;letter-spacing:-.035em;margin:0;color:#fff}
.hero-reco-place{font-size:.86rem;color:rgba(255,255,255,.72);margin-top:.4rem}
.hero-reco-score{text-align:right;white-space:nowrap}
.hero-reco-score-value{font-size:2.9rem;font-weight:900;line-height:1;color:#FF6B70}
.hero-reco-score-label{font-size:.6rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
  color:rgba(255,255,255,.55);margin-top:.3rem}
.hero-reco-why{position:relative;z-index:2;font-size:.96rem;line-height:1.5;color:rgba(255,255,255,.9);
  margin:1rem 0 0;max-width:760px}
.hero-reco-chips{position:relative;z-index:2;display:flex;flex-wrap:wrap;gap:.35rem;margin-top:1rem}
.hero-reco-chip{font-size:.66rem;font-weight:800;border-radius:999px;padding:.26rem .62rem;
  background:rgba(255,255,255,.13);color:#fff;border:1px solid rgba(255,255,255,.16)}
.hero-reco-chip.warn{background:rgba(255,214,102,.18);color:#FFD666;border-color:rgba(255,214,102,.3)}
.hero-reco-facts{position:relative;z-index:2;display:flex;flex-wrap:wrap;gap:1.7rem;margin-top:1.15rem;
  padding-top:1rem;border-top:1px solid rgba(255,255,255,.12)}
.hero-reco-fact{min-width:96px}
.hero-reco-fact-value{font-size:1.2rem;font-weight:900;color:#fff;line-height:1.1}
.hero-reco-fact-label{font-size:.62rem;text-transform:uppercase;letter-spacing:.07em;font-weight:800;
  color:rgba(255,255,255,.55);margin-top:.2rem}
.alt-title{font-size:.68rem;text-transform:uppercase;letter-spacing:.09em;font-weight:900;color:var(--muted);
  margin:.2rem 0 .5rem}

/* Fotografia en las tarjetas de alternativas */
.reco-photo{width:calc(100% + 2.3rem);height:132px;object-fit:cover;display:block;
  margin:-1.05rem -1.15rem .85rem -1.15rem;border-bottom:1px solid rgba(17,24,39,.10);background:#F1F5F9}
.reco-photo-fallback{width:calc(100% + 2.3rem);height:132px;margin:-1.05rem -1.15rem .85rem -1.15rem;
  display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#FFFFFF,#F3F4F6);
  color:var(--tui-dark);font-weight:900;border-bottom:1px solid rgba(17,24,39,.10)}

@media(max-width:900px){
  .hero-reco-top{flex-direction:column}
  .hero-reco-name{font-size:1.9rem}
  .hero-reco-score{text-align:left}
  .hero-reco-score-value{font-size:2.2rem}
}

</style>
"""


def inject_styles() -> None:
    """Inyecta la hoja de estilos. Debe llamarse una vez, al inicio del script."""
    st.markdown(CSS, unsafe_allow_html=True)
