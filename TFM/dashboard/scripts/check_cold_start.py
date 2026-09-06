"""Simula un arranque en frío como el de Streamlit Cloud.

Borra la base de datos y ejecuta el mismo bootstrap que hace la aplicación al
iniciarse, para comprobar que se reconstruye sola desde `data/raw/`. Es la
verificación que evita publicar un dashboard vacío.

Uso:
    python scripts/check_cold_start.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_PATH  # noqa: E402
from database.init_db import init_db  # noqa: E402
from services.data_control_service import (  # noqa: E402
    bootstrap_missing_sources,
    get_source_health,
    seed_data_sources,
)


def main() -> int:
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        path.unlink(missing_ok=True)
    print(f"Base borrada. Existe antes del arranque: {DB_PATH.exists()}")

    # Exactamente lo que hace bootstrap() en streamlit_app.py.
    init_db()
    seed_data_sources()
    bootstrap_missing_sources()

    print(f"Existe despues del arranque: {DB_PATH.exists()}\n")
    sources = get_source_health()
    empty: list[str] = []
    for source in sources:
        rows = int(source.get("Filas actuales") or 0)
        print(f"  {source['Estado']:<14} {source['Dataset']:<30} filas={rows}")
        if rows == 0:
            empty.append(source["Dataset"])

    print()
    if empty:
        print(f"FALLO: {len(empty)} fuente(s) sin datos: {', '.join(empty)}")
        print("El despliegue mostraria un dashboard vacio.")
        return 1
    print(f"OK: las {len(sources)} fuentes se han cargado solas desde data/raw/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
