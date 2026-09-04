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
from services.analytics_service import (
    get_dashboard_metrics,
    get_destination_metrics,
    instrumentation_status,
)
from services.assistant_service import answer_question, get_initial_summary
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
    --tui-red-soft:rgba(212,14,20,.14);
    --tui-red-deep:#B80B10;
    --tui-dark:#0E2642;
    --tui-digital:#2E88B8;
    --tui-blue:#AEE8FF;
    --tui-blue-strong:#8FDFFF;
    --tui-blue50:#E8F8FF;
    --tui-blue25:#F4FBFF;
    --bg:#FBFEFF;
    --paper:#FFFFFF;
    --text:#1B2B3A;
    --muted:#6B8093;
    --border:#CFEFFF;
    --success:#19865E;
    --warning:#D68A00;
    --error:#C73535;
    --shadow:0 16px 40px rgba(13,35,64,.07);
}
html, body, [class*="css"] { font-family:'Inter', Arial, sans-serif; }
.stApp {
    color:var(--text);
    background-color:#FFFDFB;
    background-image:
      radial-gradient(circle at 92% 0%, rgba(174,232,255,.20), transparent 26%),
      radial-gradient(circle at 9% 7%, rgba(212,14,20,.035), transparent 18%),
      repeating-linear-gradient(0deg, rgba(212,14,20,.055) 0 1px, transparent 1px 28px),
      repeating-linear-gradient(90deg, rgba(212,14,20,.055) 0 1px, transparent 1px 28px);
    background-attachment:fixed;
}
/* Cuaderno antiguo: la cuadrícula vive en el fondo y nunca tapa Streamlit. */
[data-testid="stAppViewContainer"] > .main .block-container {
    background:rgba(255,255,255,.965);
    border:1px solid rgba(212,14,20,.16);
    border-radius:24px;
    box-shadow:
      0 18px 42px rgba(13,35,64,.055),
      inset 0 0 0 7px rgba(174,232,255,.045);
    padding-left:1.8rem;
    padding-right:1.8rem;
}
[data-testid="stHeader"] { background:rgba(255,255,255,.72); backdrop-filter:blur(12px); }
.block-container { padding-top:1.15rem; padding-bottom:4rem; max-width:1580px; }
h1,h2,h3,h4 { color:var(--tui-dark); letter-spacing:-.03em; }
h1 { font-size:2.05rem !important; font-weight:900 !important; }
h2 { font-size:1.3rem !important; font-weight:900 !important; }
h3 { font-size:1.03rem !important; font-weight:850 !important; }
p,label,span,div { text-rendering:optimizeLegibility; }

