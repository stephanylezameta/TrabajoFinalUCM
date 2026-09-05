from __future__ import annotations

from typing import Any

from database.connection import db_session
from services.data_control_service import (
    get_database_health,
    get_last_error,
    get_recent_updates,
    get_source_health,
    get_update_runs,
)

LEVEL_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}


def _alert(level: str, title: str, message: str, source_id: str | None = None, action: str | None = None) -> dict[str, Any]:
    return {
        "level": level,
        "title": title,
        "message": message,
        "source_id": source_id,
        "action": action,
    }


def evaluate_database_integrity() -> list[dict[str, Any]]:
    db = get_database_health()
    if not db["exists"]:
        return [_alert("CRITICAL", "Base de datos no disponible", "No se encuentra el fichero SQLite configurado.", action="Ejecutar scripts/build_model.py")]
    if db["integrity"] != "ok":
        return [_alert("CRITICAL", "Integridad SQLite", f"PRAGMA integrity_check devuelve: {db['integrity']}", action="Revisar o reconstruir la base de datos")]
    return []


def evaluate_source_freshness() -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for source in get_source_health():
        if not source["enabled"]:
            continue
        sid = source["source_id"]
        name = source["Dataset"]
        state = source["Estado"]
        ratio = source.get("Ratio intervalo")
        if state == "Falta fuente":
            alerts.append(_alert("CRITICAL", f"Fuente no disponible · {name}", f"No se encuentra {source['Fichero / endpoint actual']}.", sid, "Restaurar la fuente o revisar la ruta"))
        elif state == "Sin ejecutar":
            alerts.append(_alert("WARNING", f"Fuente sin ejecutar · {name}", "No existe una actualización satisfactoria registrada.", sid, "Ejecutar la actualización"))
        elif state == "Atrasada":
            level = "CRITICAL" if ratio is not None and ratio > 2 else "WARNING"
            alerts.append(_alert(level, f"Actualización retrasada · {name}", f"La fuente supera su intervalo de {source['Intervalo objetivo']}. Retraso: {source['Horas de retraso']} h.", sid, "Actualizar la fuente"))
    return alerts


def evaluate_scraping_errors() -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    sources = get_source_health()
    for source in sources:
        if not source["enabled"] or source["Estado"] != "ERROR":
            continue
        recent = get_update_runs(limit=3, source_id=source["source_id"])
        consecutive = 0
        for run in recent:
            if run["status"] == "error":
                consecutive += 1
            else:
                break
        level = "CRITICAL" if consecutive >= 2 else "WARNING"
        error = source.get("Último error") or "Error no detallado"
        alerts.append(_alert(level, f"Error de actualización · {source['Dataset']}", error, source["source_id"], "Revisar la última ejecución y volver a lanzar la fuente"))
    return alerts


def evaluate_empty_datasets() -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for source in get_source_health():
        if source["enabled"] and int(source.get("Filas actuales") or 0) == 0:
            alerts.append(_alert("CRITICAL", f"Dataset vacío · {source['Dataset']}", f"La tabla {source['Tabla destino']} no contiene registros.", source["source_id"], "Reimportar la fuente"))
    return alerts


def evaluate_row_count_changes() -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    with db_session() as conn:
        source_ids = [r[0] for r in conn.execute("SELECT source_id FROM data_sources WHERE enabled=1")]
        for source_id in source_ids:
            rows = conn.execute(
                """
                SELECT rows_after FROM update_runs
                 WHERE source_id=? AND status IN ('success','warning') AND rows_after IS NOT NULL
                 ORDER BY started_at DESC LIMIT 2
                """,
                (source_id,),
            ).fetchall()
            if len(rows) < 2 or rows[1][0] in (None, 0):
                continue
            current, previous = int(rows[0][0]), int(rows[1][0])
            change = (current - previous) / previous
            if change <= -0.50:
                level = "CRITICAL"
            elif change <= -0.20:
                level = "WARNING"
            else:
                continue
            name_row = conn.execute("SELECT display_name FROM data_sources WHERE source_id=?", (source_id,)).fetchone()
            name = name_row[0] if name_row else source_id
            alerts.append(_alert(level, f"Caída de volumen · {name}", f"Las filas han pasado de {previous:,} a {current:,} ({change:.0%}).", source_id, "Revisar fuente, esquema y filtros de ingesta"))
    return alerts


