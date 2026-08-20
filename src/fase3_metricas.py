"""
Fase 3 (cierre) - Metricas de riesgo sobre la curva de capital diaria.

Calcula Sharpe anualizado, maximo drawdown, CAGR y metricas de las
operaciones, para la ESTRATEGIA y para BUY-AND-HOLD, tanto en el
periodo completo como desglosado por tramo (train/validation/test).

No optimiza nada ni prueba otros parametros de medias moviles.
"""

import json
import math
from pathlib import Path

import pandas as pd

CAPITAL_INICIAL = 10000.0
DIAS_TRADING_ANIO = 252

# Simplificacion: se asume tasa libre de riesgo = 0 para el Sharpe.
# En un entorno real habria que restar la tasa libre de riesgo diaria
# a cada retorno antes de anualizar.
TASA_LIBRE_RIESGO = 0.0

MIN_OPERACIONES_FIABLE = 30

RAIZ = Path(__file__).resolve().parent.parent
CSV_CURVA = RAIZ / "resultados" / "curva_capital.csv"
CSV_OPERACIONES = RAIZ / "resultados" / "operaciones.csv"
CONFIG_SPLIT = RAIZ / "datos" / "config_split.json"
JSON_SALIDA = RAIZ / "resultados" / "metricas.json"


def cargar_curva(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def cargar_operaciones(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["fecha_entrada", "fecha_salida"])
    return df


def filtrar_por_tramo(df: pd.DataFrame, tramo_info: dict) -> pd.DataFrame:
    inicio = pd.Timestamp(tramo_info["fecha_inicio"])
    fin = pd.Timestamp(tramo_info["fecha_fin"])
    return df[(df["Date"] >= inicio) & (df["Date"] <= fin)].reset_index(drop=True)


def calcular_retornos_diarios(capital: pd.Series) -> pd.Series:
    """capital[t]/capital[t-1] - 1. El primer dia (sin retorno previo) se descarta."""
    return capital.pct_change().dropna()


def calcular_sharpe(retornos: pd.Series) -> float:
    retornos_ajustados = retornos - TASA_LIBRE_RIESGO
    desviacion = retornos_ajustados.std(ddof=1)
    if desviacion == 0:
        return float("nan")
    return (retornos_ajustados.mean() / desviacion) * math.sqrt(DIAS_TRADING_ANIO)


def calcular_max_drawdown(df_segmento: pd.DataFrame, columna_capital: str) -> dict:
    capital = df_segmento[columna_capital]
    fechas = df_segmento["Date"]

    pico_historico = capital.cummax()
    drawdown = capital / pico_historico - 1

    idx_valle = drawdown.idxmin()
    max_dd = drawdown.loc[idx_valle]
    idx_pico = capital.loc[:idx_valle].idxmax()

    return {
        "max_drawdown_pct": max_dd * 100,
        "fecha_pico": fechas.loc[idx_pico],
        "fecha_valle": fechas.loc[idx_valle],
        "dias_caida": int(idx_valle - idx_pico),
    }


def calcular_cagr(capital_inicial: float, capital_final: float, num_dias_mercado: int) -> float:
    anios = num_dias_mercado / DIAS_TRADING_ANIO
    return (capital_final / capital_inicial) ** (1 / anios) - 1


def calcular_metricas_serie(df_segmento: pd.DataFrame, columna_capital: str,
                             capital_inicial_base: float = None) -> dict:
    df_segmento = df_segmento.reset_index(drop=True)
    capital = df_segmento[columna_capital]

    retornos = calcular_retornos_diarios(capital)
    sharpe = calcular_sharpe(retornos)
    dd = calcular_max_drawdown(df_segmento, columna_capital)

    capital_inicial = capital_inicial_base if capital_inicial_base is not None else capital.iloc[0]
    capital_final = capital.iloc[-1]
    num_dias = len(df_segmento)
    cagr = calcular_cagr(capital_inicial, capital_final, num_dias)
    retorno_total = capital_final / capital_inicial - 1

    return {
        "capital_inicial": round(float(capital_inicial), 2),
        "capital_final": round(float(capital_final), 2),
        "num_dias_mercado": num_dias,
        "retorno_total_pct": round(float(retorno_total) * 100, 4),
        "cagr_pct": round(float(cagr) * 100, 4),
        "sharpe_anualizado": round(float(sharpe), 4),
        "max_drawdown_pct": round(float(dd["max_drawdown_pct"]), 4),
        "fecha_pico_drawdown": str(dd["fecha_pico"].date()),
        "fecha_valle_drawdown": str(dd["fecha_valle"].date()),
        "dias_caida_drawdown": dd["dias_caida"],
    }


def calcular_metricas_operaciones(operaciones: pd.DataFrame) -> dict:
    n_total = len(operaciones)
    ganadoras = operaciones[operaciones["resultado_neto"] > 0]
    perdedoras = operaciones[operaciones["resultado_neto"] < 0]

    suma_ganancias = ganadoras["resultado_neto"].sum()
    suma_perdidas = perdedoras["resultado_neto"].sum()  # negativo o 0

    if suma_perdidas == 0:
        profit_factor = None
    else:
        profit_factor = suma_ganancias / abs(suma_perdidas)

    return {
        "num_operaciones": n_total,
        "num_ganadoras": len(ganadoras),
        "num_perdedoras": len(perdedoras),
        "num_breakeven": n_total - len(ganadoras) - len(perdedoras),
        "pct_acierto": round(len(ganadoras) / n_total * 100, 4) if n_total else None,
        "retorno_medio_ganadoras_pct": round(float(ganadoras["retorno_pct"].mean()), 4) if len(ganadoras) else None,
        "retorno_medio_perdedoras_pct": round(float(perdedoras["retorno_pct"].mean()), 4) if len(perdedoras) else None,
        "profit_factor": round(float(profit_factor), 4) if profit_factor is not None else None,
        "duracion_media_dias_mercado": round(float(operaciones["dias_en_mercado"].mean()), 2) if n_total else None,
    }


def imprimir_tabla_comparativa(titulo: str, metricas_estrategia: dict, metricas_bh: dict) -> None:
    print(f"\n{titulo}")
    print(f"{'Metrica':<22}{'Estrategia':>16}{'Buy & Hold':>16}")
    print("-" * 54)
    print(f"{'Sharpe anualizado':<22}{metricas_estrategia['sharpe_anualizado']:>16.4f}"
          f"{metricas_bh['sharpe_anualizado']:>16.4f}")
    print(f"{'Max Drawdown (%)':<22}{metricas_estrategia['max_drawdown_pct']:>16.2f}"
          f"{metricas_bh['max_drawdown_pct']:>16.2f}")
    print(f"{'CAGR (%)':<22}{metricas_estrategia['cagr_pct']:>16.2f}"
          f"{metricas_bh['cagr_pct']:>16.2f}")
    print(f"{'Retorno total (%)':<22}{metricas_estrategia['retorno_total_pct']:>16.2f}"
          f"{metricas_bh['retorno_total_pct']:>16.2f}")


def main() -> None:
    curva = cargar_curva(CSV_CURVA)
    operaciones = cargar_operaciones(CSV_OPERACIONES)

    with open(CONFIG_SPLIT, "r", encoding="utf-8") as f:
        config_split = json.load(f)

    # --- Metricas globales ---
    metricas_estrategia_global = calcular_metricas_serie(
        curva, "capital", capital_inicial_base=CAPITAL_INICIAL
    )
    metricas_bh_global = calcular_metricas_serie(
        curva, "capital_buy_and_hold", capital_inicial_base=CAPITAL_INICIAL
    )

    print("=" * 60)
    print("METRICAS DE RIESGO - PERIODO COMPLETO")
    print("=" * 60)
    imprimir_tabla_comparativa("Periodo completo:", metricas_estrategia_global, metricas_bh_global)
    print(f"\nDrawdown estrategia: pico {metricas_estrategia_global['fecha_pico_drawdown']} -> "
          f"valle {metricas_estrategia_global['fecha_valle_drawdown']} "
          f"({metricas_estrategia_global['dias_caida_drawdown']} dias de mercado)")
    print(f"Drawdown buy&hold:   pico {metricas_bh_global['fecha_pico_drawdown']} -> "
          f"valle {metricas_bh_global['fecha_valle_drawdown']} "
          f"({metricas_bh_global['dias_caida_drawdown']} dias de mercado)")

    # --- Desglose por tramo ---
    resultado_tramos = {}
    print("\n" + "=" * 60)
    print("DESGLOSE POR TRAMO")
    print("=" * 60)

    for nombre_tramo in ("train", "validation", "test"):
        curva_tramo = filtrar_por_tramo(curva, config_split[nombre_tramo])

        m_estrategia = calcular_metricas_serie(curva_tramo, "capital")
        m_bh = calcular_metricas_serie(curva_tramo, "capital_buy_and_hold")

        resultado_tramos[nombre_tramo] = {
            "estrategia": m_estrategia,
            "buy_and_hold": m_bh,
        }

        imprimir_tabla_comparativa(
            f"\nTramo: {nombre_tramo.upper()} "
            f"({config_split[nombre_tramo]['fecha_inicio']} a {config_split[nombre_tramo]['fecha_fin']})",
            m_estrategia, m_bh,
        )

    # --- Metricas de operaciones (solo estrategia) ---
    metricas_ops = calcular_metricas_operaciones(operaciones)

    print("\n" + "=" * 60)
    print("METRICAS DE OPERACIONES (ESTRATEGIA)")
    print("=" * 60)
    print(f"Numero de operaciones:        {metricas_ops['num_operaciones']}")
    print(f"Ganadoras / Perdedoras / BE:  {metricas_ops['num_ganadoras']} / "
          f"{metricas_ops['num_perdedoras']} / {metricas_ops['num_breakeven']}")
    print(f"% de acierto:                 {metricas_ops['pct_acierto']}")
    print(f"Retorno medio ganadoras (%):  {metricas_ops['retorno_medio_ganadoras_pct']}")
    print(f"Retorno medio perdedoras (%): {metricas_ops['retorno_medio_perdedoras_pct']}")
    print(f"Profit factor:                {metricas_ops['profit_factor']}")
    print(f"Duracion media (dias mkt):    {metricas_ops['duracion_media_dias_mercado']}")

    # --- Advertencia obligatoria sobre tamaño de muestra por tramo ---
    conteo_por_tramo = operaciones["tramo"].value_counts().reindex(
        ["train", "validation", "test"]
    ).fillna(0).astype(int)

    print("\n" + "=" * 60)
    print("ADVERTENCIA - TAMANO DE MUESTRA POR TRAMO")
    print("=" * 60)
    tramos_insuficientes = []
    for nombre_tramo, n in conteo_por_tramo.items():
        print(f"  {nombre_tramo}: {n} operaciones")
        if n < MIN_OPERACIONES_FIABLE:
            tramos_insuficientes.append(nombre_tramo)

    if tramos_insuficientes:
        print(f"\nAVISO: los tramos {tramos_insuficientes} tienen menos de "
              f"{MIN_OPERACIONES_FIABLE} operaciones. Con tan pocas observaciones, "
              "el Sharpe, el drawdown y el CAGR de esos tramos NO permiten "
              "conclusiones estadisticas fiables; son solo orientativos.")
    else:
        print(f"\nTodos los tramos superan el umbral de {MIN_OPERACIONES_FIABLE} operaciones.")

    # --- Guardar JSON ---
    salida = {
        "periodo_completo": {
            "estrategia": metricas_estrategia_global,
            "buy_and_hold": metricas_bh_global,
        },
        "por_tramo": resultado_tramos,
        "operaciones": metricas_ops,
        "operaciones_por_tramo": conteo_por_tramo.to_dict(),
        "tramos_con_menos_de_min_operaciones": tramos_insuficientes,
        "umbral_minimo_operaciones_fiable": MIN_OPERACIONES_FIABLE,
        "tasa_libre_riesgo_usada": TASA_LIBRE_RIESGO,
    }

    RAIZ.joinpath("resultados").mkdir(parents=True, exist_ok=True)
    with open(JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(salida, f, indent=2, ensure_ascii=False)

    print(f"\nMetricas guardadas en: {JSON_SALIDA}")


if __name__ == "__main__":
    main()
