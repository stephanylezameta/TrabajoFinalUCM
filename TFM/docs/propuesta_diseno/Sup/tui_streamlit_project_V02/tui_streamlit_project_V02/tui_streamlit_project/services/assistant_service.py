from __future__ import annotations

import re
from typing import Any

from services.alert_service import get_active_alerts, get_alerts, get_system_status
from services.analytics_service import get_dashboard_metrics, instrumentation_status
from services.data_control_service import (
    get_database_health,
    get_database_tables,
    get_last_error,
    get_overdue_sources,
    get_recent_updates,
    get_row_count_change,
    get_source_health,
)


def _source_by_id(source_id: str) -> dict[str, Any] | None:
    return next((s for s in get_source_health() if s["source_id"] == source_id), None)


def _source_for_prompt(prompt: str) -> dict[str, Any] | None:
    p = prompt.lower()
    aliases = {
        "clima": "climate",
        "climate": "climate",
        "conectividad": "connectivity",
        "pasajeros": "connectivity",
        "seguridad": "country_indicators",
        "sanidad": "country_indicators",
        "banco mundial": "country_indicators",
        "tdrs": "destinations_tdrs",
        "destinos": "destinations_tdrs",
        "catálogo": "products_html",
        "catalogo": "products_html",
        "ofertas": "products_html",
    }
    for token, sid in aliases.items():
        if token in p:
            return _source_by_id(sid)
    return None


def get_initial_summary() -> str:
    status = get_system_status()
    sources = get_source_health()
    problems = [s for s in sources if s["enabled"] and s["Estado"] != "OK"]
    lines = [
        f"He revisado {status['active_sources']} fuentes activas: **{status['healthy_sources']} están al día**.",
        f"SQLite: **{status['database_integrity']}**. Registros controlados en fuentes: **{status['total_rows']:,}**.",
    ]
    if problems:
        lines.append(f"Hay **{len(problems)} fuente(s) que requieren revisión**: " + ", ".join(s["Dataset"] for s in problems[:4]) + ".")
    else:
        lines.append("No se detectan fuentes fuera de intervalo ni errores activos con las reglas actuales.")
    if status.get("last_update"):
        lines.append(f"Última actualización satisfactoria registrada: **{status['last_update']}**.")
    return "\n\n".join(lines)


def _all_updated_answer() -> dict[str, Any]:
    status = get_system_status()
    overdue = get_overdue_sources()
    if not overdue and status["database_integrity"] == "ok":
        text = f"Sí. Las **{status['healthy_sources']} fuentes activas** están dentro de intervalo y SQLite responde correctamente."
    else:
        text = f"No completamente. Hay **{len(overdue)} fuente(s)** fuera de estado OK y {status['open_alerts']} alertas operativas."
    return {"text": text, "table": overdue[:10] if overdue else None}


