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
