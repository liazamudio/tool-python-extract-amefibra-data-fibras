"""Funciones de procesamiento y normalización de datos de FIBRAs."""

import re
import unicodedata
from datetime import datetime
from typing import Callable, Optional

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


def obtener_anios_disponibles_comunes(historiales: dict) -> list[int]:
    """Años calendario con al menos una distribución en TODOS los historiales dados.

    `historiales` es un dict `{ticker: DataFrame de distribuciones}` (el que arma
    `presentacion.descargar_historiales_dividendos`). Es la **intersección** de
    `obtener_anios_disponibles` de cada ticker: solo los años en que *todos* tienen
    datos, del más reciente al más antiguo. Las entradas con valor `None` (ticker
    cuyo historial no se pudo descargar) se ignoran: la intersección se calcula solo
    sobre los tickers con datos, para no dejarla vacía por un fallo individual.
    """
    conjuntos = [
        set(obtener_anios_disponibles(historial))
        for historial in historiales.values()
        if historial is not None and not historial.empty
    ]
    if not conjuntos:
        return []
    return sorted(set.intersection(*conjuntos), reverse=True)


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


def _retornos_totales_mensuales(cierres: pd.Series, pagos: pd.DataFrame, fecha_fin: pd.Timestamp) -> pd.Series:
    """Retorno TOTAL mensual (variación de precio + dividendos del mes), en fracción (no %).

    Se usa retorno total y no solo de precio porque el riesgo relevante para quien
    invierte es la volatilidad de lo que efectivamente recibe cada mes, dividendos
    incluidos, no solo la del precio. Un retorno por cada cierre de fin de mes en
    `cierres` hasta `fecha_fin` (inclusive), salvo el primero, que solo sirve de base
    para calcular el retorno del segundo (por eso la serie resultante tiene un
    elemento menos que meses con cierre en `cierres`). Compartida por
    `calcular_riesgo_mensual` (ventana de 12 meses) y la ficha comparativa
    multi-periodo (`armar_tabla_multiperiodo`), cada quien decide cuántos retornos
    de la cola usar según su propia ventana.
    """
    cierres_mensuales = cierres.sort_index().resample("ME").last().dropna()
    cierres_mensuales = cierres_mensuales[cierres_mensuales.index <= fecha_fin + pd.offsets.MonthEnd(0)]

    pagos_por_mes = pagos.copy()
    pagos_por_mes["ex_date"] = pd.to_datetime(pagos_por_mes["ex_date"], errors="coerce")
    dividendos_mensuales = (
        pagos_por_mes.set_index("ex_date")["amount_mxn"]
        .resample("ME")
        .sum()
        .reindex(cierres_mensuales.index[1:], fill_value=0.0)
    )

    retornos_precio = cierres_mensuales.pct_change().dropna()
    return retornos_precio + dividendos_mensuales / cierres_mensuales.shift(1).reindex(retornos_precio.index)


def calcular_riesgo_mensual(
    cierres: pd.Series,
    pagos: pd.DataFrame,
    fecha_inicio: pd.Timestamp,
    fecha_fin: pd.Timestamp,
) -> dict:
    """Volatilidad del retorno TOTAL mensual (variación de precio + dividendos del mes) del periodo.

    Se calculan 12 retornos mensuales a partir de 13 cierres de fin de mes (el mes
    anterior al inicio del periodo sirve de base para el primer retorno), por lo que
    `cierres` debe cubrir desde antes de `fecha_inicio` hasta `fecha_fin`.

    Devuelve la desviación estándar de esos 12 retornos en su forma mensual directa
    (más intuitiva para una ficha rápida de leer) y su versión anualizada
    (mensual × √12, más comparable con benchmarks de mercado que reportan
    volatilidad anual), junto con la serie de los 12 retornos mensuales (para un
    gráfico de barras positivo/negativo en la ficha completa).

    Lanza `ValueError` si `cierres` no alcanza para completar los 12 retornos
    mensuales del periodo (p. ej. tickers con menos de 12 meses de historial).
    """
    retornos_totales = _retornos_totales_mensuales(cierres, pagos, fecha_fin)
    if len(retornos_totales) < 12:
        raise ValueError(
            "No hay suficiente historial de precios para calcular los 12 retornos "
            f"mensuales del periodo {fecha_inicio:%Y-%m-%d} a {fecha_fin:%Y-%m-%d} "
            f"(se necesitan 13 cierres de fin de mes; hay {len(retornos_totales) + 1})."
        )
    retornos_totales = retornos_totales.tail(12)
    volatilidad_mensual_pct = float(retornos_totales.std() * 100)
    return {
        "retornos_mensuales_pct": retornos_totales * 100,
        "volatilidad_mensual_pct": volatilidad_mensual_pct,
        "volatilidad_anualizada_pct": volatilidad_mensual_pct * (12**0.5),
    }


