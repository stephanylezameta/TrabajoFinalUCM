# Design Document — Data Quality & Outlier Analysis

## Introducción

Este documento describe la arquitectura del Notebook de Calidad de Datos (`notebooks/Calidad_Datos_Outliers.ipynb`), que analiza las 11 fuentes de datos del sistema de recomendación turística TUI. El diseño se organiza en funciones reutilizables auxiliares y una secuencia lógica de celdas que implementan los 10 requisitos.

---

## Arquitectura del Notebook

### Estructura de Celdas

El notebook se organiza en secciones secuenciales, donde cada sección corresponde a uno o más requisitos:

```
[Markdown] Título y descripción
[Code]     Imports y configuración
[Code]     Funciones auxiliares (helpers)
[Markdown] §1 — Carga y Perfilado
[Code]     Carga de fuentes
[Code]     Perfilado por fuente
[Markdown] §2 — Valores Nulos
[Code]     Análisis de nulos + heatmaps
[Markdown] §3 — Duplicados
[Code]     Detección de duplicados
[Markdown] §4 — Consistencia e Integridad
[Code]     Verificación de nombres + rangos + FK
[Markdown] §5 — Distribuciones
[Code]     Histogramas + estadísticos
[Markdown] §6 — Detección de Outliers
[Code]     IQR + Z-score + multivariante
[Markdown] §7 — Visualización de Outliers
[Code]     Scatter plots + correlaciones + pair plots
[Markdown] §8 — Tratamiento y DataFrame Limpio
[Code]     Winsorización + generación CSV
[Markdown] §9 — Relaciones entre Variables
[Code]     Correlaciones cruzadas
[Markdown] §10 — Conclusiones y Recomendaciones
[Markdown] Tabla resumen + recomendaciones
```

### Flujo de Datos

```
data/*.csv, data/*.db, data/embeddings/*.npy
         │
         ▼
┌────────────────────┐
│  carga_fuentes()   │  → Dict[str, pd.DataFrame | np.ndarray]
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  perfilar_fuente() │  → Dict resumen (filas, cols, dtypes, memoria)
└────────┬───────────┘
         │
         ▼
┌────────────────────────────────────────────────┐
│  analisis_nulos() / detectar_duplicados() /    │
│  verificar_consistencia() / verificar_rangos() │
│  → Indicadores de calidad por fuente           │
└────────┬───────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  estadisticos_descriptivos()             │
│  detectar_outliers_iqr()                 │
│  detectar_outliers_zscore()              │
│  detectar_outliers_multivariante()       │
│  → Tabla de outliers por variable/método │
└────────┬─────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────┐
│  aplicar_winsorizacion()                 │
│  generar_dataframe_limpio()              │
│  → data/processed/dataframe_limpio.csv   │
└──────────────────────────────────────────┘
```

---

## Componentes Principales

### 1. Módulo de Funciones Auxiliares

Todas las funciones helper se definen en una celda temprana del notebook para ser reutilizadas en las secciones posteriores.