def evaluate_null_anomalies() -> list[dict[str, Any]]:
    # Solo campos estructuralmente imprescindibles; evita generar falsos positivos
    # por columnas opcionales del catálogo.
    checks = {
        "products_html": ("products", ["product_id", "title"]),
        "destinations_tdrs": ("destinations", ["destination_id", "name"]),
        "climate": ("climate_observations", ["destination_name", "year_month"]),
        "connectivity": ("connectivity_stats", ["destination_name"]),
        "country_indicators": ("country_indicators", ["iso", "country_name"]),
    }
    alerts: list[dict[str, Any]] = []
    sources = {s["source_id"]: s for s in get_source_health()}
    with db_session() as conn:
        for sid, (table, fields) in checks.items():
            total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            if not total:
                continue
            for field in fields:
                nulls = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{field}" IS NULL OR TRIM(CAST("{field}" AS TEXT))=""').fetchone()[0]
                ratio = nulls / total
                if ratio > 0.05:
                    source = sources.get(sid, {})
                    alerts.append(_alert("WARNING", f"Nulos en campo clave · {source.get('Dataset', sid)}", f"{field}: {nulls}/{total} registros ({ratio:.1%}).", sid, "Revisar esquema y normalización"))
    return alerts


def get_alerts(include_ok: bool = True) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    alerts.extend(evaluate_database_integrity())
    alerts.extend(evaluate_empty_datasets())
    alerts.extend(evaluate_scraping_errors())
    alerts.extend(evaluate_source_freshness())
    alerts.extend(evaluate_row_count_changes())
    alerts.extend(evaluate_null_anomalies())

    # Evita duplicados de la misma causa/fuente generados por reglas solapadas.
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for item in alerts:
        key = (item["title"], item.get("source_id"))
        if key not in seen:
            deduped.append(item)
            seen.add(key)
    alerts = sorted(deduped, key=lambda x: LEVEL_ORDER.get(x["level"], 9))
    if not alerts and include_ok:
        alerts.append(_alert("OK", "Sistema sin alertas operativas", "Todas las fuentes activas están dentro de los controles disponibles y SQLite responde correctamente."))
    return alerts


def get_active_alerts() -> list[dict[str, Any]]:
    return [a for a in get_alerts(include_ok=False) if a["level"] in {"CRITICAL", "WARNING", "INFO"}]


def get_system_status() -> dict[str, Any]:
    sources = get_source_health()
    active = [s for s in sources if s["enabled"]]
    alerts = get_alerts(include_ok=False)
    critical = sum(1 for a in alerts if a["level"] == "CRITICAL")
    warnings = sum(1 for a in alerts if a["level"] == "WARNING")
    healthy = sum(1 for s in active if s["Estado"] == "OK")
    overdue = sum(1 for s in active if s["Estado"] == "Atrasada")
    db = get_database_health()
    successful_dates = [s.get("Última actualización") for s in active if s.get("Última actualización")]
    last_update = max(successful_dates) if successful_dates else None
    total_rows = sum(int(s.get("Filas actuales") or 0) for s in active)
    recent = get_recent_updates(1)
    if critical:
        status = "critical"
    elif warnings:
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "active_sources": len(active),
        "healthy_sources": healthy,
        "overdue_sources": overdue,
        "critical_alerts": critical,
        "warnings": warnings,
        "open_alerts": critical + warnings,
        "last_update": last_update,
        "database_integrity": db["integrity"],
        "total_rows": total_rows,
        "last_run": recent[0] if recent else None,
        "last_error": get_last_error(),
    }
