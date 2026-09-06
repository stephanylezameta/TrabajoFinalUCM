from __future__ import annotations

"""Bloques de render compartidos por las vistas.

Aquí solo hay presentación: ninguna función de este módulo consulta SQLite
directamente, salvo a través de los servicios ya existentes.
"""

from html import escape

import streamlit as st

from services.alert_service import get_alerts


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


def render_alert(item: dict) -> None:
    level = str(item.get("level", "INFO")).upper()
    css_level = level.lower()
    title = escape(str(item.get("title", "Alerta")))
    message = escape(str(item.get("message", "")))
    action = item.get("action")
    action_html = (
        f'<div class="alert-action">Acción recomendada · {escape(str(action))}</div>'
        if action
        else ""
    )
    st.markdown(
        f"""
        <div class="alert-card alert-{css_level}">
          <div class="alert-head"><div class="alert-title">{title}</div><span class="alert-badge badge-{css_level}">{level}</span></div>
          <div class="alert-message">{message}</div>{action_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_system_alerts(title: str = "Alertas de sistema") -> None:
    """Bloque único de alertas operativas para las vistas de control y datos."""
    alerts = get_alerts()
    st.markdown(f"### {title}")
    if not alerts:
        return
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
