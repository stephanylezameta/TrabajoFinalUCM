"""
Capa 3: rankea regiones turísticas europeas (NUTS2) por pernoctaciones
reales (Eurostat tour_occ_nin2). Para identificar destinos "oportunidad"
coherentes con la tesis del proyecto (redistribución hacia destinos NO
saturados), interesa sobre todo la franja MEDIA de la tabla -- el top 20-30
son justamente los destinos más masificados (overtourism), lo opuesto a
lo que buscamos promover.
"""

import eurostat


def main() -> None:
    lineas = []
    lineas.append("Descargando y filtrando dataset tour_occ_nin2...\n")
    df = eurostat.get_data_df("tour_occ_nin2")

    geo_col = "geo\\TIME_PERIOD"

    filtrado = df[
        (df["unit"] == "NR")
        & (df["c_resid"] == "TOTAL")
        & (df["nace_r2"] == "I551-I553")
        & (df[geo_col].str.len() == 4)
    ].copy()

    anios_candidatos = ["2024", "2023", "2022"]
    anio = next(a for a in anios_candidatos if filtrado[a].notna().sum() > 50)
    lineas.append(f"Usando año: {anio} ({filtrado[anio].notna().sum()} regiones con dato)\n")

    filtrado = filtrado[[geo_col, anio]].dropna().sort_values(anio, ascending=False)
    filtrado = filtrado.reset_index(drop=True)

    try:
        dic_geo = dict(eurostat.get_dic("tour_occ_nin2", "geo"))
    except Exception as exc:
        lineas.append(f"(No se pudo cargar el diccionario de nombres: {exc})")
        lineas.append("Seguimos solo con códigos NUTS2.\n")
        dic_geo = {}

    lineas.append(f"Total de regiones NUTS2 con dato: {len(filtrado)}\n")
    lineas.append("=== TOP 1-150 regiones NUTS2 por pernoctaciones turísticas ===\n")
    for i, (_, row) in enumerate(filtrado.head(150).iterrows(), 1):
        codigo = row[geo_col]
        nombre = dic_geo.get(codigo, "???")
        pernoctaciones = int(row[anio])
        lineas.append(f"{i:3d}. {codigo}  {nombre:50s}  {pernoctaciones:>15,}")

    salida = "\n".join(lineas)
    print(salida)

    with open("destinos_eurostat.txt", "w", encoding="utf-8") as f:
        f.write(salida)


if __name__ == "__main__":
    main()