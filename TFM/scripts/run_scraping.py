"""
Script CLI para ejecutar el pipeline de scraping del Motor de Recomendación TUI.

Uso:
    python scripts/run_scraping.py --sources tripadvisor reddit --regiones Mallorca Tenerife
    python scripts/run_scraping.py --database-url sqlite:///data/tui.db
    python scripts/run_scraping.py  # Ejecuta todas las fuentes con config por defecto

Carga variables de entorno desde .env y ejecuta el orquestador de scraping.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Añadir el directorio raíz del proyecto al path para imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def _cargar_env() -> None:
    """Carga variables de entorno desde el fichero .env si existe."""
    try:
        from dotenv import load_dotenv

        env_path = _PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            logging.info("Variables de entorno cargadas desde %s", env_path)
        else:
            logging.debug("Fichero .env no encontrado en %s", env_path)
    except ImportError:
        logging.debug(
            "python-dotenv no instalado; usando variables de entorno del sistema"
        )


def _configurar_logging(nivel: str = "INFO") -> None:
    """Configura el logging global del script.

    Args:
        nivel: Nivel de logging (DEBUG, INFO, WARNING, ERROR).
    """
    logging.basicConfig(
        level=getattr(logging, nivel.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _parse_args() -> argparse.Namespace:
    """Parsea los argumentos de la línea de comandos.

    Returns:
        Namespace con los argumentos parseados.
    """
    parser = argparse.ArgumentParser(
        description="Ejecuta el pipeline de scraping del Motor de Recomendación TUI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python scripts/run_scraping.py
  python scripts/run_scraping.py --sources tripadvisor reddit
  python scripts/run_scraping.py --regiones Mallorca Tenerife Cancún
  python scripts/run_scraping.py --database-url sqlite:///data/mi_bd.db
        """,
    )

    parser.add_argument(
        "--sources",
        nargs="+",
        default=None,
        choices=["tripadvisor", "reddit", "reddit_arctic", "booking", "eurostat", "ine", "unwto"],
        help=(
            "Fuentes a ejecutar. Si no se especifica, se ejecutan todas. "
            "Opciones: tripadvisor, reddit, booking, eurostat, ine, unwto"
        ),
    )

    parser.add_argument(
        "--regiones",
        nargs="+",
        default=None,
        help=(
            "Destinos/regiones a buscar. Si no se especifica, se usan las "
            "regiones por defecto (Mallorca, Tenerife, Cancún)."
        ),
    )

    parser.add_argument(
        "--database-url",
        default=None,
        help=(
            "URL de conexión SQLAlchemy. Si no se especifica, se usa la "
            "variable de entorno DATABASE_URL o el valor por defecto."
        ),
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de logging (default: INFO).",
    )

    return parser.parse_args()


def _imprimir_resumen(report) -> None:
    """Imprime un resumen del ciclo de extracción.

    Args:
        report: Instancia de ExtractionReport con los resultados.
    """
    print("\n" + "=" * 60)
    print("  RESUMEN DEL CICLO DE EXTRACCIÓN")
    print("=" * 60)
    print(f"  Inicio:           {report.fecha_inicio.strftime('%Y-%m-%d %H:%M:%S')}")
    if report.fecha_fin:
        print(f"  Fin:              {report.fecha_fin.strftime('%Y-%m-%d %H:%M:%S')}")
        duracion = (report.fecha_fin - report.fecha_inicio).total_seconds()
        print(f"  Duración:         {duracion:.1f} segundos")
    print(f"  Fuentes OK:       {', '.join(report.fuentes_ejecutadas) or 'ninguna'}")
    print(f"  Fuentes fallidas: {', '.join(report.fuentes_fallidas) or 'ninguna'}")
    print(f"  Total reseñas:    {report.total_resenas}")
    print(f"  Total indicadores:{report.total_indicadores}")
    print(f"  Excluidos:        {report.total_excluidos}")

    if report.errores:
        print("\n  Errores:")
        for error in report.errores:
            print(f"    - {error}")

    print("=" * 60 + "\n")


def main() -> None:
    """Punto de entrada principal del script de scraping."""
    # Cargar .env antes de parsear argumentos
    _cargar_env()

    args = _parse_args()
    _configurar_logging(args.log_level)

    logger = logging.getLogger(__name__)
    logger.info("Iniciando pipeline de scraping...")

    # Determinar URL de base de datos
    database_url = (
        args.database_url
        or os.environ.get("DATABASE_URL")
        or "sqlite:///data/tui_recomendador.db"
    )

    # Importar e instanciar el orquestador
    from src.scraping.orchestrator import ScraperOrchestrator

    orchestrator = ScraperOrchestrator(
        database_url=database_url,
        config={
            "regiones_default": args.regiones or ["Mallorca", "Tenerife", "Cancún"],
        },
    )

    # Ejecutar ciclo de extracción
    report = orchestrator.run_cycle(
        sources=args.sources,
        regiones=args.regiones,
    )

    # Imprimir resumen
    _imprimir_resumen(report)

    # Código de salida basado en resultado
    if report.fuentes_fallidas and not report.fuentes_ejecutadas:
        logger.error("Todas las fuentes fallaron.")
        sys.exit(1)
    elif report.fuentes_fallidas:
        logger.warning(
            "Algunas fuentes fallaron: %s", report.fuentes_fallidas
        )
        sys.exit(0)
    else:
        logger.info("Pipeline completado exitosamente.")
        sys.exit(0)


if __name__ == "__main__":
    main()
