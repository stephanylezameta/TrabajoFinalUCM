from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_PATH, RAW_DIR
from database.init_db import init_db
from services.data_control_service import refresh_all_sources, seed_data_sources


def build_model(raw_dir: Path = RAW_DIR) -> None:
    init_db()
    seed_data_sources()
    results = refresh_all_sources(raw_dir=raw_dir, trigger="manual")
    for result in results:
        if result.get("status") == "success":
            print(
                f"OK  {result['source_id']}: procesados={result.get('processed')} "
                f"filas={result.get('rows_in_table')} run={result.get('run_id')}"
            )
        else:
            print(f"ERR {result['source_id']}: {result.get('error')}")
    failures = [r for r in results if r.get("status") != "success"]
    print(f"Modelo listo: {DB_PATH}")
    if failures:
        raise SystemExit(f"La actualización terminó con {len(failures)} fuente(s) con error.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construye/actualiza el modelo SQLite de TUI Data Intelligence")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    build_model(args.raw_dir)
