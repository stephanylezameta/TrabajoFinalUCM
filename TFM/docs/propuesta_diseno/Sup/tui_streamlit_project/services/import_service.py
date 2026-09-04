from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from pathlib import Path
from typing import Any, BinaryIO

import pandas as pd

from database.connection import db_session
from database.repositories import ProductRepository
from utils.text import normalize_text, slugify

PRODUCT_ALIASES = {
    "product_id": ["product_id", "id_producto", "producto_id", "id", "codigo"],
    "title": ["title", "titulo", "nombre", "producto", "paquete", "viaje"],
    "destination": ["destination", "destino", "lugar", "ciudad"],
    "hotel": ["hotel", "alojamiento"],
    "price": ["price", "precio", "precio_eur", "importe"],
    "currency": ["currency", "moneda"],
    "duration_days": ["duration_days", "duracion_dias", "dias"],
    "nights": ["nights", "noches"],
    "departure_date": ["departure_date", "fecha_salida", "salida"],
    "return_date": ["return_date", "fecha_regreso", "regreso", "fecha_vuelta"],
    "rating": ["rating", "valoracion", "puntuacion"],
    "board_basis": ["board_basis", "regimen", "pension"],
    "transport": ["transport", "transporte"],
    "airline": ["airline", "aerolinea"],
    "availability": ["availability", "disponibilidad", "plazas"],
    "discount": ["discount", "descuento"],
    "description": ["description", "descripcion"],
    "image_url": ["image_url", "imagen", "url_imagen"],
    "detail_url": ["detail_url", "url", "url_detalle", "enlace"],
}


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [normalize_text(c).replace(" ", "_") for c in out.columns]
    return out


