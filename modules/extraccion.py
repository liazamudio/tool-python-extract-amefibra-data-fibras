"""Funciones de extracción de datos de FIBRAs.

Cubre dos fuentes: la tabla del Índice FIBRAS de AMEFIBRA (vía Playwright,
porque los datos se renderizan por JavaScript/WebSocket) y las series de
dividendos/precios históricos de cada FIBRA (vía Yahoo Finance / yfinance).
"""

import asyncio
import concurrent.futures
import io
import os
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, TypeVar

import pandas as pd
import requests
import yfinance as yf
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from .procesamiento import _detectar_periodicidad, _normalizar_ticker

URL_PAGINA = "https://amefibra.com/el-mercado/indice-fibras/"

# El iframe de la tabla es .../Emisora/Reportes (a secas).
# Hay otros dos iframes hermanos que NO queremos: .../Reportes/Grafica y .../Reportes/Marquesina
PATRON_IFRAME_TABLA = re.compile(r"edimex\.com\.mx/Emisora/Reportes/?(\?.*)?$")

COLUMNAS_DISTRIBUCIONES = [
    "ticker",
    "ex_date",
    "amount_mxn",
    "close_on_ex_date_mxn",
    "yield_pct",
    "annualized_yield_pct",
    "periodicity",
]


def _limpiar_encabezado(texto: str) -> str:
    """Quita flechas de ordenamiento y espacios sobrantes de los encabezados de columna."""
    texto = re.sub(r"[↑↓]", "", str(texto))
    return re.sub(r"\s+", " ", texto).strip()


def _localizar_frame_tabla(page, intentos=10, espera_ms=1000):
    """Busca, con reintentos, el iframe que contiene la tabla de indicadores."""
    for _ in range(intentos):
        for frame in page.frames:
            if PATRON_IFRAME_TABLA.search(frame.url or ""):
                return frame
        page.wait_for_timeout(espera_ms)
    return None


def _extraer_html_tabla(frame) -> Optional[str]:
    """Dentro del iframe, ubica la tabla con más filas (la de indicadores) y regresa su HTML."""
    return frame.evaluate("""() => {
        const tablas = Array.from(document.querySelectorAll('table'));
        let mejor = null, filasMax = -1;
        for (const tabla of tablas) {
            const filas = tabla.querySelectorAll('tbody tr').length;
            if (filas > filasMax) { filasMax = filas; mejor = tabla; }
        }
        return mejor ? mejor.outerHTML : null;
    }""")