# --- Ficha comparativa de rendimiento/riesgo multi-periodo ---

_LAPSOS_MULTIPERIODO = ["1A", "2A", "5A", "10A", "Histórico"]
_ANIOS_LAPSO_FIJO = {"1A": 1, "2A": 2, "5A": 5, "10A": 10}


def calcular_cagr(valor_inicial: float, valor_final: float, años: float) -> float:
    """Tasa de crecimiento anual compuesta (CAGR): `(valor_final / valor_inicial)^(1/años) - 1`.

    Devuelve una fracción (0.10 = 10%), no un porcentaje. `valor_final` debe incluir
    ya el efecto de los dividendos del periodo si se quiere un CAGR de rendimiento
    total (ver `_calcular_indicadores_ventana`, que lo usa con `valor_final = precio
    final + dividendos acumulados`: suma simple, sin modelar reinversión nocional —
    misma convención de "dividendos como efectivo, no reinvertidos" que ya usa el
    resto de las fichas del proyecto, por consistencia).
    """
    if valor_inicial <= 0:
        raise ValueError("valor_inicial debe ser positivo para calcular CAGR.")
    if años <= 0:
        raise ValueError("años debe ser positivo para calcular CAGR.")
    return (valor_final / valor_inicial) ** (1 / años) - 1


def calcular_drawdown_maximo(precios: pd.Series) -> float:
    """Mayor caída porcentual desde un máximo hasta un mínimo posterior, dentro de `precios`.

    Devuelve un valor menor o igual a 0 (p. ej. -32.5 = una caída máxima de 32.5%
    respecto al máximo previo alcanzado). 0.0 si `precios` está vacía o solo sube.
    """
    precios = precios.sort_index()
    if precios.empty:
        return 0.0
    maximo_acumulado = precios.cummax()
    drawdown_pct = (precios - maximo_acumulado) / maximo_acumulado * 100
    return float(drawdown_pct.min())


def calcular_ratio_sharpe(rendimiento_anual_pct: float, riesgo_anual_pct: float, tasa_libre_riesgo_pct: float) -> float:
    """Ratio rendimiento/riesgo tipo Sharpe: `(rendimiento anual - tasa libre de riesgo) / riesgo anual`.

    Los tres parámetros van en el mismo tipo de unidad (% anualizado). Devuelve NaN
    si `riesgo_anual_pct` es 0 (no se puede dividir entre cero volatilidad).
    """
    if riesgo_anual_pct == 0:
        return float("nan")
    return (rendimiento_anual_pct - tasa_libre_riesgo_pct) / riesgo_anual_pct


