from __future__ import annotations

"""Vista Datos / modelo: salud de fuentes, historial, tablas y configuración."""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from components.ui import fmt_ts, render_metric_rows, render_system_alerts
from services.alert_service import get_alerts
from services.data_control_service import (
    get_database_file_info,
    get_database_files,
    get_database_tables,
    get_import_history,
    get_source_health,
    get_update_runs,
    refresh_all_sources,
    refresh_source,
    update_source_config,
)

SOURCE_COLUMNS = [
    "Estado", "Dataset", "Tipo", "Filas actuales", "Intervalo objetivo",
    "Última actualización", "Próxima esperada", "Modelo del dataset",
    "Método actual", "Scraper / conector", "Último error",
]

RUN_COLUMNS = [
    "started_at", "source_name", "status", "duration_seconds",
    "rows_before", "rows_after", "Variación", "trigger", "error_message",
]


def _render_sources_tab(sources: list[dict]) -> None:
    source_df = pd.DataFrame(sources)
    available = [col for col in SOURCE_COLUMNS if col in source_df.columns]
    st.dataframe(source_df[available], width="stretch", hide_index=True)


def _render_runs_tab(sources: list[dict]) -> None:
    f1, f2, f3, f4 = st.columns([1.3, 1, 1, 1])
    source_ids = {"Todas": None, **{s["Dataset"]: s["source_id"] for s in sources}}
    source_label = f1.selectbox("Fuente", list(source_ids), key="runs_source")
    status_filter = f2.selectbox(
        "Estado", ["Todos", "success", "warning", "error", "running"], key="runs_status"
    )
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
            lambda r: (r["rows_after"] - r["rows_before"])
            if pd.notna(r["rows_after"]) and pd.notna(r["rows_before"]) else None,
            axis=1,
        )
        available = [col for col in RUN_COLUMNS if col in df.columns]
        st.dataframe(df[available], width="stretch", hide_index=True)
    else:
        st.caption("No hay ejecuciones que coincidan con los filtros.")

    with st.expander("Histórico técnico de imports"):
        imports = get_import_history(100)
        if imports:
            st.dataframe(
                pd.DataFrame(imports).drop(columns=["details"], errors="ignore"),
                width="stretch", hide_index=True,
            )
        else:
            st.caption("Sin imports registrados.")


def _render_db_tab(tables: list[dict], db_info: dict) -> None:
    st.markdown("#### Bases de datos")
    db_files = get_database_files()
    if db_files:
        st.dataframe(pd.DataFrame(db_files), width="stretch", hide_index=True)
    else:
        st.warning("No se han encontrado ficheros SQLite en data/.")
    st.markdown("#### Tablas persistidas")
    st.dataframe(pd.DataFrame(tables), width="stretch", hide_index=True)
    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Diagnóstico SQLite**")
        st.code(db_info["path"])
        st.write(f"Integrity check: **{db_info['integrity']}**")
        st.write(f"Última modificación: **{fmt_ts(db_info['modified_at'])}**")
    with d2:
        st.markdown("**Punto de entrada de actualización**")
        st.code("python scripts\\build_model.py", language="powershell")
        st.caption(
            "Se puede programar con Task Scheduler, cron o un orquestador cuando "
            "los conectores externos estén disponibles."
        )


def _render_config_tab(sources: list[dict]) -> None:
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
    if b1.button("Guardar configuración", width="stretch", type="primary"):
        try:
            update_source_config(
                selected["source_id"], int(interval_hours), dataset_model, notes, enabled
            )
            st.success("Configuración guardada en SQLite.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"No se pudo guardar: {exc}")
    if b2.button("Actualizar fuente", width="stretch"):
        try:
            with st.spinner(f"Actualizando {selected['Dataset']}…"):
                result = refresh_source(selected["source_id"], trigger="manual")
            st.success(f"Actualización completada · {result.get('rows_in_table')} filas actuales.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Falló la actualización: {exc}")
    if b3.button("Actualizar todas las fuentes locales", width="stretch"):
        with st.spinner("Actualizando fuentes locales…"):
            results = refresh_all_sources(trigger="manual")
        failed = [r for r in results if r.get("status") != "success"]
        if failed:
            st.error(f"Proceso terminado con {len(failed)} fuente(s) con error.")
            st.json(failed)
        else:
            st.success("Todas las fuentes locales se han actualizado correctamente.")
        st.rerun()


def render_data_model() -> None:
    db_info = get_database_file_info()
    sources = get_source_health()
    alerts = get_alerts(include_ok=False)
    ok_sources = sum(1 for s in sources if s["enabled"] and s["Estado"] == "OK")
    tables = get_database_tables()

    # El mismo sistema de alertas operativas se muestra en Control Web y aquí.
    render_system_alerts("Alertas de datos")

    render_metric_rows([
        ("SQLite", "OK" if db_info["integrity"] == "ok" else "Revisar"),
        ("Tablas", len(tables)),
        ("Fuentes activas", sum(1 for s in sources if s["enabled"])),
        ("Fuentes al día", ok_sources),
        ("Alertas", len(alerts)),
        ("Tamaño DB", f"{db_info['size_mb']} MB"),
    ], columns=3)

    tab_sources, tab_runs, tab_db, tab_config = st.tabs(
        ["Fuentes", "Historial de actualizaciones", "Bases y tablas", "Configuración"]
    )
    with tab_sources:
        _render_sources_tab(sources)
    with tab_runs:
        _render_runs_tab(sources)
    with tab_db:
        _render_db_tab(tables, db_info)
    with tab_config:
        _render_config_tab(sources)
