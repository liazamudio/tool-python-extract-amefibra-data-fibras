"""Funciones de procesamiento y normalización de datos de FIBRAs."""

import re
import unicodedata
from datetime import datetime
from typing import Optional

import pandas as pd

FUENTE_DATOS = "AMEFIBRA / Economatica México"


def _a_snake_case(texto: str) -> str:
    """Convierte un encabezado de columna a snake_case ASCII (apto para CSV/análisis).

    Ejemplos: "Cotización" -> "cotizacion", "Máx. 52 s." -> "max_52_s",
    "Var. %" -> "var_pct" (el '%' se convierte a la palabra "pct" ANTES de quitar
    acentos/puntuación, para que no colisione con la columna "Var.", que da "var").
    """
    texto = texto.replace("%", "pct")
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_acentos).strip("_").lower()


def normalizar_para_analisis(df: pd.DataFrame, momento_extraccion: Optional[datetime] = None) -> pd.DataFrame:
    """Prepara el DataFrame crudo del Índice FIBRAS para un export "listo para análisis".

    Encabezados en snake_case, columnas de porcentaje convertidas a numérico, y
    columnas de trazabilidad (momento de extracción y fuente de los datos).
    """
    momento_extraccion = momento_extraccion or datetime.now()
    resultado = df.copy()
    resultado.columns = [_a_snake_case(str(columna)) for columna in resultado.columns]
    for columna in resultado.columns:
        serie = resultado[columna]
        if pd.api.types.is_string_dtype(serie):
            valores = serie.astype(str).str.strip()
            if valores.str.endswith("%").all():
                resultado[columna] = pd.to_numeric(valores.str.rstrip("%"), errors="coerce")
    resultado.insert(0, "fecha_hora_extraccion", momento_extraccion.isoformat(timespec="seconds"))
    resultado.insert(1, "fuente_datos", FUENTE_DATOS)
    return resultado


def _normalizar_ticker(ticker: str) -> str:
    ticker = str(ticker).strip().upper()
    if not ticker:
        raise ValueError("El ticker no puede estar vacío.")
    return ticker.removesuffix(".MX")


def _detectar_periodicidad(fechas: pd.Series) -> str:
    diferencias = fechas.sort_values().diff().dt.days.dropna()
    if diferencias.empty:
        return "indeterminada"
    mediana = diferencias.median()
    if mediana <= 45:
        return "mensual"
    if mediana <= 120:
        return "trimestral"
    return "otra"


def obtener_anios_disponibles(historial: pd.DataFrame) -> list[int]:
    """Años calendario con al menos una distribución en `historial`, del más reciente al más antiguo."""
    años = pd.to_datetime(historial["ex_date"], errors="coerce").dt.year.dropna().astype(int)
    return sorted(años.unique().tolist(), reverse=True)


def calcular_ventana_movil_12_meses(fecha_referencia: Optional[datetime] = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Rango de los últimos 12 meses completos terminando en `fecha_referencia`.

    `fecha_referencia` es parametrizable para poder correr el análisis de forma
    retrospectiva (pruebas, revisiones históricas); por defecto usa la fecha actual
    del sistema. `fecha_fin = fecha_referencia`; `fecha_inicio = fecha_fin - 1 año +
    1 día` (con fecha de referencia 2026-08-30, el rango resultante es
    2025-08-31 a 2026-08-30).
    """
    fecha_fin = pd.Timestamp(fecha_referencia) if fecha_referencia is not None else pd.Timestamp(datetime.now().date())
    fecha_inicio = fecha_fin - pd.DateOffset(years=1) + pd.Timedelta(days=1)
    return fecha_inicio, fecha_fin


def calcular_riesgo_mensual(
    cierres: pd.Series,
    pagos: pd.DataFrame,
    fecha_inicio: pd.Timestamp,
    fecha_fin: pd.Timestamp,
) -> dict:
    """Volatilidad del retorno TOTAL mensual (variación de precio + dividendos del mes) del periodo.

    Se usa retorno total y no solo de precio porque el riesgo relevante para quien
    invierte es la volatilidad de lo que efectivamente recibe cada mes, dividendos
    incluidos, no solo la del precio. Se calculan 12 retornos mensuales a partir de
    13 cierres de fin de mes (el mes anterior al inicio del periodo sirve de base
    para el primer retorno), por lo que `cierres` debe cubrir desde antes de
    `fecha_inicio` hasta `fecha_fin`.

    Devuelve la desviación estándar de esos 12 retornos en su forma mensual directa
    (más intuitiva para una ficha rápida de leer) y su versión anualizada
    (mensual × √12, más comparable con benchmarks de mercado que reportan
    volatilidad anual), junto con la serie de los 12 retornos mensuales (para un
    gráfico de barras positivo/negativo en la ficha completa).

    Lanza `ValueError` si `cierres` no alcanza para completar los 12 retornos
    mensuales del periodo (p. ej. tickers con menos de 12 meses de historial).
    """
    cierres_mensuales = cierres.sort_index().resample("ME").last().dropna()
    cierres_mensuales = cierres_mensuales[cierres_mensuales.index <= fecha_fin + pd.offsets.MonthEnd(0)]
    if len(cierres_mensuales) < 13:
        raise ValueError(
            "No hay suficiente historial de precios para calcular los 12 retornos "
            f"mensuales del periodo {fecha_inicio:%Y-%m-%d} a {fecha_fin:%Y-%m-%d} "
            f"(se necesitan 13 cierres de fin de mes; hay {len(cierres_mensuales)})."
        )
    cierres_mensuales = cierres_mensuales.tail(13)

    pagos_por_mes = pagos.copy()
    pagos_por_mes["ex_date"] = pd.to_datetime(pagos_por_mes["ex_date"], errors="coerce")
    dividendos_mensuales = (
        pagos_por_mes.set_index("ex_date")["amount_mxn"]
        .resample("ME")
        .sum()
        .reindex(cierres_mensuales.index[1:], fill_value=0.0)
    )

    retornos_precio = cierres_mensuales.pct_change().dropna()
    retornos_totales = retornos_precio + dividendos_mensuales / cierres_mensuales.shift(1).reindex(retornos_precio.index)
    volatilidad_mensual_pct = float(retornos_totales.std() * 100)
    return {
        "retornos_mensuales_pct": retornos_totales * 100,
        "volatilidad_mensual_pct": volatilidad_mensual_pct,
        "volatilidad_anualizada_pct": volatilidad_mensual_pct * (12**0.5),
    }
