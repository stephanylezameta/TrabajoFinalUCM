"""Ad-hoc probe: ejercita la capa de analítica del panel «Monitor performance»
con ~100 combinaciones de filtros y valida invariantes.

No es un test unitario; es una batería de exploración para detectar errores
(excepciones) y anomalías de datos (invariantes rotos) en las mismas funciones
que alimentan el dashboard desplegado. Cada combinación de (periodo, destino,
tipo) x función cuenta como una prueba.

Uso:  python scripts/dashboard_probe.py
"""

from __future__ import annotations

import itertools
import os
import traceback
from datetime import date

from services import performance_analytics as pa
from services import spain_reference

# Fecha fija para que los presets relativos ("Hoy", "7 días"...) caigan dentro
# del rango de datos (2026-09-08 .. 2026-09-15). date.today() sería 2026-09-15.
TODAY = date(2026, 9, 15)

RANK_ORDERS = ("clicks", "ctr", "users", "impressions")


class Probe:
    def __init__(self) -> None:
        self.n_tests = 0
        self.errors: list[dict] = []
        self.anomalies: list[dict] = []

    def check(self, ok: bool, label: str, detail: str) -> None:
        """Registra una anomalía si el invariante no se cumple."""
        if not ok:
            self.anomalies.append({"label": label, "detail": detail})

    def run(self, label: str, fn) -> object:
        """Ejecuta una llamada de panel; captura la excepción como error."""
        self.n_tests += 1
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - queremos capturar cualquier fallo
            self.errors.append({
                "label": label,
                "exc": f"{type(exc).__name__}: {exc}",
                "tb": traceback.format_exc(limit=3),
            })
            return None


def _validate_dest_perf(probe: Probe, label: str, rows: list[dict]) -> None:
    for r in rows or []:
        d = r.get("destination", "?")
        probe.check(r["clicks"] >= 0, f"{label} clicks>=0", f"{d}: {r['clicks']}")
        probe.check(r["impressions"] >= 0, f"{label} impr>=0", f"{d}: {r['impressions']}")
        probe.check(
            r["clicks"] <= r["impressions"] or r["impressions"] == 0,
            f"{label} clicks<=impressions",
            f"{d}: clicks={r['clicks']} impr={r['impressions']}",
        )
        if r.get("ctr") is not None:
            probe.check(0 <= r["ctr"] <= 1, f"{label} 0<=ctr<=1", f"{d}: ctr={r['ctr']}")


def _validate_kpis(probe: Probe, label: str, kpis: dict) -> None:
    if not kpis:
        return
    ctr = kpis.get("ctr", {})
    if ctr.get("available") and ctr.get("value") is not None:
        probe.check(0 <= ctr["value"] <= 1, f"{label} kpi ctr in [0,1]", f"ctr={ctr['value']}")
    for name in ("sessions_started", "recommendations", "impressions", "clicks"):
        k = kpis.get(name, {})
        v = k.get("value")
        if v is not None:
            probe.check(v >= 0, f"{label} kpi {name}>=0", f"{name}={v}")
    imp = kpis.get("impressions", {}).get("value")
    clk = kpis.get("clicks", {}).get("value")
    if imp is not None and clk is not None:
        probe.check(clk <= imp or imp == 0, f"{label} kpi clicks<=impressions", f"clicks={clk} impr={imp}")


def _validate_map(probe: Probe, label: str, points: list[dict]) -> None:
    for p in points or []:
        d = p.get("destination", "?")
        # El mapa de España solo debe contener destinos españoles con coordenada.
        ref = spain_reference.get_reference(d)
        is_spain = ref is not None and (ref.get("country") or "España") == "España"
        probe.check(is_spain, f"{label} map solo España", f"{d} no es español")
        probe.check("lat" in p and "lon" in p, f"{label} map tiene coords", f"{d}")


def _validate_funnel(probe: Probe, label: str, steps: list[dict]) -> None:
    if not steps:
        return
    vals = [s["value"] for s in steps]
    # El embudo debe decrecer de forma monotónica.
    for a, b in zip(vals, vals[1:]):
        probe.check(b <= a, f"{label} funnel monotónico", f"{vals}")
    for s in steps:
        if s.get("pct_of_prev") is not None:
            probe.check(0 <= s["pct_of_prev"] <= 1, f"{label} funnel conv<=100%",
                        f"{s['step']}: {s['pct_of_prev']}")


def _validate_saturation(probe: Probe, label: str, data: dict) -> None:
    if not data or not data.get("available"):
        return
    for p in data["points"]:
        probe.check(0 <= p["saturation"] <= 1, f"{label} sat in [0,1]",
                    f"{p['destination']}: {p['saturation']}")
        probe.check(p["quadrant"] in {
            "Masificado", "Oportunidad", "Menor prioridad", "Oportunidad secundaria"
        }, f"{label} cuadrante válido", f"{p['destination']}: {p.get('quadrant')}")


