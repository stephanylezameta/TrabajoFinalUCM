from __future__ import annotations

"""Hoja de estilos de la aplicación.

Todo el CSS vive aquí en lugar de estar embebido en ``streamlit_app.py``. El
tema de ``.streamlit/config.toml`` solo gobierna de facto el color primario de
los widgets: el resto lo define esta hoja.

La tipografía de marca es **Gotham**. Streamlit no sirve fuentes locales por
ruta (``url(assets/...)`` no resuelve desde el CSS inyectado), así que los .otf
se embeben en base64 dentro de bloques ``@font-face``. Si algún .otf falta o no
se puede leer, se degrada limpiamente al fallback (Poppins/Arial) sin romper.
"""

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

# Directorio de fuentes: dashboard/assets/fonts (relativo a este módulo).
_FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"

# Mapa fichero .otf -> peso CSS. Book=400, Medium=500, Bold=700, Black=900.
_GOTHAM_FACES = (
    ("Gotham-Book.otf", 400),
    ("Gotham-Medium.otf", 500),
    ("Gotham-Bold.otf", 700),
    ("Gotham-Black.otf", 900),
)


@lru_cache(maxsize=1)
def _gotham_font_faces() -> str:
    """Construye los ``@font-face`` de Gotham embebidos en base64.

    Lee los .otf una sola vez (cacheado) y los codifica a data URI. Cualquier
    fichero ausente o ilegible se omite sin romper: el CSS seguirá teniendo un
    fallback tipográfico válido.
    """
    faces: list[str] = []
    for filename, weight in _GOTHAM_FACES:
        path = _FONTS_DIR / filename
        try:
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        except (OSError, ValueError):
            # Fuente no disponible: se degrada al fallback silenciosamente.
            continue
        faces.append(
            "@font-face{"
            "font-family:'Gotham';"
            f"src:url(data:font/otf;base64,{encoded}) format('opentype');"
            f"font-weight:{weight};font-style:normal;font-display:swap;"
            "}"
        )
    return "".join(faces)


