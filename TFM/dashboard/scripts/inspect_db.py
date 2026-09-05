"""Inspecciona un SQLite: tablas, columnas, filas y una muestra de datos.

Uso:
    python scripts/inspect_db.py ..\\data\\tui_recomendador.db
    python scripts/inspect_db.py ..\\data\\tui_recomendador.db --sample 3
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def inspect(path: Path, sample: int = 2) -> int:
    if not path.exists():
        print(f"No existe: {path}")
        return 1

    size_kb = path.stat().st_size / 1024
    print(f"Fichero : {path}")
    print(f"Tamano  : {size_kb:,.1f} KB")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        objects = conn.execute(
            "SELECT type, name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        tables = [o["name"] for o in objects if o["type"] == "table"]
        views = [o["name"] for o in objects if o["type"] == "view"]
        indexes = [o["name"] for o in objects if o["type"] == "index"]

        print(f"Tablas  : {len(tables)}   Vistas: {len(views)}   Indices: {len(indexes)}")
        if not tables:
            print("\nLa base no contiene ninguna tabla: esta vacia.")
            return 0

        total_rows = 0
        print("\n=== Resumen ===")
        for table in tables:
            try:
                n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error as exc:
                print(f"  {table:<34} error: {exc}")
                continue
            total_rows += n
            cols = [r["name"] for r in conn.execute(f'PRAGMA table_info("{table}")')]
            print(f"  {table:<34} {n:>8,} filas   {len(cols)} columnas")
        print(f"\n  TOTAL de filas en la base: {total_rows:,}")

        print("\n=== Detalle ===")
        for table in tables:
            info = list(conn.execute(f'PRAGMA table_info("{table}")'))
            try:
                n = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            except sqlite3.Error:
                continue
            print(f"\n-- {table}  ({n:,} filas)")
            for col in info:
                pk = "  PK" if col["pk"] else ""
                notnull = " NOT NULL" if col["notnull"] else ""
                print(f"     {col['name']:<28} {col['type'] or '?':<12}{notnull}{pk}")
            if n and sample:
                rows = conn.execute(f'SELECT * FROM "{table}" LIMIT {int(sample)}').fetchall()
                for idx, row in enumerate(rows, 1):
                    data = {k: row[k] for k in row.keys()}
                    text = ", ".join(f"{k}={str(v)[:44]!r}" for k, v in list(data.items())[:7])
                    print(f"     muestra {idx}: {text}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--sample", type=int, default=2)
    args = parser.parse_args()
    raise SystemExit(inspect(args.path, args.sample))
