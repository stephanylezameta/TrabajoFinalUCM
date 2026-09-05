from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any
import uuid

from config import DATA_DIR, DB_PATH, RAW_DIR
from database.connection import db_session
from services.import_service import (
    import_climate_csv,
    import_connectivity_csv,
    import_country_indicators_csv,
)
from services.reference_service import (
    import_destinations_from_proposal_html,
    import_products_from_experience_html,
)

# Cadencias operativas iniciales. Son configuración del proyecto, no metadatos
# presentes en los ficheros fuente, y pueden cambiarse desde la propia app.
DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "source_id": "products_html",
        "display_name": "Catálogo / ofertas HTML",
        "source_file": "tui_experiencia_final.html",
        "target_table": "products",
        "source_type": "HTML",
        "provider": "HTML de referencia local",
        "update_method": "HTML import",
        "refresh_interval_hours": 6,
        "dataset_model": "No documentado en la fuente",
        "scraper_script": "Pendiente de conectar scraper web",
        "automation_mode": "Manual",
        "notes": "La carga actual parsea tarjetas .offer sin ejecutar JavaScript.",
    },
    {
        "source_id": "destinations_tdrs",
        "display_name": "Factores de destinos TDRS",
        "source_file": "propuesta_7.html",
        "target_table": "destinations",
        "source_type": "HTML",
        "provider": "Propuesta 7 local",
        "update_method": "HTML import",
        "refresh_interval_hours": 168,
        "dataset_model": "TDRS CSV v3.1 · 5 señales CSV + KNN k=3",
        "scraper_script": "No aplica actualmente; fuente HTML local",
        "automation_mode": "Manual",
        "notes": "El HTML mantiene el roster/base de destinos. El ranking TDRS CSV v2 utiliza clima, conectividad y seguridad/sanidad desde los CSV.",
    },
    {
        "source_id": "climate",
        "display_name": "Clima por destino",
        "source_file": "clima_todos_los_destinos.csv",
        "target_table": "climate_observations",
        "source_type": "CSV",
        "provider": "Dataset suministrado",
        "update_method": "CSV import",
        "refresh_interval_hours": 24,
        "dataset_model": "No documentado en el CSV",
        "scraper_script": "Pendiente de conectar scraper/API de clima",
        "automation_mode": "Manual",
        "notes": "Cadencia diaria configurada como objetivo operativo inicial.",
    },
    {
        "source_id": "connectivity",
        "display_name": "Conectividad y pasajeros",
        "source_file": "conectividad_y_pasajeros_2025.csv",
        "target_table": "connectivity_stats",
        "source_type": "CSV",
        "provider": "Dataset suministrado",
        "update_method": "CSV import",
        "refresh_interval_hours": 168,
        "dataset_model": "No documentado en el CSV",
        "scraper_script": "Pendiente de conectar scraper/API de conectividad",
        "automation_mode": "Manual",
        "notes": "Cadencia semanal configurada como objetivo operativo inicial.",
    },
    {
        "source_id": "country_indicators",
        "display_name": "Seguridad y sanidad",
        "source_file": "seguridad_y_sanidad_banco_mundial.csv",
        "target_table": "country_indicators",
        "source_type": "CSV",
        "provider": "Banco Mundial (según nombre del fichero)",
        "update_method": "CSV import",
        "refresh_interval_hours": 720,
        "dataset_model": "No documentado en el CSV",
        "scraper_script": "Pendiente de conectar API/fuente de indicadores",
        "automation_mode": "Manual",
        "notes": "Cadencia mensual configurada como objetivo operativo inicial.",
    },
]