```python
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from scipy import stats
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor


def perfilar_fuente(df: pd.DataFrame, nombre: str) -> Dict:
    """
    Genera resumen estructural de un DataFrame.
    
    Returns:
        Dict con keys: nombre, filas, columnas, dtypes, memoria_mb
    """
    return {
        "nombre": nombre,
        "filas": len(df),
        "columnas": df.shape[1],
        "dtypes": df.dtypes.value_counts().to_dict(),
        "memoria_mb": df.memory_usage(deep=True).sum() / (1024 * 1024),
    }


def analisis_nulos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula nulos absolutos y porcentaje por columna.
    Marca columnas con >50% como críticas.
    
    Returns:
        DataFrame con cols: columna, nulos_abs, nulos_pct, critica
    """
    nulos = df.isnull().sum()
    pct = (nulos / len(df)) * 100
    resultado = pd.DataFrame({
        "columna": nulos.index,
        "nulos_abs": nulos.values,
        "nulos_pct": pct.values,
        "critica": pct.values > 50.0,
    })
    return resultado


def indicador_completitud(df: pd.DataFrame) -> float:
    """
    Calcula porcentaje de celdas no nulas sobre el total.
    
    Returns:
        Float en [0, 1] representando completitud global.
    """
    total = df.shape[0] * df.shape[1]
    if total == 0:
        return 1.0
    return (total - df.isnull().sum().sum()) / total


def detectar_duplicados(df: pd.DataFrame, id_cols: Optional[List[str]] = None) -> Dict:
    """
    Detecta filas duplicadas y verifica unicidad de IDs.
    
    Returns:
        Dict con keys: n_duplicados, pct_unicos, ejemplos, ids_repetidos
    """
    n_dup = df.duplicated().sum()
    unicidad = (len(df) - n_dup) / len(df) if len(df) > 0 else 1.0
    ejemplos = df[df.duplicated(keep=False)].head(5)
    
    ids_repetidos = {}
    if id_cols:
        for col in id_cols:
            if col in df.columns:
                dup_ids = df[df.duplicated(subset=[col], keep=False)][col].unique()
                if len(dup_ids) > 0:
                    ids_repetidos[col] = dup_ids.tolist()
    
    return {
        "n_duplicados": int(n_dup),
        "pct_unicos": unicidad,
        "ejemplos": ejemplos,
        "ids_repetidos": ids_repetidos,
    }


def verificar_rango(
    df: pd.DataFrame, col: str, min_val: float, max_val: float
) -> pd.DataFrame:
    """
    Identifica filas donde una columna tiene valores fuera del rango [min_val, max_val].
    
    Returns:
        DataFrame con filas que tienen valores fuera de rango.
    """
    mask = (df[col] < min_val) | (df[col] > max_val)
    return df[mask]


def cobertura_cruzada(
    destinos_por_fuente: Dict[str, set]
) -> pd.DataFrame:
    """
    Genera informe de cobertura cruzada entre fuentes.
    Para cada par de fuentes, identifica destinos presentes en una pero ausentes en otra.
    
    Returns:
        DataFrame con cols: fuente_origen, fuente_destino, destinos_faltantes, n_faltantes
    """
    registros = []
    fuentes = list(destinos_por_fuente.keys())
    for i, f1 in enumerate(fuentes):
        for f2 in fuentes[i + 1:]:
            en_f1_no_f2 = destinos_por_fuente[f1] - destinos_por_fuente[f2]
            en_f2_no_f1 = destinos_por_fuente[f2] - destinos_por_fuente[f1]
            if en_f1_no_f2:
                registros.append({
                    "fuente_origen": f1,
                    "fuente_destino": f2,
                    "destinos_faltantes": list(en_f1_no_f2),
                    "n_faltantes": len(en_f1_no_f2),
                })
            if en_f2_no_f1:
                registros.append({
                    "fuente_origen": f2,
                    "fuente_destino": f1,
                    "destinos_faltantes": list(en_f2_no_f1),
                    "n_faltantes": len(en_f2_no_f1),
                })
    return pd.DataFrame(registros)


def estadisticos_descriptivos(series: pd.Series) -> Dict:
    """
    Calcula 9 estadísticos descriptivos para una serie numérica.
    
    Returns:
        Dict con keys: media, mediana, std, asimetria, curtosis, min, max, q1, q3
    """
    return {
        "media": series.mean(),
        "mediana": series.median(),
        "std": series.std(),
        "asimetria": series.skew(),
        "curtosis": series.kurtosis(),
        "min": series.min(),
        "max": series.max(),
        "q1": series.quantile(0.25),
        "q3": series.quantile(0.75),
    }


def detectar_outliers_iqr(series: pd.Series) -> pd.Series:
    """
    Detecta outliers usando método IQR (umbral 1.5×IQR).
    
    Returns:
        Serie booleana indicando True para outliers.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return (series < lower) | (series > upper)


def detectar_outliers_zscore(series: pd.Series, umbral: float = 3.0) -> pd.Series:
    """
    Detecta outliers usando método Z-score (|z| > umbral).
    
    Returns:
        Serie booleana indicando True para outliers.
    """
    z = np.abs(stats.zscore(series.dropna()))
    mask = pd.Series(False, index=series.index)
    mask.loc[series.dropna().index] = z > umbral
    return mask


def detectar_outliers_multivariante(
    df: pd.DataFrame, cols: List[str], metodo: str = "isolation_forest"
) -> pd.Series:
    """
    Detecta outliers multivariantes usando Isolation Forest o LOF.
    
    Args:
        df: DataFrame con datos
        cols: Columnas numéricas a considerar
        metodo: 'isolation_forest' o 'lof'
    
    Returns:
        Serie booleana indicando True para outliers.
    """
    datos = df[cols].dropna()
    if metodo == "isolation_forest":
        modelo = IsolationForest(contamination=0.05, random_state=42)
    else:
        modelo = LocalOutlierFactor(n_neighbors=20, contamination=0.05)
    
    if metodo == "isolation_forest":
        preds = modelo.fit_predict(datos)
    else:
        preds = modelo.fit_predict(datos)
    
    resultado = pd.Series(False, index=df.index)
    resultado.loc[datos.index] = preds == -1
    return resultado


def aplicar_winsorizacion(
    series: pd.Series, percentil_inf: float = 0.05, percentil_sup: float = 0.95
) -> Tuple[pd.Series, pd.Series]:
    """
    Aplica winsorización reemplazando valores fuera de [P_inf, P_sup].
    
    Returns:
        Tuple de (serie_winsorizada, mascara_modificados)
    """
    p_low = series.quantile(percentil_inf)
    p_high = series.quantile(percentil_sup)
    modificados = (series < p_low) | (series > p_high)
    winsorizada = series.clip(lower=p_low, upper=p_high)
    return winsorizada, modificados


def tabla_resumen_outliers(
    resultados: Dict[str, Dict[str, int]], total_filas: int
) -> pd.DataFrame:
    """
    Genera tabla resumen de outliers por variable y método.
    
    Args:
        resultados: {variable: {metodo: n_outliers}}
        total_filas: número total de registros
    
    Returns:
        DataFrame con cols: variable, metodo, n_outliers, pct_outliers
    """
    registros = []
    for var, metodos in resultados.items():
        for metodo, n in metodos.items():
            registros.append({
                "variable": var,
                "metodo": metodo,
                "n_outliers": n,
                "pct_outliers": (n / total_filas) * 100 if total_filas > 0 else 0,
            })
    return pd.DataFrame(registros)


def seleccionar_top_cv(df: pd.DataFrame, n: int = 5) -> List[str]:
    """
    Selecciona las n variables numéricas con mayor coeficiente de variación.
    
    Returns:
        Lista de nombres de columnas.
    """
    numericas = df.select_dtypes(include=[np.number])
    cv = (numericas.std() / numericas.mean()).abs()
    cv = cv.replace([np.inf, -np.inf], np.nan).dropna()
    return cv.nlargest(n).index.tolist()


def calcular_correlacion_significativa(
    x: pd.Series, y: pd.Series, metodo: str = "pearson"
) -> Dict:
    """
    Calcula correlación y p-value entre dos series.
    
    Returns:
        Dict con: coeficiente, p_value, significativo, interpretacion
    """
    if metodo == "pearson":
        coef, pval = stats.pearsonr(x.dropna(), y.dropna())
    else:
        coef, pval = stats.spearmanr(x.dropna(), y.dropna())
    
    significativo = pval < 0.05
    if abs(coef) > 0.7:
        fuerza = "fuerte"
    elif abs(coef) > 0.4:
        fuerza = "moderada"
    else:
        fuerza = "débil"
    direccion = "positiva" if coef > 0 else "negativa"
    
    return {
        "coeficiente": coef,
        "p_value": pval,
        "significativo": significativo,
        "interpretacion": f"Correlación {fuerza} {direccion} (r={coef:.3f}, p={pval:.4f})",
    }
```

