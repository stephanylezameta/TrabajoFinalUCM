"""
Carga manual de paquetes reales de TUI (recolectados a mano desde
es.tui.com/es/ofertas-tui/) a la tabla `products` de dashboard/data/app.db.

Reemplaza el enfoque de scraping automatizado (descartado: el sitio bloquea
el acceso automatizado incluso con Selenium, error 403 confirmado en 2
intentos). Los datos siguen siendo reales, solo que recolectados a mano en
vez de con un programa.

Uso:
    1. Completa la lista PAQUETES_REALES abajo con lo que hayas visto en la
       pagina de ofertas de TUI.
    2. cd TFM
    3. python scripts/scraping/cargar_paquetes_manual.py
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "dashboard" / "data" / "app.db"
SOURCE_LABEL = "es.tui.com/es/ofertas-tui (carga manual, verificado a mano)"

# ---------------------------------------------------------------------
# COMPLETAR ACA: un diccionario por cada paquete real visto en la web.
# El campo "destination" tiene que coincidir EXACTO con uno de nuestros
# 39 destinos (Mallorca, Costa del Sol, Túnez, etc.) para que despues se
# pueda cruzar bien en el dashboard.
#
# Campos obligatorios: title, destination, price, nights.
# El resto es opcional (dejar None si no lo viste en la pagina).
# ---------------------------------------------------------------------
PAQUETES_REALES = [
    {
        "title": "Ejemplo: Mallorca Auténtica",
        "destination": "Mallorca",
        "price": 899.0,
        "nights": 6,
        "duration_days": 7,
        "board_basis": "Todo incluido",
        "hotel": None,
        "description": "Reemplazar por el texto real de la oferta.",
        "detail_url": None,  # link real a la oferta, si se consiguio
    },
    # Agregar mas paquetes aca, con la misma forma...
]


def guardar_en_bd(paquetes: list[dict]) -> int:
    if not DB_PATH.exists():
        print(f"ERROR: no se encontro la base en {DB_PATH}.")
        return 0

    conn = sqlite3.connect(DB_PATH)
    guardados = 0
    for i, p in enumerate(paquetes):
        if not p.get("title") or not p.get("destination") or p.get("price") is None:
            print(f"Salteando paquete incompleto (falta title/destination/price): {p}")
            continue
        product_id = f"tui-manual-{i}-{int(time.time())}"
        conn.execute(
            """
            INSERT INTO products (
                product_id, title, destination, price, currency,
                duration_days, nights, hotel, board_basis, description,
                detail_url, source, created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'EUR', ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                product_id, p["title"], p["destination"], p["price"],
                p.get("duration_days"), p.get("nights"), p.get("hotel"),
                p.get("board_basis"), p.get("description"), p.get("detail_url"),
                SOURCE_LABEL,
            ),
        )
        guardados += 1
    conn.commit()
    conn.close()
    return guardados


def main():
    print(f"Cargando {len(PAQUETES_REALES)} paquetes definidos en el script...")
    guardados = guardar_en_bd(PAQUETES_REALES)
    print(f"-> {guardados} paquetes guardados en {DB_PATH}")


if __name__ == "__main__":
    main()