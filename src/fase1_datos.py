"""
Fase 1 - Pipeline de datos.

Descarga el historico diario de SPY, lo valida, lo guarda limpio
y calcula un split temporal 60/20/20 (train/validation/test).

No calcula indicadores ni hace backtest: eso es de fases posteriores.
"""

import json
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

TICKER = "SPY"
FECHA_INICIO = "2011-01-01"
FECHA_FIN = date.today().strftime("%Y-%m-%d")

RAIZ = Path(__file__).resolve().parent.parent
DATOS_DIR = RAIZ / "datos"
CSV_SALIDA = DATOS_DIR / "SPY_diario.csv"
CONFIG_SPLIT_SALIDA = DATOS_DIR / "config_split.json"

FECHA_CRASH_COVID = "2020-03-16"

COLUMNAS_FINALES = ["Date", "Open", "High", "Low", "Close", "Volume"]


def descargar_datos(ticker: str, inicio: str, fin: str) -> pd.DataFrame:
    """Descarga precios diarios SIN ajustar por dividendos (auto_adjust=False)."""
    df = yf.download(
        ticker,
        start=inicio,
        end=fin,
        auto_adjust=False,
        progress=False,
    )

    if df.empty:
        raise RuntimeError(f"yfinance no devolvio datos para {ticker} entre {inicio} y {fin}")

    # yf.download puede devolver columnas con MultiIndex (Ticker, Campo) segun version.
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns.name = None

    df = df.reset_index()
    df = df.drop(columns=["Adj Close"], errors="ignore")
    df = df[COLUMNAS_FINALES]

    return df


def validar_datos(df: pd.DataFrame) -> None:
    print("=" * 60)
    print("VALIDACION DE DATOS")
    print("=" * 60)

    print(f"Numero de filas: {len(df)}")
    print(f"Rango de fechas: {df['Date'].min().date()} a {df['Date'].max().date()}")

    print("\nValores nulos por columna:")
    print(df.isnull().sum().to_string())

    duplicadas = df["Date"].duplicated().sum()
    print(f"\nFechas duplicadas: {duplicadas}")

    high_menor_low = df[df["High"] < df["Low"]]
    print(f"\nDias con High < Low: {len(high_menor_low)}")
    if not high_menor_low.empty:
        print(high_menor_low[["Date", "High", "Low"]].to_string(index=False))

    close_fuera_rango = df[(df["Close"] < df["Low"]) | (df["Close"] > df["High"])]
    print(f"Dias con Close fuera de [Low, High]: {len(close_fuera_rango)}")
    if not close_fuera_rango.empty:
        print(close_fuera_rango[["Date", "Low", "High", "Close"]].to_string(index=False))

    print("=" * 60)


def calcular_split_temporal(df: pd.DataFrame) -> dict:
    """Split 60/20/20 por POSICION (no aleatorio), respetando el orden temporal."""
    n = len(df)
    n_train = int(n * 0.6)
    n_val = int(n * 0.8) - n_train

    train = df.iloc[:n_train]
    validation = df.iloc[n_train:n_train + n_val]
    test = df.iloc[n_train + n_val:]

    config = {
        "train": {
            "fecha_inicio": str(train["Date"].min().date()),
            "fecha_fin": str(train["Date"].max().date()),
            "num_filas": len(train),
        },
        "validation": {
            "fecha_inicio": str(validation["Date"].min().date()),
            "fecha_fin": str(validation["Date"].max().date()),
            "num_filas": len(validation),
        },
        "test": {
            "fecha_inicio": str(test["Date"].min().date()),
            "fecha_fin": str(test["Date"].max().date()),
            "num_filas": len(test),
        },
    }

    return config


def imprimir_tramo_fecha(df: pd.DataFrame, config: dict, fecha_objetivo: str) -> None:
    fecha_objetivo_ts = pd.Timestamp(fecha_objetivo)

    tramo_encontrado = None
    for nombre_tramo in ("train", "validation", "test"):
        info = config[nombre_tramo]
        inicio = pd.Timestamp(info["fecha_inicio"])
        fin = pd.Timestamp(info["fecha_fin"])
        if inicio <= fecha_objetivo_ts <= fin:
            tramo_encontrado = nombre_tramo
            break

    print(f"\nLa fecha {fecha_objetivo} (crash COVID) cae en el tramo: "
          f"{tramo_encontrado.upper() if tramo_encontrado else 'NO ENCONTRADA'}")

    if fecha_objetivo_ts not in df["Date"].values:
        print(f"Aviso: {fecha_objetivo} no esta presente en los datos descargados "
              "(puede ser fin de semana o feriado de mercado).")


def main() -> None:
    print(f"Descargando {TICKER} desde {FECHA_INICIO} hasta {FECHA_FIN} (auto_adjust=False)...")
    df = descargar_datos(TICKER, FECHA_INICIO, FECHA_FIN)

    validar_datos(df)

    DATOS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_SALIDA, index=False)
    print(f"\nDatos limpios guardados en: {CSV_SALIDA}")

    config_split = calcular_split_temporal(df)

    with open(CONFIG_SPLIT_SALIDA, "w", encoding="utf-8") as f:
        json.dump(config_split, f, indent=2, ensure_ascii=False)

    print(f"Config de split guardado en: {CONFIG_SPLIT_SALIDA}")
    print("\nSplit temporal 60/20/20 (por posicion, no aleatorio):")
    print(json.dumps(config_split, indent=2, ensure_ascii=False))

    imprimir_tramo_fecha(df, config_split, FECHA_CRASH_COVID)


if __name__ == "__main__":
    main()
