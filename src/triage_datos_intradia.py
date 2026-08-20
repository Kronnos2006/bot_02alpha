"""
Triage de datos intradia disponibles en yfinance para SPY.

Solo diagnostico: para cada intervalo intenta descargar el maximo
historico disponible (period="max") y reporta cuantas barras devuelve
realmente yfinance, sin reintentar con otro rango si falla o limita.

No calcula medias moviles, no genera senales, no crea ninguna estrategia.
"""

import pandas as pd
import yfinance as yf

TICKER = "SPY"
INTERVALOS = ["1h", "30m", "15m"]


def intentar_descarga(ticker: str, intervalo: str) -> dict:
    resultado = {
        "intervalo": intervalo,
        "ok": False,
        "num_barras": 0,
        "desde": None,
        "hasta": None,
        "anios": None,
        "error": None,
    }

    try:
        df = yf.download(
            ticker,
            period="max",
            interval=intervalo,
            auto_adjust=False,
            progress=False,
        )
    except Exception as e:
        resultado["error"] = f"{type(e).__name__}: {e}"
        return resultado

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        resultado["error"] = "yfinance devolvio un DataFrame vacio (sin excepcion)."
        return resultado

    fecha_min = df.index.min()
    fecha_max = df.index.max()
    anios = (fecha_max - fecha_min).days / 365.25

    resultado.update({
        "ok": True,
        "num_barras": len(df),
        "desde": fecha_min,
        "hasta": fecha_max,
        "anios": anios,
    })
    return resultado


def imprimir_detalle(resultado: dict) -> None:
    print("-" * 60)
    print(f"Intervalo: {resultado['intervalo']}")
    if resultado["ok"]:
        print(f"  Barras obtenidas: {resultado['num_barras']}")
        print(f"  Desde: {resultado['desde']}")
        print(f"  Hasta: {resultado['hasta']}")
        print(f"  Anios de historico: {resultado['anios']:.2f}")
    else:
        print(f"  ERROR / SIN DATOS: {resultado['error']}")


def imprimir_tabla_final(resultados: list) -> None:
    print("\n" + "=" * 78)
    print("TABLA FINAL - INVENTARIO DE DATOS INTRADIA DISPONIBLES (SPY)")
    print("=" * 78)
    print(f"{'intervalo':<10}{'barras':>8}  {'desde':<28}{'hasta':<28}{'anios':>7}")
    print("-" * 90)
    for r in resultados:
        if r["ok"]:
            desde = str(r["desde"])
            hasta = str(r["hasta"])
            print(f"{r['intervalo']:<10}{r['num_barras']:>8}  {desde:<28}{hasta:<28}{r['anios']:>7.2f}")
        else:
            print(f"{r['intervalo']:<10}{'ERROR':>8}  {r['error']}")


def main() -> None:
    print(f"Triage de datos intradia para {TICKER} (period='max', sin reintentos)...\n")

    resultados = []
    for intervalo in INTERVALOS:
        resultado = intentar_descarga(TICKER, intervalo)
        imprimir_detalle(resultado)
        resultados.append(resultado)

    imprimir_tabla_final(resultados)


if __name__ == "__main__":
    main()