def read_csv_auto(source: str | Path | bytes | BinaryIO) -> tuple[pd.DataFrame, dict[str, Any]]:
    if isinstance(source, (str, Path)):
        raw = Path(source).read_bytes()
        source_name = Path(source).name
    elif isinstance(source, bytes):
        raw, source_name = source, "uploaded.csv"
    else:
        raw, source_name = source.read(), getattr(source, "name", "uploaded.csv")
    enc = "utf-8-sig"
    for candidate in ["utf-8-sig", "utf-8", "cp1252", "latin1"]:
        try:
            text = raw.decode(candidate)
            enc = candidate
            break
        except UnicodeDecodeError:
            continue
    sample = text[:10000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        sep = dialect.delimiter
    except csv.Error:
        sep = ","
    df = pd.read_csv(io.StringIO(text), sep=sep)
    df = _clean_columns(df)
    return df, {"source_name": source_name, "encoding": enc, "separator": sep, "rows": len(df)}


def analyze_columns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    mapped = build_column_mapping(df.columns)
    reverse = {v: k for k, v in mapped.items()}
    priority = {"title", "destination", "hotel", "price", "currency", "duration_days", "nights", "departure_date", "return_date", "rating", "board_basis", "transport", "airline", "availability", "discount", "description", "image_url", "detail_url"}
    for col in df.columns:
        null_pct = float(df[col].isna().mean() * 100)
        model_field = reverse.get(col)
        score = 85 if model_field in priority else 30
        reason = "Campo prioritario para decisión de compra" if model_field in priority else "Se conserva en extra_data"
        if any(t in col for t in ["uuid", "hash", "embedding", "debug", "raw"]):
            score -= 40
            reason = "Campo técnico penalizado"
        if null_pct > 70:
            score -= 20
            reason += "; muchos nulos"
        rows.append({
            "columna": col,
            "rol_detectado": model_field or "extra_data",
            "score_utilidad": max(0, min(100, score)),
            "motivo": reason,
            "tipo": str(df[col].dtype),
            "pct_nulos": round(null_pct, 1),
            "valores_unicos": int(df[col].nunique(dropna=True)),
            "campo_modelo": model_field,
            "estado_importacion": "mapeado" if model_field else "extra_data",
        })
    return pd.DataFrame(rows).sort_values(["score_utilidad", "columna"], ascending=[False, True])


def build_column_mapping(columns) -> dict[str, str]:
    cols = {normalize_text(c).replace(" ", "_"): c for c in columns}
    mapping = {}
    for field, aliases in PRODUCT_ALIASES.items():
        for alias in aliases:
            key = normalize_text(alias).replace(" ", "_")
            if key in cols:
                mapping[field] = cols[key]
                break
    return mapping


def _json_value(v):
    if pd.isna(v):
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def import_products_from_csv(source: str | Path | bytes | BinaryIO) -> dict[str, Any]:
    df, info = read_csv_auto(source)
    mapping = build_column_mapping(df.columns)
    if not (mapping.get("title") or mapping.get("destination")):
        raise ValueError("No se detecta un CSV de productos: falta al menos título/nombre o destino.")
    known_cols = set(mapping.values())
    products = []
    for idx, row in df.iterrows():
        def val(field):
            col = mapping.get(field)
            return _json_value(row[col]) if col else None
        natural = val("product_id") or f"{val('title')}|{val('destination')}|{idx}"
        pid = str(natural) if val("product_id") is not None else "csv-" + hashlib.sha1(str(natural).encode("utf-8")).hexdigest()[:14]
        extra = {c: _json_value(row[c]) for c in df.columns if c not in known_cols}
        products.append({
            "product_id": pid,
            "title": val("title"), "destination": val("destination"), "hotel": val("hotel"),
            "price": val("price"), "currency": val("currency") or "EUR",
            "duration_days": val("duration_days"), "nights": val("nights"),
            "departure_date": val("departure_date"), "return_date": val("return_date"),
            "rating": val("rating"), "board_basis": val("board_basis"), "transport": val("transport"),
            "airline": val("airline"), "availability": val("availability"), "discount": val("discount"),
            "description": val("description"), "image_url": val("image_url"), "detail_url": val("detail_url"),
            "source": info["source_name"], "extra_data": json.dumps(extra, ensure_ascii=False, default=str),
        })
    count = ProductRepository().upsert_many(products)
    _record_import(info["source_name"], "products", count, info)
    return {**info, "imported": count, "mapping": mapping, "column_analysis": analyze_columns(df)}


def _record_import(source_name: str, source_type: str, row_count: int, details: dict[str, Any], status: str = "ok") -> None:
    with db_session() as conn:
        conn.execute("INSERT INTO imports(import_id,source_name,source_type,row_count,status,details) VALUES(?,?,?,?,?,?)",
                     (str(uuid.uuid4()), source_name, source_type, row_count, status, json.dumps(details, ensure_ascii=False, default=str)))


def import_climate_csv(path: str | Path) -> int:
    df, info = read_csv_auto(path)
    required = {"lugar", "year_month"}
    if not required.issubset(df.columns):
        raise ValueError("El CSV de clima no contiene lugar/year_month.")
    sql = """
    INSERT INTO climate_observations(destination_name,year_month,air_temp_c,water_temp_c,precipitation_mm,rain_days,sun_hours,humidity_pct,source)
    VALUES(?,?,?,?,?,?,?,?,?)
    ON CONFLICT(destination_name,year_month) DO UPDATE SET
      air_temp_c=excluded.air_temp_c,water_temp_c=excluded.water_temp_c,precipitation_mm=excluded.precipitation_mm,
      rain_days=excluded.rain_days,sun_hours=excluded.sun_hours,humidity_pct=excluded.humidity_pct,source=excluded.source
    """
    rows = [(
        str(r.get("lugar")), str(r.get("year_month")), _json_value(r.get("temp_media_aire_c")),
        _json_value(r.get("temp_media_agua_c")), _json_value(r.get("precipitacion_total_mm")),
        _json_value(r.get("dias_lluvia")), _json_value(r.get("horas_sol_totales")),
        _json_value(r.get("humedad_media_pct")), info["source_name"]
    ) for _, r in df.iterrows()]
    with db_session() as conn:
        conn.executemany(sql, rows)
    _record_import(info["source_name"], "climate", len(rows), info)
    return len(rows)


def import_connectivity_csv(path: str | Path) -> int:
    df, info = read_csv_auto(path)
    if "termino_original" not in df.columns:
        raise ValueError("El CSV de conectividad no contiene termino_original.")
    sql = """
    INSERT INTO connectivity_stats(destination_name,destination_group,iata_destination,direct_routes_es,direct_routes_uk,direct_routes_de,weekly_flights,weekly_seats,weekly_passengers,annual_passengers,source)
    VALUES(?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(destination_name) DO UPDATE SET
      destination_group=excluded.destination_group,iata_destination=excluded.iata_destination,
      direct_routes_es=excluded.direct_routes_es,direct_routes_uk=excluded.direct_routes_uk,direct_routes_de=excluded.direct_routes_de,
      weekly_flights=excluded.weekly_flights,weekly_seats=excluded.weekly_seats,weekly_passengers=excluded.weekly_passengers,
      annual_passengers=excluded.annual_passengers,source=excluded.source
    """
    rows = [(
        str(r.get("termino_original")), r.get("grupo"), r.get("iata_destino"), _json_value(r.get("rutas_directas_es")),
        _json_value(r.get("rutas_directas_uk")), _json_value(r.get("rutas_directas_de")),
        _json_value(r.get("vuelos_semanales_estimados")), _json_value(r.get("asientos_semanales_ofertados")),
        _json_value(r.get("pasajeros_semanales_estimados")), _json_value(r.get("pasajeros_anuales_estimados")), info["source_name"]
    ) for _, r in df.iterrows()]
    with db_session() as conn:
        conn.executemany(sql, rows)
    _record_import(info["source_name"], "connectivity", len(rows), info)
    return len(rows)


def import_country_indicators_csv(path: str | Path) -> int:
    df, info = read_csv_auto(path)
    if not {"iso", "pais"}.issubset(df.columns):
        raise ValueError("El CSV de seguridad/sanidad no contiene iso/pais.")
    sql = """
    INSERT INTO country_indicators(iso,country_name,hospital_beds_per_1000,homicide_rate_per_100k,source)
    VALUES(?,?,?,?,?)
    ON CONFLICT(iso) DO UPDATE SET country_name=excluded.country_name,hospital_beds_per_1000=excluded.hospital_beds_per_1000,
      homicide_rate_per_100k=excluded.homicide_rate_per_100k,source=excluded.source
    """
    rows = [(str(r.get("iso")).strip(), str(r.get("pais")), _json_value(r.get("camas_hospital_1000hab")),
             _json_value(r.get("tasa_homicidios_100mil")), info["source_name"]) for _, r in df.iterrows()]
    with db_session() as conn:
        conn.executemany(sql, rows)
    _record_import(info["source_name"], "country_indicators", len(rows), info)
    return len(rows)
