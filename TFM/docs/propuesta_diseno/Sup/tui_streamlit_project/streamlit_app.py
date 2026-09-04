from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from config import RAW_DIR
from database.init_db import init_db
from database.repositories import DestinationRepository, ProductRepository
from services.analytics_service import get_dashboard_metrics, get_destination_metrics, get_funnel_metrics, instrumentation_status
from services.booking_service import create_booking
from services.catalog_service import get_destinations, get_products
from services.import_service import import_products_from_csv
from services.reference_service import analyze_html, import_destinations_from_proposal_html, import_products_from_experience_html
from services.tdrs_service import PRESETS, compute_scores, scenario_metrics
from services.tracking_service import create_session, register_event

st.set_page_config(page_title="TUI · TDRS", page_icon="✈️", layout="wide")

CSS = """
<style>
:root { --tui-red:#D40E14; --tui-blue:#70CBF4; --tui-dark:#092A5E; --tui-digital:#176599; }
.stApp { background: #fff; }
h1,h2,h3 { color: var(--tui-dark); }
.tui-hero { padding: 2.2rem; border-radius: 18px; background: linear-gradient(120deg,#092A5E,#176599); color:white; margin-bottom:1rem; }
.tui-hero h1 { color:white; margin:0 0 .4rem 0; }
.tui-hero p { margin:0; opacity:.9; }
.kpi-note { font-size:.78rem; opacity:.72; }
.card { border:1px solid #e7edf3; border-radius:14px; padding:1rem; min-height:240px; box-shadow:0 3px 12px rgba(0,0,0,.04); }
.price { color:#D40E14; font-size:1.6rem; font-weight:800; }
.pill { display:inline-block; background:#E2F3FE; color:#092A5E; border-radius:20px; padding:.2rem .55rem; margin-right:.3rem; font-size:.75rem; }
.small { font-size:.82rem; color:#586777; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def bootstrap():
    init_db()
    if DestinationRepository().count() == 0 and (RAW_DIR / "propuesta_7.html").exists():
        import_destinations_from_proposal_html(RAW_DIR / "propuesta_7.html")
    if ProductRepository().count() == 0 and (RAW_DIR / "tui_experiencia_final.html").exists():
        import_products_from_experience_html(RAW_DIR / "tui_experiencia_final.html")


bootstrap()
if "session_id" not in st.session_state:
    st.session_state.session_id = create_session(source="streamlit")
if "page_views" not in st.session_state:
    st.session_state.page_views = set()

sid = st.session_state.session_id
view = st.sidebar.radio("Vista", ["Propuesta 7 · Catálogo", "Simulador TDRS", "Control Web", "Datos / modelo"])
if view not in st.session_state.page_views:
    register_event(sid, "page_view", view, dedupe_key=f"page_view:{view}")
    st.session_state.page_views.add(view)

if view == "Propuesta 7 · Catálogo":
    st.markdown('<div class="tui-hero"><h1>Viajes pensados para ti, buenos para el planeta</h1><p>Catálogo persistido en SQLite y servido a través de la capa de servicios.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([2,1,1])
    query = c1.text_input("Buscar", placeholder="Destino, viaje u hotel")
    destinations = ["Todos"] + get_destinations()
    destination = c2.selectbox("Destino", destinations)
    max_price = c3.number_input("Precio máximo (€)", min_value=0, value=2500, step=50)
    if query:
        register_event(sid, "search", view, metadata={"query": query}, dedupe_key=f"search:{query}:{destination}:{max_price}")
    products = get_products(query=query or None, destination=destination, max_price=max_price)
    st.caption(f"{len(products)} productos en el resultado")
    cols = st.columns(3)
    for i, p in enumerate(products):
        register_event(sid, "product_impression", view, product_id=p["product_id"], destination=p.get("destination"), dedupe_key=f"imp:{p['product_id']}:{query}:{destination}:{max_price}")
        with cols[i % 3]:
            if p.get("image_url"):
                st.image(p["image_url"], use_container_width=True)
            st.markdown(f"### {p.get('title') or 'Oferta'}")
            st.markdown(f"<span class='pill'>{p.get('destination') or 'Destino'}</span>", unsafe_allow_html=True)
            meta = " · ".join(str(x) for x in [f"{p.get('duration_days')} días" if p.get('duration_days') else None, p.get('board_basis')] if x)
            if meta: st.caption(meta)
            if p.get("description"): st.write(p["description"])
            if p.get("rating") is not None: st.write(f"⭐ {p['rating']:.1f}/5")
            if p.get("price") is not None: st.markdown(f"<div class='price'>{p['price']:,.0f} €</div>", unsafe_allow_html=True)
            if st.button("Ver oferta", key=f"view_{p['product_id']}", use_container_width=True):
                register_event(sid, "product_click", view, product_id=p["product_id"], destination=p.get("destination"))
                register_event(sid, "detail_view", view, product_id=p["product_id"], destination=p.get("destination"))
                st.session_state[f"detail_{p['product_id']}"] = True
            if st.session_state.get(f"detail_{p['product_id']}"):
                st.info("Detalle registrado. Puedes simular el checkout para alimentar Control Web.")
                passengers = st.number_input("Viajeros", 1, 10, 2, key=f"pax_{p['product_id']}")
                if st.button("Reservar (simulación académica)", key=f"book_{p['product_id']}"):
                    register_event(sid, "checkout_start", view, product_id=p["product_id"], destination=p.get("destination"))
                    bid = create_booking(sid, p["product_id"], passengers=int(passengers))
                    st.success(f"Reserva persistida: {bid[:8]}…")

elif view == "Simulador TDRS":
    st.title("Simulador de escenarios TDRS")
    st.caption("Score = media ponderada de factores normalizados; capacidad = 1 − ocupación. Los datos base proceden del simulador de referencia.")
    preset = st.radio("Escenario", list(PRESETS), horizontal=True, index=1)
    defaults = PRESETS[preset]
    with st.sidebar.expander("Pesos TDRS", expanded=True):
        weights = {
            "affinity": st.slider("Afinidad",0,100,int(defaults["affinity"])),
            "demand": st.slider("Demanda",0,100,int(defaults["demand"])),
            "occupancy": st.slider("Capacidad disponible",0,100,int(defaults["occupancy"])),
            "local_impact": st.slider("Impacto local",0,100,int(defaults["local_impact"])),
            "seasonality": st.slider("Temporada y clima",0,100,int(defaults["seasonality"])),
            "accessibility": st.slider("Accesibilidad",0,100,int(defaults["accessibility"])),
            "sustainability": st.slider("Sostenibilidad",0,100,int(defaults["sustainability"])),
        }
        max_price = st.slider("Presupuesto máximo", 400, 2500, 2500, 50)
        max_occ = st.slider("Ocupación máxima admitida (%)", 15, 100, 100)
        month = st.slider("Mes para contexto climático", 1, 12, 11)
    res = compute_scores(weights, max_price=max_price, max_occupancy_pct=max_occ, target_month=month)
    metrics = scenario_metrics(res["ranked"])
    if metrics:
        k = st.columns(5)
        k[0].metric("Presión saturados", f"{metrics['pressure']:.0%}")
        k[1].metric("Cuota emergentes", f"{metrics['emerging_share']:.0%}")
        k[2].metric("CTR estimado*", f"{metrics['estimated_ctr_pct']:.1f}%")
        k[3].metric("Equilibrio territorial", f"{metrics['territorial_balance']:.2f}")
        k[4].metric("Elegibles", f"{metrics['eligible']}")
        st.caption("*CTR estimado reproduce la simulación académica del HTML de referencia; no es tracking observado.")
    rank_rows = []
    for pos, r in enumerate(res["ranked"], 1):
        clim = r.get("climate") or {}
        conn = r.get("connectivity") or {}
        ind = r.get("country_indicators") or {}
        rank_rows.append({
            "#": pos, "Destino": r["name"], "Zona": r.get("zone"), "Score TDRS": round(r["score"],3),
            "Precio €": r.get("reference_price_eur"), "Ocupación": r.get("occupancy"),
            "Temp. aire mes °C": clim.get("air_temp_c"), "Vuelos/sem": conn.get("weekly_flights"),
            "Camas/1000": ind.get("hospital_beds_per_1000"), "Homicidios/100k": ind.get("homicide_rate_per_100k"),
            "Factor principal": r["contributions"][0]["label"] if r["contributions"] else None,
        })
    st.dataframe(pd.DataFrame(rank_rows), use_container_width=True, hide_index=True)
    if res["excluded"]:
        st.warning(f"{len(res['excluded'])} destinos excluidos por restricciones duras.")

elif view == "Control Web":
    st.title("Control Web")
    m = get_dashboard_metrics()
    c = st.columns(4)
    c[0].metric("Sesiones", m["sessions"])
    c[1].metric("Impresiones", m["impressions"])
    c[2].metric("Clics", m["clicks"])
    c[3].metric("CTR", f"{m['ctr']:.1%}" if m["ctr"] is not None else "Pendiente")
    c = st.columns(4)
    c[0].metric("Reservas", m["bookings"])
    c[1].metric("Conversión", f"{m['conversion']:.1%}" if m["conversion"] is not None else "Pendiente")
    c[2].metric("Ingresos", f"{m['revenue_eur']:,.0f} €")
    c[3].metric("ROAS", f"{m['roas']:.2f}" if m["roas"] is not None else "Pendiente")
    st.subheader("Embudo")
    funnel = pd.DataFrame(get_funnel_metrics()).set_index("step")
    st.bar_chart(funnel)
    st.subheader("Rendimiento por destino")
    st.dataframe(pd.DataFrame(get_destination_metrics()), use_container_width=True, hide_index=True)
    st.subheader("Estado de instrumentación")
    st.dataframe(pd.DataFrame(instrumentation_status()), use_container_width=True, hide_index=True)

else:
    st.title("Datos y modelo")
    st.write("La interfaz consume SQLite; los CSV se usan solo como fuentes de importación.")
    up = st.file_uploader("Importar CSV de productos", type=["csv"])
    if up is not None and st.button("Importar productos"):
        try:
            result = import_products_from_csv(up)
            st.success(f"{result['imported']} productos insertados/actualizados")
            st.dataframe(result["column_analysis"], use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(str(e))
    st.subheader("Fuentes de referencia")
    for fn in ["propuesta_7.html", "tui_experiencia_final.html"]:
        p = RAW_DIR / fn
        if p.exists():
            with st.expander(fn):
                st.json(analyze_html(p))
    st.code("python scripts/build_model.py\nstreamlit run streamlit_app.py", language="bash")