def _calcular_indicadores_ventana(
    etiqueta: str,
    precios_historicos: pd.Series,
    pagos_historicos: pd.DataFrame,
    fecha_inicio: pd.Timestamp,
    fecha_fin: pd.Timestamp,
    tasa_cetes_pct: Optional[float],
    retornos_todos: pd.Series,
) -> dict:
    """Calcula los 13 indicadores de rendimiento/riesgo del lapso `etiqueta` (ver Paso 2 del prompt).

    `precios_historicos` y `pagos_historicos` son el historial COMPLETO del ticker
    (no recortado al lapso): esta función hace el recorte internamente y, para la
    volatilidad mensual, necesita datos de antes de `fecha_inicio` para tener una
    base del primer retorno del lapso. `retornos_todos` es el resultado ya calculado
    de `_retornos_totales_mensuales(precios_historicos, pagos_historicos, fecha_fin)`:
    es el mismo para los 5 lapsos de una misma corrida (todos comparten `fecha_fin`),
    así que `armar_tabla_multiperiodo` lo calcula una sola vez en vez de repetirlo
    por cada lapso.
    """
    precios_ventana = precios_historicos[
        (precios_historicos.index >= fecha_inicio) & (precios_historicos.index <= fecha_fin)
    ]
    if precios_ventana.empty:
        raise ValueError(f"No hay precios en el lapso {etiqueta} ({fecha_inicio:%Y-%m-%d} a {fecha_fin:%Y-%m-%d}).")
    precio_inicial = float(precios_ventana.iloc[0])
    precio_final = float(precios_ventana.iloc[-1])

    pagos_ventana = pagos_historicos[
        (pagos_historicos["ex_date"] >= fecha_inicio) & (pagos_historicos["ex_date"] <= fecha_fin)
    ]
    dividendos_mxn = float(pagos_ventana["amount_mxn"].sum())
    plusvalia_mxn = precio_final - precio_inicial
    ganancia_total_mxn = plusvalia_mxn + dividendos_mxn
    pct_plusvalia = plusvalia_mxn / precio_inicial * 100
    pct_dividendos = dividendos_mxn / precio_inicial * 100
    pct_ganancia_total = pct_plusvalia + pct_dividendos

    años = (fecha_fin - fecha_inicio).days / 365.25
    # Convención de "dividendos como efectivo, no reinvertidos" (ver `calcular_cagr`).
    valor_final_con_dividendos = precio_final + dividendos_mxn
    cagr = calcular_cagr(precio_inicial, valor_final_con_dividendos, años)
    rendimiento_anual_pct = cagr * 100
    rendimiento_mensual_pct = ((1 + cagr) ** (1 / 12) - 1) * 100

    # Volatilidad: desviación estándar muestral (ddof=1, el default de pandas) de los
    # retornos mensuales del lapso. Si no hay al menos 2 retornos mensuales dentro del
    # lapso (posible en el lapso "Histórico" de un ticker recién listado), queda NaN
    # en vez de tronar toda la tabla por un lapso que de por sí ya es un caso límite.
    try:
        retornos_ventana = retornos_todos[retornos_todos.index >= fecha_inicio]
        riesgo_mensual_pct = float(retornos_ventana.std() * 100) if len(retornos_ventana) >= 2 else float("nan")
    except Exception:
        riesgo_mensual_pct = float("nan")
    riesgo_anual_pct = riesgo_mensual_pct * (12**0.5)

    drawdown_maximo_pct = calcular_drawdown_maximo(precios_ventana)

    hay_riesgo_valido = riesgo_anual_pct == riesgo_anual_pct  # descarta NaN
    ratio_sharpe = (
        calcular_ratio_sharpe(rendimiento_anual_pct, riesgo_anual_pct, tasa_cetes_pct)
        if (tasa_cetes_pct is not None and hay_riesgo_valido)
        else float("nan")
    )

    return {
        "lapso": etiqueta,
        "fecha_inicio": fecha_inicio.strftime("%Y-%m-%d"),
        "fecha_fin": fecha_fin.strftime("%Y-%m-%d"),
        "rendimiento_anual_pct": rendimiento_anual_pct,
        "rendimiento_mensual_pct": rendimiento_mensual_pct,
        "riesgo_anual_pct": riesgo_anual_pct,
        "riesgo_mensual_pct": riesgo_mensual_pct,
        "plusvalia_mxn": plusvalia_mxn,
        "dividendos_mxn": dividendos_mxn,
        "ganancia_total_mxn": ganancia_total_mxn,
        "pct_plusvalia": pct_plusvalia,
        "pct_dividendos": pct_dividendos,
        "pct_ganancia_total": pct_ganancia_total,
        "num_pagos": int(len(pagos_ventana)),
        "drawdown_maximo_pct": drawdown_maximo_pct,
        "ratio_sharpe": ratio_sharpe,
        "tasa_cetes_pct": tasa_cetes_pct if tasa_cetes_pct is not None else float("nan"),
    }