---

### 2. Componente de Carga de Datos

```python
from pathlib import Path
import sqlite3


DATA_DIR = Path(r"D:\Master\TrabajoFinalUCM\TFM\data")
PROCESSED_DIR = DATA_DIR / "processed"
EMBEDDINGS_DIR = DATA_DIR / "embeddings"

FUENTES_CONFIG = {
    "clima": DATA_DIR / "clima_todos_los_destinos.csv",
    "seguridad": DATA_DIR / "seguridad_y_sanidad_banco_mundial.csv",
    "conectividad": DATA_DIR / "conectividad_y_pasajeros_2025.csv",
    "tui_db": DATA_DIR / "tui_recomendador.db",
    "sample_db": DATA_DIR / "sample_tui.db",
    "hybrid_vectors": EMBEDDINGS_DIR / "hybrid_vectors.npy",
    "package_embeddings": EMBEDDINGS_DIR / "package_embeddings.npy",
    "paquete_ids": EMBEDDINGS_DIR / "paquete_ids.npy",
    "evaluation": PROCESSED_DIR / "evaluation_results.csv",
    "simulation": PROCESSED_DIR / "simulation_results.csv",
}


def cargar_fuente(nombre: str, ruta: Path) -> Optional[Dict]:
    """
    Carga una fuente de datos. Devuelve None y registra error si no existe.
    Para SQLite, carga cada tabla como DataFrame independiente.
    Para .npy, carga como numpy array.
    """
    if not ruta.exists():
        print(f"⚠ ERROR: No se encontró '{nombre}' en {ruta}")
        return None
    
    if ruta.suffix == ".csv":
        return {"tipo": "csv", "data": {nombre: pd.read_csv(ruta)}}
    elif ruta.suffix == ".db":
        conn = sqlite3.connect(str(ruta))
        tablas = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
        data = {}
        for tabla in tablas["name"]:
            data[f"{nombre}.{tabla}"] = pd.read_sql(f"SELECT * FROM [{tabla}]", conn)
        conn.close()
        return {"tipo": "sqlite", "data": data}
    elif ruta.suffix == ".npy":
        return {"tipo": "npy", "data": {nombre: np.load(str(ruta), allow_pickle=True)}}
    return None
```

