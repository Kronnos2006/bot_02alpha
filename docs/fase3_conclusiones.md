# Fase 3 - Conclusiones: cruce MA_20/MA_50 sobre SPY

## 1. Qué se probó

- **Estrategia**: cruce de medias móviles simples MA_20 / MA_50 sobre el Close diario de SPY.
- **Parámetros fijados de antemano, sin optimización.**
- **Periodo**: 2011-01-03 a 2026-08-19 (3930 días de mercado).
- **Solo largos**: señal de COMPRA abre posición, señal de VENTA cierra a efectivo. Nunca posiciones cortas.
- **Ejecución**: a la apertura del día siguiente a la señal (D+1), evitando look-ahead. Comisión del 0.1% por operación (compra y venta).
- **Capital inicial**: 10000.

## 2. Resultado

### Periodo completo (2011-01-03 a 2026-08-19)

| Métrica | Estrategia | Buy & Hold |
|---|---:|---:|
| Sharpe anualizado | 0.53 | 0.76 |
| Max Drawdown | -30.37% | -34.10% |
| CAGR | 5.46% | 12.25% |
| Retorno total | 128.95% | 506.34% |
| Capital final | 22,895.04 | 60,633.87 |

### Por tramo

| Tramo | Métrica | Estrategia | Buy & Hold |
|---|---|---:|---:|
| **Train** (2011-01-03 a 2020-05-15) | Sharpe | 0.39 | 0.59 |
| | Max Drawdown | -22.70% | -34.10% |
| | CAGR | 3.54% | 9.07% |
| | Retorno total | 38.44% | 125.33% |
| **Validation** (2020-05-18 a 2023-06-30) | Sharpe | 0.40 | 0.80 |
| | Max Drawdown | -30.37% | -25.36% |
| | CAGR | 4.65% | 13.95% |
| | Retorno total | 15.24% | 50.26% |
| **Test** (2023-07-03 a 2026-08-19) | Sharpe | 1.07 | 1.24 |
| | Max Drawdown | -11.01% | -19.00% |
| | CAGR | 11.16% | 19.28% |
| | Retorno total | 39.11% | 73.29% |

Fuente: `resultados/metricas.json`.

## 3. Veredicto

La estrategia **no supera al buy-and-hold en ninguna métrica ni en ningún tramo**. Sharpe 0.53 vs 0.76, CAGR 5.5% vs 12.3%. El drawdown es solo marginalmente mejor (-30.4% vs -34.1%), una diferencia insuficiente para justificar rendir a la mitad.

## 4. Observaciones

- **1205 días en efectivo (31% del periodo)**: el coste de estar fuera del mercado en un índice alcista supera el beneficio de esquivar caídas.
- El **peor drawdown de la estrategia duró 413 días de mercado** (sep-2021 a abr-2023), frente a los **23 días** del buy-and-hold durante el crash de COVID. Una caída de magnitud similar, pero mucho más prolongada.
- **61.5% de acierto y profit factor 2.17**, pese a rendir por debajo del benchmark: acertar más veces que fallar no implica batir al mercado.
- **Tamaño de muestra insuficiente en los tres tramos** (27/7/5 operaciones, umbral 30). Las métricas por tramo son orientativas, no concluyentes.

## 5. Limitaciones conocidas

- **COVID quedó en train por decisión de diseño**: validation y test no contienen ningún shock comparable, por lo que el drawdown de esos tramos es optimista respecto a lo que podría ocurrir en producción.
- **Comisión modelada como 0.1% porcentual.** Con capital pequeño, los mínimos fijos de brokers reales serían proporcionalmente más caros que este modelo.
- **Sin slippage, sin impacto de mercado, sin dividendos** (se usaron precios sin ajustar, ver Fase 1).

## 6. Decisión

**Hipótesis descartada como estrategia autónoma. No pasa a Fase 4.**

No reoptimizar los parámetros (20/50) sobre estos mismos datos: hacerlo constituiría data snooping sobre un conjunto ya evaluado.
