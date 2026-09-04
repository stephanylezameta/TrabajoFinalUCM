from __future__ import annotations

import base64
import json
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from matplotlib import pyplot as plt

from database.init_db import init_db
from services.alert_service import get_alerts, get_system_status
from services.assistant_service import (
    ai_connection_status,
    build_weights as build_assistant_weights,
    converse as assistant_converse,
    initial_message as assistant_initial_message,
    normalize_preferences as normalize_assistant_preferences,
)
from services.analytics_service import (
    get_dashboard_metrics,
    get_destination_metrics,
    instrumentation_status,
)
from services.data_control_service import (
    bootstrap_missing_sources,
    get_database_file_info,
    get_database_files,
    get_database_tables,
    get_import_history,
    get_source_health,
    get_update_runs,
    refresh_all_sources,
    refresh_source,
    seed_data_sources,
    update_source_config,
)
from services.geospatial_service import get_geospatial_metrics, metric_value
from services.destination_image_service import get_destination_image
from services.tdrs_service import PRESETS, SCENARIO_META, compute_scores, scenario_metrics
from services.tracking_service import create_session, register_event

st.set_page_config(
    page_title="TUI Data Intelligence",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

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

</style>
"""
st.markdown(CSS, unsafe_allow_html=True)



ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "tui_logo.png"


def get_png_data_uri(path: Path) -> str:
    """Devuelve una imagen PNG local embebida para usarla en HTML de Streamlit."""
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# Ranking: se conservan los minerales de oro, plata y bronce solicitados.
RANK_ICON_URLS = [
    "https://img.icons8.com/color/1200/gold-ore.jpg",
    "https://img.icons8.com/color/1200/silver-ore.jpg",
    "https://img.icons8.com/color/1200/bronze-ore.jpg",
]

# Escenarios: imágenes aportadas por el usuario y empaquetadas localmente.
# Esto evita depender de URLs externas para los tres accesos principales.
SCENARIO_ICON_URLS = {
    "Popular": get_png_data_uri(ASSETS_DIR / "scenario_popular_van_gogh.png"),
    "Equilibrado": get_png_data_uri(ASSETS_DIR / "scenario_equilibrado_coliseo.png"),
    "Explorador": get_png_data_uri(ASSETS_DIR / "scenario_explorador_brujula.png"),
}

# Fotografías del Top 3. Se sirven desde Wikimedia Commons para que la app
# mantenga imágenes reales de los destinos sin inflar el paquete local.
# Créditos/licencias se muestran dentro de cada tarjeta.
DESTINATION_IMAGES = {
    "Algarve": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/2/23/Algarve_coast_of_Portugal.jpg",
        "alt": "Costa del Algarve, Portugal",
        "credit": "Ned Dwyer · Wikimedia Commons · CC BY-SA 4.0",
    },
    "Mallorca": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/4/46/Mallorca_Coast_R01.jpg",
        "alt": "Costa norte de Mallorca, España",
        "credit": "Marc Ryckaert · Wikimedia Commons · CC BY 3.0",
    },
    "Split": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/b/bd/Split_harbor_view.jpg",
        "alt": "Vista del puerto de Split, Croacia",
        "credit": "Ryan Matzner y Rachel Pestik · Wikimedia Commons · dominio público",
    },
    "Dubrovnik": {
        "url": "https://thumb.wikimedia.org/wikipedia/commons/thumb/d/dc/View_of_Dubrovnik_Old_Town_at_night.jpg/960px-View_of_Dubrovnik_Old_Town_at_night.jpg",
        "alt": "Vista del casco histórico de Dubrovnik, Croacia",
        "credit": "hozinja · Wikimedia Commons · CC BY 2.0",
    },
    "Zadar": {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/A_view_to_the_historical_center_of_Zadar%2C_Croatia_surrounded_by_the_Adriatic_Sea_%2848607828812%29.jpg/1280px-A_view_to_the_historical_center_of_Zadar%2C_Croatia_surrounded_by_the_Adriatic_Sea_%2848607828812%29.jpg",
        "alt": "Vista del centro histórico de Zadar, Croacia",
        "credit": "dronepicr · Wikimedia Commons · CC BY 2.0",
    },
}


def get_logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


LOGO_DATA_URI = get_logo_data_uri()

def bootstrap() -> None:
    init_db()
    seed_data_sources()
    bootstrap_missing_sources()


def fmt_ts(value: str | None) -> str:
    if not value:
        return "Sin registrar"
    return str(value).replace("T", " ")[:19]


def status_copy(status: str) -> tuple[str, str]:
    if status == "critical":
        return "Requiere atención", "critical"
    if status == "warning":
        return "Atención operativa", "warning"
    return "Sistema estable", "ok"


def page_heading(title: str) -> None:
    """Título principal sin etiqueta técnica superior ni subtítulo auxiliar."""
    st.markdown(
        f'<div class="page-heading"><h1>{escape(title)}</h1></div>',
        unsafe_allow_html=True,
    )


def render_system_alerts(title: str = "Alertas de sistema") -> None:
    """Bloque único de alertas operativas para las vistas 3 y 4."""
    alerts = get_alerts()
    st.markdown(f"### {title}")
    if len(alerts) == 1:
        render_alert(alerts[0])
        return
    alert_cols = st.columns(min(3, len(alerts)))
    for idx, item in enumerate(alerts[:3]):
        with alert_cols[idx]:
            render_alert(item)


def render_metric_rows(metrics: list[tuple[str, object]], columns: int = 3) -> None:
    if columns < 1:
        columns = 1
    for start in range(0, len(metrics), columns):
        row = st.columns(columns)
        chunk = metrics[start:start + columns]
        for idx, (label, value) in enumerate(chunk):
            row[idx].metric(label, value)


def render_alert(item: dict) -> None:
    level = str(item.get("level", "INFO")).upper()
    css_level = level.lower()
    title = escape(str(item.get("title", "Alerta")))
    message = escape(str(item.get("message", "")))
    action = item.get("action")
    action_html = f'<div class="alert-action">Acción recomendada · {escape(str(action))}</div>' if action else ""
    st.markdown(
        f"""
        <div class="alert-card alert-{css_level}">
          <div class="alert-head"><div class="alert-title">{title}</div><span class="alert-badge badge-{css_level}">{level}</span></div>
          <div class="alert-message">{message}</div>{action_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


MODEL_SLIDER_SUFFIX = {
    "sunny_days_pct": "sunny",
    "low_precipitation_pct": "precip",
    "popularity": "popular",
    "hospital_beds": "beds",
    "safety": "safety",
}


def _ensure_tdrs_assistant_state(scenario: str) -> None:
    if "tdrs_assistant_messages" not in st.session_state:
        st.session_state.tdrs_assistant_messages = [
            {"role": "assistant", "content": assistant_initial_message()}
        ]
    if "tdrs_assistant_preferences" not in st.session_state:
        st.session_state.tdrs_assistant_preferences = normalize_assistant_preferences({})
    if "tdrs_assistant_focus" not in st.session_state:
        st.session_state.tdrs_assistant_focus = None
    if "tdrs_assistant_source" not in st.session_state:
        st.session_state.tdrs_assistant_source = "local"

    # Los criterios que aún no se han hablado conservan el preset del escenario
    # activo. Así la conversación puede continuar aunque el usuario cambie de
    # Popular a Equilibrado o Explorador.
    st.session_state.tdrs_assistant_proposal = build_assistant_weights(
        st.session_state.tdrs_assistant_preferences,
        PRESETS[scenario],
    )


def _reset_tdrs_assistant() -> None:
    st.session_state.tdrs_assistant_messages = [
        {"role": "assistant", "content": assistant_initial_message()}
    ]
    st.session_state.tdrs_assistant_preferences = normalize_assistant_preferences({})
    st.session_state.tdrs_assistant_focus = None
    st.session_state.tdrs_assistant_proposal = None
    st.session_state.tdrs_assistant_applied = None
    st.session_state.tdrs_assistant_source = "local"


def _apply_assistant_weights(scenario: str) -> None:
    recommended = st.session_state.get("tdrs_assistant_proposal") or {}
    if not recommended:
        return
    for field, value in recommended.items():
        suffix = MODEL_SLIDER_SUFFIX[field]
        st.session_state[f"sb_{scenario}_{suffix}"] = int(value)
    st.session_state.tdrs_assistant_applied = {
        "scenario": scenario,
        "weights": dict(recommended),
    }
    register_event(
        st.session_state.session_id,
        "assistant_weights_applied",
        "Simulador TDRS · Asistente IA",
        metadata={
            "scenario": scenario,
            "preferences": st.session_state.get("tdrs_assistant_preferences", {}),
            "weights": recommended,
            "assistant_source": st.session_state.get("tdrs_assistant_source", "local"),
        },
    )


def _process_assistant_message(prompt: str, scenario: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return

    messages = list(st.session_state.get("tdrs_assistant_messages", []))
    messages.append({"role": "user", "content": prompt})
    result = assistant_converse(
        prompt=prompt,
        messages=messages,
        preferences=st.session_state.get("tdrs_assistant_preferences", {}),
        scenario=scenario,
        scenario_defaults=PRESETS[scenario],
        focus_field=st.session_state.get("tdrs_assistant_focus"),
    )
    messages.append({"role": "assistant", "content": result["reply"]})

    st.session_state.tdrs_assistant_messages = messages[-14:]
    st.session_state.tdrs_assistant_preferences = result["preferences"]
    st.session_state.tdrs_assistant_proposal = result["weights"]
    st.session_state.tdrs_assistant_focus = result.get("focus_field")
    st.session_state.tdrs_assistant_source = result.get("source", "local")
    st.session_state.tdrs_assistant_applied = None

    register_event(
        st.session_state.session_id,
        "assistant_message",
        "Simulador TDRS · Asistente IA",
        metadata={
            "scenario": scenario,
            "assistant_source": result.get("source", "local"),
            "missing_preferences": result.get("missing", []),
        },
    )


def render_tdrs_assistant(scenario: str) -> None:
    _ensure_tdrs_assistant_state(scenario)

    with st.sidebar.expander("Asistente IA", expanded=False):
        st.caption(
            "Cuéntame con tus propias palabras qué buscas. El asistente irá "
            "recogiendo tus preferencias y propondrá pesos para el TDRS."
        )
        connection = ai_connection_status()
        messages = st.session_state.get("tdrs_assistant_messages", [])
        has_user_turn = any(m.get("role") == "user" for m in messages)
        last_source = st.session_state.get("tdrs_assistant_source", "local")
        if connection == "connected" and (not has_user_turn or last_source == "ai"):
            st.markdown("🟢 **IA conectada**")
        elif connection == "connected":
            st.markdown("🟠 **IA configurada · último turno resuelto con fallback local**")
        else:
            st.markdown("⚪ **Conector IA preparado · modo local de demostración**")

        # Mostramos los últimos turnos para mantener el lateral compacto.
        for item in messages[-8:]:
            with st.chat_message(item.get("role", "assistant")):
                st.markdown(item.get("content", ""))

        with st.form(f"assistant_chat_form_{scenario}", clear_on_submit=True):
            prompt = st.text_input(
                "Mensaje",
                placeholder="Ej.: quiero sol, seguridad y lugares tranquilos…",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Enviar", use_container_width=True)

        if submitted and prompt.strip():
            _process_assistant_message(prompt, scenario)
            st.rerun()

        # No enseñamos una propuesta antes de que el usuario haya conversado.
        proposal = st.session_state.get("tdrs_assistant_proposal") or {}
        if proposal and has_user_turn:
            st.markdown(
                '<div class="assistant-summary"><strong>Propuesta actual</strong><br>'
                f'Sol <strong>{proposal["sunny_days_pct"]}</strong> · '
                f'precipitación <strong>{proposal["low_precipitation_pct"]}</strong> · '
                f'popularidad <strong>{proposal["popularity"]}</strong> · '
                f'sanidad <strong>{proposal["hospital_beds"]}</strong> · '
                f'seguridad <strong>{proposal["safety"]}</strong>'
                '</div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Aplicar propuesta al modelo",
                key=f"assistant_apply_{scenario}",
                use_container_width=True,
                type="primary",
                on_click=_apply_assistant_weights,
                args=(scenario,),
            )

        st.button(
            "Nueva conversación",
            key=f"assistant_reset_{scenario}",
            use_container_width=True,
            on_click=_reset_tdrs_assistant,
        )

        applied = st.session_state.get("tdrs_assistant_applied")
        if applied and applied.get("scenario") == scenario:
            st.success("La propuesta del asistente ya está aplicada a los pesos del modelo.")


def render_tdrs_sidebar_controls() -> dict:
    """Controles laterales del TDRS, incluido el asistente de personalización."""
    scenario = st.session_state.get("tdrs_scenario", "Equilibrado")
    if scenario not in {"Popular", "Equilibrado", "Explorador"}:
        scenario = "Equilibrado"
        st.session_state.tdrs_scenario = scenario
    defaults = PRESETS[scenario]

    # El asistente aparece primero y solo existe dentro de la vista Simulador TDRS.
    render_tdrs_assistant(scenario)

    with st.sidebar.expander("Pesos del modelo", expanded=True):
        weights = {
            "sunny_days_pct": st.slider("% días soleados / año", 0, 100, int(defaults["sunny_days_pct"]), key=f"sb_{scenario}_sunny"),
            "low_precipitation_pct": st.slider("% precipitación · menos es mejor", 0, 100, int(defaults["low_precipitation_pct"]), key=f"sb_{scenario}_precip"),
            "popularity": st.slider("Más visitado", 0, 100, int(defaults["popularity"]), key=f"sb_{scenario}_popular"),
            "hospital_beds": st.slider("Capacidad sanitaria", 0, 100, int(defaults["hospital_beds"]), key=f"sb_{scenario}_beds"),
            "safety": st.slider("Seguridad", 0, 100, int(defaults["safety"]), key=f"sb_{scenario}_safety"),
        }

    with st.sidebar.expander("Restricciones", expanded=True):
        max_price = st.slider("Precio máximo (€)", 400, 2500, 2500, 50, key=f"sb_{scenario}_price")
        max_stay_days = st.slider("Máx. días hospedados", 1, 365, 365, 1, key=f"sb_{scenario}_stay")

    return {
        "scenario": scenario,
        "weights": weights,
        "max_price": max_price,
        "max_stay_days": max_stay_days,
    }

def render_tdrs_scenario_selector() -> None:
    scenarios = ["Popular", "Equilibrado", "Explorador"]
    current = st.session_state.get("tdrs_scenario", "Equilibrado")
    if current not in scenarios:
        current = "Equilibrado"
        st.session_state.tdrs_scenario = current

    with st.container(border=True):
        cols = st.columns(3, gap="medium")
        for idx, name in enumerate(scenarios):
            meta = SCENARIO_META[name]
            icon_url = SCENARIO_ICON_URLS[name]
            cols[idx].markdown(
                f'<div class="scenario-icon-wrap"><img class="scenario-icon" src="{escape(icon_url, quote=True)}" alt="{escape(name, quote=True)}"></div>',
                unsafe_allow_html=True,
            )
            clicked = cols[idx].button(
                name,
                key=f"tdrs_top_scenario_{name}",
                use_container_width=True,
                type="primary" if current == name else "secondary",
            )
            if clicked and current != name:
                st.session_state.tdrs_scenario = name
                st.rerun()
        meta = SCENARIO_META[current]
        active_icon = SCENARIO_ICON_URLS[current]
        st.markdown(
            f'<div class="selector-active"><strong><img class="scenario-active-icon" src="{escape(active_icon, quote=True)}" alt="">{escape(current)}</strong> · {escape(meta["description"])}</div>',
            unsafe_allow_html=True,
        )


def render_tdrs(controls: dict) -> None:
    scenario = controls["scenario"]
    weights = controls["weights"]

    render_tdrs_scenario_selector()

    res = compute_scores(
        weights,
        max_price=controls["max_price"],
        max_stay_days=controls["max_stay_days"],
    )

    # Primero se prepara el ranking para mostrar las tres opciones principales
    # inmediatamente después del selector, sin alterar cálculos, datos ni controles.
    rank_rows = []
    for pos, r in enumerate(res["ranked"], 1):
        model = r.get("model_values") or {}
        rank_rows.append({
            "Opción": pos,
            "Destino": r["name"],
            "Días soleados %": model.get("sunny_days_pct"),
            "Precipitación %": model.get("precipitation_days_pct"),
            "Pasajeros/año": model.get("annual_passengers"),
            "Precio €": r.get("reference_price_eur"),
        })

    # Las tres opciones principales se muestran directamente tras el selector, sin título adicional.
    # El precio queda destacado en la esquina superior derecha del área informativa.
    podium = []
    for idx, row in enumerate(rank_rows[:3]):
        visitors = row.get("Pasajeros/año")
        visitors_text = "—" if visitors is None else f"{int(round(visitors)):,} pasajeros/año"
        price_text = "—" if row.get("Precio €") is None else f"{float(row['Precio €']):,.0f} €"
        destination = str(row["Destino"])
        # Prioridad: fotografía curada localmente en el código. Si el destino no
        # está en el catálogo, se busca automáticamente una imagen representativa
        # en Wikipedia/Wikimedia y se cachea para los siguientes reruns.
        image = DESTINATION_IMAGES.get(destination) or get_destination_image(destination)
        if image:
            image_html = (
                f'<img class="podium-image" src="{escape(image["url"], quote=True)}" '
                f'alt="{escape(image.get("alt", f"Imagen de {destination}"), quote=True)}" loading="lazy">'
            )
        else:
            image_html = f'<div class="podium-image-fallback">{escape(destination)}</div>'
        podium.append(
            f'<div class="podium-card {"first" if idx == 0 else ""}">'
            f'{image_html}'
            f'<div class="podium-head">'
            f'<div class="podium-head-main">'
            f'<div class="podium-rank"><img class="podium-rank-icon" src="{escape(RANK_ICON_URLS[idx], quote=True)}" alt="Posición {idx+1}"> opción {idx+1}</div>'
            f'<div class="podium-name">{escape(destination)}</div>'
            f'</div>'
            f'<div class="podium-price">{escape(price_text)}</div>'
            f'</div>'
            f'<div class="podium-meta">{escape(visitors_text)}</div>'
            '</div>'
        )
    if podium:
        st.markdown('<div class="podium-grid">' + ''.join(podium) + '</div>', unsafe_allow_html=True)

    # Los KPIs se mantienen exactamente iguales y aparecen debajo de las tres opciones.
    metrics = scenario_metrics(res["ranked"])
    if metrics:
        def fmt(v, suffix="", decimals=1):
            return "—" if v is None else f"{v:.{decimals}f}{suffix}"

        visitors = metrics.get("avg_top5_annual_passengers")
        visitors_text = "—" if visitors is None else (f"{visitors/1_000_000:.1f} M/año" if visitors >= 1_000_000 else f"{visitors/1_000:.0f} k/año")
        render_metric_rows([
            ("Elegibles", metrics["eligible"]),
            ("Días soleados Top 5", fmt(metrics.get("avg_top5_sunny_days_pct"), "%", 0)),
            ("Visitantes Top 5", visitors_text),
        ], columns=3)

    remaining_rows = rank_rows[3:] if len(rank_rows) > 3 else rank_rows
    if remaining_rows:
        display = pd.DataFrame(remaining_rows)[[
            "Opción",
            "Destino",
            "Días soleados %",
            "Precipitación %",
            "Pasajeros/año",
            "Precio €",
        ]]
        # La tabla visible se limita a variables comerciales y de clima.
        # Score, cobertura, sanidad, seguridad y trazabilidad KNN siguen
        # disponibles internamente para el cálculo, pero no se muestran aquí.
        for col in ["Días soleados %", "Precipitación %", "Pasajeros/año", "Precio €"]:
            display[col] = display[col].map(lambda v: "—" if pd.isna(v) else (f"{v:,.0f}" if col in {"Pasajeros/año", "Precio €"} else f"{v:.2f}"))
        st.dataframe(display, use_container_width=True, hide_index=True, height=500)
    if res["excluded"]:
        st.warning(f"{len(res['excluded'])} destinos quedan fuera por precio o duración conocida del catálogo.")

def _draw_world_polygons(ax) -> None:
    world_path = Path(__file__).resolve().parent / "data" / "world_lowres.geojson"
    if not world_path.exists():
        return
    try:
        world = json.loads(world_path.read_text(encoding="utf-8"))
    except Exception:
        return
    for feature in world.get("features", []):
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates") or []
        polygons = coords if geometry.get("type") == "MultiPolygon" else [coords]
        for polygon in polygons:
            if not polygon:
                continue
            ring = polygon[0]
            if len(ring) < 3:
                continue
            xs = [pt[0] for pt in ring]
            ys = [pt[1] for pt in ring]
            ax.fill(xs, ys, facecolor="#F4FBFE", edgecolor="#C5E6F4", linewidth=.45, zorder=1)


def render_geospatial_map(rows: list[dict], metric: str) -> None:
    if not rows:
        st.info("No hay destinos geolocalizados disponibles para el mapa.")
        return
    values = [metric_value(r, metric) for r in rows]
    max_value = max(values) if values else 0
    active = [r for r in rows if metric_value(r, metric) > 0]
    focus = active if active else rows

    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    _draw_world_polygons(ax)
    for row in rows:
        value = metric_value(row, metric)
        size = 34 if max_value <= 0 else 38 + 300 * ((value / max_value) ** 0.55)
        point_color = "#D40E14" if value > 0 else "#AEE8FF"
        ax.scatter(row["longitude"], row["latitude"], s=size, color=point_color, edgecolor="#FFFFFF", linewidth=1.0, alpha=.88, zorder=3)
        if value > 0 or len(rows) <= 18:
            label_value = f"{value:,.0f}" if metric != "Ingresos" else f"{value:,.0f} €"
            ax.annotate(f"{row['destination']}\n{label_value}", (row["longitude"], row["latitude"]), xytext=(4, 5), textcoords="offset points", fontsize=7, color="#0E2642", zorder=4)

    lons = [r["longitude"] for r in focus]
    lats = [r["latitude"] for r in focus]
    if lons and lats:
        lon_margin = max(6.0, (max(lons) - min(lons)) * .18)
        lat_margin = max(5.0, (max(lats) - min(lats)) * .22)
        ax.set_xlim(max(-180, min(lons) - lon_margin), min(180, max(lons) + lon_margin))
        ax.set_ylim(max(-60, min(lats) - lat_margin), min(85, max(lats) + lat_margin))
    ax.set_facecolor("#FFFFFF")
    ax.grid(True, color="#E7F4F9", linewidth=.5, alpha=.65)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout(pad=.3)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def render_control_web() -> None:
    render_system_alerts("Alertas de sistema")
    m = get_dashboard_metrics()
    render_metric_rows([
        ("Sesiones", m["sessions"]),
        ("Clics", m["clicks"]),
        ("Reservas", m["bookings"]),
        ("Ingresos", f"{m['revenue_eur']:,.0f} €"),
        ("Cancelaciones", m["cancellations"]),
        ("ROI", f"{m['roi']:.1%}" if m.get("roi") is not None else "Pendiente"),
    ], columns=3)

    left, right = st.columns([1.45, 1], gap="large")
    with left:
        st.markdown("### Mapa geoespacial")
        if "geo_metric_selected" not in st.session_state:
            st.session_state.geo_metric_selected = "Clics"
        metric = st.session_state.geo_metric_selected
        metric_cols = st.columns(3, gap="small")
        for idx, label in enumerate(["Clics", "Reservas", "Ingresos"]):
            clicked = metric_cols[idx].button(
                label,
                key=f"geo_metric_button_{label}",
                use_container_width=True,
                type="primary" if metric == label else "secondary",
            )
            if clicked and metric != label:
                st.session_state.geo_metric_selected = label
                st.rerun()
        geo_rows = get_geospatial_metrics()
        render_geospatial_map(geo_rows, metric)
    with right:
        st.markdown("### Estado de instrumentación")
        st.dataframe(pd.DataFrame(instrumentation_status()), use_container_width=True, hide_index=True, height=300)

    st.markdown("### Rendimiento por destino")
    destinations = pd.DataFrame(get_destination_metrics())
    if destinations.empty:
        st.info("Todavía no hay interacción por destino suficiente para construir esta tabla.")
    else:
        st.dataframe(destinations, use_container_width=True, hide_index=True)

def render_data_model() -> None:
    db_info = get_database_file_info()
    sources = get_source_health()
    alerts = get_alerts(include_ok=False)
    ok_sources = sum(1 for s in sources if s["enabled"] and s["Estado"] == "OK")
    tables = get_database_tables()
    status = "critical" if db_info["integrity"] != "ok" else "warning" if alerts else "ok"

    # El mismo sistema de alertas operativas se muestra en las vistas 3 y 4.
    render_system_alerts("Alertas de datos")

    render_metric_rows([
        ("SQLite", "OK" if db_info["integrity"] == "ok" else "Revisar"),
        ("Tablas", len(tables)),
        ("Fuentes activas", sum(1 for s in sources if s["enabled"])),
        ("Fuentes al día", ok_sources),
        ("Alertas", len(alerts)),
        ("Tamaño DB", f"{db_info['size_mb']} MB"),
    ], columns=3)


    tab_sources, tab_runs, tab_db, tab_config = st.tabs(["Fuentes", "Historial de actualizaciones", "Bases y tablas", "Configuración"])

    with tab_sources:
        source_df = pd.DataFrame(sources)
        visible_cols = [
            "Estado", "Dataset", "Tipo", "Filas actuales", "Intervalo objetivo", "Última actualización",
            "Próxima esperada", "Modelo del dataset", "Método actual", "Scraper / conector", "Último error",
        ]
        st.dataframe(source_df[visible_cols], use_container_width=True, hide_index=True)

    with tab_runs:
        f1, f2, f3, f4 = st.columns([1.3, 1, 1, 1])
        source_ids = {"Todas": None, **{s["Dataset"]: s["source_id"] for s in sources}}
        source_label = f1.selectbox("Fuente", list(source_ids), key="runs_source")
        status_filter = f2.selectbox("Estado", ["Todos", "success", "warning", "error", "running"], key="runs_status")
        start = f3.date_input("Desde", value=date.today() - timedelta(days=30), key="runs_start")
        end = f4.date_input("Hasta", value=date.today(), key="runs_end")
        runs = get_update_runs(
            limit=250,
            source_id=source_ids[source_label],
            status=status_filter,
            start_date=start,
            end_date=end,
        )
        if runs:
            df = pd.DataFrame(runs)
            df["Variación"] = df.apply(
                lambda r: (r["rows_after"] - r["rows_before"]) if pd.notna(r["rows_after"]) and pd.notna(r["rows_before"]) else None,
                axis=1,
            )
            cols = ["started_at", "source_name", "status", "duration_seconds", "rows_before", "rows_after", "Variación", "trigger", "error_message"]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.caption("No hay ejecuciones que coincidan con los filtros.")

        with st.expander("Histórico técnico de imports"):
            imports = get_import_history(100)
            if imports:
                st.dataframe(pd.DataFrame(imports).drop(columns=["details"], errors="ignore"), use_container_width=True, hide_index=True)
            else:
                st.caption("Sin imports registrados.")

    with tab_db:
        st.markdown("#### Bases de datos")
        db_files = get_database_files()
        if db_files:
            st.dataframe(pd.DataFrame(db_files), use_container_width=True, hide_index=True)
        else:
            st.warning("No se han encontrado ficheros SQLite en data/.")
        st.markdown("#### Tablas persistidas")
        st.dataframe(pd.DataFrame(tables), use_container_width=True, hide_index=True)
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Diagnóstico SQLite**")
            st.code(db_info["path"])
            st.write(f"Integrity check: **{db_info['integrity']}**")
            st.write(f"Última modificación: **{fmt_ts(db_info['modified_at'])}**")
        with d2:
            st.markdown("**Punto de entrada de actualización**")
            st.code("python scripts\\build_model.py", language="powershell")
            st.caption("Se puede programar con Task Scheduler, cron o un orquestador cuando los conectores externos estén disponibles.")

    with tab_config:
        source_options = {f"{s['Dataset']} · {s['source_id']}": s for s in sources}
        selected_label = st.selectbox("Fuente", list(source_options), key="config_source")
        selected = source_options[selected_label]
        col1, col2 = st.columns([1, 2])
        interval_hours = col1.number_input(
            "Intervalo objetivo (horas)", min_value=1, max_value=8760,
            value=int(selected["interval_hours"]), step=1,
        )
        enabled = col1.checkbox("Fuente activa", value=bool(selected["enabled"]))
        dataset_model = col2.text_input(
            "Modelo utilizado / versión del dataset",
            value=selected.get("Modelo del dataset") or "No documentado",
        )
        notes = col2.text_area("Notas operativas", value=selected.get("Notas") or "", height=100)
        b1, b2, b3 = st.columns([1, 1, 1.6])
        if b1.button("Guardar configuración", use_container_width=True, type="primary"):
            try:
                update_source_config(selected["source_id"], int(interval_hours), dataset_model, notes, enabled)
                st.success("Configuración guardada en SQLite.")
                st.rerun()
            except Exception as exc:
                st.error(f"No se pudo guardar: {exc}")
        if b2.button("Actualizar fuente", use_container_width=True):
            try:
                with st.spinner(f"Actualizando {selected['Dataset']}…"):
                    result = refresh_source(selected["source_id"], trigger="manual")
                st.success(f"Actualización completada · {result.get('rows_in_table')} filas actuales.")
                st.rerun()
            except Exception as exc:
                st.error(f"Falló la actualización: {exc}")
        if b3.button("Actualizar todas las fuentes locales", use_container_width=True):
            with st.spinner("Actualizando fuentes locales…"):
                results = refresh_all_sources(trigger="manual")
            failed = [r for r in results if r.get("status") != "success"]
            if failed:
                st.error(f"Proceso terminado con {len(failed)} fuente(s) con error.")
                st.json(failed)
            else:
                st.success("Todas las fuentes locales se han actualizado correctamente.")
            st.rerun()


bootstrap()
if "session_id" not in st.session_state:
    st.session_state.session_id = create_session(source="streamlit")
if "page_views" not in st.session_state:
    st.session_state.page_views = set()

system_sidebar = get_system_status()
status_text, status_css = status_copy(system_sidebar["status"])
st.sidebar.markdown(
    f"""
    <div class="tui-brand">
      <div class="tui-logo-wrap"><img class="tui-logo-img" src="{LOGO_DATA_URI}" alt="TUI logo"></div>
      <div><div class="tui-brand-title">Data Intelligence</div><div class="tui-brand-sub">Madrid UI · Operations</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

NAV = ["Simulador TDRS", "Control Web", "Datos / modelo"]
view = st.sidebar.radio("Vista", NAV, index=0, key="sidebar_view")

tdrs_controls = None
if view == "Simulador TDRS":
    if "tdrs_scenario" not in st.session_state:
        st.session_state.tdrs_scenario = "Equilibrado"
    tdrs_controls = render_tdrs_sidebar_controls()

st.sidebar.markdown(
    f"""
    <div class="sidebar-status">
      <div class="sidebar-status-row"><span class="status-dot dot-{status_css}"></span>{escape(status_text)}</div>
      <div class="sidebar-time">Última actualización · {escape(fmt_ts(system_sidebar.get('last_update')))}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

sid = st.session_state.session_id
if view not in st.session_state.page_views:
    register_event(sid, "page_view", view, dedupe_key=f"page_view:{view}")
    st.session_state.page_views.add(view)

if view == "Simulador TDRS":
    render_tdrs(tdrs_controls)
elif view == "Control Web":
    render_control_web()
else:
    render_data_model()
