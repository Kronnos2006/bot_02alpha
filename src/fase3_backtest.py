"""
Fase 3 - Motor de backtest.

Simula una estrategia de solo-largos (CASH / LONG) ejecutando las
senales de resultados/senales.csv sobre las aperturas de D+1, y genera
una curva de capital diaria (una fila por cada dia de mercado) junto
con el registro de operaciones completadas.

Convencion de comisiones (0.1% por operacion):
La comision se considera INCLUIDA dentro del capital disponible, no
un costo adicional que exceda ese capital. Es decir, al comprar:
    capital_disponible = valor_operacion + comision
    valor_operacion = capital_disponible / (1 + COMISION)
Esto garantiza que el capital nunca se vuelva negativo por comisiones
y que se use exactamente el 100% del capital disponible.

No calcula Sharpe ni drawdown, no añade stop loss, take profit,
position sizing variable, slippage ni apalancamiento. Eso es de fases
posteriores.
"""

import json
from pathlib import Path

import pandas as pd

CAPITAL_INICIAL = 10000.0
COMISION = 0.001  # 0.1%

RAIZ = Path(__file__).resolve().parent.parent
CSV_PRECIOS = RAIZ / "datos" / "SPY_diario.csv"
CONFIG_SPLIT = RAIZ / "datos" / "config_split.json"
CSV_SENALES = RAIZ / "resultados" / "senales.csv"
RESULTADOS_DIR = RAIZ / "resultados"
CSV_CURVA = RESULTADOS_DIR / "curva_capital.csv"
CSV_OPERACIONES = RESULTADOS_DIR / "operaciones.csv"