def armar_tabla_multiperiodo(
    ticker: str,
    precios_historicos: pd.Series,
    pagos_historicos: pd.DataFrame,
    fecha_referencia: Optional[datetime] = None,
    obtener_tasa_cetes: Optional[Callable[[pd.Timestamp, pd.Timestamp], float]] = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Arma la tabla comparativa de rendimiento y riesgo de `ticker` en 5 ventanas de tiempo.

    Lapsos evaluados, contados hacia atrás desde `fecha_referencia` (por defecto,
    hoy): último año (1A), últimos 2/5/10 años, e Histórico (desde el primer precio
    disponible). Un lapso fijo (1A/2A/5A/10A) se OMITE por completo —no se muestra
    con datos parciales— si el ticker no tiene historial de precios suficiente para
    cubrirlo completo; queda documentado en la lista de `notas` devuelta, no como
    fila vacía o en cero.

    `obtener_tasa_cetes(fecha_inicio, fecha_fin)` debe devolver la tasa de CETES 28
    días promedio (% anualizado) de ese rango — usando el promedio del periodo
    disponible si Banxico no cubre el lapso completo, criterio de respaldo suficiente
    para este indicador — o lanzar una excepción si no está disponible (p. ej. sin
    token de Banxico configurado: ver `extraccion.obtener_cetes_28d`). Si se omite o
    falla, el ratio tipo Sharpe de cada lapso queda en NaN, con una nota explicando
    por qué (una sola vez, no repetida por cada lapso).

    Devuelve `(tabla, notas)`: `tabla` tiene una fila por lapso aplicable (indexada
    por `lapso`); `notas` es la lista de avisos sobre lapsos omitidos y limitaciones,
    pensada para mostrarse como pie de página adicional en la ficha.
    """
    ticker_base = _normalizar_ticker(ticker)
    fecha_fin = pd.Timestamp(fecha_referencia) if fecha_referencia is not None else pd.Timestamp(datetime.now().date())

    precios_historicos = precios_historicos.sort_index()
    if precios_historicos.empty:
        raise ValueError(f"No hay historial de precios para {ticker_base}.")
    primer_fecha_disponible = precios_historicos.index.min()

    pagos_historicos = pagos_historicos.copy()
    pagos_historicos["ex_date"] = pd.to_datetime(pagos_historicos["ex_date"], errors="coerce")
    pagos_historicos["amount_mxn"] = pd.to_numeric(pagos_historicos["amount_mxn"], errors="coerce")
    if "ticker" in pagos_historicos.columns:
        pagos_historicos = pagos_historicos[pagos_historicos["ticker"].astype(str).str.upper() == ticker_base]

    # Los 5 lapsos comparten la misma `fecha_fin`, así que los retornos mensuales del
    # historial completo (usados para la volatilidad de cada lapso) son idénticos para
    # los 5: se calculan una sola vez en vez de repetir el resample/agrupación 5 veces.
    # Si el cálculo falla (datos de precios/pagos con alguna forma inesperada), se
    # degrada a una serie vacía en vez de tronar toda la tabla: cada lapso ya maneja
    # "sin suficientes retornos" dejando su riesgo/Sharpe en NaN.
    try:
        retornos_todos = _retornos_totales_mensuales(precios_historicos, pagos_historicos, fecha_fin)
    except Exception:
        retornos_todos = pd.Series(dtype=float)

    filas = []
    notas = []
    aviso_cetes_ya_dado = False

    for etiqueta in _LAPSOS_MULTIPERIODO:
        if etiqueta == "Histórico":
            fecha_inicio = primer_fecha_disponible
        else:
            años_lapso = _ANIOS_LAPSO_FIJO[etiqueta]
            fecha_inicio = fecha_fin - pd.DateOffset(years=años_lapso)
            if fecha_inicio < primer_fecha_disponible:
                notas.append(
                    f"Se omite el lapso {etiqueta}: {ticker_base} no tiene {años_lapso} año(s) completo(s) "
                    f"de historial de precios (primer dato disponible: {primer_fecha_disponible:%Y-%m-%d})."
                )
                continue

        tasa_cetes_pct = None
        if obtener_tasa_cetes is not None:
            try:
                tasa_cetes_pct = obtener_tasa_cetes(fecha_inicio, fecha_fin)
            except Exception as error:
                if not aviso_cetes_ya_dado:
                    notas.append(f"Ratio tipo Sharpe no disponible en ningún lapso: {error}")
                    aviso_cetes_ya_dado = True

        filas.append(
            _calcular_indicadores_ventana(
                etiqueta, precios_historicos, pagos_historicos, fecha_inicio, fecha_fin, tasa_cetes_pct, retornos_todos
            )
        )

    if not filas:
        raise ValueError(
            f"Ningún lapso es aplicable para {ticker_base}: no hay historial de precios suficiente "
            f"(primer dato disponible: {primer_fecha_disponible:%Y-%m-%d})."
        )

    tabla = pd.DataFrame(filas).set_index("lapso")
    return tabla, notas


# --- Escenario de inversión multianual (2/3/5/10 años) ---

HORIZONTES_ESCENARIO_MULTIANUAL = [2, 3, 5, 10]


def calcular_ventana_multianual(fecha_final, años: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Ventana móvil de `años` años hacia atrás desde `fecha_final` (ambos extremos inclusive).

    `[fecha_final - N años + 1 día, fecha_final]` (N años completos, ambos extremos
    inclusive). Es la generalización exacta de `calcular_ventana_movil_12_meses`
    (con `años=1` produce la misma ventana que esa función usaría para esa
    `fecha_final`), pero con `fecha_final` anclada a la última fecha con datos
    disponibles del universo analizado en vez de a "hoy", para que el resultado sea
    reproducible y comparable con la ficha de los últimos 12 meses.
    """
    fecha_final = pd.Timestamp(fecha_final)
    fecha_inicio = fecha_final - pd.DateOffset(years=int(años)) + pd.Timedelta(days=1)
    return fecha_inicio, fecha_final


def calcular_escenario_multianual(
    precios_historicos: pd.Series,
    pagos_historicos: pd.DataFrame,
    fecha_final,
    años: int,
    capital_invertido: float = 10000.0,
) -> dict:
    """Indicadores del escenario de inversión de un ticker sobre la ventana móvil de `años` años.

    Réplica de la metodología de la ficha completa para cliente de los últimos 12
    meses (`presentacion._calcular_ficha_completa`, modo ventana móvil): mismo
    tratamiento del precio inicial (primer cierre disponible en la ventana) y final,
    títulos adquiridos con `capital_invertido // precio_inicial`, plusvalía y
    distribuciones a nivel de la posición completa, y el mismo supuesto de que las
    distribuciones se reciben en efectivo (no se reinvierten). Agrega, para el
    horizonte de `N = años`: la distribución promedio anual (`distribuciones_totales
    / N`), el CAGR y el rendimiento anual simple (`rendimiento_total / N`).

    `precios_historicos` (Series de cierres indexada por fecha) y `pagos_historicos`
    (DataFrame con `ex_date`/`amount_mxn`) deben cubrir al menos toda la ventana; el
    filtro de suficiencia de historial se hace antes, en
    `presentacion._preparar_escenario_multianual`.
    """
    if capital_invertido <= 0:
        raise ValueError("El capital invertido debe ser positivo.")
    años = int(años)
    fecha_inicio, fecha_fin = calcular_ventana_multianual(fecha_final, años)

    precios = precios_historicos.sort_index()
    precios_ventana = precios[(precios.index >= fecha_inicio) & (precios.index <= fecha_fin)]
    if precios_ventana.empty:
        raise ValueError(
            f"No hay precios en la ventana de {años} años ({fecha_inicio:%Y-%m-%d} a {fecha_fin:%Y-%m-%d})."
        )
    precio_compra = float(precios_ventana.iloc[0])
    precio_actual = float(precios_ventana.iloc[-1])
    fecha_inicial = precios_ventana.index[0]
    fecha_final_real = precios_ventana.index[-1]

    pagos = pagos_historicos.copy()
    pagos["ex_date"] = pd.to_datetime(pagos["ex_date"], errors="coerce")
    pagos["amount_mxn"] = pd.to_numeric(pagos["amount_mxn"], errors="coerce")
    pagos_ventana = pagos[
        (pagos["ex_date"] >= fecha_inicio) & (pagos["ex_date"] <= fecha_fin) & pagos["amount_mxn"].notna()
    ]

    titulos = int(capital_invertido // precio_compra)
    plusvalia = titulos * (precio_actual - precio_compra)
    dividendo_por_titulo = float(pagos_ventana["amount_mxn"].sum())
    distribuciones_totales = titulos * dividendo_por_titulo
    valor_final_posicion = titulos * precio_actual
    retorno_total = plusvalia + distribuciones_totales
    rendimiento_total_pct = retorno_total / capital_invertido * 100
    plusvalia_pct = plusvalia / capital_invertido * 100
    distribucion_promedio_anual = distribuciones_totales / años
    rendimiento_anual_simple_pct = rendimiento_total_pct / años

    # CAGR = ((1 + rend_total/100)^(1/N) − 1) × 100. Si la pérdida total es ≥ 100%
    # (1 + rend_total/100 ≤ 0) no existe una tasa compuesta anual real: queda NaN
    # (la ficha lo muestra como "n/a" con nota), no una excepción de raíz negativa.
    base_cagr = 1 + rendimiento_total_pct / 100
    cagr_pct = (base_cagr ** (1 / años) - 1) * 100 if base_cagr > 0 else float("nan")

    # Volatilidad del retorno total mensual sobre toda la ventana: misma definición
    # que la ficha de 12 meses y la multi-periodo (desviación estándar muestral,
    # ddof=1, anualizada con √12). Queda NaN si no hay al menos 2 retornos mensuales.
    try:
        retornos = _retornos_totales_mensuales(precios, pagos, fecha_fin)
        retornos_ventana = retornos[retornos.index >= fecha_inicio]
        vol_mensual_pct = float(retornos_ventana.std() * 100) if len(retornos_ventana) >= 2 else float("nan")
    except Exception:
        vol_mensual_pct = float("nan")
    vol_anualizada_pct = vol_mensual_pct * (12**0.5)

    return {
        "años": años,
        "fecha_inicio_ventana": fecha_inicio,
        "fecha_fin_ventana": fecha_fin,
        "fecha_inicial": fecha_inicial,
        "fecha_final": fecha_final_real,
        "capital_invertido": float(capital_invertido),
        "precio_compra": precio_compra,
        "precio_actual": precio_actual,
        "titulos": titulos,
        "valor_final_posicion": valor_final_posicion,
        "plusvalia": plusvalia,
        "plusvalia_pct": plusvalia_pct,
        "dividendo_por_titulo": dividendo_por_titulo,
        "distribucion_promedio_anual": distribucion_promedio_anual,
        "distribuciones_totales": distribuciones_totales,
        "retorno_total": retorno_total,
        "cagr_pct": cagr_pct,
        "rendimiento_anual_simple_pct": rendimiento_anual_simple_pct,
        "rendimiento_total_pct": rendimiento_total_pct,
        "volatilidad_mensual_pct": vol_mensual_pct,
        "volatilidad_anualizada_pct": vol_anualizada_pct,
        "num_pagos": int(len(pagos_ventana)),
    }
