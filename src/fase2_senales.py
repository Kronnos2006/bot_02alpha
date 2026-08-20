"""
Fase 2 - Generacion de senales.

Calcula MA_20 y MA_50 sobre el Close de SPY y genera senales de cruce
(compra cuando MA_20 cruza por encima de MA_50, venta cuando cruza por
debajo). La ejecucion se marca en la apertura de la sesion SIGUIENTE
a la senal, para evitar sesgo de look-ahead.

No calcula rentabilidad ni simula capital: eso es de fases posteriores.
"""

import json
from pathlib import Path

import pandas as pd

MA_CORTA = 20
MA_LARGA = 50

RAIZ = Path(__file__).resolve().parent.parent
CSV_ENTRADA = RAIZ / "datos" / "SPY_diario.csv"
CONFIG_SPLIT = RAIZ / "datos" / "config_split.json"
RESULTADOS_DIR = RAIZ / "resultados"
CSV_SALIDA = RESULTADOS_DIR / "senales.csv"


def cargar_datos(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def calcular_medias_moviles(df: pd.DataFrame) -> pd.DataFrame:
    df["MA_20"] = df["Close"].rolling(window=MA_CORTA).mean()
    df["MA_50"] = df["Close"].rolling(window=MA_LARGA).mean()
    return df


def generar_senales(df: pd.DataFrame) -> pd.DataFrame:
    df["diff"] = df["MA_20"] - df["MA_50"]
    df["diff_prev"] = df["diff"].shift(1)

    cruce_arriba = (df["diff_prev"] < 0) & (df["diff"] >= 0)
    cruce_abajo = (df["diff_prev"] > 0) & (df["diff"] <= 0)

    df["tipo_senal"] = None
    df.loc[cruce_arriba, "tipo_senal"] = "COMPRA"
    df.loc[cruce_abajo, "tipo_senal"] = "VENTA"

    # Solo puede haber senal donde ambas medias existen (sin NaN por rolling).
    sin_medias = df["MA_20"].isna() | df["MA_50"].isna() | df["diff_prev"].isna()
    df.loc[sin_medias, "tipo_senal"] = None

    senales = df[df["tipo_senal"].notna()].copy()
    senales = senales.rename(columns={"Date": "fecha_senal", "Close": "close_senal"})

    # fecha_ejecucion / precio_ejecucion = apertura de la sesion SIGUIENTE.
    df_fecha_siguiente = df["Date"].shift(-1)
    df_open_siguiente = df["Open"].shift(-1)

    senales["fecha_ejecucion"] = df_fecha_siguiente.loc[senales.index].values
    senales["precio_ejecucion"] = df_open_siguiente.loc[senales.index].values

    senales["ejecutable"] = senales["fecha_ejecucion"].notna()

    senales = senales[[
        "fecha_senal", "tipo_senal", "close_senal",
        "fecha_ejecucion", "precio_ejecucion", "ejecutable",
    ]].reset_index(drop=True)

    return senales


def verificar_look_ahead(senales: pd.DataFrame) -> None:
    ejecutables = senales[senales["ejecutable"]]

    violaciones = ejecutables[ejecutables["fecha_ejecucion"] <= ejecutables["fecha_senal"]]

    if not violaciones.empty:
        print("\n!!! VIOLACION DE LOOK-AHEAD DETECTADA !!!")
        print(violaciones.to_string(index=False))
        raise AssertionError(
            f"{len(violaciones)} senal(es) tienen fecha_ejecucion <= fecha_senal. "
            "Esto es un sesgo de look-ahead y no debe ocurrir jamas."
        )

    print(f"\nVerificacion de look-ahead: OK. Las {len(ejecutables)} senales ejecutables "
          "cumplen fecha_ejecucion > fecha_senal, sin excepciones.")


def clasificar_por_tramo(senales: pd.DataFrame, config_split: dict) -> pd.Series:
    def tramo_de_fecha(fecha: pd.Timestamp) -> str:
        for nombre_tramo in ("train", "validation", "test"):
            info = config_split[nombre_tramo]
            inicio = pd.Timestamp(info["fecha_inicio"])
            fin = pd.Timestamp(info["fecha_fin"])
            if inicio <= fecha <= fin:
                return nombre_tramo
        return "fuera_de_rango"

    return senales["fecha_senal"].apply(tramo_de_fecha)


def main() -> None:
    print(f"Leyendo datos desde: {CSV_ENTRADA}")
    df = cargar_datos(CSV_ENTRADA)

    df = calcular_medias_moviles(df)
    senales = generar_senales(df)

    verificar_look_ahead(senales)

    with open(CONFIG_SPLIT, "r", encoding="utf-8") as f:
        config_split = json.load(f)

    senales["tramo"] = clasificar_por_tramo(senales, config_split)

    n_compra = (senales["tipo_senal"] == "COMPRA").sum()
    n_venta = (senales["tipo_senal"] == "VENTA").sum()

    print("\n" + "=" * 60)
    print("RESUMEN DE SENALES")
    print("=" * 60)
    print(f"Senales de COMPRA: {n_compra}")
    print(f"Senales de VENTA:  {n_venta}")
    print(f"Total: {len(senales)}")

    print("\nSenales por tramo:")
    print(senales["tramo"].value_counts().reindex(
        ["train", "validation", "test", "fuera_de_rango"]
    ).fillna(0).astype(int).to_string())

    print("\nPrimeras 5 senales:")
    primeras = senales.head(5).copy()
    primeras["fecha_senal"] = primeras["fecha_senal"].dt.date
    primeras["fecha_ejecucion"] = primeras["fecha_ejecucion"].dt.date
    print(primeras[[
        "fecha_senal", "tipo_senal", "close_senal", "fecha_ejecucion", "precio_ejecucion"
    ]].to_string(index=False))

    no_ejecutables = (~senales["ejecutable"]).sum()
    if no_ejecutables:
        print(f"\nSenales no ejecutables (sin sesion siguiente, ej. ultimo dia del dataset): "
              f"{no_ejecutables}")

    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    senales.to_csv(CSV_SALIDA, index=False)
    print(f"\nSenales guardadas en: {CSV_SALIDA}")


if __name__ == "__main__":
    main()
