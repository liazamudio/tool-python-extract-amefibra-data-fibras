"""Funciones de presentación y exportación de resultados de FIBRAs (CSV, Excel, fichas HTML)."""

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import ipywidgets as widgets
import pandas as pd
from IPython.display import HTML, display

from .extraccion import (
    COLUMNAS_DISTRIBUCIONES,
    URL_PAGINA,
    _descargar_cierres_anuales,
    obtener_distribuciones,
    obtener_tabla_fibras_en_notebook,
)
from .procesamiento import _normalizar_ticker, normalizar_para_analisis


def exportar_csv_analitico(df: pd.DataFrame, carpeta_salida: Path) -> Path:
    """Normaliza `df` para análisis y lo exporta a un CSV "profesional" dentro de `carpeta_salida`."""
    momento = datetime.now()
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    nombre = f"{momento:%Y%m%d_%H%M%S}_indice_fibras_amefibra.csv"
    ruta = carpeta_salida / nombre
    normalizar_para_analisis(df, momento).to_csv(ruta, index=False, encoding="utf-8")
    return ruta


def exportar_csv_emisoras(df_emisoras: pd.DataFrame, carpeta_salida: Path) -> Path:
    """Exporta el listado de emisoras a un CSV dentro de `carpeta_salida`, con nombre con marca de tiempo."""
    momento = datetime.now()
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    nombre = f"{momento:%Y%m%d_%H%M%S}_list_of_tickers.csv"
    ruta = carpeta_salida / nombre
    df_emisoras.to_csv(ruta, index=False, encoding="utf-8")
    return ruta


def _buscar_csv_emisoras_mas_reciente(carpeta_salida: Path) -> Optional[Path]:
    """Busca en `carpeta_salida` el CSV `*_list_of_tickers.csv` más reciente.

    La fecha/hora que determina cuál es "el más reciente" es la incluida en el
    propio nombre del archivo (prefijo `YYYYMMDD_HHMMSS_`), no la fecha de
    modificación en disco, porque esta última no es confiable (copias, checkouts
    de git, etc. la alteran sin que cambie el contenido).
    """
    if not carpeta_salida.exists():
        return None
    candidatos = sorted(carpeta_salida.glob("*_list_of_tickers.csv"))
    return candidatos[-1] if candidatos else None


def mostrar_emisoras(df: Optional[pd.DataFrame], carpeta_salida: Path) -> pd.DataFrame:
    """Obtiene el listado de emisoras, lo muestra en pantalla y lo exporta a CSV en `carpeta_salida`.

    Si `df` fue generado en la corrida actual (no es `None` ni está vacío), se usa
    ese dato recién extraído de AMEFIBRA. Si no (porque las celdas de extracción no
    se ejecutaron), se reutiliza el CSV `*_list_of_tickers.csv` más reciente ya
    guardado en `carpeta_salida`, para no depender de repetir la extracción.
    """
    if df is not None and not df.empty:
        print("Fuente de emisoras: extracción de AMEFIBRA de esta corrida.")
        df_emisoras = df[["Emisora"]]
        print(df_emisoras)
        ruta = exportar_csv_emisoras(df_emisoras, carpeta_salida)
        print(f"CSV de emisoras guardado en: {ruta}")
        return df_emisoras

    ruta_historico = _buscar_csv_emisoras_mas_reciente(carpeta_salida)
    if ruta_historico is None:
        raise FileNotFoundError(
            "No hay un DataFrame `df` de esta corrida (¿no se ejecutaron las celdas de "
            f"extracción de AMEFIBRA?) ni un CSV 'list_of_tickers' en {carpeta_salida}. "
            "Corre la extracción de AMEFIBRA o coloca ahí un CSV histórico de emisoras."
        )
    print(f"Fuente de emisoras: histórico de {ruta_historico.name} (no se ejecutó la extracción de AMEFIBRA en esta corrida).")
    df_emisoras = pd.read_csv(ruta_historico)[["Emisora"]]
    print(df_emisoras)
    return df_emisoras


def exportar_csv_excel(df: pd.DataFrame, ruta: Path) -> Path:
    """Exporta `df` a un CSV compatible con Excel (con BOM, para tildes/ñ correctas)."""
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


def exportar_xlsx(df: pd.DataFrame, ruta: Path) -> Path:
    """Exporta `df` a un archivo de Excel (.xlsx)."""
    df.to_excel(ruta, index=False)
    return ruta


