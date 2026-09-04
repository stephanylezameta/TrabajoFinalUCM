from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import DB_PATH, RAW_DIR
from database.init_db import init_db
from services.import_service import import_climate_csv, import_connectivity_csv, import_country_indicators_csv
from services.reference_service import import_destinations_from_proposal_html, import_products_from_experience_html


def build_model(raw_dir: Path = RAW_DIR) -> None:
    init_db()
    sources = {
        "proposal": raw_dir / "propuesta_7.html",
        "experience": raw_dir / "tui_experiencia_final.html",
        "climate": raw_dir / "clima_todos_los_destinos.csv",
        "connectivity": raw_dir / "conectividad_y_pasajeros_2025.csv",
        "safety": raw_dir / "seguridad_y_sanidad_banco_mundial.csv",
    }
    if sources["proposal"].exists():
        print("Destinos de referencia:", import_destinations_from_proposal_html(sources["proposal"]))
    if sources["experience"].exists():
        print("Productos HTML:", import_products_from_experience_html(sources["experience"]))
    if sources["climate"].exists():
        print("Filas clima:", import_climate_csv(sources["climate"]))
    if sources["connectivity"].exists():
        print("Filas conectividad:", import_connectivity_csv(sources["connectivity"]))
    if sources["safety"].exists():
        print("Países seguridad/sanidad:", import_country_indicators_csv(sources["safety"]))
    print(f"Modelo listo: {DB_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construye el modelo SQLite de TUI/TDRS")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    args = parser.parse_args()
    build_model(args.raw_dir)
