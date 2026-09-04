"""Funciones de presentación y exportación de resultados de FIBRAs (CSV, Excel, fichas HTML/PDF)."""

import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import ipywidgets as widgets
import pandas as pd
from IPython.display import HTML, display
from playwright.sync_api import sync_playwright

from .extraccion import (
    COLUMNAS_DISTRIBUCIONES,
    URL_PAGINA,
    _descargar_cierres_anuales,
    _descargar_cierres_rango,
    _descargar_historico_completo,
    ejecutar_con_playwright_sync,
    obtener_cetes_28d,
    obtener_distribuciones,
    obtener_precio_actual,
    obtener_tabla_fibras_en_notebook,
)
from .procesamiento import (
    _normalizar_ticker,
    armar_tabla_multiperiodo,
    calcular_riesgo_mensual,
    calcular_ventana_movil_12_meses,
    normalizar_para_analisis,
)


def aplicar_tema_oscuro_notebook() -> None:
    """Inyecta un fondo oscuro para las celdas, el markdown y las salidas del notebook.

    Es un `<style>` inyectado vía `IPython.display.HTML`, así que solo tiene efecto
    en entornos donde las celdas comparten un mismo documento HTML (Jupyter
    clásico, JupyterLab, o al exportar el notebook a HTML): ahí sí oscurece todas
    las celdas y salidas, aunque el propio Jupyter recargue su tema. En el
    notebook de VS Code, en cambio, cada salida de celda se renderiza en un
    iframe aislado del resto de la interfaz (otras celdas, markdown, cromo de la
    UI), así que este `<style>` no logra salir de su propia salida; para un
    fondo oscuro real en VS Code hay que cambiar el tema del editor
    (`Ver > Paleta de comandos > Preferencias: Cambiar tema de color`).
    """
    display(HTML("""<style>
/* JupyterLab (y el HTML exportado con nbconvert) define sus colores como variables
   CSS en :root; redefinirlas aquí es lo que de verdad oscurece cada celda, el
   markdown y las salidas, en vez de pelear clase por clase contra las reglas ya
   definidas (que las consumen vía var(...) y suelen ganar por especificidad). */
:root {
    --jp-layout-color0: #1e1e1e !important;
    --jp-layout-color1: #1e1e1e !important;
    --jp-layout-color2: #3c3c3c !important;
    --jp-layout-color3: #4d4d4d !important;
    --jp-layout-color4: #6e6e6e !important;
    --jp-cell-editor-background: #252526 !important;
    --jp-cell-editor-background-color: #252526 !important;
    --jp-content-font-color0: #ffffff !important;
    --jp-content-font-color1: #d4d4d4 !important;
    --jp-content-font-color2: #a0a0a0 !important;
    --jp-content-font-color3: #6e6e6e !important;
    --jp-ui-font-color0: #ffffff !important;
    --jp-ui-font-color1: #d4d4d4 !important;
    --jp-ui-font-color2: #a0a0a0 !important;
    --jp-ui-font-color3: #6e6e6e !important;
    --jp-border-color0: #3c3c3c !important;
    --jp-border-color1: #3c3c3c !important;
    --jp-border-color2: #3c3c3c !important;
    --jp-border-color3: #3c3c3c !important;
    --jp-inverse-layout-color0: #ffffff !important;
    /* Filas alternadas de tablas (p. ej. display(df)) y fondo de errores/avisos. */
    --jp-rendermime-table-row-background: #2a2a2a !important;
    --jp-rendermime-table-row-hover-background: #37373d !important;
    --jp-rendermime-error-background: #4b1d1d !important;
    /* Resaltado de sintaxis del código (Pygments/CodeMirror), tipo VS Code Dark+. */
    --jp-mirror-editor-variable-color: #d4d4d4 !important;
    --jp-mirror-editor-keyword-color: #569cd6 !important;
    --jp-mirror-editor-string-color: #ce9178 !important;
    --jp-mirror-editor-comment-color: #6a9955 !important;
    --jp-mirror-editor-number-color: #b5cea8 !important;
    --jp-mirror-editor-operator-color: #d4d4d4 !important;
    --jp-mirror-editor-punctuation-color: #d4d4d4 !important;
    --jp-mirror-editor-bracket-color: #d4d4d4 !important;
    --jp-mirror-editor-def-color: #dcdcaa !important;
    --jp-mirror-editor-builtin-color: #4ec9b0 !important;
    --jp-mirror-editor-attribute-color: #9cdcfe !important;
    --jp-mirror-editor-property-color: #9cdcfe !important;
    --jp-mirror-editor-atom-color: #569cd6 !important;
    --jp-mirror-editor-meta-color: #d4d4d4 !important;
    --jp-mirror-editor-qualifier-color: #d4d4d4 !important;
    --jp-mirror-editor-tag-color: #569cd6 !important;
    --jp-mirror-editor-link-color: #9cdcfe !important;
    --jp-mirror-editor-error-color: #f48771 !important;
    --jp-mirror-editor-hr-color: #6e6e6e !important;
    --jp-mirror-editor-header-color: #569cd6 !important;
}
body, html { background: #1e1e1e !important; }
/* Clases de Jupyter clásico (nbclassic/notebook), que no usan estas variables. */
#notebook, #notebook-container, .cell, .input_area, .output_area,
.text_cell_render, .rendered_html, .CodeMirror {
    background: #1e1e1e !important;
    color: #d4d4d4 !important;
    border-color: #3c3c3c !important;
}
a, .rendered_html a, .jp-RenderedHTMLCommon a {
    color: #4fc1ff !important;
}
</style>"""))


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


