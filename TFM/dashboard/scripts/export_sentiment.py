"""Exporta el sentimiento agregado por destino desde el pipeline del TFM.

La base `tui_recomendador.db` pesa 64 MB y está excluida por `.gitignore`, así
que no puede viajar al despliegue. Este script agrega sus 38.000 reseñas
analizadas a una fila por destino y las deja en `data/raw/` como CSV: versionable,
auditable y consumible por el ETL que ya existe.

El modelo de sentimiento (un transformer multilingüe) se ejecutó en el pipeline;
aquí solo se agrega su salida. No se recalcula nada.

Uso:
    python scripts/export_sentiment.py
    python scripts/export_sentiment.py --db ..\\data\\tui_recomendador.db --min-reviews 5
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import RAW_DIR  # noqa: E402

DEFAULT_DB = PROJECT_ROOT.parent / "data" / "tui_recomendador.db"
OUTPUT = RAW_DIR / "sentimiento_por_destino.csv"

# Una sola consulta agregada. Se exportan los recuentos además de las medias para
# que el dato sea auditable: sin el volumen, una media no se puede interpretar.
QUERY = """
SELECT r.destino_nombre                                              AS destino,
       COUNT(*)                                                      AS resenas_analizadas,
       ROUND(AVG(s.sentiment_score), 4)                              AS sentimiento_medio,
       ROUND(AVG(s.confianza), 4)                                    AS confianza_media,
       SUM(CASE WHEN s.sentiment_label='positive' THEN 1 ELSE 0 END)  AS resenas_positivas,
       SUM(CASE WHEN s.sentiment_label='neutral'  THEN 1 ELSE 0 END)  AS resenas_neutras,
       SUM(CASE WHEN s.sentiment_label='negative' THEN 1 ELSE 0 END)  AS resenas_negativas,
       MIN(s.modelo)                                                  AS modelo_sentimiento
  FROM resenas r
  JOIN resenas_sentimiento s ON s.id_resena = r.id_resena
 WHERE r.destino_nombre IS NOT NULL AND TRIM(r.destino_nombre) <> ''
 GROUP BY r.destino_nombre
HAVING COUNT(*) >= ?
 ORDER BY COUNT(*) DESC
"""

COLUMNS = [
    "destino",
    "resenas_analizadas",
    "sentimiento_medio",
    "confianza_media",
    "resenas_positivas",
    "resenas_neutras",
    "resenas_negativas",
    "pct_negativas",
    "modelo_sentimiento",
]


def export(db_path: Path, min_reviews: int, output: Path) -> int:
    if not db_path.exists():
        print(f"No existe la base del pipeline: {db_path}")
        print("Sin ella no se puede regenerar el CSV, pero el ya exportado sigue siendo válido.")
        return 1

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(QUERY, (int(min_reviews),)).fetchall()
    finally:
        conn.close()

    if not rows:
        print("La consulta no ha devuelto filas. ¿Están pobladas resenas y resenas_sentimiento?")
        return 1

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            total = int(row["resenas_analizadas"]) or 1
            writer.writerow({
                "destino": row["destino"],
                "resenas_analizadas": row["resenas_analizadas"],
                "sentimiento_medio": row["sentimiento_medio"],
                "confianza_media": row["confianza_media"],
                "resenas_positivas": row["resenas_positivas"],
                "resenas_neutras": row["resenas_neutras"],
                "resenas_negativas": row["resenas_negativas"],
                "pct_negativas": round(int(row["resenas_negativas"]) / total * 100, 2),
                "modelo_sentimiento": row["modelo_sentimiento"],
            })

    total_reviews = sum(int(r["resenas_analizadas"]) for r in rows)
    print(f"Escrito {output}")
    print(f"  {len(rows)} destinos, {total_reviews:,} reseñas analizadas agregadas")
    print(f"  modelo: {rows[0]['modelo_sentimiento']}")
    print("\n  Peores por sentimiento (con al menos 100 reseñas):")
    worst = sorted(
        (r for r in rows if int(r["resenas_analizadas"]) >= 100),
        key=lambda r: float(r["sentimiento_medio"]),
    )[:5]
    for row in worst:
        print(
            f"    {row['destino']:<20} {row['sentimiento_medio']}  "
            f"({row['resenas_analizadas']} reseñas, {row['resenas_negativas']} negativas)"
        )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--min-reviews", type=int, default=25,
        help="Descarta destinos con menos reseñas. Una media sobre unas pocas "
             "reseñas no es evidencia. Con 25 se conserva la cobertura completa "
             "de los destinos del catálogo.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    raise SystemExit(export(args.db, args.min_reviews, args.output))