def obtener_tabla_fibras(headless: bool = True, timeout_datos_ms: int = 30000) -> pd.DataFrame:
    """Abre la página del Índice FIBRAS y devuelve la tabla de indicadores como DataFrame."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        page = browser.new_page(locale="es-MX")
        try:
            page.goto(URL_PAGINA, wait_until="domcontentloaded")
            frame = _localizar_frame_tabla(page)
            if frame is None:
                raise RuntimeError("No se encontró el iframe con la tabla de FIBRAs.")
            try:
                frame.wait_for_function("""() => {
                    const filas = document.querySelectorAll('table tbody tr');
                    if (filas.length === 0) return false;
                    const celda = filas[0].querySelector('td:nth-child(2)');
                    const texto = celda ? celda.textContent.trim() : '';
                    return texto.length > 0 && texto !== '0' && texto !== '0.00';
                }""", timeout=timeout_datos_ms)
            except PWTimeout:
                print("Aviso: se agotó el tiempo esperando datos en vivo; se usará lo cargado.", file=sys.stderr)
            html_tabla = _extraer_html_tabla(frame)
        finally:
            browser.close()
    if not html_tabla:
        raise RuntimeError("No se pudo extraer la tabla de indicadores.")
    df = pd.read_html(io.StringIO(html_tabla))[0]
    df.columns = [_limpiar_encabezado(columna) for columna in df.columns]
    return df.dropna(axis=1, how="all")


_T = TypeVar("_T")


def ejecutar_con_playwright_sync(tarea: Callable[[], _T]) -> _T:
    """Ejecuta `tarea` (que usa la API síncrona de Playwright) de forma segura desde un notebook de Jupyter.

    El kernel de Jupyter ya corre un event loop de asyncio, y la API síncrona de
    Playwright no admite ejecutarse dentro de uno (lanza Error), así que se
    despacha a un hilo aparte. Playwright crea su propio loop internamente con
    asyncio.new_event_loop(), que en Windows respeta la *policy* activa; el
    kernel deja configurada una policy basada en SelectorEventLoop (para
    compatibilidad con zmq/tornado), que no soporta subprocesos, y Playwright
    necesita subprocesos para lanzar el navegador. Por eso se activa aquí,
    solo para este hilo, la policy de Proactor que sí los soporta. La API de
    policies está deprecada desde Python 3.14 (se retira en 3.16) pero sigue
    siendo, por ahora, el único gancho disponible para influir en qué clase de
    loop crea Playwright (llama a asyncio.new_event_loop() directo, sin
    exponer alternativa).
    """

    def _tarea_en_hilo():
        if sys.platform == "win32":
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        return tarea()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_tarea_en_hilo).result()


def obtener_tabla_fibras_en_notebook(headless: bool = True, timeout_datos_ms: int = 30000) -> pd.DataFrame:
    """Como `obtener_tabla_fibras`, pero segura de llamar desde un notebook de Jupyter (ver `ejecutar_con_playwright_sync`)."""
    return ejecutar_con_playwright_sync(
        lambda: obtener_tabla_fibras(headless=headless, timeout_datos_ms=timeout_datos_ms)
    )


def _descargar_con_reintentos(ticker_yahoo: str, intentos: int = 3, espera_s: float = 2.0):
    ultimo_error = None
    for intento in range(intentos):
        try:
            return yf.Ticker(ticker_yahoo).dividends
        except Exception as error:
            ultimo_error = error
            if intento < intentos - 1:
                time.sleep(espera_s * (intento + 1))
    raise RuntimeError(f"No se pudo descargar distribuciones de {ticker_yahoo}.") from ultimo_error


_CACHE_CIERRES_ANUALES: dict[tuple[str, int], pd.Series] = {}


def _descargar_cierres_anuales(ticker_yahoo: str, año: int) -> pd.Series:
    """Cierres diarios de `ticker_yahoo` en el año calendario `año`.

    Los años ya cerrados (anteriores al actual) se cachean en memoria (diccionario
    simple, no `functools.lru_cache`: ver `_descargar_cierres_rango` para por qué):
    dos fichas consecutivas del mismo ticker/año (p. ej. la ficha de rendimiento y la
    ficha de ejemplo para cliente) no vuelven a descargar los mismos precios de
    Yahoo Finance. El año en curso nunca se cachea, porque sus cierres cambian
    mientras avanza el año (el último cierre disponible es el "precio actual").
    """
    if año >= datetime.now().year:
        return _descargar_cierres_anuales_sin_cachear(ticker_yahoo, año)
    clave = (ticker_yahoo, año)
    if clave not in _CACHE_CIERRES_ANUALES:
        _CACHE_CIERRES_ANUALES[clave] = _descargar_cierres_anuales_sin_cachear(ticker_yahoo, año)
    return _CACHE_CIERRES_ANUALES[clave].copy()


def _descargar_cierres_anuales_sin_cachear(ticker_yahoo: str, año: int) -> pd.Series:
    inicio = pd.Timestamp(year=año, month=1, day=1)
    fin = pd.Timestamp(year=año + 1, month=1, day=1)
    precios = yf.download(
        ticker_yahoo,
        start=inicio.strftime("%Y-%m-%d"),
        end=fin.strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if precios is None or precios.empty:
        raise ValueError(f"No hay precios disponibles para {ticker_yahoo} en {año}.")
    if isinstance(precios.columns, pd.MultiIndex):
        precios.columns = precios.columns.get_level_values(0)
    if "Close" not in precios:
        raise ValueError(f"La respuesta de precios de {ticker_yahoo} no contiene cierre.")
    cierres = precios["Close"].dropna()
    cierres.index = pd.to_datetime(cierres.index).tz_localize(None).normalize()
    return cierres


_CACHE_CIERRES_RANGO: dict[tuple[str, pd.Timestamp, pd.Timestamp], pd.Series] = {}


def _descargar_cierres_rango(ticker_yahoo: str, inicio: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    """Cierres diarios de `ticker_yahoo` entre `inicio` y `fin` (ambos inclusive).

    Generaliza `_descargar_cierres_anuales` para un rango arbitrario de fechas (p. ej.
    la ventana móvil de últimos 12 meses). Se cachea en memoria (diccionario simple,
    no `functools.lru_cache`: ese decorador envuelve la función en un objeto de C que
    `%autoreload` de IPython no siempre logra actualizar en caliente al agregar
    funciones nuevas al módulo) solo cuando `fin` ya quedó en el pasado (rango
    cerrado); si `fin` es hoy o una fecha futura, se descarga siempre en fresco,
    mismo criterio que se usa para el año en curso en `_descargar_cierres_anuales`.
    """
    if fin.normalize() >= pd.Timestamp(datetime.now().date()):
        return _descargar_cierres_rango_sin_cachear(ticker_yahoo, inicio, fin)
    clave = (ticker_yahoo, inicio, fin)
    if clave not in _CACHE_CIERRES_RANGO:
        _CACHE_CIERRES_RANGO[clave] = _descargar_cierres_rango_sin_cachear(ticker_yahoo, inicio, fin)
    return _CACHE_CIERRES_RANGO[clave].copy()


def _descargar_cierres_rango_sin_cachear(ticker_yahoo: str, inicio: pd.Timestamp, fin: pd.Timestamp) -> pd.Series:
    precios = yf.download(
        ticker_yahoo,
        start=inicio.strftime("%Y-%m-%d"),
        end=(fin + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if precios is None or precios.empty:
        raise ValueError(
            f"No hay precios disponibles para {ticker_yahoo} entre {inicio:%Y-%m-%d} y {fin:%Y-%m-%d}."
        )
    if isinstance(precios.columns, pd.MultiIndex):
        precios.columns = precios.columns.get_level_values(0)
    if "Close" not in precios:
        raise ValueError(f"La respuesta de precios de {ticker_yahoo} no contiene cierre.")
    cierres = precios["Close"].dropna()
    cierres.index = pd.to_datetime(cierres.index).tz_localize(None).normalize()
    return cierres


def _descargar_historico_completo(ticker_yahoo: str) -> pd.Series:
    """Cierres diarios de `ticker_yahoo` desde el primer dato disponible en Yahoo Finance hasta hoy.

    Usada por la ficha comparativa multi-periodo (lapso "Histórico" y para acotar
    qué otros lapsos son aplicables según cuánto historial tiene el ticker). No se
    cachea: se descarga una sola vez por corrida de esa ficha.
    """
    precios = yf.download(ticker_yahoo, period="max", auto_adjust=False, progress=False, threads=False)
    if precios is None or precios.empty:
        raise ValueError(f"No hay precios históricos disponibles para {ticker_yahoo}.")
    if isinstance(precios.columns, pd.MultiIndex):
        precios.columns = precios.columns.get_level_values(0)
    if "Close" not in precios:
        raise ValueError(f"La respuesta de precios de {ticker_yahoo} no contiene cierre.")
    cierres = precios["Close"].dropna()
    cierres.index = pd.to_datetime(cierres.index).tz_localize(None).normalize()
    return cierres


def obtener_distribuciones(ticker: str, carpeta_salida: Path, intentos: int = 3) -> pd.DataFrame:
    """Obtiene distribuciones históricas de una FIBRA BMV y las exporta a `carpeta_salida`."""
    ticker_base = _normalizar_ticker(ticker)
    ticker_yahoo = f"{ticker_base}.MX"
    serie = _descargar_con_reintentos(ticker_yahoo, intentos=intentos)
    if serie.empty:
        raise ValueError(f"Yahoo Finance no devolvió distribuciones para {ticker_yahoo}.")

    distribuciones = serie.rename("amount_mxn").rename_axis("ex_date").reset_index()
    distribuciones["ex_date"] = pd.to_datetime(distribuciones["ex_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    distribuciones["amount_mxn"] = pd.to_numeric(distribuciones["amount_mxn"], errors="coerce")
    distribuciones = distribuciones.dropna(subset=["ex_date", "amount_mxn"])
    distribuciones = distribuciones[distribuciones["amount_mxn"] > 0]
    distribuciones = distribuciones.drop_duplicates(subset=["ex_date", "amount_mxn"])

    precios = yf.download(
        ticker_yahoo,
        start=(distribuciones["ex_date"].min() - pd.Timedelta(days=5)).strftime("%Y-%m-%d"),
        end=(distribuciones["ex_date"].max() + pd.Timedelta(days=2)).strftime("%Y-%m-%d"),
        auto_adjust=False,
        progress=False,
        threads=False,
    )
    if precios is None or precios.empty:
        cierre = pd.Series(dtype=float)
    else:
        if isinstance(precios.columns, pd.MultiIndex):
            precios.columns = precios.columns.get_level_values(0)
        cierre = precios["Close"].copy() if "Close" in precios else pd.Series(dtype=float)
        cierre.index = pd.to_datetime(cierre.index).tz_localize(None).normalize()

    distribuciones["close_on_ex_date_mxn"] = distribuciones["ex_date"].map(cierre)
    distribuciones["yield_pct"] = (
        distribuciones["amount_mxn"] / distribuciones["close_on_ex_date_mxn"] * 100
    ).where(distribuciones["close_on_ex_date_mxn"] > 0)
    diferencias_dias = distribuciones["ex_date"].sort_values().diff().dt.days
    intervalo_referencia = diferencias_dias.dropna().median()
    # Con una sola distribución en todo el historial (FIBRA de IPO muy reciente o muy
    # poco líquida), `diferencias_dias` no tiene ningún valor no nulo del cual sacar
    # una mediana, así que `intervalo_referencia` queda NaN y `annualized_yield_pct`
    # también: no hay forma de estimar el intervalo entre pagos con un solo dato.
    distribuciones["annualized_yield_pct"] = (
        distribuciones["yield_pct"] * 365 / diferencias_dias.fillna(intervalo_referencia)
    )
    periodicidad = _detectar_periodicidad(distribuciones["ex_date"])
    resultado = pd.DataFrame({
        "ticker": ticker_base,
        "ex_date": distribuciones["ex_date"],
        "amount_mxn": distribuciones["amount_mxn"],
        "close_on_ex_date_mxn": distribuciones["close_on_ex_date_mxn"],
        "yield_pct": distribuciones["yield_pct"],
        "annualized_yield_pct": distribuciones["annualized_yield_pct"],
        "periodicity": periodicidad,
    })
    resultado = resultado.sort_values("ex_date").reset_index(drop=True)[COLUMNAS_DISTRIBUCIONES]
    resultado["ex_date"] = resultado["ex_date"].dt.strftime("%Y-%m-%d")
    momento = datetime.now()
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_{ticker_base}_dividendos.csv"
    resultado.to_csv(ruta, index=False, encoding="utf-8")
    resultado.attrs["ruta_csv"] = ruta
    return resultado


# --- CETES 28 días (Banxico), para la tasa libre de riesgo del ratio tipo Sharpe ---

URL_BANXICO_SIE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series"
# CETES 28 días, tasa de rendimiento en subasta primaria (% anualizado).
SERIE_CETES_28D = "SF43936"
VARIABLE_ENTORNO_TOKEN_BANXICO = "BANXICO_SIE_TOKEN"


class CetesNoDisponibleError(RuntimeError):
    """La tasa de CETES 28 días no se pudo obtener (sin token de Banxico, o falla de red/API).

    Se distingue de otros errores para que quien calcule el ratio tipo Sharpe pueda
    degradar con el criterio documentado (dejar el ratio en NaN, con una nota) en vez
    de tronar toda la ficha multi-periodo por un solo indicador.
    """


def obtener_cetes_28d(fecha_inicio: pd.Timestamp, fecha_fin: pd.Timestamp) -> pd.Series:
    """Tasa de rendimiento de CETES 28 días (% anualizado) entre `fecha_inicio` y `fecha_fin`.

    Fuente: API SIE de Banxico (serie `SF43936`), la fuente oficial de esta tasa en
    México. Requiere un token personal gratuito (se obtiene en
    https://www.banxico.org.mx/SieAPIRest/service/v1/token), leído de la variable de
    entorno `BANXICO_SIE_TOKEN`; no se pide interactivamente ni se guarda en el
    repositorio. Sin ese token, o si la API falla, se lanza `CetesNoDisponibleError`
    en vez de inventar una tasa.
    """
    token = os.environ.get(VARIABLE_ENTORNO_TOKEN_BANXICO)
    if not token:
        raise CetesNoDisponibleError(
            f"No hay token de Banxico configurado (variable de entorno {VARIABLE_ENTORNO_TOKEN_BANXICO}). "
            "Se obtiene gratis en https://www.banxico.org.mx/SieAPIRest/service/v1/token."
        )
    url = f"{URL_BANXICO_SIE}/{SERIE_CETES_28D}/datos/{fecha_inicio:%Y-%m-%d}/{fecha_fin:%Y-%m-%d}"
    try:
        respuesta = requests.get(url, headers={"Bmx-Token": token}, timeout=30)
        respuesta.raise_for_status()
        datos = respuesta.json()["bmx"]["series"][0]["datos"]
    except Exception as error:
        raise CetesNoDisponibleError(f"No se pudo obtener CETES 28 días de Banxico: {error}") from error

    serie = pd.DataFrame(datos)
    serie["fecha"] = pd.to_datetime(serie["fecha"], format="%d/%m/%Y")
    serie["dato"] = pd.to_numeric(serie["dato"], errors="coerce")
    serie = serie.dropna(subset=["dato"]).set_index("fecha")["dato"].sort_index()
    if serie.empty:
        raise CetesNoDisponibleError(f"Banxico no devolvió datos de CETES 28 días entre {fecha_inicio:%Y-%m-%d} y {fecha_fin:%Y-%m-%d}.")
    return serie