def _calcular_rendimiento(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    fecha_referencia: Optional[datetime] = None,
) -> dict:
    """Calcula los indicadores de rendimiento total de un ticker en un año calendario
    o en la ventana móvil de últimos 12 meses (ver `crear_ficha_rendimiento`).

    Es el cálculo compartido por `crear_ficha_rendimiento` (una ficha por ticker) y
    `crear_comparativo_rendimiento` (una tabla con todos los tickers seleccionados),
    para no duplicar la lógica ni arriesgar que ambas versiones diverjan.
    """
    usar_ventana_movil = fecha_referencia is not None or año is None
    if not usar_ventana_movil and (not isinstance(año, int) or año < 1900 or año > 2100):
        raise ValueError("El año debe ser un entero entre 1900 y 2100.")
    ticker_base = _normalizar_ticker(ticker)
    historial = historial if historial is not None else obtener_distribuciones(ticker_base, carpeta_salida)
    requerido = {"ticker", "ex_date", "amount_mxn", "yield_pct"}
    faltantes = requerido.difference(historial.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el historial: {sorted(faltantes)}")

    pagos_ticker = historial.copy()
    pagos_ticker["ex_date"] = pd.to_datetime(pagos_ticker["ex_date"], errors="coerce")
    pagos_ticker["amount_mxn"] = pd.to_numeric(pagos_ticker["amount_mxn"], errors="coerce")
    pagos_ticker = pagos_ticker[pagos_ticker["ticker"].astype(str).str.upper() == ticker_base]

    riesgo = None
    if usar_ventana_movil:
        fecha_inicio, fecha_fin = calcular_ventana_movil_12_meses(fecha_referencia)
        pagos = pagos_ticker[
            (pagos_ticker["ex_date"] >= fecha_inicio)
            & (pagos_ticker["ex_date"] <= fecha_fin)
            & pagos_ticker["amount_mxn"].notna()
        ]
        cierres_historicos = _descargar_cierres_rango(f"{ticker_base}.MX", fecha_inicio - pd.Timedelta(days=40), fecha_fin)
        cierres = cierres_historicos[(cierres_historicos.index >= fecha_inicio) & (cierres_historicos.index <= fecha_fin)]
        if cierres.empty:
            raise ValueError(
                f"No hay precios disponibles para {ticker_base} entre {fecha_inicio:%Y-%m-%d} y {fecha_fin:%Y-%m-%d}."
            )
        etiqueta_periodo = f"Últimos 12 meses ({fecha_inicio:%d/%m/%Y}–{fecha_fin:%d/%m/%Y})"
        etiqueta_total = "Rendimiento total de los últimos 12 meses"
        etiqueta_pagos = "Distribuciones del periodo"
        sufijo_archivo = f"{fecha_fin:%Y%m%d}_ult12m"
        riesgo = calcular_riesgo_mensual(cierres_historicos, pagos, fecha_inicio, fecha_fin)
        aviso_riesgo = " El riesgo mostrado es histórico y tampoco debe interpretarse como predictor de riesgo futuro."
    else:
        pagos = pagos_ticker[(pagos_ticker["ex_date"].dt.year == año) & pagos_ticker["amount_mxn"].notna()]
        cierres = _descargar_cierres_anuales(f"{ticker_base}.MX", año)
        etiqueta_periodo = f"Año calendario {año}"
        etiqueta_total = "Rendimiento total del año"
        etiqueta_pagos = "Distribuciones del año"
        sufijo_archivo = f"{año}"
        aviso_riesgo = ""

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

    return {
        "ticker_base": ticker_base,
        "usar_ventana_movil": usar_ventana_movil,
        "etiqueta_periodo": etiqueta_periodo,
        "etiqueta_total": etiqueta_total,
        "etiqueta_pagos": etiqueta_pagos,
        "sufijo_archivo": sufijo_archivo,
        "aviso_riesgo": aviso_riesgo,
        "precio_inicial": precio_inicial,
        "precio_final": precio_final,
        "fecha_inicial": fecha_inicial,
        "fecha_final": fecha_final,
        "total_dividendos": total_dividendos,
        "variacion_capital": variacion_capital,
        "ganancia_total": ganancia_total,
        "rendimiento_dividendos": rendimiento_dividendos,
        "rendimiento_capital": rendimiento_capital,
        "rendimiento_total": rendimiento_total,
        "pagos": pagos,
        "riesgo": riesgo,
    }


def crear_ficha_rendimiento(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Calcula y exporta una ficha HTML de rendimiento total para un año calendario.

    Si `fecha_referencia` se especifica, `año` se ignora y el periodo analizado es,
    en cambio, la ventana móvil de los últimos 12 meses completos terminando en esa
    fecha (`calcular_ventana_movil_12_meses`; por defecto, si se pasa una fecha
    "vacía"/None con este modo activo, la fecha de referencia es hoy). Este modo
    agrega además el riesgo mensual promedio del periodo (volatilidad del retorno
    total mensual) como cifra destacada junto al rendimiento total; el modo de año
    calendario (`fecha_referencia=None`, el de siempre) no se modifica.
    """
    datos = _calcular_rendimiento(ticker, año, carpeta_salida, historial, fecha_referencia)
    ticker_base = datos["ticker_base"]
    etiqueta_periodo = datos["etiqueta_periodo"]
    etiqueta_total = datos["etiqueta_total"]
    etiqueta_pagos = datos["etiqueta_pagos"]
    sufijo_archivo = datos["sufijo_archivo"]
    aviso_riesgo = datos["aviso_riesgo"]
    precio_inicial = datos["precio_inicial"]
    precio_final = datos["precio_final"]
    fecha_inicial = datos["fecha_inicial"]
    fecha_final = datos["fecha_final"]
    total_dividendos = datos["total_dividendos"]
    variacion_capital = datos["variacion_capital"]
    ganancia_total = datos["ganancia_total"]
    rendimiento_dividendos = datos["rendimiento_dividendos"]
    rendimiento_capital = datos["rendimiento_capital"]
    rendimiento_total = datos["rendimiento_total"]
    pagos = datos["pagos"]

    riesgo_html = ""
    if datos["usar_ventana_movil"]:
        riesgo_html = (
            '<div class="legend">Riesgo mensual promedio (volatilidad del retorno total mensual): '
            f'{datos["riesgo"]["volatilidad_mensual_pct"]:,.2f}%</div>'
        )

    max_componente = max(abs(total_dividendos), abs(variacion_capital), 0.000001)
    ancho_dividendos = abs(total_dividendos) / max_componente * 100
    ancho_capital = abs(variacion_capital) / max_componente * 100
    color_capital = "#e0725c" if variacion_capital < 0 else "#4fae8c"
    color_total = "#f2836a" if rendimiento_total < 0 else "#5fd9b0"
    tabla_pagos = pagos[["ex_date", "amount_mxn", "yield_pct"]].sort_values("ex_date").copy()
    tabla_pagos["ex_date"] = tabla_pagos["ex_date"].dt.strftime("%Y-%m-%d")
    tabla_pagos["amount_mxn"] = tabla_pagos["amount_mxn"].map(lambda valor: f"${valor:,.4f}")
    tabla_pagos["yield_pct"] = tabla_pagos["yield_pct"].map(lambda valor: f"{valor:,.2f}%")
    tabla_html = tabla_pagos.to_html(index=False, classes="payments", border=0, justify="left")
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Ficha {escape(ticker_base)} {sufijo_archivo}</title>
<style>
body{{margin:0;background:#12201e;color:#e8ede9;font-family:Georgia,serif}}main{{max-width:900px;margin:32px auto;padding:32px;background:#1b2926;color:#e8ede9;box-shadow:0 8px 24px #00000066}}h1{{margin:0 0 6px;font-size:36px;color:#e8ede9}}h2{{color:#e8ede9;margin-top:28px}}.subtitle{{color:#8ba39c;margin-bottom:28px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metric{{border-top:3px solid #d8a24a;padding:12px 0}}.label{{font:12px sans-serif;text-transform:uppercase;letter-spacing:1px;color:#8ba39c}}.value{{font-size:24px;margin-top:6px;color:#e8ede9}}.total{{margin:28px 0;padding:18px;background:#1e352e;border-left:5px solid {color_total}}}.total strong{{font-size:34px;color:{color_total}}}.bar{{height:28px;display:flex;margin:12px 0 8px;background:#2a3835}}.bar div{{height:100%}}.legend{{font:14px sans-serif;color:#9db3ac}}table{{width:100%;border-collapse:collapse;font:14px sans-serif;margin-top:20px}}th,td{{padding:9px;border-bottom:1px solid #30423e;text-align:left;color:#e8ede9}}th{{color:#8ba39c}}.notice{{margin-top:28px;font:12px sans-serif;color:#8ba39c}}@media(max-width:650px){{main{{margin:0;padding:22px}}h1{{font-size:29px}}.metrics{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<h1>Ficha de rendimiento: {escape(ticker_base)}</h1><div class="subtitle">{etiqueta_periodo} · cierres del {fecha_inicial} al {fecha_final}</div>
<div class="metrics"><div class="metric"><div class="label">Precio inicial</div><div class="value">${precio_inicial:,.2f} MXN</div></div><div class="metric"><div class="label">Precio final</div><div class="value">${precio_final:,.2f} MXN</div></div><div class="metric"><div class="label">Variación de precio</div><div class="value">{rendimiento_capital:,.2f}%</div></div></div>
<div class="total"><div class="label">{etiqueta_total}</div><strong>{rendimiento_total:,.2f}%</strong><div class="legend">Dividendos: {rendimiento_dividendos:,.2f}% · Capital: {rendimiento_capital:,.2f}% · Ganancia total: ${ganancia_total:,.2f} MXN</div>{riesgo_html}</div>
<h2>Composición de la ganancia</h2><div class="bar"><div style="width:{ancho_dividendos:.2f}%;background:#d8a24a"></div><div style="width:{ancho_capital:.2f}%;background:{color_capital}"></div></div><div class="legend">Dividendos recibidos: ${total_dividendos:,.4f} MXN · Variación de capital: ${variacion_capital:,.2f} MXN</div>
<h2>{etiqueta_pagos} ({len(pagos)} pagos)</h2>{tabla_html}
<div class="notice">Ficha informativa basada en datos históricos. Los pagos se identifican por ex_date. No constituye una recomendación de compra o venta; el rendimiento pasado no garantiza resultados futuros.{aviso_riesgo}</div>
</main></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_{ticker_base}_{sufijo_archivo}_ficha_rendimiento.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


_MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}
_MESES_ABREV_ES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _fecha_larga_es(fecha: pd.Timestamp) -> str:
    """Formatea una fecha como '07 de julio de 2025', sin depender del locale del sistema."""
    return f"{fecha.day:02d} de {_MESES_ES[fecha.month]} de {fecha.year}"


def _fecha_corta_es(fecha: pd.Timestamp) -> str:
    """Formatea una fecha como '07 Mar 2025', para caber en una columna de tabla angosta."""
    return f"{fecha.day:02d} {_MESES_ABREV_ES[fecha.month - 1].capitalize()} {fecha.year}"


def _calcular_ficha_completa(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    capital_invertido: float = 10000.0,
    fecha_referencia: Optional[datetime] = None,
) -> dict:
    """Calcula los indicadores de la ficha completa para cliente de un ticker en un
    año calendario o en la ventana móvil de últimos 12 meses (ver `crear_ficha_completa_cliente`).

    Es el cálculo compartido por `crear_ficha_completa_cliente` (una ficha por
    ticker) y `crear_comparativo_completo_cliente` (una tabla con todos los tickers
    seleccionados), para no duplicar la lógica ni arriesgar que ambas versiones
    diverjan.
    """
    usar_ventana_movil = fecha_referencia is not None or año is None
    if not usar_ventana_movil and (not isinstance(año, int) or año < 1900 or año > 2100):
        raise ValueError("El año debe ser un entero entre 1900 y 2100.")
    if capital_invertido <= 0:
        raise ValueError("El capital invertido debe ser positivo.")
    ticker_base = _normalizar_ticker(ticker)
    historial = historial if historial is not None else obtener_distribuciones(ticker_base, carpeta_salida)
    requerido = {"ticker", "ex_date", "amount_mxn"}
    faltantes = requerido.difference(historial.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el historial: {sorted(faltantes)}")

    pagos_ticker = historial.copy()
    pagos_ticker["ex_date"] = pd.to_datetime(pagos_ticker["ex_date"], errors="coerce")
    pagos_ticker["amount_mxn"] = pd.to_numeric(pagos_ticker["amount_mxn"], errors="coerce")
    pagos_ticker = pagos_ticker[pagos_ticker["ticker"].astype(str).str.upper() == ticker_base]

    riesgo = None
    aviso_riesgo = ""
    if usar_ventana_movil:
        fecha_inicio, fecha_fin = calcular_ventana_movil_12_meses(fecha_referencia)
        pagos = pagos_ticker[
            (pagos_ticker["ex_date"] >= fecha_inicio)
            & (pagos_ticker["ex_date"] <= fecha_fin)
            & pagos_ticker["amount_mxn"].notna()
        ]
        cierres_historicos = _descargar_cierres_rango(f"{ticker_base}.MX", fecha_inicio - pd.Timedelta(days=40), fecha_fin)
        cierres = cierres_historicos[(cierres_historicos.index >= fecha_inicio) & (cierres_historicos.index <= fecha_fin)]
        if cierres.empty:
            raise ValueError(
                f"No hay precios disponibles para {ticker_base} entre {fecha_inicio:%Y-%m-%d} y {fecha_fin:%Y-%m-%d}."
            )
        etiqueta_periodo = f"{fecha_inicio:%b %Y}–{fecha_fin:%b %Y} · Desempeño en 12 meses"
        etiqueta_dist = "Distribuciones del periodo"
        sufijo_archivo = f"{fecha_fin:%Y%m%d}_ult12m"
        meses_periodo = pd.period_range(start=fecha_inicio, end=fecha_fin, freq="M")
    else:
        pagos = pagos_ticker[(pagos_ticker["ex_date"].dt.year == año) & pagos_ticker["amount_mxn"].notna()]
        cierres = _descargar_cierres_anuales(f"{ticker_base}.MX", año)
        etiqueta_periodo = f"{año} · Desempeño en 12 meses"
        etiqueta_dist = "Distribuciones en el año"
        sufijo_archivo = f"{año}"

    precio_compra = float(cierres.iloc[0])
    precio_actual = float(cierres.iloc[-1])
    fecha_inicial = cierres.index[0]
    fecha_final = cierres.index[-1]

    titulos = int(capital_invertido // precio_compra)
    plusvalia = titulos * (precio_actual - precio_compra)
    dividendo_por_titulo = float(pagos["amount_mxn"].sum())
    distribuciones_totales = titulos * dividendo_por_titulo
    retorno_total = plusvalia + distribuciones_totales
    rendimiento_total_pct = retorno_total / capital_invertido * 100

    if usar_ventana_movil:
        pagos_por_mes = (
            pagos.groupby(pagos["ex_date"].dt.to_period("M"))["amount_mxn"].sum().reindex(meses_periodo, fill_value=0.0)
        )
        etiquetas_meses = [f"{_MESES_ABREV_ES[periodo.month - 1]} {periodo.year % 100:02d}" for periodo in meses_periodo]
    else:
        pagos_por_mes = pagos.groupby(pagos["ex_date"].dt.month)["amount_mxn"].sum().reindex(range(1, 13), fill_value=0.0)
        etiquetas_meses = _MESES_ABREV_ES

    if usar_ventana_movil:
        riesgo = calcular_riesgo_mensual(cierres_historicos, pagos, fecha_inicio, fecha_fin)
        aviso_riesgo = " El riesgo mostrado es histórico y tampoco debe interpretarse como predictor de riesgo futuro."

    detalle_pagos = pagos.sort_values("ex_date").copy()
    if "yield_pct" in detalle_pagos.columns:
        detalle_pagos["yield_pct"] = pd.to_numeric(detalle_pagos["yield_pct"], errors="coerce")
    else:
        detalle_pagos["yield_pct"] = detalle_pagos["amount_mxn"] / precio_compra * 100

    return {
        "ticker_base": ticker_base,
        "usar_ventana_movil": usar_ventana_movil,
        "etiqueta_periodo": etiqueta_periodo,
        "etiqueta_dist": etiqueta_dist,
        "sufijo_archivo": sufijo_archivo,
        "aviso_riesgo": aviso_riesgo,
        "precio_compra": precio_compra,
        "precio_actual": precio_actual,
        "fecha_inicial": fecha_inicial,
        "fecha_final": fecha_final,
        "titulos": titulos,
        "plusvalia": plusvalia,
        "dividendo_por_titulo": dividendo_por_titulo,
        "distribuciones_totales": distribuciones_totales,
        "retorno_total": retorno_total,
        "rendimiento_total_pct": rendimiento_total_pct,
        "pagos_por_mes": pagos_por_mes,
        "etiquetas_meses": etiquetas_meses,
        "detalle_pagos": detalle_pagos,
        "riesgo": riesgo,
    }


def crear_ficha_completa_cliente(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Calcula y exporta la ficha HTML completa anual para el cliente, con datos reales de un ticker/año.

    A diferencia de `crear_ficha_rendimiento` (que ya no se modifica), esta ficha usa
    un diseño distinto pensado como entregable final para el cliente: escenario de
    inversión con un capital de referencia, distribuciones mensuales, el historial
    detallado de pagos (fecha, monto y rendimiento) y el rendimiento total en el
    año. Reutiliza las mismas fuentes de datos (`obtener_distribuciones`,
    `_descargar_cierres_anuales`) que la ficha de rendimiento, en vez de duplicar
    la lógica de extracción.

    Si `fecha_referencia` se especifica (o `año` se omite), `año` se ignora y el
    periodo analizado es la ventana móvil de los últimos 12 meses completos
    terminando en esa fecha, igual que en `crear_ficha_rendimiento`. Este modo
    agrega, además, una sección de riesgo del periodo (volatilidad anualizada del
    retorno total mensual, con la serie de los 12 retornos mensuales en barras);
    el modo de año calendario (por defecto) no se modifica.
    """
    datos = _calcular_ficha_completa(ticker, año, carpeta_salida, historial, capital_invertido, fecha_referencia)
    ticker_base = datos["ticker_base"]
    etiqueta_periodo = datos["etiqueta_periodo"]
    etiqueta_dist = datos["etiqueta_dist"]
    sufijo_archivo = datos["sufijo_archivo"]
    aviso_riesgo = datos["aviso_riesgo"]
    precio_compra = datos["precio_compra"]
    precio_actual = datos["precio_actual"]
    fecha_inicial = datos["fecha_inicial"]
    fecha_final = datos["fecha_final"]
    titulos = datos["titulos"]
    plusvalia = datos["plusvalia"]
    dividendo_por_titulo = datos["dividendo_por_titulo"]
    distribuciones_totales = datos["distribuciones_totales"]
    retorno_total = datos["retorno_total"]
    rendimiento_total_pct = datos["rendimiento_total_pct"]
    etiquetas_meses = datos["etiquetas_meses"]
    valores_mensuales = datos["pagos_por_mes"].tolist()
    detalle_pagos = datos["detalle_pagos"]

    max_mensual = max(max(valores_mensuales), 0.000001)
    barras_html = "".join(
        f'<div class="bar-col"><div class="bar-fill" style="height:{valor / max_mensual * 100:.1f}%"></div>'
        f'<span class="bar-label">{etiqueta}</span></div>'
        for etiqueta, valor in zip(etiquetas_meses, valores_mensuales)
    )

    riesgo_seccion_html = ""
    if datos["usar_ventana_movil"]:
        riesgo = datos["riesgo"]
        retornos_mensuales = riesgo["retornos_mensuales_pct"]
        max_retorno_abs = max(retornos_mensuales.abs().max(), 0.000001)
        barras_riesgo_html = "".join(
            f'<div class="bar-col"><div class="bar-fill {"pos" if retorno >= 0 else "neg"}" '
            f'style="height:{abs(retorno) / max_retorno_abs * 100:.1f}%"></div>'
            f'<span class="bar-label">{_MESES_ABREV_ES[fecha.month - 1]} {fecha.year % 100:02d}</span></div>'
            for fecha, retorno in retornos_mensuales.items()
        )
        riesgo_seccion_html = f"""<div class="section">
<h2 class="section-title">Riesgo del periodo</h2>
<div class="dist-grid">
<div class="dist-values">
<div class="big">{riesgo["volatilidad_anualizada_pct"]:,.2f}%</div><div class="caption">volatilidad anualizada</div>
<div class="big">{riesgo["volatilidad_mensual_pct"]:,.2f}%</div><div class="caption">volatilidad mensual promedio</div>
</div>
<div class="chart">{barras_riesgo_html}</div>
</div>
<div class="period-note">Retorno total mensual (variación de precio + dividendos del mes) de cada uno de los últimos 12 meses; verde = mes positivo, rojo = mes negativo.</div>
</div>"""

    filas_detalle = "".join(
        f"<tr><td>{_fecha_corta_es(fila.ex_date)}</td>"
        f'<td class="num">${fila.amount_mxn:,.4f}</td>'
        f'<td class="num">{fila.yield_pct:,.2f}%</td></tr>'
        for fila in detalle_pagos.itertuples()
    )

    signo = "+" if rendimiento_total_pct >= 0 else ""
    color_rendimiento = "#c0503c" if rendimiento_total_pct < 0 else "#2f8f6f"

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Ficha completa {escape(ticker_base)} {sufijo_archivo}</title>
<style>
body{{margin:0;background:#f4f6f5;font-family:'Segoe UI',Arial,sans-serif;color:#25332e}}
.card{{max-width:480px;margin:24px auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 6px 18px #00000022;color:#1c2a25}}
.header{{background:#2f5d50;color:#fff;text-align:center;padding:22px 16px}}
.header h1{{margin:0;font-size:22px;letter-spacing:1px}}
.header .subtitle{{margin-top:4px;font-size:13px;color:#cfe3da}}
.section{{padding:18px 22px}}
.scenario{{display:flex;gap:14px;align-items:stretch}}
.scenario p{{flex:1;font-size:13px;line-height:1.5;margin:0;color:#1c2a25}}
.price-boxes{{flex:1;display:flex;flex-direction:column;gap:4px}}
.price-box{{border:1px solid #d8e3df;border-radius:8px;padding:8px;text-align:center}}
.price-box .label{{font-size:10px;text-transform:uppercase;color:#55675f;display:block}}
.price-box .value{{font-size:15px;font-weight:600;margin-top:4px;color:#1c2a25}}
.arrow{{text-align:center;font-size:16px;color:#2f5d50}}
.period-note{{font-size:11px;color:#55675f;font-style:italic;margin-top:10px}}
h2.section-title{{font-size:13px;text-transform:uppercase;letter-spacing:.5px;color:#3a6b5e;border-bottom:1px solid #e3ece8;padding-bottom:6px;margin:0 0 12px}}
.dist-grid{{display:flex;gap:16px;align-items:flex-end}}
.dist-values{{flex:0 0 130px}}
.dist-values .big{{font-size:19px;font-weight:700;color:#2f5d50}}
.dist-values .caption{{font-size:11px;color:#55675f;margin:2px 0 10px}}
.chart{{flex:1;display:flex;align-items:flex-end;gap:4px;height:70px}}
.bar-col{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}}
.bar-fill{{width:70%;background:#3a8f78;border-radius:2px 2px 0 0;min-height:2px}}
.bar-fill.pos{{background:#2f8f6f}}
.bar-fill.neg{{background:#c0503c}}
.bar-label{{font-size:8px;color:#5c6b65;margin-top:3px}}
table.detalle{{width:100%;border-collapse:collapse;margin-top:10px;font-size:12px}}
table.detalle th{{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.3px;color:#55675f;padding:6px 8px;border-bottom:1px solid #d8e3df}}
table.detalle th.num{{text-align:right}}
table.detalle td{{padding:7px 8px;color:#1c2a25;background:#ffffff;border-bottom:1px solid #eef2f0}}
table.detalle td.num{{text-align:right;font-variant-numeric:tabular-nums}}
table.detalle tr:last-child td{{border-bottom:none}}
table.detalle tbody tr:nth-child(even) td{{background:#f7faf8}}
table.resumen{{width:100%;border-collapse:collapse;margin-top:14px;font-size:13px}}
table.resumen td{{padding:8px 10px;color:#1c2a25}}
table.resumen tr.plusvalia-row td{{background:#eef4f1}}
table.resumen tr.dist-row td{{background:#f7faf8}}
table.resumen td.valor{{text-align:right;font-weight:600}}
.retorno{{text-align:center;font-size:13px;color:#3a6b5e;margin-top:10px}}
.retorno strong{{font-size:15px}}
.rendimiento{{text-align:center;padding:18px 0 8px}}
.rendimiento .label{{font-size:12px;color:#55675f}}
.rendimiento .value{{font-size:34px;font-weight:700;color:{color_rendimiento}}}
.disclaimer{{font-size:9px;color:#5c6b65;text-align:center;padding:0 22px 12px;line-height:1.4}}
.footer{{background:#22463c;color:#fff;text-align:center;padding:12px;font-size:12px;letter-spacing:2px}}
</style></head>
<body><div class="card">
<div class="header"><h1>{escape(ticker_base)}</h1><div class="subtitle">{etiqueta_periodo}</div></div>
<div class="section">
<div class="scenario">
<p>Supongamos que hace un año invertiste ${capital_invertido:,.0f}; con ese monto pudiste adquirir {titulos} títulos.</p>
<div class="price-boxes">
<div class="price-box"><span class="label">Precio de compra</span><div class="value">${precio_compra:,.2f}</div></div>
<div class="arrow">&#8595;</div>
<div class="price-box"><span class="label">Precio actual</span><div class="value">${precio_actual:,.2f}</div></div>
</div>
</div>
<div class="period-note">Periodo de análisis: {_fecha_larga_es(fecha_inicial)} – {_fecha_larga_es(fecha_final)}</div>
</div>
<div class="section">
<h2 class="section-title">{etiqueta_dist}</h2>
<div class="dist-grid">
<div class="dist-values">
<div class="big">${dividendo_por_titulo:,.4f}</div><div class="caption">(por título)</div>
<div class="big">${distribuciones_totales:,.2f}</div><div class="caption">(por los {titulos} títulos)</div>
</div>
<div class="chart">{barras_html}</div>
</div>
<table class="detalle">
<thead><tr><th>Fecha</th><th class="num">Monto por título</th><th class="num">Rendimiento</th></tr></thead>
<tbody>{filas_detalle}</tbody>
</table>
</div>
<div class="section">
<table class="resumen">
<tr class="plusvalia-row"><td>Plusvalía</td><td class="valor">${plusvalia:,.2f}</td></tr>
<tr class="dist-row"><td>Distribuciones</td><td class="valor">${distribuciones_totales:,.2f}</td></tr>
</table>
<div class="retorno">Retorno total: <strong>${retorno_total:,.2f}</strong></div>
</div>
{riesgo_seccion_html}<div class="rendimiento">
<div class="label">Rendimiento total en 1 año</div>
<div class="value">{signo}{rendimiento_total_pct:,.2f}%</div>
</div>
<div class="disclaimer">Ficha informativa basada en datos históricos.<br>No constituye recomendaciones de inversión ni ofertas de compra o venta de activos financieros.<br>Rendimientos pasados no garantizan rendimientos futuros.{aviso_riesgo}</div>
<div class="footer">{escape(marca)}</div>
</div></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_{ticker_base}_{sufijo_archivo}_ficha_completa_cliente.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


_ETIQUETAS_INDICADORES_MULTIPERIODO = [
    ("periodo", "Periodo"),
    ("rendimiento_anual_pct", "Rendimiento anual (CAGR)"),
    ("rendimiento_mensual_pct", "Rendimiento mensual"),
    ("riesgo_anual_pct", "Riesgo anual"),
    ("riesgo_mensual_pct", "Riesgo mensual"),
    ("drawdown_maximo_pct", "Drawdown máximo"),
    ("ratio_sharpe", "Ratio tipo Sharpe"),
    ("tasa_cetes_pct", "CETES 28d usado"),
    ("plusvalia_mxn", "Plusvalía acumulada"),
    ("dividendos_mxn", "Dividendos acumulados"),
    ("ganancia_total_mxn", "Ganancia total"),
    ("pct_plusvalia", "% Plusvalía"),
    ("pct_dividendos", "% Dividendos"),
    ("pct_ganancia_total", "% Ganancia total"),
    ("num_pagos", "Núm. pagos"),
]


def _formatear_indicador_multiperiodo(clave: str, fila: pd.Series) -> str:
    """Formatea un indicador de la tabla multi-periodo para mostrarse en la ficha HTML."""
    if clave == "periodo":
        return f"{fila['fecha_inicio']} a {fila['fecha_fin']}"
    valor = fila[clave]
    if pd.isna(valor):
        return "N/D"
    if clave == "num_pagos":
        return f"{int(valor)}"
    if clave.endswith("_mxn"):
        signo = "-" if valor < 0 else ""
        return f"{signo}${abs(valor):,.2f} MXN"
    if clave == "ratio_sharpe":
        return f"{valor:,.2f}"
    return f"{valor:,.2f}%"


def _renderizar_ficha_multiperiodo(ticker_base: str, tabla: pd.DataFrame, notas: list[str]) -> str:
    """Arma el HTML responsivo de la ficha comparativa multi-periodo: una tarjeta por lapso.

    Las tarjetas se acomodan en una cuadrícula que se ajusta sola al ancho disponible
    (`grid-template-columns: repeat(auto-fit, minmax(...))`), por lo que se ven varias
    columnas en escritorio y una sola en celular, sin scroll horizontal ni zoom.
    """
    tarjetas = []
    for lapso, fila in tabla.iterrows():
        filas_html = "".join(
            f'<div class="fila"><span class="etiqueta">{escape(etiqueta)}</span>'
            f'<span class="valor">{escape(_formatear_indicador_multiperiodo(clave, fila))}</span></div>'
            for clave, etiqueta in _ETIQUETAS_INDICADORES_MULTIPERIODO
        )
        tarjetas.append(f'<div class="tarjeta"><h2>{escape(str(lapso))}</h2>{filas_html}</div>')

    notas_html = (
        f'<div class="notas"><strong>Notas:</strong><ul>{"".join(f"<li>{escape(n)}</li>" for n in notas)}</ul></div>'
        if notas
        else ""
    )

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Ficha multi-periodo {escape(ticker_base)}</title>
<style>
body{{margin:0;background:#12201e;color:#e8ede9;font-family:Georgia,serif}}
main{{max-width:1100px;margin:32px auto;padding:32px;background:#1b2926;color:#e8ede9;box-shadow:0 8px 24px #00000066}}
h1{{margin:0 0 6px;font-size:32px;color:#e8ede9}}
.subtitle{{color:#8ba39c;margin-bottom:24px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}}
.tarjeta{{background:#1e352e;border-top:3px solid #d8a24a;border-radius:6px;padding:16px}}
.tarjeta h2{{margin:0 0 10px;font-size:20px;color:#e8ede9}}
.fila{{display:flex;justify-content:space-between;gap:12px;padding:5px 0;border-bottom:1px solid #30423e;font:14px sans-serif}}
.fila:last-child{{border-bottom:none}}
.etiqueta{{color:#8ba39c}}
.valor{{color:#e8ede9;font-weight:600;text-align:right}}
.notas{{margin-top:24px;font:13px sans-serif;color:#9db3ac}}
.notas ul{{margin:6px 0 0;padding-left:20px}}
.notice{{margin-top:28px;font:12px sans-serif;color:#8ba39c}}
@media(max-width:650px){{main{{margin:0;padding:20px}}h1{{font-size:26px}}}}
</style></head><body><main>
<h1>Ficha comparativa de rendimiento multi-periodo: {escape(ticker_base)}</h1>
<div class="subtitle">Rendimiento y riesgo en distintas ventanas de tiempo</div>
<div class="grid">{"".join(tarjetas)}</div>
{notas_html}
<div class="notice">Ficha informativa basada en datos históricos. Los pagos se identifican por ex_date. No constituye una recomendación de compra o venta; el rendimiento pasado no garantiza resultados futuros. El riesgo y el ratio tipo Sharpe mostrados son históricos y tampoco deben interpretarse como predictores de riesgo o rendimiento futuro.</div>
</main></body></html>"""


def crear_ficha_multiperiodo(
    ticker: str,
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    fecha_referencia: Optional[datetime] = None,
) -> tuple[pd.DataFrame, Path]:
    """Calcula y exporta la ficha comparativa de rendimiento y riesgo de `ticker` en 5 ventanas
    de tiempo (1A, 2A, 5A, 10A e Histórico), y la deja lista para mostrarse en el notebook.

    A diferencia de las demás fichas del proyecto (año calendario o ventana móvil de
    12 meses, un solo periodo cada una), esta compara varias ventanas simultáneamente
    para dar una lectura rápida de corto/mediano/largo plazo (ver
    `procesamiento.armar_tabla_multiperiodo` para el detalle de los 13 indicadores
    por lapso y la regla de qué lapsos se omiten por falta de historial). Descarga el
    historial de precios COMPLETO del ticker (desde su primer dato disponible en
    Yahoo Finance), porque el lapso "Histórico" y la regla de aplicabilidad de los
    demás lapsos lo requieren.

    El ratio tipo Sharpe usa CETES 28 días (`extraccion.obtener_cetes_28d`) como tasa
    libre de riesgo. Si no hay token de Banxico configurado (variable de entorno
    `BANXICO_SIE_TOKEN`) o la API falla, ese indicador queda en NaN ("N/D" en la
    ficha) para todos los lapsos, con una nota al pie explicando por qué — el resto
    de la ficha se genera con normalidad, no se bloquea por ese único indicador.

    Devuelve `(tabla, ruta)`: `tabla` es el DataFrame para mostrarse en el notebook;
    `ruta` es el HTML exportado a `carpeta_salida`.
    """
    ticker_base = _normalizar_ticker(ticker)
    historial = historial if historial is not None else obtener_distribuciones(ticker_base, carpeta_salida)
    requerido = {"ticker", "ex_date", "amount_mxn"}
    faltantes = requerido.difference(historial.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas en el historial: {sorted(faltantes)}")

    precios_historicos = _descargar_historico_completo(f"{ticker_base}.MX")

    def _tasa_cetes_promedio(fecha_inicio: pd.Timestamp, fecha_fin: pd.Timestamp) -> float:
        serie = obtener_cetes_28d(fecha_inicio, fecha_fin)
        return float(serie.mean())

    tabla, notas = armar_tabla_multiperiodo(
        ticker_base,
        precios_historicos,
        historial,
        fecha_referencia=fecha_referencia,
        obtener_tasa_cetes=_tasa_cetes_promedio,
    )

    html = _renderizar_ficha_multiperiodo(ticker_base, tabla, notas)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_{ticker_base}_rendimiento-multiperiodo.html"
    ruta.write_text(html, encoding="utf-8")
    return tabla, ruta


def mostrar_ficha_multiperiodo(
    ticker: str,
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Genera la ficha comparativa multi-periodo con `crear_ficha_multiperiodo` y la muestra en el notebook."""
    tabla, ruta = crear_ficha_multiperiodo(ticker, carpeta_salida, historial, fecha_referencia)
    ticker_base = _normalizar_ticker(ticker)
    print(f"Ficha comparativa de rendimiento multi-periodo: {ticker_base}")
    print(f"Ficha multi-periodo generada: {ruta}")
    display(tabla)
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
    # Con una sola distribución registrada no hay forma de estimar el intervalo entre
    # pagos, así que `annualized_yield_pct` queda NaN para ese caso (ver
    # `obtener_distribuciones`); con dos o más pagos, sí debe estar siempre poblado.
    if len(historial) >= 2:
        assert historial["annualized_yield_pct"].notna().all()
    assert Path(historial.attrs["ruta_csv"]).exists()

    print(f"Ticker probado: {ticker}. Registros: {len(historial)}")
    print(f"Periodicidad detectada: {historial['periodicity'].iloc[0]}")
    print(f"CSV generado: {historial.attrs['ruta_csv']}")
    display(historial.tail(10))
    return historial


def mostrar_ficha_rendimiento(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Genera la ficha de rendimiento con `crear_ficha_rendimiento` y la muestra en el notebook.

    Ver `crear_ficha_rendimiento` para el modo de ventana móvil de últimos 12 meses
    (`fecha_referencia`, o `año=None`), que coexiste con el modo de año calendario.
    """
    ruta = crear_ficha_rendimiento(ticker, año, carpeta_salida, historial, fecha_referencia)
    print(f"Ficha generada: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    return ruta


def mostrar_ficha_completa_cliente(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Genera la ficha completa anual para el cliente con `crear_ficha_completa_cliente` y la muestra en el notebook.

    Ver `crear_ficha_completa_cliente` para el modo de ventana móvil de últimos 12
    meses (`fecha_referencia`, o `año=None`), que coexiste con el modo de año
    calendario.
    """
    ruta = crear_ficha_completa_cliente(ticker, año, carpeta_salida, historial, capital_invertido, marca, fecha_referencia)
    print(f"Ficha completa generada: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    return ruta


_PATRON_TIMESTAMP_FICHA = re.compile(r"^(\d{8})_(\d{6})_")


def exportar_ficha_a_pdf(
    ruta_html: Path,
    ticker: str,
    descripcion: str,
    periodo: str,
    carpeta_salida: Path,
) -> Path:
    """Exporta a PDF una ficha HTML ya generada (por `crear_ficha_rendimiento` o
    `crear_ficha_completa_cliente`), con un nombre de archivo estandarizado:
    `AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.pdf`.

    La fecha/hora del nombre se toma del propio nombre de `ruta_html` (prefijo
    `YYYYMMDD_HHMMSS_` que ya generan ambas funciones de ficha), es decir, el
    momento en que se consultaron los datos, no el momento de esta exportación ni
    la fecha de modificación en disco del archivo (que, como en el resto del
    proyecto, no es confiable). `descripcion` debe tener como máximo cuatro
    palabras; se normaliza a minúsculas separadas por guiones (p. ej.
    "rendimiento anual" -> "rendimiento-anual"). Si ya existe un PDF con el mismo
    nombre, se sobrescribe.
    """
    coincidencia = _PATRON_TIMESTAMP_FICHA.match(ruta_html.name)
    if not coincidencia:
        raise ValueError(
            f"'{ruta_html.name}' no tiene el prefijo de fecha/hora esperado (YYYYMMDD_HHMMSS_)."
        )
    momento = datetime.strptime(coincidencia.group(1) + coincidencia.group(2), "%Y%m%d%H%M%S")

    palabras = str(descripcion).strip().lower().split()
    if not palabras:
        raise ValueError("La descripción breve no puede estar vacía.")
    if len(palabras) > 4:
        raise ValueError("La descripción breve debe tener máximo cuatro palabras.")
    descripcion_normalizada = "-".join(palabras)

    ticker_base = _normalizar_ticker(ticker)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    ruta_pdf = carpeta_salida / f"{momento:%Y-%m-%d_%H%M}_{ticker_base}_{descripcion_normalizada}_{periodo}.pdf"

    def _generar_pdf() -> None:
        with sync_playwright() as playwright:
            navegador = playwright.chromium.launch()
            try:
                pagina = navegador.new_page()
                pagina.goto(ruta_html.resolve().as_uri())
                pagina.pdf(path=str(ruta_pdf), format="Letter", print_background=True)
            finally:
                navegador.close()

    ejecutar_con_playwright_sync(_generar_pdf)
    return ruta_pdf


def exportar_comparativo_a_html(
    ruta_html: Path,
    descripcion: str,
    periodo: str,
    carpeta_salida: Path,
) -> Path:
    """Copia un comparativo de FIBRAs ya generado (por `crear_comparativo_rendimiento`
    o `crear_comparativo_completo_cliente`) a la carpeta de entregables, con un
    nombre de archivo estandarizado: `AAAA-MM-DD_HHMM_comparativo_descripcion-breve_periodo.html`.

    Análogo a `exportar_ficha_a_pdf`, pero el entregable se queda en HTML
    responsivo en vez de convertirse a PDF: al juntar a todas las FIBRAs
    seleccionadas en un solo archivo, el nombre ya no lleva un ticker específico.
    La fecha/hora del nombre se toma del propio nombre de `ruta_html` (prefijo
    `YYYYMMDD_HHMMSS_` que ya generan ambas funciones de comparativo), es decir, el
    momento en que se consultaron los datos. `descripcion` debe tener como máximo
    cuatro palabras. Si ya existe un archivo con el mismo nombre, se sobrescribe.
    """
    coincidencia = _PATRON_TIMESTAMP_FICHA.match(ruta_html.name)
    if not coincidencia:
        raise ValueError(
            f"'{ruta_html.name}' no tiene el prefijo de fecha/hora esperado (YYYYMMDD_HHMMSS_)."
        )
    momento = datetime.strptime(coincidencia.group(1) + coincidencia.group(2), "%Y%m%d%H%M%S")

    palabras = str(descripcion).strip().lower().split()
    if not palabras:
        raise ValueError("La descripción breve no puede estar vacía.")
    if len(palabras) > 4:
        raise ValueError("La descripción breve debe tener máximo cuatro palabras.")
    descripcion_normalizada = "-".join(palabras)

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    ruta_destino = carpeta_salida / f"{momento:%Y-%m-%d_%H%M}_comparativo_{descripcion_normalizada}_{periodo}.html"
    ruta_destino.write_text(ruta_html.read_text(encoding="utf-8"), encoding="utf-8")
    return ruta_destino


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


# --- Análisis de múltiples FIBRAs a la vez ---


class _SelectorTickersMultiple(widgets.VBox):
    """Lista de casillas (`Checkbox`), una por ticker, para elegir varias FIBRAs a la vez.

    Se usa en vez de `ipywidgets.SelectMultiple` porque en ese control hay que hacer
    Ctrl/Shift+clic para marcar más de una opción (poco evidente, y en algunos
    frontends un clic normal deselecciona el resto). Con una casilla por ticker,
    marcar varias es un clic por cada una, sin combinaciones de teclado.

    Expone `.value` como la tupla de tickers marcados, en el orden del listado, para
    que las celdas siguientes lo lean igual que a los demás selectores del notebook.
    """

    def __init__(self, tickers: list[str], seleccionados_iniciales: list[str]) -> None:
        self._casillas = [
            widgets.Checkbox(value=(ticker in seleccionados_iniciales), description=ticker, indent=False)
            for ticker in tickers
        ]
        encabezado = widgets.HTML("<b>Tickers a analizar</b> (marca una o varias):")
        super().__init__([encabezado, *self._casillas])

    @property
    def value(self) -> tuple[str, ...]:
        return tuple(casilla.description for casilla in self._casillas if casilla.value)


def seleccionar_tickers_interactivo(
    emisoras: pd.Series, valores_simulados: Optional[list[str]] = None
) -> "_SelectorTickersMultiple":
    """Despliega un widget de selección MÚLTIPLE para elegir entre 1 y N tickers en un solo paso.

    Análogo a `seleccionar_ticker_interactivo`, pero permite analizar varias FIBRAs
    a la vez (N = total de emisoras listadas): muestra una casilla por ticker y se
    pueden marcar varias con un clic cada una. Como el listado no tiene duplicados,
    no se puede repetir una emisora. La validación de "al menos 1 ticker" se hace al
    leer la selección en `armar_tabla_tickers_seleccionados` (una celda después),
    siguiendo el mismo patrón de los demás selectores del notebook.

    `valores_simulados` fija la selección inicial para pruebas automatizadas (donde
    no hay un usuario real interactuando con el widget); si incluye algún ticker
    fuera del listado, se lanza un error claro en vez de continuar con uno inválido.
    """
    tickers_disponibles = sorted(pd.Series(emisoras).astype(str).unique().tolist())
    if not tickers_disponibles:
        raise ValueError("No hay tickers disponibles para elegir.")
    valores_simulados = list(valores_simulados) if valores_simulados is not None else []
    invalidos = [t for t in valores_simulados if t not in tickers_disponibles]
    if invalidos:
        raise ValueError(f"Estos tickers no están en el listado: {invalidos}. Tickers válidos: {tickers_disponibles}.")
    selector = _SelectorTickersMultiple(tickers_disponibles, valores_simulados)
    display(selector)
    return selector


def armar_tabla_tickers_seleccionados(
    seleccion, emisoras: pd.Series, df_indice: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """Valida la selección de tickers y arma el DataFrame `tickers_seleccionados`.

    - Exige al menos 1 ticker; quita duplicados conservando el orden de aparición.
    - Verifica que cada ticker esté en el listado de emisoras (`emisoras`).
    - Adjunta como metadato la cotización y variación de AMEFIBRA de esta corrida si
      `df_indice` las trae (columnas `Emisora` / `Cotización` / `Var. %`); si no se
      ejecutó la extracción en vivo, esas columnas quedan vacías (`<NA>`).

    Las celdas siguientes (precio/periodicidad, años disponibles, fichas de
    rendimiento anual y de 12 meses) iteran sobre este DataFrame en lugar de sobre
    un único ticker.
    """
    disponibles = set(pd.Series(emisoras).astype(str))
    tickers: list[str] = []
    for valor in seleccion:
        ticker = str(valor).strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    if not tickers:
        raise ValueError(
            "Selecciona al menos un ticker en el widget de arriba (clic, o Ctrl/Shift+clic para "
            "varios) antes de correr esta celda."
        )
    no_listados = [t for t in tickers if t not in disponibles]
    if no_listados:
        raise ValueError(f"Estos tickers no están en el listado de emisoras: {no_listados}.")

    tabla = pd.DataFrame({"ticker": tickers})
    columnas_metadato = {"cotizacion_amefibra": "Cotización", "var_pct_amefibra": "Var. %"}
    for columna_destino, columna_origen in columnas_metadato.items():
        if df_indice is not None and not df_indice.empty and {"Emisora", columna_origen}.issubset(df_indice.columns):
            tabla[columna_destino] = tabla["ticker"].map(df_indice.set_index("Emisora")[columna_origen])
        else:
            tabla[columna_destino] = pd.NA

    print(f"Tickers seleccionados ({len(tabla)}): {', '.join(tabla['ticker'])}.")
    return tabla


def descargar_historiales_dividendos(
    tickers, emisoras: pd.Series, carpeta_salida: Path
) -> dict:
    """Descarga el historial de distribuciones de cada ticker, tolerando fallos individuales.

    Devuelve un dict `{ticker: DataFrame}` (o `{ticker: None}` si la descarga de ese
    ticker falló: se muestra una advertencia visible y se continúa con los demás).
    Reutiliza `obtener_distribuciones` (misma validación de forma y export a CSV que
    el flujo de un solo ticker).
    """
    disponibles = set(pd.Series(emisoras).astype(str))
    historiales: dict = {}
    for ticker in tickers:
        if ticker not in disponibles:
            print(f"  Aviso: {ticker} no está en el listado de emisoras; se omite.")
            historiales[ticker] = None
            continue
        try:
            historial = obtener_distribuciones(ticker, carpeta_salida)
            historiales[ticker] = historial
            print(
                f"  {ticker}: {len(historial)} distribuciones · periodicidad "
                f"{historial['periodicity'].iloc[0]} · CSV: {historial.attrs['ruta_csv'].name}"
            )
        except Exception as error:  # noqa: BLE001 - tolerancia a fallos por ticker, a propósito
            print(f"  Aviso: no se pudo obtener el historial de dividendos de {ticker}: {error}")
            historiales[ticker] = None
    return historiales


def resumen_precio_periodicidad(
    tickers_seleccionados: pd.DataFrame, historiales: dict
) -> pd.DataFrame:
    """Tabla única con el precio actual y la periodicidad de dividendos de cada ticker seleccionado.

    `precio_actual` es el último cierre diario disponible en Yahoo Finance
    (`obtener_precio_actual`); `periodicidad` sale del historial ya descargado en
    `historiales`. Si falla la obtención de alguno para un ticker, esa celda queda
    como `N/A` y el resto de la tabla se arma igual (misma tolerancia a fallos
    individuales que el resto del notebook).
    """
    filas = []
    for ticker in tickers_seleccionados["ticker"]:
        try:
            precio_actual = f"${obtener_precio_actual(ticker):,.2f}"
        except Exception:  # noqa: BLE001 - degradación a "N/A" a propósito
            precio_actual = "N/A"
        historial = historiales.get(ticker)
        periodicidad = (
            historial["periodicity"].iloc[0] if historial is not None and not historial.empty else "N/A"
        )
        filas.append({"ticker": ticker, "precio_actual": precio_actual, "periodicidad": periodicidad})
    tabla = pd.DataFrame(filas)
    display(tabla)
    return tabla


_COLOR_POSITIVO_OSCURO = "#5fd9b0"
_COLOR_NEGATIVO_OSCURO = "#f2836a"
_COLOR_POSITIVO_CLARO = "#2f8f6f"
_COLOR_NEGATIVO_CLARO = "#c0503c"


def _fila_comparativo(tickers_ok: list[str], datos_por_ticker: dict, etiqueta: str, formato, campo_color: Optional[str] = None, color_pos: str = _COLOR_POSITIVO_OSCURO, color_neg: str = _COLOR_NEGATIVO_OSCURO) -> str:
    """Arma una fila `<tr>` de una tabla comparativa: una etiqueta y una celda por FIBRA.

    Si `campo_color` se indica, el texto de cada celda se resalta en `color_pos` o
    `color_neg` según el signo del valor numérico en `datos_por_ticker[ticker][campo_color]`.
    Compartida por `crear_comparativo_rendimiento` y `crear_comparativo_completo_cliente`
    para que ambas tablas comparativas se vean y se comporten igual.
    """
    celdas = []
    for ticker in tickers_ok:
        datos = datos_por_ticker[ticker]
        texto = escape(formato(datos))
        if campo_color is not None:
            color = color_neg if datos[campo_color] < 0 else color_pos
            texto = f'<span style="color:{color};font-weight:600">{texto}</span>'
        celdas.append(f"<td>{texto}</td>")
    return f"<tr><th>{escape(etiqueta)}</th>{''.join(celdas)}</tr>"


def crear_comparativo_rendimiento(
    tickers_seleccionados: pd.DataFrame,
    historiales: dict,
    carpeta_salida: Path,
    año: Optional[int] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Calcula y exporta el comparativo de rendimiento de todas las FIBRAs seleccionadas en una sola tabla.

    Reutiliza el mismo cálculo que `crear_ficha_rendimiento` (`_calcular_rendimiento`)
    para cada ticker, con el mismo año calendario o la misma ventana móvil de
    últimos 12 meses aplicados por igual a todos ellos (`mostrar_ficha_rendimiento`
    sigue disponible sin cambios para el análisis de un solo ticker). No omite
    ningún indicador de los que ya muestra la ficha individual: además de la tabla
    resumen (indicadores en filas, FIBRAs en columnas), incluye el detalle completo
    de distribuciones de todas las FIBRAs. El diseño es de tablas anchas con scroll
    horizontal controlado y la primera columna fija, para que se lea igual de bien
    en escritorio y en celular.
    """
    datos_por_ticker: dict[str, dict] = {}
    for ticker in tickers_seleccionados["ticker"]:
        historial = historiales.get(ticker)
        if historial is None or historial.empty:
            print(f"Aviso: se omite {ticker} del comparativo de rendimiento: sin historial de dividendos disponible.")
            continue
        try:
            datos_por_ticker[ticker] = _calcular_rendimiento(ticker, año, carpeta_salida, historial, fecha_referencia)
        except Exception as error:  # noqa: BLE001 - tolerancia a fallos por ticker, a propósito
            print(f"Aviso: no se pudo calcular el rendimiento de {ticker} para el comparativo: {error}")
    if not datos_por_ticker:
        raise ValueError("No hay tickers con datos suficientes para armar el comparativo de rendimiento.")

    tickers_ok = list(datos_por_ticker)
    referencia = datos_por_ticker[tickers_ok[0]]
    encabezados_html = "".join(f"<th>{escape(t)}</th>" for t in tickers_ok)

    filas_resumen_html = "".join([
        _fila_comparativo(tickers_ok, datos_por_ticker, "Periodo (cierres)", lambda d: f"{d['fecha_inicial']} a {d['fecha_final']}"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Precio inicial", lambda d: f"${d['precio_inicial']:,.2f} MXN"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Precio final", lambda d: f"${d['precio_final']:,.2f} MXN"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Variación de precio", lambda d: f"{d['rendimiento_capital']:,.2f}%", "rendimiento_capital"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Rendimiento por dividendos", lambda d: f"{d['rendimiento_dividendos']:,.2f}%"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Rendimiento total", lambda d: f"{d['rendimiento_total']:,.2f}%", "rendimiento_total"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Ganancia total", lambda d: f"${d['ganancia_total']:,.2f} MXN", "ganancia_total"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Dividendos recibidos", lambda d: f"${d['total_dividendos']:,.4f} MXN"),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Variación de capital", lambda d: f"${d['variacion_capital']:,.2f} MXN", "variacion_capital"),
    ])
    if referencia["usar_ventana_movil"]:
        filas_resumen_html += _fila_comparativo(
            tickers_ok, datos_por_ticker, "Riesgo mensual promedio", lambda d: f'{d["riesgo"]["volatilidad_mensual_pct"]:,.2f}%'
        )

    filas_pagos = []
    for ticker in tickers_ok:
        pagos = datos_por_ticker[ticker]["pagos"].sort_values("ex_date")
        for fila in pagos.itertuples():
            filas_pagos.append(
                f"<tr><td>{escape(ticker)}</td><td>{fila.ex_date:%Y-%m-%d}</td>"
                f'<td class="num">${fila.amount_mxn:,.4f}</td><td class="num">{fila.yield_pct:,.2f}%</td></tr>'
            )
    filas_pagos_html = "".join(filas_pagos) if filas_pagos else '<tr><td colspan="4">Sin distribuciones en el periodo.</td></tr>'

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparativo de rendimiento {referencia['sufijo_archivo']}</title>
<style>
body{{margin:0;background:#12201e;color:#e8ede9;font-family:Georgia,serif}}
main{{max-width:1200px;margin:32px auto;padding:32px;background:#1b2926;color:#e8ede9;box-shadow:0 8px 24px #00000066}}
h1{{margin:0 0 6px;font-size:32px;color:#e8ede9}}
h2{{color:#e8ede9;margin-top:28px;font-size:20px}}
.subtitle{{color:#8ba39c;margin-bottom:24px}}
.tabla-scroll{{overflow-x:auto;margin-top:12px;border:1px solid #30423e;border-radius:6px}}
table{{border-collapse:collapse;font:14px sans-serif;width:100%;min-width:520px}}
th,td{{padding:10px 14px;border-bottom:1px solid #30423e;text-align:right;white-space:nowrap}}
th{{color:#8ba39c;font-weight:600}}
tbody th{{text-align:left;color:#e8ede9;background:#1e352e;position:sticky;left:0;z-index:1}}
thead th:first-child{{text-align:left;position:sticky;left:0;background:#1b2926;z-index:2}}
tbody tr:nth-child(even) td{{background:#1e2c29}}
.notice{{margin-top:28px;font:12px sans-serif;color:#8ba39c}}
@media(max-width:650px){{main{{margin:0;padding:18px}}h1{{font-size:24px}}}}
</style></head><body><main>
<h1>Comparativo de rendimiento de FIBRAs</h1>
<div class="subtitle">{referencia['etiqueta_periodo']} · {len(tickers_ok)} FIBRAs</div>
<div class="tabla-scroll"><table><thead><tr><th>Indicador</th>{encabezados_html}</tr></thead>
<tbody>{filas_resumen_html}</tbody></table></div>
<h2>Detalle de distribuciones ({referencia['etiqueta_pagos'].lower()})</h2>
<div class="tabla-scroll"><table><thead><tr><th>FIBRA</th><th>Fecha</th><th>Monto</th><th>Rendimiento</th></tr></thead>
<tbody>{filas_pagos_html}</tbody></table></div>
<div class="notice">Ficha informativa basada en datos históricos. Los pagos se identifican por ex_date. No constituye una recomendación de compra o venta; el rendimiento pasado no garantiza resultados futuros.{referencia['aviso_riesgo']}</div>
</main></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_comparativo_{referencia['sufijo_archivo']}_rendimiento.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def mostrar_comparativo_rendimiento(
    tickers_seleccionados: pd.DataFrame,
    historiales: dict,
    carpeta_salida: Path,
    carpeta_export: Path,
    año: Optional[int] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Genera, muestra y exporta a HTML el comparativo de rendimiento de todas las FIBRAs seleccionadas.

    Sustituye a una ficha y un PDF por ticker por una sola tabla comparativa con la
    misma información, mostrada en el notebook y exportada como un único archivo
    HTML responsivo (ya no PDF) en `carpeta_export`.
    """
    ruta = crear_comparativo_rendimiento(tickers_seleccionados, historiales, carpeta_salida, año, fecha_referencia)
    print(f"Comparativo de rendimiento generado: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    if año is not None:
        descripcion_export, periodo_export = "rendimiento anual", str(año)
    else:
        _, fecha_fin = calcular_ventana_movil_12_meses(fecha_referencia)
        descripcion_export, periodo_export = "rendimiento 12 meses", f"{fecha_fin:%Y%m%d}"
    ruta_export = exportar_comparativo_a_html(ruta, descripcion_export, periodo_export, carpeta_export)
    print(f"HTML exportado: {ruta_export}")
    return ruta


def crear_comparativo_completo_cliente(
    tickers_seleccionados: pd.DataFrame,
    historiales: dict,
    carpeta_salida: Path,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    año: Optional[int] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Calcula y exporta el "Comparativo de FIBRAs" (ficha completa para cliente) de
    todas las FIBRAs seleccionadas en una sola tabla.

    Reutiliza el mismo cálculo que `crear_ficha_completa_cliente`
    (`_calcular_ficha_completa`) para cada ticker, con el mismo año calendario o la
    misma ventana móvil de últimos 12 meses y el mismo capital de referencia
    aplicados por igual a todos ellos (`mostrar_ficha_completa_cliente` sigue
    disponible sin cambios para el análisis de un solo ticker). No omite ningún
    indicador de los que ya muestra la ficha individual: incluye el resumen del
    escenario de inversión, las distribuciones mensuales por título, el retorno
    mensual del periodo (cuando aplica) y el detalle completo de pagos, todo como
    tablas anchas con scroll horizontal controlado y la primera columna fija.
    """
    datos_por_ticker: dict[str, dict] = {}
    for ticker in tickers_seleccionados["ticker"]:
        historial = historiales.get(ticker)
        if historial is None or historial.empty:
            print(f"Aviso: se omite {ticker} del comparativo de FIBRAs: sin historial de dividendos disponible.")
            continue
        try:
            datos_por_ticker[ticker] = _calcular_ficha_completa(
                ticker, año, carpeta_salida, historial, capital_invertido, fecha_referencia
            )
        except Exception as error:  # noqa: BLE001 - tolerancia a fallos por ticker, a propósito
            print(f"Aviso: no se pudo calcular la ficha completa de {ticker} para el comparativo: {error}")
    if not datos_por_ticker:
        raise ValueError("No hay tickers con datos suficientes para armar el comparativo de FIBRAs.")

    tickers_ok = list(datos_por_ticker)
    referencia = datos_por_ticker[tickers_ok[0]]
    encabezados_html = "".join(f"<th>{escape(t)}</th>" for t in tickers_ok)

    filas_resumen_html = "".join([
        _fila_comparativo(tickers_ok, datos_por_ticker, "Precio de compra", lambda d: f"${d['precio_compra']:,.2f}", color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Precio actual", lambda d: f"${d['precio_actual']:,.2f}", color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Títulos", lambda d: f"{d['titulos']}", color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Plusvalía", lambda d: f"${d['plusvalia']:,.2f}", "plusvalia", _COLOR_POSITIVO_CLARO, _COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Dividendo por título", lambda d: f"${d['dividendo_por_titulo']:,.4f}", color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Distribuciones totales", lambda d: f"${d['distribuciones_totales']:,.2f}", color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Retorno total", lambda d: f"${d['retorno_total']:,.2f}", "retorno_total", _COLOR_POSITIVO_CLARO, _COLOR_NEGATIVO_CLARO),
        _fila_comparativo(tickers_ok, datos_por_ticker, "Rendimiento total", lambda d: f"{d['rendimiento_total_pct']:,.2f}%", "rendimiento_total_pct", _COLOR_POSITIVO_CLARO, _COLOR_NEGATIVO_CLARO),
    ])
    if referencia["usar_ventana_movil"]:
        filas_resumen_html += "".join([
            _fila_comparativo(tickers_ok, datos_por_ticker, "Volatilidad mensual promedio", lambda d: f'{d["riesgo"]["volatilidad_mensual_pct"]:,.2f}%', color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
            _fila_comparativo(tickers_ok, datos_por_ticker, "Volatilidad anualizada", lambda d: f'{d["riesgo"]["volatilidad_anualizada_pct"]:,.2f}%', color_pos=_COLOR_POSITIVO_CLARO, color_neg=_COLOR_NEGATIVO_CLARO),
        ])

    encabezados_meses_html = "".join(f"<th>{escape(m)}</th>" for m in referencia["etiquetas_meses"])
    filas_mensual_html = "".join(
        f"<tr><th>{escape(t)}</th>" + "".join(f"<td>${valor:,.2f}</td>" for valor in datos_por_ticker[t]["pagos_por_mes"].tolist()) + "</tr>"
        for t in tickers_ok
    )

    seccion_riesgo_html = ""
    if referencia["usar_ventana_movil"]:
        filas_riesgo_html = "".join(
            f"<tr><th>{escape(t)}</th>" + "".join(
                f'<td><span style="color:{_COLOR_NEGATIVO_CLARO if retorno < 0 else _COLOR_POSITIVO_CLARO};font-weight:600">{retorno:,.2f}%</span></td>'
                for retorno in datos_por_ticker[t]["riesgo"]["retornos_mensuales_pct"].tolist()
            ) + "</tr>"
            for t in tickers_ok
        )
        seccion_riesgo_html = f"""
<h2 class="section-title">Retorno total mensual por FIBRA</h2>
<div class="tabla-scroll"><table><thead><tr><th>FIBRA</th>{encabezados_meses_html}</tr></thead>
<tbody>{filas_riesgo_html}</tbody></table></div>
<div class="period-note">Retorno total mensual (variación de precio + dividendos del mes); verde = mes positivo, rojo = mes negativo.</div>"""

    filas_detalle = []
    for t in tickers_ok:
        detalle = datos_por_ticker[t]["detalle_pagos"].sort_values("ex_date")
        for fila in detalle.itertuples():
            filas_detalle.append(
                f"<tr><td>{escape(t)}</td><td>{_fecha_corta_es(fila.ex_date)}</td>"
                f'<td class="num">${fila.amount_mxn:,.4f}</td><td class="num">{fila.yield_pct:,.2f}%</td></tr>'
            )
    filas_detalle_html = "".join(filas_detalle) if filas_detalle else '<tr><td colspan="4">Sin distribuciones en el periodo.</td></tr>'

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparativo de FIBRAs {referencia['sufijo_archivo']}</title>
<style>
body{{margin:0;background:#f4f6f5;font-family:'Segoe UI',Arial,sans-serif;color:#25332e}}
main{{max-width:1200px;margin:24px auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 6px 18px #00000022;color:#1c2a25}}
.header{{background:#2f5d50;color:#fff;text-align:center;padding:22px 16px}}
.header h1{{margin:0;font-size:24px;letter-spacing:1px}}
.header .subtitle{{margin-top:4px;font-size:13px;color:#cfe3da}}
.section{{padding:18px 22px}}
h2.section-title{{font-size:13px;text-transform:uppercase;letter-spacing:.5px;color:#3a6b5e;border-bottom:1px solid #e3ece8;padding-bottom:6px;margin:18px 0 12px}}
.tabla-scroll{{overflow-x:auto;border:1px solid #e3ece8;border-radius:6px}}
table{{border-collapse:collapse;width:100%;min-width:520px;font-size:13px}}
th,td{{padding:9px 12px;border-bottom:1px solid #eef2f0;text-align:right;white-space:nowrap}}
th{{color:#55675f;font-size:11px;text-transform:uppercase;letter-spacing:.3px}}
tbody th{{text-align:left;color:#1c2a25;background:#f7faf8;position:sticky;left:0;z-index:1;text-transform:none;font-weight:600}}
thead th:first-child{{text-align:left;position:sticky;left:0;background:#ffffff;z-index:2}}
tbody tr:nth-child(even) td{{background:#f7faf8}}
.period-note{{font-size:11px;color:#55675f;font-style:italic;margin-top:8px}}
.disclaimer{{font-size:9px;color:#5c6b65;text-align:center;padding:0 22px 12px;line-height:1.4}}
.footer{{background:#22463c;color:#fff;text-align:center;padding:12px;font-size:12px;letter-spacing:2px}}
@media(max-width:650px){{.section{{padding:14px}}.header h1{{font-size:20px}}}}
</style></head>
<body><main>
<div class="header"><h1>Comparativo de FIBRAs</h1><div class="subtitle">{referencia['etiqueta_periodo']} · Capital de referencia: ${capital_invertido:,.0f} · {len(tickers_ok)} FIBRAs</div></div>
<div class="section">
<h2 class="section-title">Resumen del escenario de inversión</h2>
<div class="tabla-scroll"><table><thead><tr><th>Indicador</th>{encabezados_html}</tr></thead>
<tbody>{filas_resumen_html}</tbody></table></div>
</div>
<div class="section">
<h2 class="section-title">{escape(referencia['etiqueta_dist'])} (por título, por mes)</h2>
<div class="tabla-scroll"><table><thead><tr><th>FIBRA</th>{encabezados_meses_html}</tr></thead>
<tbody>{filas_mensual_html}</tbody></table></div>
{seccion_riesgo_html}
</div>
<div class="section">
<h2 class="section-title">Detalle de distribuciones</h2>
<div class="tabla-scroll"><table><thead><tr><th>FIBRA</th><th>Fecha</th><th>Monto por título</th><th>Rendimiento</th></tr></thead>
<tbody>{filas_detalle_html}</tbody></table></div>
</div>
<div class="disclaimer">Ficha informativa basada en datos históricos.<br>No constituye recomendaciones de inversión ni ofertas de compra o venta de activos financieros.<br>Rendimientos pasados no garantizan rendimientos futuros.{referencia['aviso_riesgo']}</div>
<div class="footer">{escape(marca)}</div>
</main></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_comparativo_{referencia['sufijo_archivo']}_ficha_completa_cliente.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


def mostrar_comparativo_completo_cliente(
    tickers_seleccionados: pd.DataFrame,
    historiales: dict,
    carpeta_salida: Path,
    carpeta_export: Path,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    año: Optional[int] = None,
    fecha_referencia: Optional[datetime] = None,
) -> Path:
    """Genera, muestra y exporta a HTML el "Comparativo de FIBRAs" (ficha completa
    para cliente) de todas las FIBRAs seleccionadas.

    Sustituye a una ficha y un PDF por ticker por una sola tabla comparativa con la
    misma información, mostrada en el notebook y exportada como un único archivo
    HTML responsivo (ya no PDF) en `carpeta_export`.
    """
    ruta = crear_comparativo_completo_cliente(
        tickers_seleccionados, historiales, carpeta_salida, capital_invertido, marca, año, fecha_referencia
    )
    print(f"Comparativo de FIBRAs generado: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    if año is not None:
        descripcion_export, periodo_export = "ficha completa cliente", str(año)
    else:
        _, fecha_fin = calcular_ventana_movil_12_meses(fecha_referencia)
        descripcion_export, periodo_export = "ficha completa 12 meses", f"{fecha_fin:%Y%m%d}"
    ruta_export = exportar_comparativo_a_html(ruta, descripcion_export, periodo_export, carpeta_export)
    print(f"HTML exportado: {ruta_export}")
    return ruta