TABLE_ROLES = {
    "products": "Catálogo normalizado de ofertas/paquetes",
    "sessions": "Sesiones de navegación",
    "events": "Tracking de interacción",
    "bookings": "Reservas/conversiones",
    "destinations": "Factores base del ranking TDRS",
    "climate_observations": "Series mensuales de clima por destino",
    "connectivity_stats": "Conectividad aérea y pasajeros",
    "country_indicators": "Indicadores de seguridad/sanidad por país",
    "imports": "Histórico de importaciones",
    "data_sources": "Registro operativo de fuentes y cadencias",
    "update_runs": "Histórico operativo de actualizaciones/scraping",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_sqlite_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    value = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def seed_data_sources() -> None:
    sql = """
    INSERT OR IGNORE INTO data_sources(
        source_id,display_name,source_file,target_table,source_type,provider,
        update_method,refresh_interval_hours,dataset_model,scraper_script,
        automation_mode,enabled,notes
    ) VALUES(
        :source_id,:display_name,:source_file,:target_table,:source_type,:provider,
        :update_method,:refresh_interval_hours,:dataset_model,:scraper_script,
        :automation_mode,1,:notes
    )
    """
    with db_session() as conn:
        conn.executemany(sql, DEFAULT_SOURCES)
        conn.execute(
            """
            UPDATE data_sources
               SET dataset_model='TDRS CSV v3.1 · 5 señales CSV + KNN k=3', updated_at=CURRENT_TIMESTAMP
             WHERE source_id='destinations_tdrs'
               AND (dataset_model IS NULL OR dataset_model LIKE 'TDRS CSV v2%' OR dataset_model LIKE 'TDRS CSV v3%')
            """
        )
        # Migra app.db creadas con versiones anteriores sin sobrescribir configuración del usuario.
        for source in DEFAULT_SOURCES:
            current = conn.execute(
                "SELECT last_success_at FROM data_sources WHERE source_id=?", (source["source_id"],)
            ).fetchone()
            if current and current[0]:
                continue
            imp = conn.execute(
                "SELECT imported_at,row_count,status FROM imports WHERE source_name=? ORDER BY imported_at DESC LIMIT 1",
                (source["source_file"],),
            ).fetchone()
            if imp:
                conn.execute(
                    "UPDATE data_sources SET last_success_at=?,last_status=?,last_row_count=? WHERE source_id=?",
                    (imp[0], "ok" if (imp[2] or "ok") == "ok" else imp[2], imp[1], source["source_id"]),
                )
                continue
            table = source["target_table"]
            columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            if "updated_at" in columns:
                last = conn.execute(f'SELECT MAX(updated_at),COUNT(*) FROM "{table}"').fetchone()
                if last and last[0] and last[1]:
                    conn.execute(
                        "UPDATE data_sources SET last_success_at=?,last_status='ok',last_row_count=? WHERE source_id=?",
                        (last[0], last[1], source["source_id"]),
                    )


def _row_count(table: str) -> int:
    with db_session() as conn:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def update_source_config(
    source_id: str,
    refresh_interval_hours: int,
    dataset_model: str,
    notes: str | None = None,
    enabled: bool = True,
) -> None:
    if refresh_interval_hours < 1:
        raise ValueError("El intervalo debe ser de al menos 1 hora.")
    with db_session() as conn:
        conn.execute(
            """
            UPDATE data_sources
               SET refresh_interval_hours=?, dataset_model=?, notes=?, enabled=?, updated_at=CURRENT_TIMESTAMP
             WHERE source_id=?
            """,
            (int(refresh_interval_hours), dataset_model.strip() or "No documentado", notes, int(enabled), source_id),
        )


def _start_run(source_id: str, trigger: str, rows_before: int | None) -> str:
    run_id = str(uuid.uuid4())
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO update_runs(run_id,source_id,status,rows_before,trigger,metadata)
            VALUES(?,?, 'running', ?, ?, ?)
            """,
            (run_id, source_id, rows_before, trigger, json.dumps({"engine": "local-import"})),
        )
        conn.execute(
            "UPDATE data_sources SET last_attempt_at=CURRENT_TIMESTAMP,last_status='running',last_error=NULL,updated_at=CURRENT_TIMESTAMP WHERE source_id=?",
            (source_id,),
        )
    return run_id


def _finish_run(
    run_id: str,
    source_id: str,
    status: str,
    started_perf: float,
    rows_before: int | None,
    rows_after: int | None,
    processed: int | None = None,
    error: str | None = None,
) -> None:
    duration = round(perf_counter() - started_perf, 4)
    inserted = None
    deleted = None
    updated = None
    if rows_before is not None and rows_after is not None:
        delta = rows_after - rows_before
        inserted = max(delta, 0)
        deleted = max(-delta, 0)
        # Los importadores actuales son UPSERT. Las filas procesadas que no aumentan el total
        # se registran como potencialmente actualizadas, no como inserciones inventadas.
        if processed is not None:
            updated = max(int(processed) - inserted, 0)
    with db_session() as conn:
        conn.execute(
            """
            UPDATE update_runs
               SET finished_at=CURRENT_TIMESTAMP,status=?,rows_after=?,rows_inserted=?,rows_updated=?,rows_deleted=?,
                   error_message=?,duration_seconds=?
             WHERE run_id=?
            """,
            (status, rows_after, inserted, updated, deleted, error, duration, run_id),
        )
        if status in {"success", "warning"}:
            conn.execute(
                """
                UPDATE data_sources
                   SET last_success_at=CURRENT_TIMESTAMP,last_status='ok',last_row_count=?,last_error=NULL,updated_at=CURRENT_TIMESTAMP
                 WHERE source_id=?
                """,
                (rows_after, source_id),
            )
        else:
            conn.execute(
                """
                UPDATE data_sources
                   SET last_status='error',last_error=?,updated_at=CURRENT_TIMESTAMP
                 WHERE source_id=?
                """,
                (error, source_id),
            )


def _record_html_import(source_name: str, source_type: str, row_count: int, details: dict[str, Any]) -> None:
    with db_session() as conn:
        conn.execute(
            "INSERT INTO imports(import_id,source_name,source_type,row_count,status,details) VALUES(?,?,?,?,?,?)",
            (str(uuid.uuid4()), source_name, source_type, row_count, "ok", json.dumps(details, ensure_ascii=False, default=str)),
        )


def refresh_source(source_id: str, raw_dir: Path = RAW_DIR, trigger: str = "manual") -> dict[str, Any]:
    seed_data_sources()
    with db_session() as conn:
        row = conn.execute("SELECT * FROM data_sources WHERE source_id=?", (source_id,)).fetchone()
    if row is None:
        raise KeyError(f"Fuente desconocida: {source_id}")
    source = dict(row)
    path = raw_dir / source["source_file"]
    try:
        rows_before = _row_count(source["target_table"])
    except Exception:
        rows_before = None
    started_perf = perf_counter()
    run_id = _start_run(source_id, trigger, rows_before)
    try:
        if not path.exists():
            raise FileNotFoundError(f"No existe el fichero fuente: {path}")
        if source_id == "products_html":
            count = import_products_from_experience_html(path)
            _record_html_import(path.name, "products_html", count, {"path": str(path), "method": source["update_method"]})
        elif source_id == "destinations_tdrs":
            count = import_destinations_from_proposal_html(path)
            _record_html_import(path.name, "destinations_html", count, {"path": str(path), "method": source["update_method"]})
        elif source_id == "climate":
            count = import_climate_csv(path)
        elif source_id == "connectivity":
            count = import_connectivity_csv(path)
        elif source_id == "country_indicators":
            count = import_country_indicators_csv(path)
        else:
            raise NotImplementedError(f"No hay importador asociado a {source_id}")
        current_rows = _row_count(source["target_table"])
        _finish_run(run_id, source_id, "success", started_perf, rows_before, current_rows, processed=count)
        return {
            "run_id": run_id,
            "source_id": source_id,
            "processed": count,
            "rows_before": rows_before,
            "rows_in_table": current_rows,
            "status": "success",
        }
    except Exception as exc:
        _finish_run(run_id, source_id, "error", started_perf, rows_before, rows_before, error=str(exc))
        raise


def refresh_all_sources(raw_dir: Path = RAW_DIR, trigger: str = "manual") -> list[dict[str, Any]]:
    seed_data_sources()
    results: list[dict[str, Any]] = []
    for source in DEFAULT_SOURCES:
        try:
            results.append(refresh_source(source["source_id"], raw_dir=raw_dir, trigger=trigger))
        except Exception as exc:
            results.append({"source_id": source["source_id"], "status": "error", "error": str(exc)})
    return results


def bootstrap_missing_sources(raw_dir: Path = RAW_DIR) -> None:
    seed_data_sources()
    with db_session() as conn:
        sources = [dict(r) for r in conn.execute("SELECT * FROM data_sources WHERE enabled=1 ORDER BY source_id")]
    for source in sources:
        try:
            if _row_count(source["target_table"]) == 0 and (raw_dir / source["source_file"]).exists():
                refresh_source(source["source_id"], raw_dir=raw_dir, trigger="startup")
        except Exception:
            # El panel operativo mostrará el error; el arranque de Streamlit no queda bloqueado.
            continue


def get_database_files() -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    candidates = set(DATA_DIR.rglob("*.db")) | set(DATA_DIR.rglob("*.sqlite")) | set(DATA_DIR.rglob("*.sqlite3"))
    for path in sorted(candidates):
        try:
            stat = path.stat()
            integrity = None
            if path.resolve() == Path(DB_PATH).resolve():
                try:
                    integrity = get_database_file_info()["integrity"]
                except Exception as exc:
                    integrity = f"error: {exc}"
            files.append({
                "Base de datos": path.name,
                "Ruta": str(path),
                "Motor": "SQLite",
                "Tamaño MB": round(stat.st_size / 1024 / 1024, 3),
                "Última modificación": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "Integridad": integrity or "OK",
            })
        except OSError:
            continue
    return files


def get_database_file_info() -> dict[str, Any]:
    path = Path(DB_PATH)
    exists = path.exists()
    stat = path.stat() if exists else None
    integrity = "Sin base de datos"
    if exists:
        try:
            with db_session() as conn:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        except Exception as exc:
            integrity = f"error: {exc}"
    return {
        "path": str(path),
        "exists": exists,
        "engine": "SQLite",
        "size_mb": round(stat.st_size / 1024 / 1024, 3) if stat else 0,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else None,
        "integrity": integrity,
    }


def get_database_health() -> dict[str, Any]:
    return get_database_file_info()


def get_database_tables() -> list[dict[str, Any]]:
    with db_session() as conn:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        out = []
        for name in names:
            n = int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            last_update = None
            columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{name}")')}
            for candidate in ("updated_at", "finished_at", "imported_at", "timestamp", "started_at", "created_at", "last_success_at"):
                if candidate in columns:
                    last_update = conn.execute(f'SELECT MAX("{candidate}") FROM "{name}"').fetchone()[0]
                    if last_update:
                        break
            if not last_update and name not in {"data_sources", "update_runs"}:
                registry = conn.execute(
                    "SELECT MAX(last_success_at) FROM data_sources WHERE target_table=?", (name,)
                ).fetchone()
                last_update = registry[0] if registry else None
            out.append({
                "Tabla / dataset": name,
                "Filas": n,
                "Última escritura": last_update,
                "Función": TABLE_ROLES.get(name, "Tabla de aplicación"),
            })
    return out


def get_table_stats() -> list[dict[str, Any]]:
    return get_database_tables()


def _coverage_for_source(source_id: str) -> str | None:
    with db_session() as conn:
        if source_id == "climate":
            row = conn.execute("SELECT MIN(year_month),MAX(year_month) FROM climate_observations").fetchone()
            return f"{row[0]} → {row[1]}" if row and row[0] else None
        if source_id == "connectivity":
            return "Snapshot 2025"
        if source_id == "country_indicators":
            return f"{_row_count('country_indicators')} países/áreas"
        if source_id == "products_html":
            return f"{_row_count('products')} ofertas"
        if source_id == "destinations_tdrs":
            return f"{_row_count('destinations')} destinos"
    return None


def get_source_health() -> list[dict[str, Any]]:
    seed_data_sources()
    now = _utcnow()
    with db_session() as conn:
        sources = [dict(r) for r in conn.execute("SELECT * FROM data_sources ORDER BY display_name")]
    out = []
    for source in sources:
        last = _parse_sqlite_ts(source.get("last_success_at"))
        interval = int(source.get("refresh_interval_hours") or 0)
        next_due = last + timedelta(hours=interval) if last and interval else None
        source_path = RAW_DIR / source["source_file"] if source.get("source_file") else None
        file_ok = bool(source_path and source_path.exists())
        overdue_hours = max((now - next_due).total_seconds() / 3600, 0) if next_due and now > next_due else 0.0
        age_hours = max((now - last).total_seconds() / 3600, 0) if last else None
        overdue_ratio = (age_hours / interval) if age_hours is not None and interval else None
        if not source.get("enabled"):
            health = "Desactivada"
        elif source.get("last_status") == "error":
            health = "ERROR"
        elif not file_ok:
            health = "Falta fuente"
        elif last is None:
            health = "Sin ejecutar"
        elif next_due and now > next_due:
            health = "Atrasada"
        else:
            health = "OK"
        current_rows = 0
        try:
            current_rows = _row_count(source["target_table"])
        except Exception:
            pass
        out.append({
            "source_id": source["source_id"],
            "Estado": health,
            "Dataset": source["display_name"],
            "Tabla destino": source["target_table"],
            "Fuente": source.get("provider"),
            "Fichero / endpoint actual": source.get("source_file"),
            "Tipo": source.get("source_type"),
            "Método actual": source.get("update_method"),
            "Automatización": source.get("automation_mode"),
            "Intervalo objetivo": format_interval(interval),
            "interval_hours": interval,
            "Última actualización": source.get("last_success_at"),
            "Próxima esperada": _iso(next_due),
            "Horas de retraso": round(overdue_hours, 1),
            "Ratio intervalo": round(overdue_ratio, 2) if overdue_ratio is not None else None,
            "Filas actuales": current_rows,
            "Cobertura": _coverage_for_source(source["source_id"]),
            "Modelo del dataset": source.get("dataset_model"),
            "Scraper / conector": source.get("scraper_script"),
            "Último error": source.get("last_error"),
            "Notas": source.get("notes"),
            "enabled": bool(source.get("enabled")),
        })
    return out


def get_data_sources_status() -> list[dict[str, Any]]:
    return get_source_health()


def get_source_status(source_id: str) -> dict[str, Any] | None:
    return next((s for s in get_source_health() if s["source_id"] == source_id), None)


def get_overdue_sources() -> list[dict[str, Any]]:
    return [s for s in get_source_health() if s["enabled"] and s["Estado"] in {"Atrasada", "ERROR", "Falta fuente", "Sin ejecutar"}]


def get_import_history(limit: int = 100) -> list[dict[str, Any]]:
    with db_session() as conn:
        return [dict(r) for r in conn.execute(
            """
            SELECT imported_at,source_name,source_type,row_count,status,details
              FROM imports
             ORDER BY imported_at DESC
             LIMIT ?
            """,
            (int(limit),),
        )]


def get_update_runs(
    limit: int = 100,
    source_id: str | None = None,
    status: str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if source_id and source_id != "Todas":
        clauses.append("u.source_id=?")
        params.append(source_id)
    if status and status != "Todos":
        clauses.append("u.status=?")
        params.append(status)
    if start_date:
        clauses.append("date(u.started_at) >= date(?)")
        params.append(str(start_date))
    if end_date:
        clauses.append("date(u.started_at) <= date(?)")
        params.append(str(end_date))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(int(limit))
    with db_session() as conn:
        rows = conn.execute(
            f"""
            SELECT u.run_id,u.source_id,s.display_name AS source_name,u.started_at,u.finished_at,u.status,
                   u.rows_before,u.rows_after,u.rows_inserted,u.rows_updated,u.rows_deleted,
                   u.error_message,u.duration_seconds,u.trigger,u.metadata
              FROM update_runs u
              LEFT JOIN data_sources s ON s.source_id=u.source_id
              {where}
             ORDER BY u.started_at DESC
             LIMIT ?
            """,
            params,
        )
        return [dict(r) for r in rows]


def get_recent_updates(limit: int = 10) -> list[dict[str, Any]]:
    return get_update_runs(limit=limit)


def get_last_error() -> dict[str, Any] | None:
    with db_session() as conn:
        row = conn.execute(
            """
            SELECT u.source_id,s.display_name AS source_name,u.started_at,u.error_message,u.trigger
              FROM update_runs u LEFT JOIN data_sources s ON s.source_id=u.source_id
             WHERE u.status='error'
             ORDER BY u.started_at DESC LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None


def get_row_count_change(source_id: str) -> dict[str, Any] | None:
    with db_session() as conn:
        rows = [dict(r) for r in conn.execute(
            """
            SELECT started_at,rows_before,rows_after
              FROM update_runs
             WHERE source_id=? AND status IN ('success','warning') AND rows_after IS NOT NULL
             ORDER BY started_at DESC LIMIT 2
            """,
            (source_id,),
        )]
    if not rows:
        return None
    latest = rows[0]
    baseline = rows[1]["rows_after"] if len(rows) > 1 else latest.get("rows_before")
    current = latest.get("rows_after")
    change = None if baseline in (None, 0) or current is None else (current - baseline) / baseline
    return {
        "source_id": source_id,
        "current": current,
        "previous": baseline,
        "change_pct": change,
        "started_at": latest.get("started_at"),
    }


def format_interval(hours: int | None) -> str:
    if not hours:
        return "Manual"
    hours = int(hours)
    if hours % 720 == 0:
        months = hours // 720
        return f"Cada {months} mes" + ("es" if months != 1 else "")
    if hours % 168 == 0:
        weeks = hours // 168
        return f"Cada {weeks} semana" + ("s" if weeks != 1 else "")
    if hours % 24 == 0:
        days = hours // 24
        return f"Cada {days} día" + ("s" if days != 1 else "")
    return f"Cada {hours} h"
