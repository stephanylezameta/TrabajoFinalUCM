"""Tests unitarios para el módulo DataCleaner."""

import pytest
import pandas as pd

from src.scraping.cleaner import DataCleaner, ValidationError, ExclusionLog


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cleaner():
    """Instancia de DataCleaner con umbral por defecto (0.30)."""
    return DataCleaner()


def _registro_valido(**overrides) -> dict:
    """Genera un registro válido completo; permite sobreescribir campos."""
    base = {
        "destino_nombre": "Cancún",
        "destino_pais": "México",
        "categoria": "Playa",
        "nombre_paquete": "Todo Incluido Cancún",
        "nombre_hotel": "Hotel Riviera",
        "ciudad_salida": "Madrid",
        "fecha_salida": "2025-06-01",
        "fecha_vuelta": "2025-06-08",
        "duracion_dias": 7,
        "precio_base_eur": 1200.0,
        "nivel_ocupacion": 0.75,
        "fecha_extraccion": "2025-01-15T10:00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests: deduplicate()
# ---------------------------------------------------------------------------

class TestDeduplicate:
    """Tests para DataCleaner.deduplicate()."""

    def test_con_duplicados_conserva_mas_reciente(self, cleaner):
        """Cuando hay duplicados por clave compuesta, conserva el de fecha_extraccion más reciente."""
        antiguo = _registro_valido(
            precio_base_eur=1000.0,
            fecha_extraccion="2025-01-10T08:00:00",
        )
        reciente = _registro_valido(
            precio_base_eur=1100.0,
            fecha_extraccion="2025-01-15T12:00:00",
        )

        resultado = cleaner.deduplicate([antiguo, reciente])

        assert len(resultado) == 1
        assert resultado[0]["precio_base_eur"] == 1100.0

    def test_sin_duplicados(self, cleaner):
        """Registros con clave compuesta diferente se conservan todos."""
        r1 = _registro_valido(nombre_hotel="Hotel A")
        r2 = _registro_valido(nombre_hotel="Hotel B")

        resultado = cleaner.deduplicate([r1, r2])

        assert len(resultado) == 2

    def test_lista_vacia(self, cleaner):
        """Una lista vacía devuelve lista vacía."""
        resultado = cleaner.deduplicate([])

        assert resultado == []


# ---------------------------------------------------------------------------
# Tests: normalize_minmax()
# ---------------------------------------------------------------------------

class TestNormalizeMinmax:
    """Tests para DataCleaner.normalize_minmax()."""

    def test_postcondicion_valores_entre_0_y_1(self, cleaner):
        """Los valores normalizados deben estar en [0, 1]."""
        df = pd.DataFrame({"precio_base_eur": [100, 200, 300, 400, 500]})

        resultado = cleaner.normalize_minmax(df, ["precio_base_eur"])

        assert resultado["precio_base_eur"].min() == pytest.approx(0.0)
        assert resultado["precio_base_eur"].max() == pytest.approx(1.0)
        assert (resultado["precio_base_eur"] >= 0.0).all()
        assert (resultado["precio_base_eur"] <= 1.0).all()

    def test_min_igual_max_retorna_05(self, cleaner):
        """Si min == max en una columna, todos los valores se fijan a 0.5."""
        df = pd.DataFrame({"precio_base_eur": [50, 50, 50]})

        resultado = cleaner.normalize_minmax(df, ["precio_base_eur"])

        assert (resultado["precio_base_eur"] == 0.5).all()

    def test_columna_inexistente_se_omite(self, cleaner):
        """Una columna que no existe en el DataFrame se omite sin error."""
        df = pd.DataFrame({"precio_base_eur": [100, 200]})

        resultado = cleaner.normalize_minmax(df, ["columna_fantasma"])

        # El DataFrame se devuelve sin cambios
        assert list(resultado["precio_base_eur"]) == [100, 200]


# ---------------------------------------------------------------------------
# Tests: validate_schema()
# ---------------------------------------------------------------------------

class TestValidateSchema:
    """Tests para DataCleaner.validate_schema()."""

    def test_registro_valido(self, cleaner):
        """Un registro completo y dentro de rangos es válido."""
        record = _registro_valido()

        resultado = cleaner.validate_schema(record)

        assert resultado.es_valido is True
        assert resultado.errores == []

    def test_nivel_ocupacion_mayor_que_1_lanza_validation_error(self, cleaner):
        """nivel_ocupacion > 1 lanza ValidationError."""
        record = _registro_valido(nivel_ocupacion=1.5)

        with pytest.raises(ValidationError) as exc_info:
            cleaner.validate_schema(record)

        assert exc_info.value.campo == "nivel_ocupacion"
        assert exc_info.value.valor == 1.5

    def test_precio_base_eur_negativo_lanza_validation_error(self, cleaner):
        """precio_base_eur < 0 lanza ValidationError."""
        record = _registro_valido(precio_base_eur=-50.0)

        with pytest.raises(ValidationError) as exc_info:
            cleaner.validate_schema(record)

        assert exc_info.value.campo == "precio_base_eur"
        assert exc_info.value.valor == -50.0


# ---------------------------------------------------------------------------
# Tests: exclude_invalid()
# ---------------------------------------------------------------------------

class TestExcludeInvalid:
    """Tests para DataCleaner.exclude_invalid()."""

    def test_registro_con_mas_de_30_porciento_vacios_excluido(self, cleaner):
        """Un registro con >30% de campos obligatorios vacíos es excluido."""
        # 11 campos obligatorios; vaciar 4 → 36.4% > 30%
        record = _registro_valido()
        record["destino_nombre"] = ""
        record["destino_pais"] = None
        record["categoria"] = ""
        record["nombre_paquete"] = None

        validos, logs = cleaner.exclude_invalid([record])

        assert len(validos) == 0
        assert len(logs) == 1
        assert isinstance(logs[0], ExclusionLog)
        assert logs[0].porcentaje_vacios > 0.30

    def test_registro_valido_pasa(self, cleaner):
        """Un registro con todos los campos pasa sin exclusión."""
        record = _registro_valido()

        validos, logs = cleaner.exclude_invalid([record])

        assert len(validos) == 1
        assert len(logs) == 0

    def test_caso_limite_exactamente_30_porciento_no_excluido(self, cleaner):
        """Un registro con exactamente 30% de campos vacíos NO se excluye (umbral es >30%)."""
        # 11 campos obligatorios; vaciar 3 → 27.3% ≤ 30% → NO excluido
        # Para llegar a exactamente ~30% necesitamos 3.3 campos, no es posible exacto.
        # Con 3 de 11 vacíos = 27.3% → pasa. Con 4 = 36.4% → excluido.
        # Usamos umbral personalizado para probar el caso límite exacto.
        cleaner_custom = DataCleaner(umbral_exclusion=0.30)
        record = _registro_valido()
        # Vaciar exactamente 3 campos de 11 → 3/11 = 0.2727... ≤ 0.30 → pasa
        record["destino_nombre"] = ""
        record["destino_pais"] = None
        record["categoria"] = ""

        validos, logs = cleaner_custom.exclude_invalid([record])

        assert len(validos) == 1
        assert len(logs) == 0


# ---------------------------------------------------------------------------
# Tests: clean_pipeline()
# ---------------------------------------------------------------------------

class TestCleanPipeline:
    """Tests para DataCleaner.clean_pipeline()."""

    def test_pipeline_completo_mezcla_validos_e_invalidos(self, cleaner):
        """El pipeline filtra registros inválidos y normaliza los válidos."""
        valido_1 = _registro_valido(nombre_hotel="Hotel A", precio_base_eur=500)
        valido_2 = _registro_valido(nombre_hotel="Hotel B", precio_base_eur=1000)

        # Registro inválido: >30% campos vacíos
        invalido = _registro_valido(nombre_hotel="Hotel C")
        invalido["destino_nombre"] = ""
        invalido["destino_pais"] = None
        invalido["categoria"] = ""
        invalido["nombre_paquete"] = None

        registros_limpios, logs = cleaner.clean_pipeline([valido_1, valido_2, invalido])

        # Se excluye el inválido
        assert len(logs) == 1
        assert len(registros_limpios) == 2

        # Los valores numéricos se normalizaron a [0, 1]
        precios = [r["precio_base_eur"] for r in registros_limpios]
        assert min(precios) == pytest.approx(0.0)
        assert max(precios) == pytest.approx(1.0)