---

### 3. Componente de Visualización

```python
import matplotlib.pyplot as plt
import seaborn as sns


def heatmap_nulidad(df: pd.DataFrame, titulo: str) -> None:
    """Genera heatmap de nulidad para DataFrames con >3 columnas."""
    if df.shape[1] <= 3:
        return
    fig, ax = plt.subplots(figsize=(12, max(4, df.shape[1] * 0.3)))
    sns.heatmap(df.isnull().T, cbar=True, cmap="YlOrRd", ax=ax)
    ax.set_title(f"Mapa de Nulidad — {titulo}")
    ax.set_xlabel("Registros")
    ax.set_ylabel("Columnas")
    plt.tight_layout()
    plt.show()


def histograma_kde(series: pd.Series, titulo: str) -> None:
    """Genera histograma con estimación de densidad KDE."""
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(series.dropna(), kde=True, ax=ax)
    ax.set_title(f"Distribución — {titulo}")
    ax.set_xlabel(titulo)
    plt.tight_layout()
    plt.show()


def boxplot_outliers(
    series: pd.Series, n_iqr: int, n_zscore: int, titulo: str
) -> None:
    """Genera boxplot anotando cantidad de outliers por método."""
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.boxplot(x=series, ax=ax)
    ax.set_title(f"{titulo}\nOutliers: IQR={n_iqr}, Z-score={n_zscore}")
    plt.tight_layout()
    plt.show()


def scatter_outliers(
    df: pd.DataFrame, x_col: str, y_col: str, outlier_mask: pd.Series
) -> None:
    """Genera scatter plot resaltando outliers en rojo."""
    fig, ax = plt.subplots(figsize=(10, 6))
    normales = df[~outlier_mask]
    atipicos = df[outlier_mask]
    ax.scatter(normales[x_col], normales[y_col], alpha=0.5, label="Normal", c="steelblue")
    ax.scatter(atipicos[x_col], atipicos[y_col], alpha=0.8, label="Outlier", c="red", marker="x")
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_title(f"{x_col} vs {y_col}")
    ax.legend()
    plt.tight_layout()
    plt.show()


def comparar_distribuciones(
    antes: pd.Series, despues: pd.Series, titulo: str
) -> None:
    """Histogramas superpuestos antes/después del tratamiento."""
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(antes.dropna(), kde=True, color="red", alpha=0.4, label="Antes", ax=ax)
    sns.histplot(despues.dropna(), kde=True, color="green", alpha=0.4, label="Después", ax=ax)
    ax.set_title(f"Comparación — {titulo}")
    ax.legend()
    plt.tight_layout()
    plt.show()
```

---

### 4. Componente de Generación del DataFrame Limpio