def crear_ficha_rendimiento(
    ticker: str,
    año: int,
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
) -> Path:
    """Calcula y exporta una ficha HTML de rendimiento total para un año calendario."""
    if not isinstance(año, int) or año < 1900 or año > 2100:
        raise ValueError("El año debe ser un entero entre 1900 y 2100.")
    ticker_base = _normalizar_ticker(ticker)
    historial = historial if historial is not None else obtener_distribuciones(ticker_base, carpeta_salida)
    requerido = {"ticker", "ex_date", "amount_mxn", "yield_pct"}
    faltantes = requerido.difference(historial.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el historial: {sorted(faltantes)}")

    pagos = historial.copy()
    pagos["ex_date"] = pd.to_datetime(pagos["ex_date"], errors="coerce")
    pagos["amount_mxn"] = pd.to_numeric(pagos["amount_mxn"], errors="coerce")
    pagos = pagos[
        (pagos["ticker"].astype(str).str.upper() == ticker_base)
        & (pagos["ex_date"].dt.year == año)
        & pagos["amount_mxn"].notna()
    ]
    cierres = _descargar_cierres_anuales(f"{ticker_base}.MX", año)
    precio_inicial = float(cierres.iloc[0])
    precio_final = float(cierres.iloc[-1])
    total_dividendos = float(pagos["amount_mxn"].sum())
    variacion_capital = precio_final - precio_inicial
    ganancia_total = total_dividendos + variacion_capital
    rendimiento_dividendos = total_dividendos / precio_inicial * 100
    rendimiento_capital = variacion_capital / precio_inicial * 100
    rendimiento_total = ganancia_total / precio_inicial * 100
    fecha_inicial = cierres.index[0].strftime("%Y-%m-%d")
    fecha_final = cierres.index[-1].strftime("%Y-%m-%d")
    max_componente = max(abs(total_dividendos), abs(variacion_capital), 0.000001)
    ancho_dividendos = abs(total_dividendos) / max_componente * 100
    ancho_capital = abs(variacion_capital) / max_componente * 100
    color_capital = "#e0725c" if variacion_capital < 0 else "#4fae8c"
    color_total = "#e0725c" if rendimiento_total < 0 else "#5fd9b0"
    tabla_pagos = pagos[["ex_date", "amount_mxn", "yield_pct"]].sort_values("ex_date").copy()
    tabla_pagos["ex_date"] = tabla_pagos["ex_date"].dt.strftime("%Y-%m-%d")
    tabla_pagos["amount_mxn"] = tabla_pagos["amount_mxn"].map(lambda valor: f"${valor:,.4f}")
    tabla_pagos["yield_pct"] = tabla_pagos["yield_pct"].map(lambda valor: f"{valor:,.2f}%")
    tabla_html = tabla_pagos.to_html(index=False, classes="payments", border=0, justify="left")
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Ficha {escape(ticker_base)} {año}</title>
<style>
body{{margin:0;background:#12201e;color:#e8ede9;font-family:Georgia,serif}}main{{max-width:900px;margin:32px auto;padding:32px;background:#1b2926;box-shadow:0 8px 24px #00000066}}h1{{margin:0 0 6px;font-size:36px}}.subtitle{{color:#8ba39c;margin-bottom:28px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metric{{border-top:3px solid #d8a24a;padding:12px 0}}.label{{font:12px sans-serif;text-transform:uppercase;letter-spacing:1px;color:#8ba39c}}.value{{font-size:24px;margin-top:6px}}.total{{margin:28px 0;padding:18px;background:#1e352e;border-left:5px solid {color_total}}}.total strong{{font-size:34px;color:{color_total}}}.bar{{height:28px;display:flex;margin:12px 0 8px;background:#2a3835}}.bar div{{height:100%}}.legend{{font:14px sans-serif;color:#9db3ac}}table{{width:100%;border-collapse:collapse;font:14px sans-serif;margin-top:20px}}th,td{{padding:9px;border-bottom:1px solid #30423e;text-align:left}}th{{color:#8ba39c}}.notice{{margin-top:28px;font:12px sans-serif;color:#8ba39c}}@media(max-width:650px){{main{{margin:0;padding:22px}}h1{{font-size:29px}}.metrics{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<h1>Ficha de rendimiento: {escape(ticker_base)}</h1><div class="subtitle">Año calendario {año} · cierres del {fecha_inicial} al {fecha_final}</div>
<div class="metrics"><div class="metric"><div class="label">Precio inicial</div><div class="value">${precio_inicial:,.2f} MXN</div></div><div class="metric"><div class="label">Precio final</div><div class="value">${precio_final:,.2f} MXN</div></div><div class="metric"><div class="label">Variación de precio</div><div class="value">{rendimiento_capital:,.2f}%</div></div></div>
<div class="total"><div class="label">Rendimiento total del año</div><strong>{rendimiento_total:,.2f}%</strong><div class="legend">Dividendos: {rendimiento_dividendos:,.2f}% · Capital: {rendimiento_capital:,.2f}% · Ganancia total: ${ganancia_total:,.2f} MXN</div></div>
<h2>Composición de la ganancia</h2><div class="bar"><div style="width:{ancho_dividendos:.2f}%;background:#d8a24a"></div><div style="width:{ancho_capital:.2f}%;background:{color_capital}"></div></div><div class="legend">Dividendos recibidos: ${total_dividendos:,.4f} MXN · Variación de capital: ${variacion_capital:,.2f} MXN</div>
<h2>Distribuciones del año ({len(pagos)} pagos)</h2>{tabla_html}
<div class="notice">Ficha informativa basada en datos históricos. Los pagos se identifican por ex_date. No constituye una recomendación de compra o venta; el rendimiento pasado no garantiza resultados futuros.</div>
</main></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_{ticker_base}_{año}_ficha_rendimiento.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def ejecutar_extraccion_indice(
    headless: bool,
    timeout_datos_ms: int,
    carpeta_salida: Path,
    exportar_csv: bool = True,
) -> pd.DataFrame:
    """Descarga la tabla del Índice FIBRAS, la muestra y (opcionalmente) exporta el CSV analítico."""
    print(f"Consultando {URL_PAGINA} ...")
    df = obtener_tabla_fibras_en_notebook(headless=headless, timeout_datos_ms=timeout_datos_ms)
    print(f"Índice FIBRAS - {datetime.now():%Y-%m-%d %H:%M} (dato con ~20 min de retraso)")
    display(df)
    if exportar_csv:
        ruta = exportar_csv_analitico(df, carpeta_salida)
        print(f"CSV analítico guardado en: {ruta}")
    return df


def probar_historial_dividendos(ticker: str, emisoras: pd.Series, carpeta_salida: Path) -> pd.DataFrame:
    """Descarga el historial de dividendos de `ticker`, valida su forma y muestra un resumen."""
    assert ticker in set(emisoras), "El ticker de prueba no está en el listado AMEFIBRA."
    historial = obtener_distribuciones(ticker, carpeta_salida)
    assert list(historial.columns) == COLUMNAS_DISTRIBUCIONES
    assert historial["ex_date"].is_monotonic_increasing
    assert not historial.duplicated(subset=["ticker", "ex_date", "amount_mxn"]).any()
    assert (historial["amount_mxn"] > 0).all()
    assert historial["annualized_yield_pct"].notna().all()
    assert Path(historial.attrs["ruta_csv"]).exists()

    print(f"Ticker probado: {ticker}. Registros: {len(historial)}")
    print(f"Periodicidad detectada: {historial['periodicity'].iloc[0]}")
    print(f"CSV generado: {historial.attrs['ruta_csv']}")
    display(historial.tail(10))
    return historial


def mostrar_ficha_rendimiento(
    ticker: str,
    año: int,
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
) -> Path:
    """Genera la ficha de rendimiento con `crear_ficha_rendimiento` y la muestra en el notebook."""
    ruta = crear_ficha_rendimiento(ticker, año, carpeta_salida, historial)
    print(f"Ficha generada: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    return ruta


def seleccionar_anio_interactivo(años_disponibles: list[int], valor_simulado: Optional[int] = None) -> widgets.Dropdown:
    """Despliega un dropdown para elegir, de los años con datos disponibles, cuál consultar.

    Devuelve el widget: en uso interactivo, el usuario cambia la selección en el
    notebook y una celda posterior lee `selector.value`. `valor_simulado` fija el
    valor inicial del dropdown para pruebas automatizadas (donde no hay un usuario
    real interactuando con el widget); si no es uno de los años disponibles, se
    lanza un error claro en vez de continuar con un año inválido.
    """
    if not años_disponibles:
        raise ValueError("No hay años disponibles para este ticker.")
    if valor_simulado is not None and valor_simulado not in años_disponibles:
        raise ValueError(f"El año {valor_simulado} no está disponible. Años válidos: {años_disponibles}.")
    print(f"Hay información disponible de {min(años_disponibles)} a {max(años_disponibles)}.")
    valor_inicial = valor_simulado if valor_simulado is not None else max(años_disponibles)
    selector = widgets.Dropdown(options=años_disponibles, value=valor_inicial, description="Año:")
    display(selector)
    return selector


def seleccionar_ticker_interactivo(emisoras: pd.Series, valor_simulado: Optional[str] = None) -> widgets.Dropdown:
    """Despliega un dropdown para elegir, de los tickers listados en el Índice FIBRAS, cuál consultar.

    Devuelve el widget: en uso interactivo, el usuario cambia la selección en el
    notebook y una celda posterior lee `selector.value`. `valor_simulado` fija el
    valor inicial del dropdown para pruebas automatizadas (donde no hay un usuario
    real interactuando con el widget); si no es uno de los tickers listados, se
    lanza un error claro en vez de continuar con un ticker inválido.
    """
    tickers_disponibles = sorted(emisoras.unique().tolist())
    if not tickers_disponibles:
        raise ValueError("No hay tickers disponibles para elegir.")
    if valor_simulado is not None and valor_simulado not in tickers_disponibles:
        raise ValueError(f"El ticker {valor_simulado!r} no está en el listado. Tickers válidos: {tickers_disponibles}.")
    valor_inicial = valor_simulado if valor_simulado is not None else tickers_disponibles[0]
    selector = widgets.Dropdown(options=tickers_disponibles, value=valor_inicial, description="Ticker:")
    display(selector)
    return selector