CSS = "<style>" + _gotham_font_faces() + """
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
html, body, [class*="css"] { font-family:'Gotham','Poppins', Arial, sans-serif; }
/* Gotham en todo MENOS los iconos: los Material Symbols de Streamlit necesitan
   su propia fuente; forzarles Gotham hacía que se viera el texto del icono
   (p. ej. "keyboard_arrow_down") en vez del símbolo. */
.stApp, .stApp *:not([class*="material"]):not([data-testid="stIconMaterial"]):not(.material-icons):not(.material-symbols-outlined) {
    font-family:'Gotham','Poppins', Arial, sans-serif;
}
/* Restaura la fuente de iconos de Streamlit explícitamente. */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-outlined,
span[class*="material-symbols"], span[class*="material-icons"] {
    font-family:'Material Symbols Outlined','Material Symbols Rounded','Material Icons' !important;
}
.stApp {
    color:var(--text);
    background-color:#FFFFFF;
    background-image:none;
}
/* Fondo principal blanco, limpio. */
[data-testid="stAppViewContainer"] > .main .block-container {
    position:relative;
    background:#FFFFFF;
    border:none;
    border-radius:0;
    box-shadow:none;
    padding-left:1.8rem;
    padding-right:1.8rem;
    z-index:1;
}

[data-testid="stAppViewContainer"] > .main .block-container > * { position:relative; z-index:1; }
[data-testid="stHeader"] { background:rgba(236,244,250,.82); backdrop-filter:blur(12px); }
.block-container { padding-top:1.15rem; padding-bottom:4rem; max-width:1580px; }
h1,h2,h3,h4 { color:var(--tui-dark); letter-spacing:-.03em; }
h1 { font-size:2.05rem !important; font-weight:900 !important; }
h2 { font-size:1.3rem !important; font-weight:900 !important; }
h3 { font-size:1.03rem !important; font-weight:900 !important; }
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
.sidebar-status-row { display:flex; align-items:center; gap:.45rem; color:var(--tui-dark); font-size:.79rem; font-weight:900; }
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
[data-testid="stSidebar"] [data-testid="stExpander"] summary { color:var(--tui-dark); font-weight:900; }
[data-testid="stSidebar"] [data-testid="stSlider"] { margin-bottom:.35rem; }
[data-testid="stSidebar"] [data-testid="stSlider"] label, [data-testid="stSidebar"] [data-testid="stSelectbox"] label { color:#334155!important; font-weight:750; font-size:.80rem; }

/* HERO y contenedores principales */
.hero { position:relative; overflow:hidden; padding:1.5rem 1.65rem; border-radius:24px; margin-bottom:1rem; background:linear-gradient(180deg,rgba(255,255,255,.96) 0%,rgba(247,247,248,.95) 100%); color:var(--tui-dark); box-shadow:var(--shadow); animation:fadeUp .42s ease both; border:1px solid rgba(17,24,39,.10); }
.hero:before { content:""; position:absolute; width:260px; height:260px; border-radius:50%; right:-88px; top:-115px; border:24px solid rgba(17,24,39,.04); animation:floatOrb 8s ease-in-out infinite; }
.hero:after { content:""; position:absolute; width:180px; height:180px; border-radius:50%; left:-95px; bottom:-110px; background:radial-gradient(circle,rgba(17,24,39,.08),rgba(17,24,39,.01) 65%,transparent 70%); }
.hero h1 { color:var(--tui-dark) !important; margin:0 0 .3rem 0; position:relative; z-index:2; }
.hero p { margin:0; color:#475467; font-size:.93rem; max-width:900px; position:relative; z-index:2; }
.hero-kicker { text-transform:uppercase; letter-spacing:.11em; font-weight:900; font-size:.66rem; color:#6B7280; margin-bottom:.42rem; position:relative; z-index:2; }
.hero-status { display:inline-flex; align-items:center; gap:.45rem; background:rgba(17,24,39,.05); border:1px solid rgba(17,24,39,.08); border-radius:999px; padding:.33rem .65rem; font-size:.72rem; font-weight:900; margin-top:.85rem; position:relative; z-index:2; color:var(--tui-dark); }

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
.badge-critical{background:#FBE1E1;color:#9C2020}.badge-warning{background:#FFF0CC;color:#8D5D00}.badge-info{background:#EAECF0;color:#344054}.badge-ok{background:#DDF3E9;color:#116947}.alert-message { color:var(--muted); font-size:.76rem; line-height:1.45; margin-top:.28rem; }.alert-action { color:#344054; font-size:.71rem; font-weight:700; margin-top:.35rem; }

[data-testid="stChatMessage"] { background:linear-gradient(180deg,rgba(255,255,255,.78),rgba(246,250,253,.74)); border:1px solid rgba(17,24,39,.10); border-radius:15px; padding:.25rem .35rem; backdrop-filter:blur(3px); }
[data-testid="stChatInput"] { border-color:var(--border); }
div.stButton > button { min-height:3rem; padding:.58rem 1rem; border-radius:999px; border:1px solid rgba(17,24,39,.16); background:linear-gradient(180deg,#FFFFFF 0%,#F2F4F7 100%); color:var(--tui-dark); font-weight:900; transition:.18s ease; box-shadow:inset 0 1px 0 rgba(255,255,255,.92), 0 8px 18px rgba(17,24,39,.06); }
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

/* ==========================================================================
   Recomendador España (API). Diseño "portada de viaje": una recomendación
   principal inmersiva a pantalla completa y dos tarjetas editoriales debajo.
   Lenguaje visual único: rojo TUI de acento, oscuro TUI de texto, tipografía
   Poppins de peso alto, sombras en capas y radios generosos y consistentes.
   ========================================================================== */

/* --- Cabecera comercial del recomendador, tono editorial de viajes --- */
.reco-header{margin:.3rem 0 1.3rem;animation:fadeUp .4s ease both}
.reco-kicker{display:inline-flex;align-items:center;gap:.5rem;font-size:.66rem;font-weight:700;
  letter-spacing:.16em;text-transform:uppercase;color:var(--tui-red);margin-bottom:.55rem}
.reco-kicker:before{content:"";width:22px;height:2px;border-radius:2px;background:var(--tui-red)}
.reco-hero-title{font-size:2.55rem;font-weight:700;color:var(--tui-dark);line-height:1.06;letter-spacing:-.035em;
  margin:0 0 .55rem}
.reco-hero-title em{font-style:normal;color:var(--tui-red)}
.reco-hero-lead{font-size:1.05rem;color:var(--muted);line-height:1.55;font-weight:400;margin:0;max-width:620px}

/* --- Oferta destacada (opción 1): tarjeta comercial estilo TUI ---
   Banner de imagen a todo el ancho con el titular montado, y un panel claro
   debajo con el motivo, el contexto del viaje y los datos clave. */
.offer{position:relative;overflow:hidden;border-radius:24px;margin:.5rem 0 1.6rem;background:#fff;
  border:1px solid rgba(17,24,39,.07);
  box-shadow:0 4px 16px rgba(17,24,39,.05),0 34px 70px -28px rgba(17,24,39,.36);
  animation:fadeUp .55s cubic-bezier(.16,1,.3,1) both}
/* Banner: la imagen llena todo el ancho, sin franjas, esquinas superiores redondeadas. */
.offer-media{position:relative;width:100%;height:380px;background-size:cover;background-position:center 42%;
  border-radius:24px 24px 0 0;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.offer-media--empty{background:linear-gradient(135deg,#1B2432,#3A4657)}
.offer-media-veil{position:absolute;inset:0;z-index:1;pointer-events:none;
  background:linear-gradient(180deg,rgba(17,24,39,0) 40%,rgba(17,24,39,.34) 66%,rgba(17,24,39,.86) 100%)}
.offer-flag{position:absolute;top:1.2rem;left:1.2rem;z-index:2;display:inline-flex;align-items:center;gap:.4rem;
  font-size:.66rem;font-weight:700;letter-spacing:.04em;color:#fff;background:var(--tui-red);
  padding:.42rem .85rem;border-radius:999px;box-shadow:0 8px 20px rgba(212,14,20,.42)}
.offer-media-caption{position:relative;z-index:2;padding:1.7rem 1.9rem}
.offer-name{font-size:2.9rem;font-weight:700;line-height:1;letter-spacing:-.04em;margin:0;color:#fff;
  text-shadow:0 5px 30px rgba(0,0,0,.55)}
.offer-place{font-size:.92rem;color:rgba(255,255,255,.94);margin-top:.5rem;font-weight:500;
  display:flex;align-items:center;gap:.3rem;text-shadow:0 2px 14px rgba(0,0,0,.45)}
/* Panel claro */
.offer-body{padding:1.6rem 1.9rem 1.8rem;display:flex;flex-direction:column}
.offer-typology{align-self:flex-start;font-size:.62rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  border-radius:999px;padding:.26rem .68rem;background:var(--tui-red-soft);color:var(--tui-red-deep)}
.offer-why{font-size:1.14rem;line-height:1.5;color:var(--tui-dark);font-weight:500;margin:.9rem 0 0;max-width:760px}
.offer-chips{display:flex;flex-wrap:wrap;gap:.45rem;margin-top:1.1rem}
.offer-chip{font-size:.72rem;font-weight:600;border-radius:999px;padding:.34rem .78rem;
  background:#F1F4F8;color:#475467;border:1px solid rgba(17,24,39,.06)}
.offer-chip.warn{background:#FFF3D6;color:#8D5D00;border-color:rgba(141,93,0,.16)}
.offer-facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:.7rem;margin-top:1.4rem;
  padding-top:1.35rem;border-top:1px solid rgba(17,24,39,.08)}
.offer-fact{background:#F7F9FB;border:1px solid rgba(17,24,39,.05);border-radius:16px;padding:.85rem .6rem;text-align:center}
.offer-fact-value{font-size:1.55rem;font-weight:700;color:var(--tui-dark);line-height:1;letter-spacing:-.02em}
.offer-fact-label{font-size:.58rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--muted);margin-top:.35rem}

/* --- Tarjetas de alternativas: editorial, imagen banner + datos limpios --- */
.alt-title{font-size:1.2rem;font-weight:700;color:var(--tui-dark);letter-spacing:-.015em;
  margin:1.6rem 0 1rem;display:flex;align-items:center;gap:.6rem}
.alt-title:before{content:"";width:4px;height:22px;background:var(--tui-red);border-radius:3px}
/* Rejilla de alternativas: un único bloque CSS grid (no st.columns) para no
   romper el DOM de React con un número variable de columnas. */
.alt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1rem;align-items:stretch}
.reco-card{position:relative;overflow:hidden;border-radius:22px;background:#fff;padding:0;
  border:1px solid rgba(17,24,39,.07);
  box-shadow:0 4px 14px rgba(17,24,39,.04),0 16px 36px -16px rgba(17,24,39,.16);
  height:100%;transition:transform .3s cubic-bezier(.16,1,.3,1),box-shadow .3s ease;
  display:flex;flex-direction:column}
.reco-card:hover{transform:translateY(-7px);
  box-shadow:0 10px 22px rgba(17,24,39,.07),0 32px 56px -18px rgba(17,24,39,.26)}
/* Banner: imagen pegada a los bordes de la tarjeta, sin franja blanca.
   Ocupa todo el ancho y redondea las esquinas superiores igual que la tarjeta. */
.reco-photo-wrap{position:relative;width:100%;aspect-ratio:16/10;overflow:hidden;background:#EEF2F6;
  display:block;margin:0;line-height:0;border-radius:21px 21px 0 0}
.reco-photo{width:100%;height:100%;object-fit:cover;object-position:center center;display:block;
  margin:0;background:#EEF2F6;transition:transform .55s cubic-bezier(.16,1,.3,1)}
.reco-card:hover .reco-photo{transform:scale(1.08)}
.reco-photo-veil{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(17,24,39,0) 34%,rgba(17,24,39,.72) 100%)}
.reco-photo-fallback{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#243244,#3B4A5E);color:#fff;font-weight:700;font-size:1.3rem;letter-spacing:.02em}
.reco-rank-badge{position:absolute;top:.9rem;left:.9rem;z-index:2;font-size:.58rem;font-weight:700;
  letter-spacing:.08em;text-transform:uppercase;color:var(--tui-dark);background:rgba(255,255,255,.95);
  border-radius:999px;padding:.3rem .68rem;box-shadow:0 6px 16px rgba(17,24,39,.22);backdrop-filter:blur(4px)}
/* Nombre y lugar montados sobre la foto, estilo tarjeta de viaje. */
.reco-photo-caption{position:absolute;left:1.1rem;right:1.1rem;bottom:1rem;z-index:2;line-height:1.1}
.reco-name{font-size:1.5rem;font-weight:700;color:#fff;line-height:1.06;letter-spacing:-.025em;
  text-shadow:0 3px 18px rgba(0,0,0,.5)}
.reco-place{font-size:.76rem;color:rgba(255,255,255,.92);font-weight:500;margin-top:.28rem;
  display:inline-flex;align-items:center;gap:.28rem}
/* Cuerpo: todo visible, sin desplegables, para comparar de un vistazo. */
.reco-body{padding:1.2rem 1.3rem 1.35rem;display:flex;flex-direction:column;gap:.78rem;flex:1}
.reco-typology{align-self:flex-start;font-size:.6rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  border-radius:999px;padding:.24rem .62rem;background:var(--tui-red-soft);color:var(--tui-red-deep)}
.reco-headline{font-size:.86rem;color:#5B6472;line-height:1.5;font-weight:400;margin:0}
.reco-block-title{font-size:.6rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);
  margin:.15rem 0 .1rem}
.reco-list{margin:0;padding-left:1.05rem;font-size:.79rem;color:#5B6472;line-height:1.55}
.reco-list li{margin-bottom:.15rem}
.reco-chips{display:flex;flex-wrap:wrap;gap:.36rem}
.reco-chip{font-size:.64rem;font-weight:600;border-radius:999px;padding:.24rem .58rem;
  background:#F1F4F8;color:#475467;border:1px solid rgba(17,24,39,.06)}
.reco-chip.ok{background:#E4F5EC;color:#0F7A4D;border-color:rgba(15,122,77,.14)}
.reco-chip.warn{background:#FFF3D6;color:#8D5D00;border-color:rgba(141,93,0,.16)}
/* Barras del desglose del score, siempre visibles. */
.reco-bars{display:flex;flex-direction:column;gap:.1rem}
.reco-bar-row{display:flex;align-items:center;gap:.55rem;margin-bottom:.38rem}
.reco-bar-label{font-size:.68rem;color:#5B6472;min-width:120px;font-weight:500}
.reco-bar-track{flex:1;height:6px;border-radius:999px;background:#EEF1F5;overflow:hidden}
.reco-bar-fill{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--tui-red),#FF7A80)}
.reco-bar-value{font-size:.68rem;font-weight:700;color:var(--tui-dark);min-width:34px;text-align:right}
/* Rejilla de datos objetivos, tono producto. */
.reco-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:.55rem;margin-top:.1rem}
.reco-fact{background:#F7F9FB;border:1px solid rgba(17,24,39,.05);border-radius:14px;padding:.62rem .5rem;text-align:center}
.reco-fact-value{font-size:1.08rem;font-weight:700;color:var(--tui-dark);line-height:1}
.reco-fact-label{font-size:.55rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);margin-top:.3rem}

@media(max-width:900px){
  .reco-hero-title{font-size:1.85rem}
  .offer-media{height:260px}
  .offer-name{font-size:2rem}
  .offer-media-caption{padding:1.3rem}
  .offer-body{padding:1.3rem}
  .reco-facts{grid-template-columns:repeat(3,1fr)}
}

/* ==========================================================================
   Recomendador España — Asistente de viaje (MAQUETA del chat).
   Estética producto de viajes: burbujas con acento TUI, tarjetas de destino
   compactas embebidas en la respuesta del asistente. Reutiliza las variables
   de marca (rojo TUI, oscuro TUI, muted) y radios/sombras del resto de la app.
   ========================================================================== */

/* Aviso de vista previa (demo). Sutil, no intrusivo. */
.chatreco-preview-note{display:inline-flex;align-items:center;gap:.5rem;
  font-size:.7rem;font-weight:700;letter-spacing:.02em;color:var(--tui-red-deep);
  background:var(--tui-red-soft);border:1px solid rgba(212,14,20,.16);
  border-radius:999px;padding:.34rem .8rem;margin:.1rem 0 1rem}
/* Indicador rectangular (sin puntos circulares): una barrita de acento TUI. */
.chatreco-preview-mark{width:14px;height:4px;border-radius:2px;background:var(--tui-red)}

/* Sugerencias de arranque (chips no clicables dentro del HTML de la ventana). */
.chatreco-suggest-title{font-size:.74rem;font-weight:700;letter-spacing:.05em;
  text-transform:uppercase;color:var(--muted);margin:.15rem 0 .5rem}
.chatreco-suggest-chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-bottom:.6rem}
.chatreco-suggest-chip{font-size:.72rem;font-weight:500;color:var(--tui-dark);
  background:#fff;border:1px solid rgba(17,24,39,.14);border-radius:12px;padding:.4rem .7rem;
  box-shadow:0 2px 6px rgba(17,24,39,.05)}

/* Ventana de chat: un contenedor VISIBLE que enmarca la conversación como un
   módulo aparte del resto de la página (fondo muy sutil, borde y sombra). Así
   el chat «se nota» como una caja propia y no queda flotando sin marco. */
.chatreco-window{border:1px solid rgba(17,24,39,.12);border-radius:16px;
  background:linear-gradient(180deg,#FBFCFE 0%,#F4F7FA 100%);
  box-shadow:0 2px 8px rgba(17,24,39,.04),0 18px 40px -26px rgba(17,24,39,.30);
  padding:1rem 1.05rem 1.1rem}
.chatreco-window-head{display:flex;align-items:center;gap:.55rem;
  padding-bottom:.7rem;margin-bottom:.55rem;border-bottom:1px solid rgba(17,24,39,.08)}
.chatreco-window-dot{width:9px;height:9px;border-radius:3px;background:var(--tui-red);
  box-shadow:0 0 0 4px rgba(212,14,20,.10)}
.chatreco-window-title{font-size:.82rem;font-weight:700;color:var(--tui-dark);letter-spacing:-.01em}
.chatreco-window-sub{font-size:.68rem;color:var(--muted);margin-left:auto}

/* Filas de conversación con avatar CUADRADO (esquinas suaves, NUNCA círculos).
   El asistente a la izquierda, el usuario a la derecha. Margen amplio entre
   mensajes para que cada caja se lea separada de la anterior. */
.chatreco-row{display:flex;align-items:flex-start;gap:.6rem;margin:.85rem 0}
.chatreco-row--bot{justify-content:flex-start}
.chatreco-row--user{justify-content:flex-end}
.chatreco-avatar{flex:0 0 auto;width:34px;height:34px;border-radius:11px;
  display:flex;align-items:center;justify-content:center;
  font-size:.6rem;font-weight:700;letter-spacing:.02em;line-height:1;
  box-shadow:0 6px 16px -8px rgba(17,24,39,.4)}
.chatreco-avatar--bot{background:linear-gradient(180deg,var(--tui-red),var(--tui-red-deep));
  color:#fff}
.chatreco-avatar--user{background:#EEF1F5;color:var(--tui-dark);
  border:1px solid rgba(17,24,39,.10)}
/* La burbuja no debe estirarse a todo el ancho: se ajusta a su contenido. */
.chatreco-row .chatreco-bubble{max-width:min(680px,88%)}

/* Burbujas de chat como CAJAS bien definidas: borde visible, sombra clara y
   esquinas redondeadas PARCIALES (14px, nunca píldora total). Asistente a la
   izquierda (fondo blanco, acento TUI), usuario a la derecha (rojo TUI). */
.chatreco-bubble{display:inline-block;max-width:100%;padding:.82rem 1.05rem;
  font-size:.92rem;line-height:1.55;border-radius:14px;
  border:1px solid rgba(17,24,39,.12);
  box-shadow:0 2px 6px rgba(17,24,39,.05),0 12px 26px -16px rgba(17,24,39,.32);
  animation:fadeUp .3s ease both}
.chatreco-bubble--bot{background:#fff;color:var(--tui-dark);
  border-color:rgba(17,24,39,.12);border-top-left-radius:6px}
.chatreco-bubble--user{background:linear-gradient(180deg,var(--tui-red),var(--tui-red-deep));
  color:#fff;border-color:rgba(184,11,16,.55);border-top-right-radius:6px;
  box-shadow:0 3px 8px rgba(212,14,20,.16),0 12px 26px -14px rgba(212,14,20,.5)}

/* Rejilla de tarjetas EMBEBIDAS en la respuesta del asistente. Un único bloque
   CSS grid (no st.columns) para no romper el DOM de React. Sangrada a la altura
   de la burbuja para leerse como parte de la respuesta. */
.chatreco-cards-grid{margin:.55rem 0 .3rem;padding-left:2.6rem;
  display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.6rem}

/* Tarjeta de destino compacta embebida en el chat: CAJA definida con borde
   visible, sombra y esquinas parciales (16px). */
.chatreco-card{position:relative;overflow:hidden;border-radius:16px;background:#fff;
  border:1px solid rgba(17,24,39,.12);
  box-shadow:0 2px 8px rgba(17,24,39,.05),0 18px 38px -22px rgba(17,24,39,.32);
  display:flex;flex-direction:column;height:100%;
  transition:transform .3s cubic-bezier(.16,1,.3,1),box-shadow .3s ease;
  animation:fadeUp .38s ease both}
.chatreco-card:hover{transform:translateY(-4px);
  box-shadow:0 10px 22px rgba(17,24,39,.08),0 26px 48px -18px rgba(17,24,39,.32)}
/* Banner: imagen a todo el ancho, pegada a los bordes, esquinas superiores. */
.chatreco-media-wrap{position:relative;width:100%;aspect-ratio:16/10;overflow:hidden;
  background:#EEF2F6;border-radius:15px 15px 0 0;line-height:0}
.chatreco-media{width:100%;height:100%;object-fit:cover;object-position:center;display:block;
  transition:transform .55s cubic-bezier(.16,1,.3,1)}
.chatreco-card:hover .chatreco-media{transform:scale(1.07)}
.chatreco-media-fallback{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
  background:linear-gradient(135deg,#243244,#3B4A5E);color:#fff;font-weight:700;font-size:1.1rem}
.chatreco-media-veil{position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(180deg,rgba(17,24,39,0) 38%,rgba(17,24,39,.72) 100%)}
.chatreco-media-caption{position:absolute;left:.85rem;right:.85rem;bottom:.7rem;z-index:2;line-height:1.1}
.chatreco-name{font-size:1.15rem;font-weight:700;color:#fff;line-height:1.08;letter-spacing:-.02em;
  text-shadow:0 3px 16px rgba(0,0,0,.5)}
.chatreco-place{font-size:.68rem;color:rgba(255,255,255,.92);font-weight:500;margin-top:.2rem;
  display:inline-flex;align-items:center;gap:.24rem;text-shadow:0 2px 12px rgba(0,0,0,.45)}
.chatreco-body{padding:.85rem .95rem 1rem;display:flex;flex-direction:column;gap:.55rem;flex:1}
.chatreco-typology{align-self:flex-start;font-size:.56rem;font-weight:700;letter-spacing:.05em;
  text-transform:uppercase;border-radius:999px;padding:.22rem .56rem;
  background:var(--tui-red-soft);color:var(--tui-red-deep)}
.chatreco-headline{font-size:.79rem;color:#5B6472;line-height:1.5;font-weight:400;margin:0}
.chatreco-facts{display:grid;grid-template-columns:repeat(3,1fr);gap:.4rem;margin-top:.05rem}
.chatreco-fact{background:#F7F9FB;border:1px solid rgba(17,24,39,.05);border-radius:12px;
  padding:.5rem .35rem;text-align:center}
.chatreco-fact-value{font-size:.98rem;font-weight:700;color:var(--tui-dark);line-height:1}
.chatreco-fact-label{font-size:.5rem;font-weight:700;letter-spacing:.045em;text-transform:uppercase;
  color:var(--muted);margin-top:.28rem}
/* CTA de la maqueta: deshabilitado a propósito (es demostración). */
.chatreco-cta{margin-top:.35rem;align-self:stretch;border:none;cursor:default;
  border-radius:999px;padding:.55rem .9rem;font-family:inherit;font-weight:700;font-size:.78rem;
  color:#fff;background:linear-gradient(180deg,var(--tui-red),var(--tui-red-deep));
  box-shadow:0 8px 18px -8px rgba(212,14,20,.55);opacity:.92}

@media(max-width:900px){
  .chatreco-bubble{font-size:.88rem}
  .chatreco-cards-grid{padding-left:0}
  .chatreco-row .chatreco-bubble{max-width:82%}
}

/* ==========================================================================
   Panel de redistribución (TDRS): banda de política + etiqueta de popularidad
   ========================================================================== */
.redist-band{margin:.9rem 0 1.1rem;padding:1.1rem 1.25rem;border-radius:20px;
  background:linear-gradient(135deg,#FFFFFF 0%,#FBF4F4 100%);
  border:1px solid rgba(212,14,20,.16);box-shadow:var(--shadow-soft)}
.redist-head{display:flex;flex-direction:column;gap:.15rem;margin-bottom:.85rem}
.redist-stance{font-size:1.02rem;font-weight:900;color:var(--tui-red);letter-spacing:-.01em}
.redist-note{font-size:.76rem;color:var(--muted);line-height:1.4}
.redist-gauge{margin:.15rem 0 .95rem}
.redist-gauge-track{position:relative;height:9px;border-radius:999px;
  background:linear-gradient(90deg,#19865E 0%,#E7C24B 50%,var(--tui-red) 100%);opacity:.28}
.redist-gauge-fill{position:absolute;left:0;top:0;height:100%;border-radius:999px;
  background:linear-gradient(90deg,#19865E 0%,#E7C24B 50%,var(--tui-red) 100%)}
.redist-gauge-knob{position:absolute;top:50%;width:18px;height:18px;border-radius:50%;
  background:#fff;border:3px solid var(--tui-red);transform:translate(-50%,-50%);
  box-shadow:0 4px 12px rgba(212,14,20,.4)}
.redist-gauge-legend{display:flex;justify-content:space-between;margin-top:.5rem;
  font-size:.62rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.redist-gauge-legend span:nth-child(2){color:var(--tui-dark)}
.redist-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem}
.redist-stat{background:rgba(255,255,255,.7);border:1px solid rgba(17,24,39,.06);
  border-radius:14px;padding:.65rem .55rem;text-align:center}
.redist-stat-value{font-size:1.4rem;font-weight:900;color:var(--tui-dark);line-height:1}
.redist-stat-label{font-size:.56rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
  color:var(--muted);margin-top:.32rem}
/* Etiqueta que reemplaza al precio en el podio: popularidad/tipología. */
.redist-poptag{font-size:.66rem!important;font-weight:700!important;color:var(--tui-red)!important;
  text-transform:uppercase;letter-spacing:.04em;line-height:1.25!important;
  max-width:9rem;white-space:normal!important;text-align:right}
@media(max-width:900px){.redist-stats{grid-template-columns:1fr}}

/* ==========================================================================
   España — Copiloto de viaje al LADO de la recomendación (dos columnas).
   Izquierda: la ventana de chat (caja definida). Derecha: los resultados del
   modelo, visibles sin scroll largo. El formulario de filtros vive en un
   expander compacto encima de los resultados.
   ========================================================================== */

/* Panel contenedor del copiloto: define la columna del chat como módulo. */
.reco-copilot-pane{position:relative;border-radius:16px;padding:.1rem 0 .2rem;
  background:transparent}

/* Separador entre la zona de chat y la de recomendación (layout vertical). */
.reco-section-sep{height:1px;background:linear-gradient(90deg,rgba(17,24,39,.12),rgba(17,24,39,.02));
  margin:1.8rem 0 1.3rem}
/* Título de la sección de resultados, para separarla visualmente del chat. */
.reco-results-title{font-size:1.35rem;font-weight:700;color:var(--tui-dark);
  letter-spacing:-.02em;margin:.1rem 0 .3rem;display:flex;align-items:center;gap:.6rem}
.reco-results-title:before{content:"";width:4px;height:24px;background:var(--tui-red);border-radius:3px}
.reco-results-sub{font-size:.9rem;color:var(--muted);line-height:1.5;margin:0 0 1rem;max-width:620px}

/* En la vista España el hero destacado va en una columna junto al chat: se
   compacta un poco (banner más bajo) para que ambos quepan sin scroll largo.
   Se aplica directamente a .offer para no envolver widgets en <div> propios. */
/* La sección "Recomendación del modelo" va DEBAJO del chat, a todo el ancho.
   El hero destacado se compacta ligeramente para no ocupar de más. */
.reco-results-title + div .offer{margin:.15rem 0 1rem}
.reco-results-title + div .offer-media{height:260px}

</style>
"""


# Marca la página como "no traducir". El traductor del navegador (Google
# Translate y similares) reescribe los nodos de texto del DOM, lo que hace que
# React —el motor de Streamlit— pierda la referencia a esos nodos y lance el
# error "removeChild ... is not a child of this node". Marcar el documento como
# notranslate evita que el traductor toque el árbol y previene ese fallo.
_NO_TRANSLATE_JS = """
<script>
  const _d = window.parent?.document || document;
  if (_d && _d.documentElement) {
    _d.documentElement.setAttribute('translate', 'no');
    _d.documentElement.classList.add('notranslate');
    if (_d.body) _d.body.classList.add('notranslate');
  }
</script>
"""


def inject_styles() -> None:
    """Inyecta la hoja de estilos. Debe llamarse una vez, al inicio del script."""
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(_NO_TRANSLATE_JS, unsafe_allow_html=True)