```python
def generar_dataframe_limpio(
    df: pd.DataFrame,
    outliers_por_variable: Dict[str, pd.Series],
    estrategias: Dict[str, str],
) -> pd.DataFrame:
    """
    Aplica estrategias de tratamiento y genera DataFrame limpio con _outlier_flag.
    
    Args:
        df: DataFrame original
        outliers_por_variable: {col: mask_booleana de outliers}
        estrategias: {col: 'winsorizacion' | 'eliminacion' | 'mediana'}
    
    Returns:
        DataFrame limpio con columna _outlier_flag
    """
    df_limpio = df.copy()
    
    # Calcular _outlier_flag antes de modificar
    flag = pd.Series(False, index=df.index)
    for col, mask in outliers_por_variable.items():
        flag = flag | mask
    df_limpio["_outlier_flag"] = flag
    
    for col, estrategia in estrategias.items():
        if col not in df_limpio.columns:
            continue
        if estrategia == "winsorizacion":
            df_limpio[col], _ = aplicar_winsorizacion(df_limpio[col])
        elif estrategia == "eliminacion":
            df_limpio = df_limpio[~outliers_por_variable.get(col, pd.Series(False))]
        elif estrategia == "mediana":
            mediana = df_limpio[col].median()
            mask = outliers_por_variable.get(col, pd.Series(False))
            df_limpio.loc[mask, col] = mediana
    
    return df_limpio
```

---

## Modelo de Datos

### Indicadores de Calidad por Fuente

| Campo | Tipo | Descripción |
|-------|------|-------------|
| fuente | str | Nombre de la fuente de datos |
| completitud | float | Porcentaje de celdas no nulas [0, 1] |
| unicidad | float | Porcentaje de filas únicas [0, 1] |
| consistencia | float | Porcentaje de destinos con nombre consistente [0, 1] |
| pct_outliers | float | Porcentaje de registros con al menos un outlier |

### Tabla Resumen de Outliers

| Campo | Tipo | Descripción |
|-------|------|-------------|
| variable | str | Nombre de la columna analizada |
| metodo | str | 'iqr' o 'zscore' |
| n_outliers | int | Número de outliers detectados |
| pct_outliers | float | Porcentaje sobre total de registros |

### DataFrame Limpio (Salida)

El DataFrame limpio se guarda en `data/processed/dataframe_limpio.csv` y contiene:
- Todas las columnas originales con outliers tratados según la estrategia asignada
- Columna adicional `_outlier_flag` (bool): `True` si el registro original contenía al menos un outlier tratado

---

## Manejo de Errores

| Escenario | Comportamiento |
|-----------|---------------|
| Archivo fuente no encontrado | Registra mensaje con ruta buscada, continúa con el resto |
| Tabla SQLite vacía | Genera perfil con 0 filas, omite análisis estadístico |
| Columna numérica con 100% nulos | Omite del análisis de outliers, reporta en nulos |
| DataFrame vacío tras eliminación | Genera advertencia, no guarda CSV vacío |
| Error en carga de .npy | Registra error, continúa con otras fuentes |

---

## Artefactos de Salida

| Artefacto | Ruta | Formato |
|-----------|------|---------|
| Notebook principal | `notebooks/Calidad_Datos_Outliers.ipynb` | Jupyter Notebook |
| DataFrame limpio | `data/processed/dataframe_limpio.csv` | CSV |
| Gráficos EDA | (embebidos en notebook) | matplotlib/seaborn inline |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Profiling summary completeness

For any valid DataFrame with at least one row, `perfilar_fuente()` SHALL return a dictionary containing exactly the keys `nombre`, `filas`, `columnas`, `dtypes`, and `memoria_mb`, where `filas` equals the row count and `columnas` equals the column count.

**Validates: Requirements 1.2**

### Property 2: Graceful handling of missing data sources

For any file path that does not exist on disk, `cargar_fuente()` SHALL return `None` without raising an exception and SHALL print a message containing the string representation of the path.

**Validates: Requirements 1.4**

### Property 3: Null analysis correctness

For any DataFrame, `analisis_nulos()` SHALL return a result where `nulos_abs` for each column equals the actual count of null values, and `nulos_pct` equals `nulos_abs / len(df) * 100`.

**Validates: Requirements 2.1**

### Property 4: Critical column threshold marking

For any DataFrame, `analisis_nulos()` SHALL mark a column as `critica=True` if and only if its null percentage exceeds 50%.

**Validates: Requirements 2.2**

### Property 5: Completitud indicator formula

For any DataFrame, `indicador_completitud()` SHALL return a value equal to `(total_cells - null_cells) / total_cells` where `total_cells = rows × columns`. For an empty DataFrame (0 cells), it SHALL return 1.0.

**Validates: Requirements 2.4**

### Property 6: Duplicate detection and uniqueness indicator