def _validate_potential(probe: Probe, label: str, rows: list[dict]) -> None:
    for r in rows or []:
        probe.check(0 <= r["potential_score"] <= 1, f"{label} potential in [0,1]",
                    f"{r['destination']}: {r['potential_score']}")
        probe.check(0 <= r["saturation"] <= 1, f"{label} pot sat in [0,1]",
                    f"{r['destination']}: {r['saturation']}")


_REPORT_LINES: list[str] = []


def out(line: str = "") -> None:
    """Acumula una línea del informe. Se vuelca a UTF-8 al final; así no dependemos
    de la codificación de la consola de Windows (cp1252) ni de la tubería."""
    _REPORT_LINES.append(line)
    try:
        print(line)
    except Exception:  # noqa: BLE001 - consola no UTF-8; el fichero manda
        pass


def main() -> None:
    probe = Probe()

    presets = list(pa.PERIOD_PRESETS)
    types = ["Todos"] + spain_reference.type_options()
    all_dests = list(spain_reference.SPAIN_DESTINATIONS.keys())
    # Muestra representativa de destinos: nacionales variados + internacionales
    # + uno inexistente para probar el filtrado defensivo.
    dest_sample = [
        "Todos", "Madrid", "Barcelona", "Mallorca", "Tenerife", "Málaga",
        "Ronda", "Cádiz", "Ibiza", "Gran Canaria",
        "Bali", "Cancún", "Santorini",  # internacionales: no deben salir en mapa
        "Atlantis",  # inexistente
    ]

    combos_run = 0

    # 1) Matriz principal: periodo x destino x tipo (TODAS las combinaciones,
    #    no rotadas). Cada combo dispara todas las funciones del panel, así que
    #    genera muchas "pruebas" por combo. 4 periodos x 14 destinos x 5 tipos
    #    = 280 combinaciones de filtros distintas.
    for preset, dest, dest_type in itertools.product(presets, dest_sample, types):
        combos_run += 1
        period = pa.resolve_period(preset, today=TODAY)
        filters = pa.Filters(
            destination=dest if dest != "Todos" else None,
            dest_type=dest_type if dest_type != "Todos" else None,
        )
        tag = f"[{preset} | dest={dest} | tipo={dest_type}]"

        kpis = probe.run(f"{tag} get_kpis", lambda: pa.get_kpis(period, filters))
        _validate_kpis(probe, tag, kpis)

        perf = probe.run(f"{tag} get_destination_performance",
                         lambda: pa.get_destination_performance(period, filters))
        _validate_dest_perf(probe, tag, perf)

        probe.run(f"{tag} get_timeseries", lambda: pa.get_timeseries(period, filters))
        probe.run(f"{tag} get_destination_trends",
                  lambda: pa.get_destination_trends(period, filters))

        for order in RANK_ORDERS:
            probe.run(f"{tag} rank_destinations({order})",
                      lambda o=order: pa.rank_destinations(period, filters, order_by=o))

        pts = probe.run(f"{tag} get_spain_interest_map",
                        lambda: pa.get_spain_interest_map(period, filters))
        _validate_map(probe, tag, pts)

        probe.run(f"{tag} unmapped_interest",
                  lambda: pa.unmapped_interest(period, filters))

        funnel = probe.run(f"{tag} get_funnel", lambda: pa.get_funnel(period, filters))
        _validate_funnel(probe, tag, funnel)

        sat = probe.run(f"{tag} get_interest_vs_saturation",
                        lambda: pa.get_interest_vs_saturation(period, filters))
        _validate_saturation(probe, tag, sat)

        pot = probe.run(f"{tag} get_potential_destinations",
                        lambda: pa.get_potential_destinations(period, filters))
        _validate_potential(probe, tag, pot)

        probe.run(f"{tag} get_engagement", lambda: pa.get_engagement(period))

    # 2) Barrido extra por TIPO explícito (los 4 tipos) en histórico completo,
    #    para no depender de la rotación.
    for dest_type in spain_reference.type_options():
        period = pa.resolve_period(pa.PERIOD_ALL, today=TODAY)
        filters = pa.Filters(dest_type=dest_type)
        tag = f"[ALL | tipo={dest_type}]"
        perf = probe.run(f"{tag} get_destination_performance",
                         lambda: pa.get_destination_performance(period, filters))
        _validate_dest_perf(probe, tag, perf)
        pts = probe.run(f"{tag} get_spain_interest_map",
                        lambda: pa.get_spain_interest_map(period, filters))
        _validate_map(probe, tag, pts)

    # 3) Barrido por CADA destino del catálogo (histórico) en el mapa y perf,
    #    para cazar cualquier destino problemático.
    period_all = pa.resolve_period(pa.PERIOD_ALL, today=TODAY)
    for dest in all_dests:
        filters = pa.Filters(destination=dest)
        tag = f"[ALL | dest={dest}]"
        perf = probe.run(f"{tag} get_destination_performance",
                         lambda: pa.get_destination_performance(period_all, filters))
        _validate_dest_perf(probe, tag, perf)

    # 4) Barrido por COMUNIDAD AUTÓNOMA (filtro válido de Filters aunque la UI
    #    no lo exponga aún) cruzado con los periodos, en mapa y rendimiento.
    for preset, ccaa in itertools.product(presets, spain_reference.community_options()):
        period = pa.resolve_period(preset, today=TODAY)
        filters = pa.Filters(community=ccaa)
        tag = f"[{preset} | ccaa={ccaa}]"
        perf = probe.run(f"{tag} get_destination_performance",
                         lambda: pa.get_destination_performance(period, filters))
        _validate_dest_perf(probe, tag, perf)
        pts = probe.run(f"{tag} get_spain_interest_map",
                        lambda: pa.get_spain_interest_map(period, filters))
        _validate_map(probe, tag, pts)
        # Todos los puntos deben pertenecer a la comunidad filtrada.
        for p in pts or []:
            ref = spain_reference.get_reference(p["destination"])
            probe.check(ref is not None and ref.get("ccaa") == ccaa,
                        f"{tag} mapa respeta ccaa",
                        f"{p['destination']} ccaa={ref.get('ccaa') if ref else None}")

    # -------- Informe --------
    out("=" * 70)
    out(f"COMBINACIONES DE FILTROS PRINCIPALES: {combos_run}")
    out(f"PRUEBAS EJECUTADAS: {probe.n_tests}")
    out(f"ERRORES (excepciones): {len(probe.errors)}")
    out(f"ANOMALÍAS (invariantes): {len(probe.anomalies)}")
    out("=" * 70)

    if probe.errors:
        out("\n--- ERRORES ---")
        for e in probe.errors[:40]:
            out(f"\n{e['label']}\n  {e['exc']}")
    if probe.anomalies:
        out("\n--- ANOMALÍAS ---")
        # Agrupa por etiqueta de invariante para no repetir.
        seen: dict[str, int] = {}
        for a in probe.anomalies:
            key = a["label"]
            seen[key] = seen.get(key, 0) + 1
        for key, count in sorted(seen.items(), key=lambda kv: -kv[1]):
            example = next(a["detail"] for a in probe.anomalies if a["label"] == key)
            out(f"  [{count}x] {key} — ej: {example}")

    if not probe.errors and not probe.anomalies:
        out("\nSin errores ni anomalías detectadas.")

    # -------- Cobertura: confirma que las validaciones vieron datos reales --------
    out("\n--- COBERTURA (histórico completo, sin filtros) ---")
    period = pa.resolve_period(pa.PERIOD_ALL, today=TODAY)
    f = pa.Filters()
    perf = pa.get_destination_performance(period, f)
    total_clicks = sum(r["clicks"] for r in perf)
    total_impr = sum(r["impressions"] for r in perf)
    map_pts = pa.get_spain_interest_map(period, f)
    unmapped = pa.unmapped_interest(period, f)
    funnel = pa.get_funnel(period, f)
    sat = pa.get_interest_vs_saturation(period, f)
    pot = pa.get_potential_destinations(period, f)
    out(f"  destinos con interés: {len(perf)}  (clics={total_clicks}, impresiones={total_impr})")
    out(f"  puntos en mapa España: {len(map_pts)}")
    out(f"  destinos con interés fuera del mapa (internac./sin coord): {len(unmapped)}")
    out(f"  funnel: {[(s['step'], s['value']) for s in funnel]}")
    out(f"  saturación disponible: {sat.get('available')} (puntos={len(sat.get('points', []))})")
    out(f"  destinos con potencial: {len(pot)}")
    # CTR con la muestra de clics reales.
    top = max(perf, key=lambda r: r["clicks"], default=None)
    if top:
        out(f"  destino más clicado: {top['destination']} ({top['clicks']} clics, CTR={top['ctr']})")

    # Vuelca el informe a UTF-8, independiente de la consola.
    report_path = os.path.join(os.path.dirname(__file__), "_probe_report.txt")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(_REPORT_LINES) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - persistimos el fallo para diagnosticarlo
        err_path = os.path.join(os.path.dirname(__file__), "_probe_crash.txt")
        with open(err_path, "w", encoding="utf-8") as fh:
            fh.write(traceback.format_exc())
        raise