def answer_question(prompt: str) -> dict[str, Any]:
    p = re.sub(r"\s+", " ", prompt.strip().lower())
    if not p:
        return {"text": "Escribe una pregunta sobre fuentes, actualizaciones, SQLite, tracking o rendimiento web."}

    source = _source_for_prompt(p)

    if any(x in p for x in ["qué está pasando", "que esta pasando", "resumen", "estado general"]):
        return {"text": get_initial_summary(), "alerts": get_alerts()[:6]}

    if any(x in p for x in ["está todo actualizado", "esta todo actualizado", "todo actualizado", "al día", "al dia"]):
        return _all_updated_answer()

    if "alert" in p or "problema" in p:
        alerts = get_active_alerts()
        text = "No hay alertas activas." if not alerts else f"Hay **{len(alerts)} alerta(s) activa(s)**. Las más importantes aparecen debajo."
        return {"text": text, "alerts": alerts[:10]}

    if source and any(x in p for x in ["cuándo", "cuando", "actualiz", "estado", "intervalo", "modelo", "filas", "registros"]):
        text = (
            f"**{source['Dataset']}** está en estado **{source['Estado']}**. "
            f"Filas actuales: **{source['Filas actuales']:,}**. Última actualización: **{source['Última actualización'] or 'sin registrar'}**. "
            f"Próxima esperada: **{source['Próxima esperada'] or 'no calculable'}**. "
            f"Modelo/versión: **{source['Modelo del dataset'] or 'No documentado'}**."
        )
        return {"text": text, "table": [source]}

    if any(x in p for x in ["qué scraping toca", "que scraping toca", "fuera de intervalo", "vencid", "retrasad"]):
        overdue = get_overdue_sources()
        if not overdue:
            return {"text": "No hay fuentes activas fuera de intervalo en este momento."}
        return {"text": f"Hay **{len(overdue)} fuente(s)** que requieren ejecución o revisión.", "table": overdue}

    if any(x in p for x in ["base de datos", "sqlite", "qué base", "que base"]):
        db = get_database_health()
        tables = get_database_tables()
        return {
            "text": f"La aplicación usa **{db['engine']}** en `{db['path']}`. Integridad: **{db['integrity']}**. Contiene **{len(tables)} tablas**.",
            "table": tables,
        }

    if "tabla" in p:
        tables = get_database_tables()
        return {"text": f"SQLite contiene **{len(tables)} tablas de aplicación**.", "table": tables}

    if any(x in p for x in ["últimas actualizaciones", "ultimas actualizaciones", "última ejecución", "ultima ejecucion", "historial"]):
        runs = get_recent_updates(10)
        return {"text": f"Estas son las **{len(runs)} ejecuciones más recientes** registradas en `update_runs`.", "table": runs}

    if any(x in p for x in ["último error", "ultimo error", "error más reciente", "error mas reciente"]):
        error = get_last_error()
        if not error:
            return {"text": "No existe ningún error de actualización registrado en `update_runs`."}
        return {"text": f"El último error corresponde a **{error['source_name']}** ({error['started_at']}): {error['error_message']}"}

    if any(x in p for x in ["ha cambiado", "cambio de filas", "variación", "variacion"]):
        if source:
            change = get_row_count_change(source["source_id"])
            if not change or change["change_pct"] is None:
                return {"text": f"Todavía no hay dos ejecuciones comparables para calcular la variación de **{source['Dataset']}**."}
            return {"text": f"{source['Dataset']}: {change['previous']:,} → {change['current']:,} filas (**{change['change_pct']:+.1%}**)."}
        return {"text": "Indica la fuente que quieres comparar, por ejemplo: “¿Ha cambiado el número de filas de conectividad?”"}

    if any(x in p for x in ["tracking", "instrumentación", "instrumentacion"]):
        rows = instrumentation_status()
        pending = sum(1 for r in rows if r["estado"] != "disponible")
        return {"text": f"El tracking tiene **{pending} KPI(s) pendientes de instrumentar** según los datos actuales.", "table": rows}

    if any(x in p for x in ["web", "ctr", "conversión", "conversion", "sesiones", "reservas", "rendimiento"]):
        m = get_dashboard_metrics()
        ctr = f"{m['ctr']:.1%}" if m["ctr"] is not None else "pendiente de instrumentar"
        conversion = f"{m['conversion']:.1%}" if m["conversion"] is not None else "pendiente de instrumentar"
        return {
            "text": f"Control Web: **{m['sessions']} sesiones**, **{m['impressions']} impresiones**, **{m['clicks']} clics**, CTR **{ctr}**, **{m['bookings']} reservas** y conversión **{conversion}**.",
            "metrics": {
                "Sesiones": m["sessions"],
                "Impresiones": m["impressions"],
                "Clics": m["clicks"],
                "Reservas": m["bookings"],
            },
        }

    if "modelo" in p or "dataset" in p:
        sources = get_source_health()
        rows = [{"Dataset": s["Dataset"], "Modelo / versión": s["Modelo del dataset"], "Método": s["Método actual"]} for s in sources]
        return {"text": "Estos son los modelos/versiones documentados para las fuentes actuales. Cuando la fuente no lo declara, se mantiene como **No documentado**.", "table": rows}

    return {
        "text": (
            "Puedo consultar el estado real del sistema. Prueba con: **¿Está todo actualizado?**, **¿Qué fuentes tienen problemas?**, "
            "**¿Cuándo se actualizó el clima?**, **¿Qué tablas contiene SQLite?**, **¿Cuál fue el último error?** o **¿Cómo está funcionando la web?**"
        )
    }