def cargar_precios(ruta: Path) -> pd.DataFrame:
    df = pd.read_csv(ruta, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


def cargar_senales_ejecutables(ruta: Path) -> pd.DataFrame:
    senales = pd.read_csv(ruta, parse_dates=["fecha_senal", "fecha_ejecucion"])
    senales = senales[senales["ejecutable"] == True]  # noqa: E712
    senales = senales.sort_values("fecha_senal").reset_index(drop=True)
    return senales


def construir_mapa_ejecucion(senales: pd.DataFrame) -> dict:
    duplicadas = senales["fecha_ejecucion"].duplicated()
    if duplicadas.any():
        raise AssertionError(
            "Hay mas de una senal ejecutandose el mismo dia; el motor de backtest "
            "asume una senal ejecutable por fecha_ejecucion."
        )
    return {
        row["fecha_ejecucion"]: row
        for _, row in senales.iterrows()
    }


def clasificar_tramo(fecha: pd.Timestamp, config_split: dict) -> str:
    for nombre_tramo in ("train", "validation", "test"):
        info = config_split[nombre_tramo]
        inicio = pd.Timestamp(info["fecha_inicio"])
        fin = pd.Timestamp(info["fecha_fin"])
        if inicio <= fecha <= fin:
            return nombre_tramo
    return "fuera_de_rango"


def ejecutar_backtest(df: pd.DataFrame, mapa_ejecucion: dict):
    estado = "CASH"
    num_acciones = 0.0
    capital = CAPITAL_INICIAL

    posicion_abierta = None  # dict con datos de la entrada en curso
    operaciones = []
    eventos = []  # secuencia de ('ABRIR' | 'CERRAR', fecha) para verificar alternancia

    filas_curva = []

    for idx, fila in df.iterrows():
        fecha = fila["Date"]

        senal = mapa_ejecucion.get(fecha)
        if senal is not None:
            tipo = senal["tipo_senal"]
            precio = senal["precio_ejecucion"]

            if tipo == "COMPRA" and estado == "CASH":
                valor_operacion = capital / (1 + COMISION)
                comision_entrada = capital - valor_operacion
                num_acciones = valor_operacion / precio

                posicion_abierta = {
                    "fecha_entrada": fecha,
                    "idx_entrada": idx,
                    "precio_entrada": precio,
                    "num_acciones": num_acciones,
                    "comision_entrada": comision_entrada,
                    "capital_al_entrar": capital,
                }
                eventos.append(("ABRIR", fecha))

                estado = "LONG"
                # `capital` deja de representar efectivo: se revalua abajo con el Close.

            elif tipo == "VENTA" and estado == "LONG":
                valor_operacion = num_acciones * precio
                comision_salida = valor_operacion * COMISION
                capital_resultante = valor_operacion - comision_salida

                p = posicion_abierta
                resultado_bruto = (precio - p["precio_entrada"]) * p["num_acciones"]
                resultado_neto = capital_resultante - p["capital_al_entrar"]
                retorno_pct = resultado_neto / p["capital_al_entrar"] * 100

                operaciones.append({
                    "fecha_entrada": p["fecha_entrada"],
                    "precio_entrada": p["precio_entrada"],
                    "fecha_salida": fecha,
                    "precio_salida": precio,
                    "num_acciones": p["num_acciones"],
                    "comisiones_totales": p["comision_entrada"] + comision_salida,
                    "resultado_bruto": resultado_bruto,
                    "resultado_neto": resultado_neto,
                    "retorno_pct": retorno_pct,
                    "dias_en_mercado": idx - p["idx_entrada"],
                })
                eventos.append(("CERRAR", fecha))

                capital = capital_resultante
                num_acciones = 0.0
                estado = "CASH"
                posicion_abierta = None

            # COMPRA estando en LONG, o VENTA estando en CASH -> no hacer nada.

        if estado == "LONG":
            capital_dia = num_acciones * fila["Close"]
        else:
            capital_dia = capital

        filas_curva.append({
            "Date": fecha,
            "estado": estado,
            "num_acciones": num_acciones if estado == "LONG" else 0.0,
            "capital": capital_dia,
        })

    verificar_alternancia_eventos(eventos)

    curva = pd.DataFrame(filas_curva)
    operaciones_df = pd.DataFrame(operaciones)

    return curva, operaciones_df, posicion_abierta


def verificar_alternancia_eventos(eventos: list) -> None:
    """Nunca dos ABRIR seguidos sin un CERRAR intermedio (ni dos CERRAR seguidos)."""
    esperado = "ABRIR"
    for tipo_evento, fecha in eventos:
        if tipo_evento != esperado:
            raise AssertionError(
                f"Secuencia de eventos invalida en {fecha.date()}: se esperaba "
                f"{esperado} pero se encontro {tipo_evento}. Esto indicaria dos "
                "aperturas (o dos cierres) consecutivos sin su contraparte."
            )
        esperado = "CERRAR" if esperado == "ABRIR" else "ABRIR"


def calcular_buy_and_hold(df: pd.DataFrame) -> pd.Series:
    primer_open = df.iloc[0]["Open"]
    valor_operacion = CAPITAL_INICIAL / (1 + COMISION)
    num_acciones_bh = valor_operacion / primer_open
    return num_acciones_bh * df["Close"]


def verificaciones_finales(curva: pd.DataFrame, df_precios: pd.DataFrame) -> None:
    if len(curva) != len(df_precios):
        raise AssertionError(
            f"La curva de capital tiene {len(curva)} filas pero SPY_diario.csv "
            f"tiene {len(df_precios)} dias de mercado. Deben coincidir exactamente."
        )

    if (curva["capital"] < 0).any():
        raise AssertionError("Se detecto capital negativo en la curva de la estrategia.")

    if (curva["capital_buy_and_hold"] < 0).any():
        raise AssertionError("Se detecto capital negativo en la curva de buy-and-hold.")

    print("\nVerificaciones obligatorias: OK")
    print(f"  - Filas en curva de capital == filas en SPY_diario.csv ({len(curva)})")
    print("  - Capital nunca negativo (estrategia y buy-and-hold)")
    print("  - Nunca dos aperturas seguidas sin cierre intermedio")


def main() -> None:
    df_precios = cargar_precios(CSV_PRECIOS)
    senales = cargar_senales_ejecutables(CSV_SENALES)
    mapa_ejecucion = construir_mapa_ejecucion(senales)

    with open(CONFIG_SPLIT, "r", encoding="utf-8") as f:
        config_split = json.load(f)

    curva, operaciones, posicion_abierta = ejecutar_backtest(df_precios, mapa_ejecucion)
    curva["capital_buy_and_hold"] = calcular_buy_and_hold(df_precios).values

    if not operaciones.empty:
        operaciones["tramo"] = operaciones["fecha_entrada"].apply(
            lambda f: clasificar_tramo(f, config_split)
        )

    verificaciones_finales(curva, df_precios)

    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    curva.to_csv(CSV_CURVA, index=False)
    operaciones.to_csv(CSV_OPERACIONES, index=False)

    # --- Salida por consola ---
    print("\n" + "=" * 60)
    print("RESUMEN DEL BACKTEST")
    print("=" * 60)

    n_total = len(operaciones)
    print(f"\nOperaciones completadas: {n_total}")
    if n_total:
        print("Por tramo:")
        print(operaciones["tramo"].value_counts()
              .reindex(["train", "validation", "test", "fuera_de_rango"])
              .fillna(0).astype(int).to_string())

    if posicion_abierta is not None:
        print(f"\nPosicion ABIERTA al final del dataset (no contada como completada):")
        print(f"  fecha_entrada={posicion_abierta['fecha_entrada'].date()} "
              f"precio_entrada={posicion_abierta['precio_entrada']:.2f} "
              f"num_acciones={posicion_abierta['num_acciones']:.4f}")

    capital_final_estrategia = curva["capital"].iloc[-1]
    capital_final_bh = curva["capital_buy_and_hold"].iloc[-1]
    retorno_estrategia = (capital_final_estrategia / CAPITAL_INICIAL - 1) * 100
    retorno_bh = (capital_final_bh / CAPITAL_INICIAL - 1) * 100

    print(f"\nCapital inicial: {CAPITAL_INICIAL:,.2f}")
    print(f"Capital final estrategia:    {capital_final_estrategia:,.2f}  "
          f"(retorno: {retorno_estrategia:+.2f}%)")
    print(f"Capital final buy-and-hold:  {capital_final_bh:,.2f}  "
          f"(retorno: {retorno_bh:+.2f}%)")

    dias_mercado = (curva["estado"] == "LONG").sum()
    dias_efectivo = (curva["estado"] == "CASH").sum()
    print(f"\nDias en mercado (LONG): {dias_mercado}")
    print(f"Dias en efectivo (CASH): {dias_efectivo}")

    print(f"\nCurva de capital guardada en: {CSV_CURVA}")
    print(f"Operaciones guardadas en: {CSV_OPERACIONES}")


if __name__ == "__main__":
    main()