For any DataFrame, `detectar_duplicados()` SHALL return `n_duplicados` equal to the count of rows that are exact duplicates of another row, and `pct_unicos` equal to `(total_rows - n_duplicados) / total_rows`. When ID columns are specified, non-unique IDs SHALL be reported.

**Validates: Requirements 3.1, 3.3, 3.4**

### Property 7: Cross-source destination coverage

For any collection of destination name sets from different data sources, `cobertura_cruzada()` SHALL report, for each ordered pair of sources (A, B), the exact set of destinations present in A but absent in B. The reported missing destinations SHALL equal the set difference A - B.

**Validates: Requirements 4.1, 4.2**

### Property 8: Range validation correctness

For any DataFrame, column, and valid range [min_val, max_val], `verificar_rango()` SHALL return exactly those rows where the column value is strictly less than min_val or strictly greater than max_val, and no other rows.

**Validates: Requirements 4.3**

### Property 9: Descriptive statistics completeness

For any numeric Series with at least 2 non-null values, `estadisticos_descriptivos()` SHALL return a dictionary containing exactly the 9 keys: `media`, `mediana`, `std`, `asimetria`, `curtosis`, `min`, `max`, `q1`, `q3`, with values matching the corresponding pandas/scipy computations.

**Validates: Requirements 5.3**

### Property 10: Skewness threshold flagging

For any numeric Series, if the absolute value of its skewness exceeds 2, the system SHALL flag it as significantly skewed. If |skewness| ≤ 2, it SHALL NOT be flagged.

**Validates: Requirements 5.4**

### Property 11: IQR outlier detection correctness

For any numeric Series, `detectar_outliers_iqr()` SHALL return `True` for a value if and only if that value is less than `Q1 - 1.5 * IQR` or greater than `Q3 + 1.5 * IQR`, where `IQR = Q3 - Q1`.

**Validates: Requirements 6.1**

### Property 12: Z-score outlier detection correctness

For any numeric Series, `detectar_outliers_zscore()` SHALL return `True` for a value if and only if the absolute value of its Z-score exceeds 3.

**Validates: Requirements 6.2**

### Property 13: Outlier summary table structure

For any set of outlier detection results and a total row count, `tabla_resumen_outliers()` SHALL produce a DataFrame with columns `variable`, `metodo`, `n_outliers`, `pct_outliers`, where `pct_outliers` equals `n_outliers / total_filas * 100` for each row.

**Validates: Requirements 6.4**

### Property 14: Correlation matrix mathematical properties

For any DataFrame with numeric columns, the computed correlation matrix SHALL be symmetric, have values in the range [-1, 1], and have 1.0 on the diagonal.

**Validates: Requirements 7.2**

### Property 15: Top coefficient of variation selection

For any DataFrame with numeric columns, `seleccionar_top_cv()` SHALL return the n column names with the highest absolute coefficient of variation (std/mean), in descending order.

**Validates: Requirements 7.4**

### Property 16: Winsorization bounds invariant

For any numeric Series, after applying `aplicar_winsorizacion(series, 0.05, 0.95)`, all values in the resulting series SHALL be within the range [P5, P95] of the original series. Values that were already within [P5, P95] SHALL remain unchanged.

**Validates: Requirements 8.2**

### Property 17: Original data immutability

For any execution of the analysis pipeline, the files in `data/` (excluding `data/processed/`) SHALL remain byte-identical before and after execution. The system SHALL only write to `data/processed/`.

**Validates: Requirements 8.4**

### Property 18: Outlier flag correctness

For any DataFrame processed by `generar_dataframe_limpio()`, the `_outlier_flag` column SHALL be `True` for a row if and only if that row contained at least one outlier (as identified by the outlier detection masks) before treatment.

**Validates: Requirements 8.5**

### Property 19: Significant correlation reporting threshold

For any pair of numeric Series, `calcular_correlacion_significativa()` SHALL set `significativo=True` if and only if `p_value < 0.05`, and when significant, the returned dictionary SHALL contain `coeficiente`, `p_value`, and `interpretacion` keys.

**Validates: Requirements 9.3**

### Property 20: Quality indicators summary completeness

For any set of analyzed data sources, the final quality summary table SHALL contain one row per source with the columns `fuente`, `completitud`, `unicidad`, `consistencia`, and `pct_outliers`, where each indicator is a float value in a valid range.

**Validates: Requirements 10.2**