/* SIDEBAR: distribución de referencia */
[data-testid="stSidebar"] {
    background:
      linear-gradient(180deg,rgba(255,255,255,.94) 0%,rgba(247,252,255,.97) 100%);
    border-right:1px solid #E4F4FC;
    box-shadow:10px 0 28px rgba(13,35,64,.035);
}
[data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
[data-testid="stSidebar"] .block-container { padding-top:.8rem; }
.tui-brand { display:flex; gap:.78rem; align-items:center; padding:.15rem .05rem .9rem .05rem; animation:fadeSlide .45s ease both; }
.tui-logo-wrap { display:flex; align-items:center; justify-content:center; padding:.42rem .5rem; border-radius:20px; background:rgba(255,255,255,.88); border:1px solid var(--border); box-shadow:0 10px 22px rgba(13,35,64,.05); }
.tui-logo-img { width:130px; height:auto; display:block; }
.tui-brand-title { font-size:.98rem; color:var(--tui-dark); font-weight:900; line-height:1.05; }
.tui-brand-sub { color:var(--muted); font-size:.68rem; font-weight:750; margin-top:.17rem; }
.sidebar-status { border:1px solid var(--border); border-radius:16px; padding:.72rem .8rem; margin:.15rem 0 .85rem 0; background:rgba(255,255,255,.9); box-shadow:0 8px 22px rgba(13,35,64,.045); }
.sidebar-status-row { display:flex; align-items:center; gap:.45rem; color:var(--tui-dark); font-size:.79rem; font-weight:850; }
.status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.dot-ok{background:var(--success);box-shadow:0 0 0 4px rgba(25,134,94,.09)} .dot-warning{background:var(--warning)} .dot-critical{background:var(--error)}
.sidebar-time { color:var(--muted); font-size:.68rem; margin-top:.32rem; }
.sidebar-filter-intro { margin:.65rem 0 .35rem; border-radius:16px; padding:.7rem .76rem; background:linear-gradient(120deg,#EFFBFF,#FFFFFF); color:var(--tui-dark); border:1px solid var(--border); box-shadow:0 10px 24px rgba(13,35,64,.06); }
.sidebar-filter-intro strong{color:var(--tui-dark);font-size:.78rem}.sidebar-filter-intro span{display:block;color:#597488;font-size:.65rem;line-height:1.35;margin-top:.18rem}

/* radio Vista / Escenario */
[data-testid="stSidebar"] div[data-testid="stRadio"] > label { color:var(--tui-dark)!important; font-weight:900; font-size:.78rem; margin-bottom:.2rem; }
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] { gap:.04rem; }
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label {
    padding:.26rem .25rem; border-radius:10px; transition:.18s ease; font-weight:700;
}
[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:hover { background:rgba(174,232,255,.16); }

/* expanders de filtros */
[data-testid="stSidebar"] [data-testid="stExpander"] { background:rgba(255,255,255,.9); border:1px solid #E2F1F8; border-radius:16px; box-shadow:0 7px 20px rgba(13,35,64,.035); margin:.42rem 0; overflow:hidden; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color:var(--tui-dark); font-weight:850; }
[data-testid="stSidebar"] [data-testid="stSlider"] { margin-bottom:.35rem; }
[data-testid="stSidebar"] [data-testid="stSlider"] label, [data-testid="stSidebar"] [data-testid="stSelectbox"] label { color:#33465A!important; font-weight:750; font-size:.80rem; }

/* HERO premium con movimiento sutil */
.hero { position:relative; overflow:hidden; padding:1.5rem 1.65rem; border-radius:24px; margin-bottom:1rem; background:linear-gradient(120deg,#0E2642 0%,#2E88B8 58%,#AEE8FF 118%); color:#fff; box-shadow:0 18px 42px rgba(13,35,64,.12); animation:fadeUp .42s ease both; border:1px solid rgba(174,232,255,.32); }
.hero:before { content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-88px; top:-115px; border:30px solid rgba(255,255,255,.09); animation:floatOrb 8s ease-in-out infinite; }
.hero:after { content:""; position:absolute; width:180px; height:180px; border-radius:50%; left:-95px; bottom:-110px; background:radial-gradient(circle,rgba(212,14,20,.36),rgba(212,14,20,.04) 65%,transparent 70%); }
.hero h1 { color:#fff !important; margin:0 0 .3rem 0; position:relative; z-index:2; }
.hero p { margin:0; color:#F1FBFF; font-size:.93rem; max-width:900px; position:relative; z-index:2; }
.hero-kicker { text-transform:uppercase; letter-spacing:.11em; font-weight:900; font-size:.66rem; color:var(--tui-blue50); margin-bottom:.42rem; position:relative; z-index:2; }
.hero-status { display:inline-flex; align-items:center; gap:.45rem; background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.19); border-radius:999px; padding:.33rem .65rem; font-size:.72rem; font-weight:850; margin-top:.85rem; position:relative; z-index:2; }

.section-card,[data-testid="stMetric"],[data-testid="stDataFrame"] { background:rgba(255,255,255,.95); border:1px solid var(--border); box-shadow:var(--shadow); }
.section-card { border-radius:20px; padding:1rem 1.05rem; animation:fadeUp .48s ease both; }
.section-title { color:var(--tui-dark); font-weight:900; font-size:.95rem; margin-bottom:.15rem; }
.section-sub { color:var(--muted); font-size:.76rem; margin-bottom:.8rem; }
[data-testid="stMetric"] { padding:.66rem .82rem; border-radius:16px; min-height:82px; transition:transform .2s ease, box-shadow .2s ease, border-color .2s ease; }
[data-testid="stMetric"]:hover { transform:translateY(-2px); box-shadow:0 18px 36px rgba(13,35,64,.09); border-color:#B9E7FA; }
[data-testid="stMetricLabel"] { color:var(--muted); font-size:.66rem; text-transform:uppercase; letter-spacing:.045em; font-weight:900; }
[data-testid="stMetricValue"] { color:var(--tui-dark); font-weight:900; font-size:1.58rem; line-height:1.0; }

.alert-card { border-radius:14px; padding:.82rem .9rem; margin-bottom:.58rem; border:1px solid #E5F0F7; background:#fff; }
.alert-critical { border-left:4px solid var(--error); background:#FFF8F8; }.alert-warning { border-left:4px solid var(--warning); background:#FFFBF3; }.alert-info { border-left:4px solid var(--tui-digital); background:#F5FAFE; }.alert-ok { border-left:4px solid var(--success); background:#F5FBF8; }
.alert-head { display:flex; justify-content:space-between; gap:.7rem; align-items:flex-start; }.alert-title { font-weight:900; color:var(--text); font-size:.84rem; }.alert-badge { font-size:.61rem; font-weight:900; letter-spacing:.06em; border-radius:999px; padding:.18rem .45rem; white-space:nowrap; }
.badge-critical{background:#FBE1E1;color:#9C2020}.badge-warning{background:#FFF0CC;color:#8D5D00}.badge-info{background:#DFF4FE;color:#155D89}.badge-ok{background:#DDF3E9;color:#116947}.alert-message { color:var(--muted); font-size:.76rem; line-height:1.45; margin-top:.28rem; }.alert-action { color:var(--tui-digital); font-size:.71rem; font-weight:800; margin-top:.35rem; }

[data-testid="stChatMessage"] { background:rgba(255,255,255,.9); border:1px solid rgba(174,232,255,.4); border-radius:15px; padding:.25rem .35rem; }
[data-testid="stChatInput"] { border-color:var(--border); }
div.stButton > button { border-radius:999px; border:1px solid #DDF0F8; background:#fff; color:var(--tui-dark); font-weight:850; transition:.18s ease; }
div.stButton > button:hover { border-color:var(--tui-blue-strong); background:var(--tui-blue25); color:var(--tui-dark); transform:translateY(-1px); }
div.stButton > button[kind="primary"] { background:linear-gradient(90deg,var(--tui-red),var(--tui-red-deep)); color:#fff; border-color:var(--tui-red); box-shadow:0 9px 20px rgba(212,14,20,.14); }
[data-baseweb="select"] > div,[data-baseweb="input"] > div,[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input,textarea { background:#fff!important; color:var(--text)!important; border-color:#D8EFF9!important; border-radius:12px!important; }
[data-baseweb="tab-list"] { gap:.25rem; } [data-baseweb="tab"] { border-radius:999px; padding:.4rem .85rem; }
[data-testid="stDataFrame"] { border-radius:16px; overflow:hidden; animation:fadeUp .45s ease both; }
.small-note,.system-strip { color:var(--muted); font-size:.74rem; line-height:1.45; }.system-strip{display:flex;align-items:center;gap:.5rem;margin:.2rem 0 .9rem}.status-chip{display:inline-flex;border-radius:999px;padding:.22rem .55rem;font-size:.68rem;font-weight:900}.chip-ok{background:#DDF3E9;color:#116947}.chip-warning{background:#FFF0CC;color:#8D5D00}.chip-critical{background:#FBE1E1;color:#9C2020}

.page-heading{margin:.25rem 0 1rem 0;animation:fadeUp .35s ease both}.page-heading h1{margin:0!important;color:var(--tui-dark)!important;font-size:1.9rem!important}.page-heading p{margin:.28rem 0 0 0;color:var(--muted);font-size:.88rem;max-width:920px}.page-heading .kicker{font-size:.70rem;font-weight:900;letter-spacing:.11em;text-transform:uppercase;color:var(--tui-digital);margin-bottom:.26rem}
hr { border-color:#E6F3F9!important; }

@keyframes fadeUp { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeSlide { from{opacity:0;transform:translateX(-6px)} to{opacity:1;transform:translateX(0)} }
@keyframes floatOrb { 0%,100%{transform:translateY(0) rotate(0deg)} 50%{transform:translateY(10px) rotate(8deg)} }
@media(max-width:800px){.block-container{padding-left:1rem;padding-right:1rem}.hero{padding:1.15rem}.hero h1{font-size:1.5rem!important}.tui-logo-img{width:104px}}

/* Ranking premium: podium superior */
.podium-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem;margin:.65rem 0 1.15rem}
.podium-card{position:relative;overflow:hidden;border-radius:22px;padding:1.05rem 1.1rem;background:linear-gradient(145deg,#fff,#F5FBFF);border:1px solid var(--border);box-shadow:0 16px 34px rgba(13,35,64,.07);min-height:150px;transition:.18s ease}
.podium-card:hover{transform:translateY(-3px);box-shadow:0 20px 42px rgba(13,35,64,.10)}
.podium-card.first{border:1px solid rgba(212,14,20,.28);box-shadow:0 18px 40px rgba(212,14,20,.08)}
.podium-rank{font-size:.72rem;font-weight:900;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.podium-name{font-size:1.35rem;font-weight:900;color:var(--tui-dark);margin:.22rem 0}.podium-score{font-size:2rem;font-weight:900;color:var(--tui-red);line-height:1}.podium-meta{margin-top:.6rem;font-size:.74rem;color:var(--muted);line-height:1.45}
.alerts-top{margin:.2rem 0 .75rem}.alerts-top-title{font-size:.78rem;text-transform:uppercase;letter-spacing:.08em;font-weight:900;color:var(--tui-dark);margin-bottom:.35rem}
@media(max-width:900px){.podium-grid{grid-template-columns:1fr}}

.scenario-card{margin:.28rem 0 .65rem;padding:.68rem .72rem;border-radius:14px;background:linear-gradient(120deg,#F7FCFF,#FFFFFF);border:1px solid var(--border);box-shadow:0 8px 18px rgba(13,35,64,.04)}
.scenario-title{font-size:.80rem;font-weight:900;color:var(--tui-dark)}.scenario-desc{font-size:.66rem;color:var(--muted);line-height:1.35;margin-top:.16rem}
.chat-main{margin:.35rem 0 .75rem}.chat-main-title{font-size:.96rem;font-weight:900;color:var(--tui-dark);margin-bottom:.15rem}.chat-main-sub{font-size:.74rem;color:var(--muted);margin-bottom:.45rem}
.map-note{font-size:.70rem;color:var(--muted);margin:.25rem 0 .6rem}.map-kpi{font-weight:900;color:var(--tui-dark)}

</style>
"""
st.markdown(CSS, unsafe_allow_html=True)



ASSETS_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSETS_DIR / "tui_logo.png"


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


def page_heading(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="page-heading"><div class="kicker">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


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


def render_assistant_payload(payload: dict) -> None:
    """Renderiza respuestas sin introducir tarjetas KPI dentro del chat."""
    st.markdown(payload.get("text", ""))
    metrics = payload.get("metrics")
    if metrics:
        summary = " · ".join(f"**{label}:** {value}" for label, value in metrics.items())
        st.markdown(summary)
    alerts = payload.get("alerts")
    if alerts:
        for item in alerts[:6]:
            st.markdown(f"- **{item.get('level', 'INFO')} · {item.get('title', 'Alerta')}** — {item.get('message', '')}")
    table = payload.get("table")
    if table:
        df = pd.DataFrame(table)
        preferred = [c for c in [
            "Estado", "Dataset", "Intervalo objetivo", "Última actualización", "Próxima esperada", "Filas actuales",
            "Modelo del dataset", "Tabla / dataset", "Filas", "Función", "source_name", "started_at", "status",
            "rows_before", "rows_after", "duration_seconds", "trigger", "error_message", "KPI", "estado", "necesita"
        ] if c in df.columns]
        if preferred:
            df = df[preferred]
        st.dataframe(df.head(15), use_container_width=True, hide_index=True)

def render_home() -> None:
    system = get_system_status()
    alerts = get_alerts()

    st.markdown('<div class="alerts-top"><div class="alerts-top-title">Alertas y estado</div></div>', unsafe_allow_html=True)
    if alerts:
        alert_cols = st.columns(min(3, len(alerts)))
        for idx, item in enumerate(alerts[:3]):
            with alert_cols[idx]:
                render_alert(item)
    else:
        render_alert({"level": "OK", "title": "Sistema sin alertas operativas", "message": "Las fuentes activas están dentro de los controles disponibles y SQLite responde correctamente."})

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = [
            {"role": "assistant", "payload": {"text": get_initial_summary()}}
        ]
    pending = st.session_state.pop("assistant_pending_prompt", None)
    if pending:
        st.session_state.chat_messages.append({"role": "user", "content": pending})
        st.session_state.chat_messages.append({"role": "assistant", "payload": answer_question(pending)})

    st.markdown('<div class="chat-main"><div class="chat-main-title">Asistente operativo</div><div class="chat-main-sub">Pregunta por actualizaciones, fuentes, SQLite, tracking o rendimiento web.</div></div>', unsafe_allow_html=True)
    with st.container(border=True):
        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    render_assistant_payload(message.get("payload", {"text": message.get("content", "")}))
                else:
                    st.markdown(message.get("content", ""))
        prompt = st.chat_input("Pregunta sobre tus datos…", key="assistant_chat_input")

    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        st.session_state.chat_messages.append({"role": "assistant", "payload": answer_question(prompt)})
        register_event(st.session_state.session_id, "assistant_query", "Inicio · Asistente", metadata={"prompt": prompt[:300]})
        st.rerun()

    # Los KPIs quedan fuera del chat y debajo de la conversación.
    st.markdown("### Estado operativo")
    last_run = system.get("last_run") or {}
    render_metric_rows([
        ("Fuentes activas", system["active_sources"]),
        ("Fuentes al día", system["healthy_sources"]),
        ("Alertas abiertas", system["open_alerts"]),
        ("Último scraping", fmt_ts(last_run.get("started_at"))[-8:] if last_run else "Sin ejecutar"),
        ("Filas totales", f"{system['total_rows']:,}"),
        ("Estado DB", "OK" if system["database_integrity"] == "ok" else "Revisar"),
    ], columns=3)
    st.markdown('<div class="system-strip">Consulta operativa basada en SQLite, fuentes registradas y ejecuciones persistidas. No se generan estados ficticios.</div>', unsafe_allow_html=True)

def render_tdrs_sidebar_controls() -> dict:
    st.sidebar.markdown(
        '<div class="sidebar-filter-intro"><strong>Simulador TDRS · CSV v3.1</strong><span>Clima anual, popularidad, capacidad sanitaria y seguridad; faltantes estimados con KNN y marcados en el ranking.</span></div>',
        unsafe_allow_html=True,
    )

    labels = {
        name: f"{meta['icon']} {name} · {meta['description'].split('.')[0]}"
        for name, meta in SCENARIO_META.items()
    }
    options = list(SCENARIO_META)
    selected_label = st.sidebar.radio(
        "Escenario",
        options,
        index=1,
        key="tdrs_scenario_sidebar",
        format_func=lambda name: labels[name],
    )
    scenario = selected_label
    meta = SCENARIO_META[scenario]
    st.sidebar.markdown(
        f'<div class="scenario-card"><div class="scenario-title">{meta["icon"]} {escape(scenario)}</div><div class="scenario-desc">{escape(meta["description"])}</div></div>',
        unsafe_allow_html=True,
    )
    defaults = PRESETS[scenario]

    with st.sidebar.expander("Filtros / pesos del modelo", expanded=True):
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
        st.caption("La duración solo filtra cuando existe en el catálogo. Un valor ausente no excluye el destino.")

    return {
        "scenario": scenario,
        "weights": weights,
        "max_price": max_price,
        "max_stay_days": max_stay_days,
    }

def render_tdrs(controls: dict) -> None:
    scenario = controls["scenario"]
    weights = controls["weights"]
    meta = SCENARIO_META[scenario]

    st.markdown(
        f'<div class="section-card"><div class="section-title">{meta["icon"]} Escenario activo · {escape(scenario)} · TDRS CSV v3.1</div>'
        '<div class="section-sub">El score combina cinco señales de los CSV. Los faltantes se estiman con KNN k=3 únicamente para el scoring y se marcan como imputados; los datos originales de SQLite no se sobrescriben.</div></div>',
        unsafe_allow_html=True,
    )

    res = compute_scores(
        weights,
        max_price=controls["max_price"],
        max_stay_days=controls["max_stay_days"],
    )
    metrics = scenario_metrics(res["ranked"])
    if metrics:
        def fmt(v, suffix="", decimals=1):
            return "—" if v is None else f"{v:.{decimals}f}{suffix}"

        visitors = metrics.get("avg_top5_annual_passengers")
        visitors_text = "—" if visitors is None else (f"{visitors/1_000_000:.1f} M/año" if visitors >= 1_000_000 else f"{visitors/1_000:.0f} k/año")
        # KPIs compactos: dos filas de tres, pero con altura reducida por CSS.
        render_metric_rows([
            ("Elegibles", metrics["eligible"]),
            ("Cobertura original", fmt((metrics["avg_data_coverage"] or 0) * 100, "%", 0)),
            ("Días soleados Top 5", fmt(metrics.get("avg_top5_sunny_days_pct"), "%", 0)),
            ("Visitantes Top 5", visitors_text),
            ("Camas Top 5", fmt(metrics.get("avg_top5_hospital_beds"), "/1000", 2)),
            ("Homicidios Top 5", fmt(metrics.get("avg_top5_homicide_rate"), "/100k", 2)),
        ], columns=3)
        st.caption("Cobertura = datos originales disponibles antes de KNN. Las estimaciones KNN se usan solo para comparar destinos y quedan identificadas.")

    rank_rows = []
    for pos, r in enumerate(res["ranked"], 1):
        model = r.get("model_values") or {}
        imputed = r.get("knn_imputed_fields") or []
        rank_rows.append({
            "Posición": pos,
            "Destino": r["name"],
            "Score": round(r["score"], 3),
            "Cobertura": f"{r.get('data_coverage', 0):.0%}",
            "Días soleados %": model.get("sunny_days_pct"),
            "Precipitación %": model.get("precipitation_days_pct"),
            "Pasajeros/año": model.get("annual_passengers"),
            "Camas/1000": model.get("hospital_beds"),
            "Homicidios/100k": model.get("homicide_rate"),
            "Precio €": r.get("reference_price_eur"),
            "Días hospedados": r.get("catalog_stay_days"),
            "KNN": ", ".join(imputed) if imputed else "—",
        })

    st.markdown("### Top 3")
    podium = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, row in enumerate(rank_rows[:3]):
        visitors = row.get("Pasajeros/año")
        visitors_text = "—" if visitors is None else f"{int(round(visitors)):,} pasajeros/año"
        price_text = "—" if row.get("Precio €") is None else f"{float(row['Precio €']):,.0f} €"
        imputed_text = "sin KNN" if row.get("KNN") == "—" else "KNN aplicado"
        podium.append(
            f'<div class="podium-card {"first" if idx == 0 else ""}">'
            f'<div class="podium-rank">{medals[idx]} posición {idx+1}</div>'
            f'<div class="podium-name">{escape(str(row["Destino"]))}</div>'
            f'<div class="podium-score">{row["Score"]:.3f}</div>'
            f'<div class="podium-meta">Cobertura original {row["Cobertura"]} · {escape(visitors_text)}<br>Precio ref. {escape(price_text)} · {escape(imputed_text)}</div>'
            '</div>'
        )
    if podium:
        st.markdown('<div class="podium-grid">' + ''.join(podium) + '</div>', unsafe_allow_html=True)

    st.markdown("### Resto del ranking")
    remaining_rows = rank_rows[3:] if len(rank_rows) > 3 else rank_rows
    if remaining_rows:
        display = pd.DataFrame(remaining_rows)
        # Formato explícito para que la ausencia se vea como guion, no como None/NaN.
        for col in ["Días soleados %", "Precipitación %", "Pasajeros/año", "Camas/1000", "Homicidios/100k", "Precio €", "Días hospedados"]:
            display[col] = display[col].map(lambda v: "—" if pd.isna(v) else (f"{v:,.0f}" if col in {"Pasajeros/año", "Precio €", "Días hospedados"} else f"{v:.2f}"))
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
    if not active:
        st.caption("Todavía no hay interacción comercial con destino. El mapa muestra los destinos geolocalizados con intensidad 0; no se inventan clics, reservas ni ingresos.")


def render_control_web() -> None:
    page_heading(
        "Digital performance",
        "Control Web",
        "Seguimiento de sesiones, interacción y rendimiento comercial calculado con el tracking disponible.",
    )
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
        metric = st.radio("Visualizar por", ["Clics", "Reservas", "Ingresos"], horizontal=True, key="geo_metric")
        geo_rows = get_geospatial_metrics()
        render_geospatial_map(geo_rows, metric)
        st.markdown('<div class="map-note">La intensidad procede de <span class="map-kpi">events + bookings</span>. Las coordenadas se leen del fichero local de referencia y no se generan desde el tracking.</div>', unsafe_allow_html=True)
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
    page_heading(
        "Data operations",
        "Datos / modelo",
        "Centro técnico para controlar bases, fuentes, scraping, cadencias, modelos, histórico de ejecuciones y errores.",
    )

    # Alertas de datos al inicio de la página, antes de los KPIs.
    st.markdown("### Alertas de datos")
    if alerts:
        alert_cols = st.columns(min(3, len(alerts)))
        for idx, item in enumerate(alerts[:3]):
            with alert_cols[idx]:
                render_alert(item)
    else:
        render_alert({"level": "OK", "title": "Sin alertas", "message": "No se detectan incidencias con las reglas operativas actuales."})

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
      <div><div class="tui-brand-title">Data Intelligence</div><div class="tui-brand-sub">Madrid Luxury UI · Operations</div></div>
    </div>
    """,
    unsafe_allow_html=True,
)

NAV = ["Inicio · Asistente", "Simulador TDRS", "Control Web", "Datos / modelo"]
view = st.sidebar.radio("Vista", NAV, index=0, key="sidebar_view")

tdrs_controls = None
if view == "Simulador TDRS":
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
st.sidebar.caption("TUI Data Intelligence · entorno académico/operativo")

sid = st.session_state.session_id
if view not in st.session_state.page_views:
    register_event(sid, "page_view", view, dedupe_key=f"page_view:{view}")
    st.session_state.page_views.add(view)

if view == "Inicio · Asistente":
    render_home()
elif view == "Simulador TDRS":
    render_tdrs(tdrs_controls)
elif view == "Control Web":
    render_control_web()
else:
    render_data_model()
