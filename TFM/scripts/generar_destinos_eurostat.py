"""
Genera la lista completa de destinos "Capa 3a" a partir de Eurostat
(todas las regiones NUTS2 del dataset tour_occ_nin2, que por definición
ya miden actividad turística real -- no se aplica filtro adicional).

Excluye únicamente el agregado estadístico EA20 (zona euro), que no es
una región geográfica.

Genera un archivo scripts/destinos_capa3a.py con la lista lista para
importar desde run_bulk_scraping.py.
"""

import eurostat


def main() -> None:
    df = eurostat.get_data_df("tour_occ_nin2")
    geo_col = "geo\\TIME_PERIOD"

    filtrado = df[
        (df["unit"] == "NR")
        & (df["c_resid"] == "TOTAL")
        & (df["nace_r2"] == "I551-I553")
        & (df[geo_col].str.len() == 4)
        & (df[geo_col] != "EA20")
    ].copy()

    anios_candidatos = ["2024", "2023", "2022"]
    anio = next(a for a in anios_candidatos if filtrado[a].notna().sum() > 50)
    filtrado = filtrado[[geo_col, anio]].dropna()

    try:
        dic_geo = dict(eurostat.get_dic("tour_occ_nin2", "geo"))
    except Exception:
        dic_geo = {}

    nombres = []
    for _, row in filtrado.iterrows():
        codigo = row[geo_col]
        nombre = dic_geo.get(codigo, codigo)
        nombre_limpio = nombre.split("(")[0].strip()
        nombres.append(nombre_limpio)

    print(f"Total de destinos Eurostat (Capa 3a): {len(nombres)}")

    grupos = [nombres[i:i + 5] for i in range(0, len(nombres), 5)]

    with open("scripts/destinos_capa3a.py", "w", encoding="utf-8") as f:
        f.write('"""Generado automaticamente por generar_destinos_eurostat.py\n')
        f.write(f'Fuente: Eurostat tour_occ_nin2, año {anio}, {len(nombres)} regiones NUTS2.\n')
        f.write('Incluye TODAS las regiones del dataset (saturadas y no saturadas),\n')
        f.write('sin filtro adicional -- el propio dataset ya mide actividad turistica real.\n"""\n\n')
        f.write("DESTINOS_CAPA3A = [\n")
        for grupo in grupos:
            f.write(f"    {grupo!r},\n")
        f.write("]\n")

    print("Archivo generado: scripts/destinos_capa3a.py")


if __name__ == "__main__":
    main()