"""Configuración de pytest con base de datos aislada.

Los tests no deben depender de ``data/app.db`` ni modificarla. Aquí se apunta
``TUI_DB_PATH`` a un SQLite temporal **antes** de importar ``config`` (que lee la
variable en tiempo de import) y se construye el modelo una sola vez por sesión a
partir de los CSV/HTML reales de ``data/raw/``.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Debe ejecutarse antes de cualquier import de `config`/`database`, porque
# `database.connection` fija DB_PATH como valor por defecto en tiempo de import.
_TMP_DIR = Path(tempfile.mkdtemp(prefix="tui_tests_"))
os.environ["TUI_DB_PATH"] = str(_TMP_DIR / "test_app.db")
# Evita que los tests hagan llamadas de red al buscar imágenes o IA externa.
os.environ.pop("TUI_AI_ENDPOINT", None)
os.environ.pop("TUI_RECO_API_URL", None)
os.environ.pop("TUI_RECO_API_BASE", None)

import pytest  # noqa: E402


def pytest_sessionfinish(session, exitstatus) -> None:  # noqa: ARG001
    shutil.rmtree(_TMP_DIR, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def built_database() -> Path:
    """Construye el modelo completo en la BD temporal una vez por sesión."""
    from config import DB_PATH
    from scripts.build_model import build_model

    build_model()
    assert DB_PATH.exists(), "La base de datos de test no se ha creado"
    return DB_PATH
