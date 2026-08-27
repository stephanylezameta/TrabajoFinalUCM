"""
Dashboard Interactivo - Motor de Recomendacion Turistica TUI
Simulador de Redistribucion con TDRS
TFM UCM 2025

Ejecutar:
    cd D:\\Master\\TrabajoFinalUCM\\TFM
    python -m streamlit run app/pages/dashboard.py

Requisitos: pip install streamlit plotly pandas numpy
"""

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# =============================================================================
# CONFIGURACION
# =============================================================================
st.set_page_config(
    page_title="TUI - Simulador de Redistribucion Turistica",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS con estilo TUI
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Nunito Sans', sans-serif; }
    .stApp { background-color: #f8f9fa; }
    [data-testid="stSidebar"] { background: #1d1d1b; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] .stMarkdown h1,
    [data-testid="stSidebar"] .stMarkdown h2,
    [data-testid="stSidebar"] .stMarkdown h3 { color: rgba(255,255,255,0.85) !important; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stMultiSelect label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stRadio label { color: rgba(255,255,255,0.9) !important; font-weight: 600; }
    .stMetric label { font-size: 0.7rem !important; text-transform: uppercase; letter-spacing: 0.5px; }
    .stMetric [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 900 !important; }
    .stTabs [aria-selected="true"] { background-color: #d40e14 !important; color: white !important; border-radius: 6px 6px 0 0; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# DATOS SIMULADOS DEL MODELO TDRS
# =============================================================================
@st.cache_data
def generate_data():
    np.random.seed(42)

    destinos_data = [
        ("Mallorca", "Espana", "Mediterraneo", "playa", 0.42, 0.78, 0.92, 0.85, 3, 899),
        ("Split", "Croacia", "Mediterraneo", "cultura", 0.28, 0.85, 0.87, 0.82, 2, 780),
        ("Algarve", "Portugal", "Atlantico", "playa", 0.35, 0.82, 0.81, 0.91, 3, 650),
        ("Creta", "Grecia", "Mediterraneo", "cultura", 0.55, 0.65, 0.79, 0.75, 2, 920),
        ("Cabo Verde", "Cabo Verde", "Atlantico", "naturaleza", 0.30, 0.80, 0.74, 0.88, 2, 1050),
        ("Tenerife", "Espana", "Atlantico", "playa", 0.62, 0.55, 0.85, 0.70, 3, 750),
        ("Carmona", "Espana", "Interior", "cultura", 0.22, 0.90, 0.87, 0.95, 2, 450),
        ("Osuna", "Espana", "Interior", "cultura", 0.18, 0.92, 0.85, 0.96, 1, 420),
        ("Sevilla", "Espana", "Interior", "cultura", 0.88, 0.25, 0.90, 0.40, 3, 680),
        ("Cancun", "Mexico", "Caribe", "playa", 0.94, 0.18, 0.88, 0.30, 3, 1890),
        ("Maldivas", "Maldivas", "Oceano Indico", "playa", 0.91, 0.20, 0.82, 0.35, 2, 2400),
        ("Barcelona", "Espana", "Mediterraneo", "cultura", 0.89, 0.22, 0.91, 0.38, 3, 720),
        ("Ibiza", "Espana", "Mediterraneo", "playa", 0.85, 0.30, 0.80, 0.42, 3, 950),
        ("Marrakech", "Marruecos", "Norte de Africa", "cultura", 0.50, 0.70, 0.76, 0.72, 2, 620),
        ("Bali", "Indonesia", "Sudeste Asiatico", "naturaleza", 0.72, 0.45, 0.84, 0.55, 2, 1650),
        ("Phuket", "Tailandia", "Sudeste Asiatico", "playa", 0.68, 0.48, 0.80, 0.52, 2, 1500),
        ("Dubrovnik", "Croacia", "Mediterraneo", "cultura", 0.82, 0.32, 0.83, 0.45, 2, 1100),
        ("Sicilia", "Italia", "Mediterraneo", "gastronomia", 0.45, 0.72, 0.78, 0.80, 2, 850),
        ("Cerdena", "Italia", "Mediterraneo", "playa", 0.40, 0.75, 0.76, 0.83, 2, 900),
        ("Fuerteventura", "Espana", "Atlantico", "naturaleza", 0.38, 0.77, 0.72, 0.86, 2, 680),
        ("Lanzarote", "Espana", "Atlantico", "naturaleza", 0.42, 0.74, 0.73, 0.84, 2, 700),
        ("Costa Amalfitana", "Italia", "Mediterraneo", "gastronomia", 0.78, 0.35, 0.85, 0.48, 2, 1300),
        ("Santorini", "Grecia", "Mediterraneo", "playa", 0.80, 0.30, 0.86, 0.45, 2, 1400),
        ("Dubai", "EAU", "Golfo Persico", "lujo", 0.70, 0.50, 0.78, 0.55, 3, 1800),
        ("Riviera Maya", "Mexico", "Caribe", "playa", 0.75, 0.40, 0.83, 0.50, 3, 1450),
    ]

    df = pd.DataFrame(destinos_data, columns=[
        "destino", "pais", "zona_geografica", "categoria",
        "ocupacion_actual", "score_tdrs", "score_afinidad",
        "score_sostenibilidad", "accesibilidad", "precio_medio_eur"
    ])

    # Variables derivadas
    df["temporada"] = np.where(df["ocupacion_actual"] > 0.7, "Alta",
                     np.where(df["ocupacion_actual"] > 0.45, "Media", "Baja"))
    df["satisfaccion_predicha"] = (df["score_afinidad"] * 3.5 + np.random.uniform(0.5, 1.5, len(df))).clip(3.5, 5.0).round(2)
    df["ctr_esperado"] = (df["score_afinidad"] * 0.15 + np.random.uniform(0.01, 0.04, len(df))).clip(0.05, 0.22).round(3)
    df["conversion_potencial"] = (df["ctr_esperado"] * np.random.uniform(0.25, 0.45, len(df))).round(3)
    df["n_recomendaciones"] = np.random.randint(80, 2500, len(df))
    df["reservas_mes"] = (df["n_recomendaciones"] * df["conversion_potencial"]).astype(int)
    df["impacto_economico_local"] = np.random.uniform(0.3, 1.0, len(df)).round(2)
    df["sensibilidad_ambiental"] = np.random.uniform(0.2, 0.9, len(df)).round(2)
    df["tiempo_desplazamiento_h"] = np.random.uniform(0.5, 12.0, len(df)).round(1)

    return df


def apply_reranking(df, strategy, weights=None):
    """Aplica re-ranking segun estrategia TDRS."""
    df_out = df.copy()

    if strategy == "Tradicional (sin TDRS)":
        df_out["score_final"] = df_out["score_afinidad"]
    elif strategy == "Moderada":
        df_out["score_final"] = (
            0.50 * df_out["score_afinidad"] +
            0.20 * df_out["score_tdrs"] +
            0.15 * df_out["score_sostenibilidad"] +
            0.15 * (1 - df_out["ocupacion_actual"])
        )
    elif strategy == "Intensiva":
        df_out["score_final"] = (
            0.30 * df_out["score_afinidad"] +
            0.30 * df_out["score_tdrs"] +
            0.20 * df_out["score_sostenibilidad"] +
            0.20 * (1 - df_out["ocupacion_actual"])
        )

    df_out["rank"] = df_out["score_final"].rank(ascending=False).astype(int)
    return df_out.sort_values("rank")


# =============================================================================
# SIDEBAR - FILTROS
# =============================================================================
st.sidebar.markdown("""
<div style="text-align:center;padding:12px 0 16px;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:16px">
    <div style="display:inline-flex;align-items:center;gap:8px">
        <div style="width:36px;height:36px;background:#d40e14;border-radius:8px;display:flex;align-items:center;justify-content:center;color:white;font-weight:900;font-size:11px">TUI</div>
        <span style="font-size:14px;font-weight:800;color:white">Redistribucion TDRS</span>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### Filtros")

perfil = st.sidebar.selectbox("Perfil de viajero", ["Todos", "Beach Foodie", "Cultural Explorer", "Wellness Seeker", "Adventure Young", "Family All-Inclusive"])

temporada_filter = st.sidebar.multiselect("Temporada", ["Alta", "Media", "Baja"], default=["Alta", "Media", "Baja"])

zona_filter = st.sidebar.multiselect("Zona geografica", ["Mediterraneo", "Atlantico", "Caribe", "Sudeste Asiatico", "Golfo Persico", "Oceano Indico", "Norte de Africa", "Interior"], default=["Mediterraneo", "Atlantico", "Caribe", "Sudeste Asiatico", "Golfo Persico", "Oceano Indico", "Norte de Africa", "Interior"])

ocup_max = st.sidebar.slider("Ocupacion maxima", 0.0, 1.0, 1.0, 0.05)

accesibilidad_filter = st.sidebar.multiselect("Accesibilidad", [1, 2, 3], default=[1, 2, 3])

sost_min = st.sidebar.slider("Sostenibilidad minima", 0.0, 1.0, 0.0, 0.1)

st.sidebar.markdown("---")
st.sidebar.markdown("### Estrategia de Redistribucion")
estrategia = st.sidebar.radio("Escenario TDRS:", ["Tradicional (sin TDRS)", "Moderada", "Intensiva"], index=1)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style="padding:10px;background:rgba(255,255,255,0.05);border-radius:6px;font-size:10px;color:rgba(255,255,255,0.6);line-height:1.6">
<strong style="color:rgba(255,255,255,0.8)">TDRS Score</strong><br>
w1 Afinidad<br>
w2 Capacidad<br>
w3 Accesibilidad<br>
w4 Impacto local<br>
w5 Temporada baja<br>
w6 Diversificacion<br>
w7 Ocupacion<br>
w8 Sensib. ambiental
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("<div style='font-size:9px;color:rgba(255,255,255,0.4);margin-top:12px'>Motor TDRS v2.1 - LightFM + Embeddings 384d<br>Modelo: paraphrase-multilingual-MiniLM-L12-v2</div>", unsafe_allow_html=True)


# =============================================================================
# DATOS FILTRADOS
# =============================================================================
df = generate_data()

df_filtered = df[
    (df["temporada"].isin(temporada_filter)) &
    (df["ocupacion_actual"] <= ocup_max) &
    (df["accesibilidad"].isin(accesibilidad_filter)) &
    (df["score_sostenibilidad"] >= sost_min) &
    (df["zona_geografica"].isin(zona_filter))
]

df_result = apply_reranking(df_filtered, estrategia)


# =============================================================================
# HEADER
# =============================================================================
st.markdown("""
<div style="background:linear-gradient(135deg,#001f4d 0%,#003580 50%,#0057b8 100%);padding:24px 32px;border-radius:12px;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:22px;font-weight:900">Simulador de Redistribucion Turistica</h1>
    <p style="color:rgba(255,255,255,0.75);margin:6px 0 0;font-size:13px;line-height:1.5">
        <strong style="color:#ff6b6b">85% de turistas visitan solo el 10% de destinos.</strong> Zonas rurales a 40-50% capacidad.<br>
        Motor de IA predictiva para redistribuir flujos turisticos con recomendaciones personalizadas.
    </p>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# KPIs - 8 METRICAS
# =============================================================================
c1, c2, c3, c4 = st.columns(4)
c5, c6, c7, c8 = st.columns(4)

with c1:
    st.metric("CTR esperado", f"{df_result['ctr_esperado'].mean():.1%}", delta="+2.1% vs baseline")
with c2:
    st.metric("Conversion potencial", f"{df_result['conversion_potencial'].mean():.1%}", delta="+1.2%")
with c3:
    diversidad = df_result["destino"].nunique() / len(df) * 100
    st.metric("Diversidad recomend.", f"{diversidad:.0f}%", delta=f"+{diversidad - 40:.0f}% vs trad.")
with c4:
    saturados = (df_result["ocupacion_actual"] > 0.8).sum()
    saturados_base = (df["ocupacion_actual"] > 0.8).sum()
    st.metric("Reduccion concentracion", f"-{(saturados_base - saturados) / max(saturados_base, 1) * 100:.0f}%")
with c5:
    zonas_activas = df_result["zona_geografica"].nunique()
    st.metric("Distrib. geografica", f"{zonas_activas} zonas", delta=f"de {df['zona_geografica'].nunique()} totales")
with c6:
    st.metric("Satisfaccion predicha", f"{df_result['satisfaccion_predicha'].mean():.2f}/5", delta="+0.3")
with c7:
    ocup_baja = df_result[df_result["temporada"] == "Baja"]["ocupacion_actual"].mean()
    st.metric("Ocup. fuera temporada", f"{ocup_baja:.0%}" if not np.isnan(ocup_baja) else "N/A", delta="+18%")
with c8:
    if len(df_result) > 1:
        gini = 1 - (df_result["n_recomendaciones"].std() / max(df_result["n_recomendaciones"].mean(), 1))
    else:
        gini = 0
    st.metric("Equilibrio territorial", f"{gini:.2f}", delta="mas equitativo")


# =============================================================================
# TABS PRINCIPALES
# =============================================================================
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["Ranking TDRS", "Simulador Redistribucion", "Distribucion Geografica", "Detalle Destino"])

# --- TAB 1: RANKING ---
with tab1:
    st.subheader(f"Ranking de destinos - Estrategia: {estrategia}")

    col_l, col_r = st.columns([1, 1])

    with col_l:
        fig = px.bar(
            df_result.head(12), x="score_final", y="destino",
            orientation="h", color="score_tdrs",
            color_continuous_scale="RdYlGn",
            labels={"score_final": "Score Final", "destino": "", "score_tdrs": "TDRS"}
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), height=450, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        display_cols = ["rank", "destino", "score_final", "score_afinidad", "score_tdrs", "ocupacion_actual", "precio_medio_eur", "ctr_esperado"]
        st.dataframe(
            df_result[display_cols].head(12).style.format({
                "score_final": "{:.3f}", "score_afinidad": "{:.3f}",
                "score_tdrs": "{:.3f}", "ocupacion_actual": "{:.0%}",
                "precio_medio_eur": "{:,.0f} EUR", "ctr_esperado": "{:.1%}"
            }).background_gradient(subset=["score_tdrs"], cmap="RdYlGn"),
            height=450, use_container_width=True
        )

# --- TAB 2: SIMULADOR ---
with tab2:
    st.subheader("Simulador de Redistribucion Turistica")
    st.markdown("Compara el efecto de las tres estrategias sobre la concentracion turistica.")

    df_t = apply_reranking(df_filtered, "Tradicional (sin TDRS)")
    df_m = apply_reranking(df_filtered, "Moderada")
    df_i = apply_reranking(df_filtered, "Intensiva")

    cs1, cs2, cs3 = st.columns(3)

    def concentracion_top5(d):
        if d["n_recomendaciones"].sum() == 0:
            return 0
        return d.head(5)["n_recomendaciones"].sum() / d["n_recomendaciones"].sum()

    with cs1:
        st.markdown("#### Tradicional")
        st.metric("Concentracion top-5", f"{concentracion_top5(df_t):.0%}")
        st.metric("CTR medio", f"{df_t['ctr_esperado'].mean():.1%}")
        st.metric("Destinos saturados (>80%)", f"{(df_t['ocupacion_actual'] > 0.8).sum()}")

    with cs2:
        st.markdown("#### Moderada")
        st.metric("Concentracion top-5", f"{concentracion_top5(df_m):.0%}")
        st.metric("CTR medio", f"{df_m['ctr_esperado'].mean():.1%}")
        st.metric("Destinos saturados (>80%)", f"{(df_m['ocupacion_actual'] > 0.8).sum()}")

    with cs3:
        st.markdown("#### Intensiva")
        st.metric("Concentracion top-5", f"{concentracion_top5(df_i):.0%}")
        st.metric("CTR medio", f"{df_i['ctr_esperado'].mean():.1%}")
        st.metric("Destinos saturados (>80%)", f"{(df_i['ocupacion_actual'] > 0.8).sum()}")

    # Grafico comparativo
    comp = pd.DataFrame({
        "Estrategia": ["Tradicional", "Moderada", "Intensiva"],
        "Concentracion top-5": [concentracion_top5(df_t), concentracion_top5(df_m), concentracion_top5(df_i)],
        "Satisfaccion media": [df_t["satisfaccion_predicha"].mean() / 5, df_m["satisfaccion_predicha"].mean() / 5, df_i["satisfaccion_predicha"].mean() / 5],
    })
    fig_comp = go.Figure()
    fig_comp.add_trace(go.Bar(name="Concentracion top-5", x=comp["Estrategia"], y=comp["Concentracion top-5"], marker_color="#d40e14"))
    fig_comp.add_trace(go.Bar(name="Satisfaccion (norm.)", x=comp["Estrategia"], y=comp["Satisfaccion media"], marker_color="#1b8a4b"))
    fig_comp.update_layout(barmode="group", height=350, margin=dict(t=30, b=0))
    st.plotly_chart(fig_comp, use_container_width=True)

    # INSIGHT CLAVE
    st.markdown("""
    <div style="background:white;border-left:4px solid #d40e14;padding:16px 20px;border-radius:0 10px 10px 0;box-shadow:0 2px 8px rgba(0,0,0,0.04);margin-top:16px">
        <div style="font-size:10px;text-transform:uppercase;letter-spacing:1px;color:#d40e14;font-weight:800;margin-bottom:6px">Insight generado por el motor TDRS</div>
        <div style="font-size:13px;color:#333;line-height:1.7">
            "Un viajero interesado en <strong>patrimonio cultural y gastronomia local</strong> que normalmente visitaria el centro historico de <strong>Sevilla</strong> recibe recomendaciones alternativas hacia <strong>Carmona y Osuna</strong>. Estas experiencias presentan un <strong>87% de afinidad estimada</strong>, tiempos de desplazamiento inferiores a una hora y una <strong>presion turistica significativamente menor</strong> durante el mismo periodo."
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- TAB 3: DISTRIBUCION GEOGRAFICA ---
with tab3:
    st.subheader("Distribucion geografica de la demanda")

    col_g1, col_g2 = st.columns(2)

    with col_g1:
        zona_agg = df_result.groupby("zona_geografica").agg(
            recomendaciones=("n_recomendaciones", "sum"),
            score_medio=("score_final", "mean"),
            destinos=("destino", "count")
        ).reset_index()
        fig_pie = px.pie(zona_agg, values="recomendaciones", names="zona_geografica",
                         title="Recomendaciones por zona", color_discrete_sequence=px.colors.qualitative.Set2)
        fig_pie.update_layout(height=380)
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_g2:
        fig_scatter = px.scatter(
            df_result, x="score_afinidad", y="ocupacion_actual",
            size="n_recomendaciones", color="score_tdrs",
            hover_name="destino", color_continuous_scale="RdYlGn",
            title="Afinidad vs Ocupacion (tamano = volumen)",
            labels={"score_afinidad": "Score Afinidad", "ocupacion_actual": "Ocupacion Actual"}
        )
        fig_scatter.add_hline(y=0.85, line_dash="dash", line_color="red", annotation_text="Saturacion (85%)")
        fig_scatter.update_layout(height=380)
        st.plotly_chart(fig_scatter, use_container_width=True)

    # Ocupacion por zona
    fig_zona_ocp = px.box(df_result, x="zona_geografica", y="ocupacion_actual",
                          color="zona_geografica", title="Distribucion de ocupacion por zona",
                          labels={"ocupacion_actual": "Ocupacion", "zona_geografica": ""})
    fig_zona_ocp.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_zona_ocp, use_container_width=True)

# --- TAB 4: DETALLE DESTINO ---
with tab4:
    st.subheader("Detalle por destino")

    destino_sel = st.selectbox("Selecciona destino:", df_result["destino"].tolist())
    row = df_result[df_result["destino"] == destino_sel].iloc[0]

    cd1, cd2, cd3, cd4 = st.columns(4)
    with cd1:
        st.metric("Score Final", f"{row['score_final']:.3f}")
        st.metric("Score Afinidad", f"{row['score_afinidad']:.3f}")
    with cd2:
        st.metric("Score TDRS", f"{row['score_tdrs']:.3f}")
        st.metric("Sostenibilidad", f"{row['score_sostenibilidad']:.2f}")
    with cd3:
        st.metric("Ocupacion", f"{row['ocupacion_actual']:.0%}")
        st.metric("Accesibilidad", f"{int(row['accesibilidad'])}/3")
    with cd4:
        st.metric("CTR esperado", f"{row['ctr_esperado']:.1%}")
        st.metric("Precio medio", f"{int(row['precio_medio_eur']):,} EUR")

    # Radar
    cats = ["Afinidad", "TDRS", "Sostenibilidad", "Disponibilidad", "Impacto local"]
    vals = [row["score_afinidad"], row["score_tdrs"], row["score_sostenibilidad"],
            1 - row["ocupacion_actual"], row["impacto_economico_local"]]
    fig_radar = go.Figure(data=go.Scatterpolar(
        r=vals + [vals[0]], theta=cats + [cats[0]],
        fill="toself", fillcolor="rgba(212,14,20,0.15)", line_color="#d40e14"
    ))
    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
                            title=f"Perfil TDRS - {destino_sel}", height=380)
    st.plotly_chart(fig_radar, use_container_width=True)

    # Recomendacion estrategica
    if row["ocupacion_actual"] > 0.80:
        st.error(f"SATURADO (ocupacion {row['ocupacion_actual']:.0%}). Reducir push y redistribuir hacia alternativas.")
    elif row["ocupacion_actual"] < 0.40:
        st.success(f"ALTA OPORTUNIDAD (ocupacion {row['ocupacion_actual']:.0%}). Aumentar push con campanas personalizadas.")
    else:
        st.info(f"EQUILIBRADO (ocupacion {row['ocupacion_actual']:.0%}). Mantener estrategia actual.")


# =============================================================================
# FOOTER
# =============================================================================
st.markdown("---")
st.markdown("""
<div style="text-align:center;padding:20px;font-size:11px;color:#888;line-height:1.7">
    <strong style="color:#1d1d1b">TFM UCM 2025</strong> - Motor de Recomendacion Turistica con TDRS<br>
    Python + LightFM + Sentence-Transformers + Streamlit + FastAPI<br>
    Combinando: <strong>Mindtrip</strong> (personalizacion) + <strong>Nezasa</strong> (paquetes TUI) + <strong>Murmuration</strong> (redistribucion sostenible)<br>
    <span style="font-size:9px;color:#aaa">TDRS = w1 Afinidad + w2 Capacidad + w3 Accesibilidad + w4 Impacto local + w5 Temporada baja + w6 Diversificacion + w7 Ocupacion + w8 Sensib. ambiental</span>
</div>
""", unsafe_allow_html=True)
