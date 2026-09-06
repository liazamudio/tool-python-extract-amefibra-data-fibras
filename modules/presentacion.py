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
    HORIZONTES_ESCENARIO_MULTIANUAL,
    _normalizar_ticker,
    armar_tabla_multiperiodo,
    calcular_escenario_multianual,
    calcular_riesgo_mensual,
    calcular_ventana_movil_12_meses,
    calcular_ventana_multianual,
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
    """Obtiene el listado de emisoras, indica su procedencia y lo exporta a CSV en `carpeta_salida`.

    Si `df` fue generado en la corrida actual (no es `None` ni está vacío), se usa
    ese dato recién extraído de AMEFIBRA. Si no (porque las celdas de extracción no
    se ejecutaron), se reutiliza el CSV `*_list_of_tickers.csv` más reciente ya
    guardado en `carpeta_salida`, para no depender de repetir la extracción.

    No imprime el listado completo de emisoras: esa información ya queda visible en
    el selector de casillas que se despliega en la misma celda
    (`seleccionar_tickers_interactivo`). Sí deja la leyenda de la fuente y el
    conteo de emisoras cargadas, como trazabilidad.
    """
    if df is not None and not df.empty:
        df_emisoras = df[["Emisora"]]
        print(f"Fuente de emisoras: extracción de AMEFIBRA de esta corrida ({len(df_emisoras)} emisoras).")
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
    df_emisoras = pd.read_csv(ruta_historico)[["Emisora"]]
    print(
        f"Fuente de emisoras: histórico de {ruta_historico.name} ({len(df_emisoras)} emisoras; "
        "no se ejecutó la extracción de AMEFIBRA en esta corrida)."
    )
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
) -> tuple[Path, dict]:
    """Calcula y exporta una ficha HTML de rendimiento total para un año calendario.

    Si `fecha_referencia` se especifica, `año` se ignora y el periodo analizado es,
    en cambio, la ventana móvil de los últimos 12 meses completos terminando en esa
    fecha (`calcular_ventana_movil_12_meses`; por defecto, si se pasa una fecha
    "vacía"/None con este modo activo, la fecha de referencia es hoy). Este modo
    agrega además el riesgo mensual promedio del periodo (volatilidad del retorno
    total mensual) como cifra destacada junto al rendimiento total; el modo de año
    calendario (`fecha_referencia=None`, el de siempre) no se modifica.

    Devuelve `(ruta, datos)`: `ruta` es el HTML exportado a `carpeta_salida`; `datos`
    es el diccionario de `_calcular_rendimiento` con los mismos indicadores ya
    mostrados en la ficha, para que otra exportación (p. ej. `exportar_ficha_html`)
    los reutilice sin recalcularlos ni arriesgar que diverjan.
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
    return ruta, datos


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
) -> tuple[Path, dict]:
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

    Devuelve `(ruta, datos)`: `ruta` es el HTML exportado a `carpeta_salida`; `datos`
    es el diccionario de `_calcular_ficha_completa` con los mismos indicadores ya
    mostrados en la ficha, para que otra exportación (p. ej. `exportar_ficha_html`)
    los reutilice sin recalcularlos ni arriesgar que diverjan.
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
    return ruta, datos


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
) -> tuple[Path, pd.DataFrame]:
    """Genera la ficha comparativa multi-periodo con `crear_ficha_multiperiodo` y la muestra en el notebook.

    Devuelve `(ruta, tabla)`: `ruta` es el HTML exportado; `tabla` es el mismo
    DataFrame ya mostrado en el notebook, para que otra exportación (p. ej.
    `exportar_ficha_html`) lo reutilice sin recalcularlo.
    """
    tabla, ruta = crear_ficha_multiperiodo(ticker, carpeta_salida, historial, fecha_referencia)
    ticker_base = _normalizar_ticker(ticker)
    print(f"Ficha comparativa de rendimiento multi-periodo: {ticker_base}")
    print(f"Ficha multi-periodo generada: {ruta}")
    display(tabla)
    return ruta, tabla


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
) -> tuple[Path, dict]:
    """Genera la ficha de rendimiento con `crear_ficha_rendimiento` y la muestra en el notebook.

    Ver `crear_ficha_rendimiento` para el modo de ventana móvil de últimos 12 meses
    (`fecha_referencia`, o `año=None`), que coexiste con el modo de año calendario.
    Devuelve `(ruta, datos)`: ver `crear_ficha_rendimiento`.
    """
    ruta, datos = crear_ficha_rendimiento(ticker, año, carpeta_salida, historial, fecha_referencia)
    print(f"Ficha generada: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    return ruta, datos


def mostrar_ficha_completa_cliente(
    ticker: str,
    año: Optional[int],
    carpeta_salida: Path,
    historial: Optional[pd.DataFrame] = None,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    fecha_referencia: Optional[datetime] = None,
) -> tuple[Path, dict]:
    """Genera la ficha completa anual para el cliente con `crear_ficha_completa_cliente` y la muestra en el notebook.

    Ver `crear_ficha_completa_cliente` para el modo de ventana móvil de últimos 12
    meses (`fecha_referencia`, o `año=None`), que coexiste con el modo de año
    calendario. Devuelve `(ruta, datos)`: ver `crear_ficha_completa_cliente`.
    """
    ruta, datos = crear_ficha_completa_cliente(
        ticker, año, carpeta_salida, historial, capital_invertido, marca, fecha_referencia
    )
    print(f"Ficha completa generada: {ruta}")
    display(HTML(ruta.read_text(encoding="utf-8")))
    return ruta, datos


_PATRON_TIMESTAMP_FICHA = re.compile(r"^(\d{8})_(\d{6})_")


def extraer_fecha_consulta(ruta_ficha: Path) -> datetime:
    """Extrae la fecha/hora de consulta de datos embebida en el nombre de una ficha ya generada.

    Todas las fichas del proyecto (`crear_ficha_rendimiento`, `crear_ficha_completa_cliente`,
    `crear_ficha_multiperiodo`) escriben su HTML con el prefijo `YYYYMMDD_HHMMSS_` en
    el momento en que se descargan los datos que la alimentan; `exportar_ficha_a_pdf`
    ya reutiliza ese mismo prefijo para nombrar el PDF. Reutilizarlo aquí también
    garantiza que el HTML exportado (`exportar_ficha_html`) muestre exactamente la
    misma fecha/hora de consulta que el PDF de esa misma ficha, sin generarla de
    nuevo con `datetime.now()`.
    """
    coincidencia = _PATRON_TIMESTAMP_FICHA.match(ruta_ficha.name)
    if not coincidencia:
        raise ValueError(f"'{ruta_ficha.name}' no tiene el prefijo de fecha/hora esperado (YYYYMMDD_HHMMSS_).")
    return datetime.strptime(coincidencia.group(1) + coincidencia.group(2), "%Y%m%d%H%M%S")


def _fmt_moneda(valor, decimales: int = 2, signo: bool = False) -> str:
    """Formatea un monto en pesos: separador de miles, decimales fijos y sufijo MXN.

    `NaN`/`None` se muestran como "—" (nunca "NaN" ni vacío). Si `signo` es `True`,
    los valores positivos llevan un "+" explícito (para montos que pueden ser
    ganancia o pérdida); los negativos siempre muestran "-", tenga o no `signo=True`.
    """
    if valor is None or pd.isna(valor):
        return "—"
    prefijo = "+" if signo and valor > 0 else ("-" if valor < 0 else "")
    return f"{prefijo}${abs(valor):,.{decimales}f} MXN"


def _fmt_pct(valor, decimales: int = 2) -> str:
    """Formatea un porcentaje con signo explícito siempre (`+2.35%` / `-1.08%`) y "—" para NaN/None."""
    if valor is None or pd.isna(valor):
        return "—"
    prefijo = "+" if valor >= 0 else "-"
    return f"{prefijo}{abs(valor):,.{decimales}f}%"


def _clase_signo(valor) -> str:
    """Clase CSS ("pos"/"neg") según el signo de `valor`, o "" si es NaN/None (sin resaltar)."""
    if valor is None or pd.isna(valor):
        return ""
    return "pos" if valor >= 0 else "neg"


def armar_resumen_rendimiento(datos: dict) -> pd.DataFrame:
    """Arma la tabla resumen (Indicador/Valor) de una ficha de rendimiento para `exportar_ficha_html`.

    Parte del mismo diccionario que ya arma y muestra `crear_ficha_rendimiento`
    (`_calcular_rendimiento`, devuelto también por `mostrar_ficha_rendimiento`): no
    repite ningún cálculo, solo formatea los mismos números con las reglas
    financieras del HTML exportado (moneda/porcentaje con signo, "—" para datos
    faltantes) en vez de la tarjeta con barra de la ficha de pantalla.
    """
    filas = [
        ("Periodo (cierres)", f"{datos['fecha_inicial']} a {datos['fecha_final']}", ""),
        ("Precio inicial", _fmt_moneda(datos["precio_inicial"]), ""),
        ("Precio final", _fmt_moneda(datos["precio_final"]), ""),
        ("Variación de precio", _fmt_pct(datos["rendimiento_capital"]), _clase_signo(datos["rendimiento_capital"])),
        ("Rendimiento por dividendos", _fmt_pct(datos["rendimiento_dividendos"]), ""),
        ("Rendimiento total", _fmt_pct(datos["rendimiento_total"]), _clase_signo(datos["rendimiento_total"])),
        ("Ganancia total", _fmt_moneda(datos["ganancia_total"], signo=True), _clase_signo(datos["ganancia_total"])),
        ("Dividendos recibidos", _fmt_moneda(datos["total_dividendos"], decimales=4), ""),
        ("Variación de capital", _fmt_moneda(datos["variacion_capital"], signo=True), _clase_signo(datos["variacion_capital"])),
    ]
    if datos["usar_ventana_movil"]:
        filas.append(("Riesgo mensual promedio", _fmt_pct(datos["riesgo"]["volatilidad_mensual_pct"]), ""))
    return pd.DataFrame(filas, columns=["Indicador", "Valor", "_clase"])


def armar_resumen_ficha_completa(datos: dict, capital_invertido: float) -> pd.DataFrame:
    """Arma la tabla resumen (Indicador/Valor) de una ficha completa para cliente, para `exportar_ficha_html`.

    Parte del mismo diccionario que ya arma y muestra `crear_ficha_completa_cliente`
    (`_calcular_ficha_completa`, devuelto también por `mostrar_ficha_completa_cliente`):
    no repite ningún cálculo, solo formatea los mismos números con las reglas
    financieras del HTML exportado.
    """
    filas = [
        ("Precio de compra", _fmt_moneda(datos["precio_compra"]), ""),
        ("Precio actual", _fmt_moneda(datos["precio_actual"]), ""),
        ("Capital de referencia", _fmt_moneda(capital_invertido, decimales=0), ""),
        ("Títulos", f"{datos['titulos']:,}", ""),
        ("Plusvalía", _fmt_moneda(datos["plusvalia"], signo=True), _clase_signo(datos["plusvalia"])),
        ("Dividendo por título", _fmt_moneda(datos["dividendo_por_titulo"], decimales=4), ""),
        ("Distribuciones totales", _fmt_moneda(datos["distribuciones_totales"]), ""),
        ("Retorno total", _fmt_moneda(datos["retorno_total"], signo=True), _clase_signo(datos["retorno_total"])),
        ("Rendimiento total", _fmt_pct(datos["rendimiento_total_pct"]), _clase_signo(datos["rendimiento_total_pct"])),
    ]
    if datos["usar_ventana_movil"]:
        filas.append(("Volatilidad mensual promedio", _fmt_pct(datos["riesgo"]["volatilidad_mensual_pct"]), ""))
        filas.append(("Volatilidad anualizada", _fmt_pct(datos["riesgo"]["volatilidad_anualizada_pct"]), ""))
    return pd.DataFrame(filas, columns=["Indicador", "Valor", "_clase"])


def armar_detalle_pagos_ficha(pagos: pd.DataFrame) -> pd.DataFrame:
    """Arma la tabla de detalle de pagos (Fecha/Monto/Rendimiento) para `exportar_ficha_html`.

    Sirve tanto para `datos["pagos"]` (ficha de rendimiento) como para
    `datos["detalle_pagos"]` (ficha completa cliente): ambos traen las columnas
    `ex_date`/`amount_mxn`/`yield_pct`. No repite el cálculo, solo formatea.
    """
    detalle = pagos.sort_values("ex_date")
    filas = [
        {
            "Fecha": pd.Timestamp(fila.ex_date).strftime("%d/%m/%Y"),
            "Monto por título": _fmt_moneda(fila.amount_mxn, decimales=4),
            "Rendimiento": _fmt_pct(getattr(fila, "yield_pct", None)),
        }
        for fila in detalle.itertuples()
    ]
    if not filas:
        return pd.DataFrame(columns=["Fecha", "Monto por título", "Rendimiento"])
    return pd.DataFrame(filas)


def armar_tabla_html_multiperiodo(tabla: pd.DataFrame) -> str:
    """Arma el fragmento de tabla HTML (indicadores en filas, lapsos en columnas) de la
    ficha multi-periodo, con las reglas financieras del HTML exportado, para `exportar_ficha_html`.

    Reutiliza `tabla` tal cual la devuelve `mostrar_ficha_multiperiodo` (el mismo
    DataFrame ya mostrado en el notebook): no recalcula ningún indicador. A
    diferencia de `_formatear_indicador_multiperiodo` (que usa "N/D" y no fuerza
    signo positivo, para no alterar la ficha de pantalla ya existente), aquí se
    aplican las reglas nuevas de esta exportación: "—" para datos faltantes y
    signo explícito en porcentajes y montos.
    """
    claves_coloreadas = {
        "rendimiento_anual_pct", "rendimiento_mensual_pct", "plusvalia_mxn", "ganancia_total_mxn",
        "pct_plusvalia", "pct_ganancia_total", "drawdown_maximo_pct", "ratio_sharpe",
    }

    def _formatear(clave: str, fila: pd.Series) -> str:
        if clave == "periodo":
            return f"{fila['fecha_inicio']} a {fila['fecha_fin']}"
        valor = fila[clave]
        if pd.isna(valor):
            return "—"
        if clave == "num_pagos":
            return f"{int(valor):,}"
        if clave.endswith("_mxn"):
            return _fmt_moneda(valor, signo=True)
        if clave == "ratio_sharpe":
            return f"{'+' if valor >= 0 else ''}{valor:,.2f}"
        return _fmt_pct(valor)

    lapsos = [str(lapso) for lapso in tabla.index]
    encabezados = "".join(f"<th>{escape(lapso)}</th>" for lapso in lapsos)
    filas_html = []
    for clave, etiqueta in _ETIQUETAS_INDICADORES_MULTIPERIODO:
        celdas = []
        for lapso, fila in tabla.iterrows():
            texto = escape(_formatear(clave, fila))
            if clave in claves_coloreadas and not pd.isna(fila[clave]):
                texto = f'<span class="{_clase_signo(fila[clave])}">{texto}</span>'
            celdas.append(f"<td>{texto}</td>")
        filas_html.append(f'<tr><th scope="row">{escape(etiqueta)}</th>{"".join(celdas)}</tr>')

    return (
        '<div class="tabla-scroll"><table class="ficha-tabla ordenable">'
        f"<thead><tr><th>Indicador</th>{encabezados}</tr></thead>"
        f'<tbody>{"".join(filas_html)}</tbody></table></div>'
    )


def _tabla_html_generica(df: pd.DataFrame, ordenable: bool = True) -> str:
    """Convierte un DataFrame ya formateado (valores como texto de presentación) en un
    fragmento de tabla HTML para `exportar_ficha_html`.

    La primera columna se renderiza como encabezado de fila (`<th>`, alineada a la
    izquierda y fija al hacer scroll horizontal, vía la plantilla de
    `_plantilla_html_ficha`); el resto se alinean a la derecha con cifras
    tabulares. Si el DataFrame trae una columna `_clase` (convención de
    `armar_resumen_rendimiento`/`armar_resumen_ficha_completa`: "pos"/"neg"/""),
    se usa para resaltar en verde/rojo la última columna visible de esa fila; no se
    incluye en los encabezados. `NaN`/`None` se muestran como "—", nunca vacíos.
    """
    tiene_clase = "_clase" in df.columns
    columnas = [c for c in df.columns if c != "_clase"]
    encabezados = "".join(f"<th>{escape(str(c))}</th>" for c in columnas)
    filas_html = []
    for _, fila in df.iterrows():
        clase = str(fila["_clase"]) if tiene_clase and fila["_clase"] else ""
        celdas = []
        for i, columna in enumerate(columnas):
            valor = fila[columna]
            texto = "—" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor)
            texto_html = escape(texto)
            if clase and i == len(columnas) - 1:
                texto_html = f'<span class="{escape(clase)}">{texto_html}</span>'
            if i == 0:
                celdas.append(f'<th scope="row">{texto_html}</th>')
            else:
                celdas.append(f"<td>{texto_html}</td>")
        filas_html.append(f"<tr>{''.join(celdas)}</tr>")
    clases_tabla = "ficha-tabla" + (" ordenable" if ordenable else "")
    return (
        f'<div class="tabla-scroll"><table class="{clases_tabla}">'
        f"<thead><tr>{encabezados}</tr></thead><tbody>{''.join(filas_html)}</tbody></table></div>"
    )


def _plantilla_html_ficha(
    titulo: str,
    ticker: str,
    periodo_texto: str,
    fecha_consulta: datetime,
    cuerpo_html: str,
    nota_metodologica: str,
    fuente: str,
) -> str:
    """Plantilla compartida de las fichas exportadas a HTML (ver `exportar_ficha_html`).

    Centraliza en un solo lugar el CSS/JS de las cuatro fichas exportadas de
    `analysis-one-FIBRA` para que compartan el mismo aspecto y cualquier ajuste
    visual se haga aquí, no en cada celda. Autocontenida (sin CDN ni archivos
    externos): CSS en `<style>` y JS en `<script>`, ambos inline. El ordenamiento
    de columnas es progressive enhancement — la tabla ya viene completa en el
    HTML; el script solo reordena filas ya presentes — así que la ficha sigue
    siendo legible con JavaScript deshabilitado. Incluye reglas `@media print`
    (para guardarla como PDF de forma limpia) y `@media (prefers-color-scheme:
    dark)` (para que se lea igual con el sistema en modo oscuro).
    """
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo)} · {escape(ticker)}</title>
<style>
:root{{color-scheme:light dark}}
*{{box-sizing:border-box}}
body{{margin:0;padding:24px 16px;background:#f4f6f5;color:#1c2a25;font-family:Georgia,'Segoe UI',Arial,sans-serif;font-size:15px;line-height:1.5}}
main{{max-width:1150px;margin:0 auto;background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 6px 18px rgba(0,0,0,.12)}}
header{{background:#2f5d50;color:#fff;padding:20px 24px}}
header h1{{margin:0 0 4px;font-size:1.5rem}}
header .meta{{font-size:.85rem;color:#cfe3da}}
.section{{padding:20px 24px}}
h2{{font-size:.85rem;text-transform:uppercase;letter-spacing:.4px;color:#3a6b5e;border-bottom:1px solid #e3ece8;padding-bottom:6px;margin:20px 0 12px}}
h2:first-child{{margin-top:0}}
.tabla-scroll{{overflow-x:auto;border:1px solid #e3ece8;border-radius:6px;margin-bottom:8px}}
table.ficha-tabla{{border-collapse:collapse;width:100%;min-width:420px;font-size:.9rem}}
table.ficha-tabla th,table.ficha-tabla td{{padding:9px 12px;border-bottom:1px solid #eef2f0;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
table.ficha-tabla thead th{{position:sticky;top:0;background:#f7faf8;color:#55675f;font-size:.75rem;text-transform:uppercase;letter-spacing:.3px;text-align:right}}
table.ficha-tabla thead th:first-child{{text-align:left;position:sticky;left:0;z-index:2;font-variant-numeric:normal}}
table.ficha-tabla tbody th{{text-align:left;position:sticky;left:0;background:#f7faf8;font-weight:600;color:#1c2a25;font-variant-numeric:normal}}
table.ficha-tabla tbody tr:nth-child(even) td,table.ficha-tabla tbody tr:nth-child(even) th{{background:#fafcfb}}
table.ficha-tabla.ordenable thead th{{cursor:pointer}}
.pos{{color:#2f8f6f;font-weight:600}}
.neg{{color:#c0503c;font-weight:600}}
.nota{{font-size:.8rem;color:#55675f;margin-top:8px}}
footer{{padding:16px 24px;background:#f7faf8;border-top:1px solid #e3ece8;font-size:.75rem;color:#55675f;line-height:1.5}}
footer .disclaimer{{margin-top:6px;font-style:italic}}
@media(max-width:650px){{body{{padding:12px 8px}}header{{padding:16px}}.section{{padding:16px}}}}
@media print{{
  body{{background:#fff;padding:0}}
  main{{box-shadow:none;border-radius:0;max-width:none}}
  table.ficha-tabla.ordenable thead th{{cursor:default}}
  .tabla-scroll{{overflow-x:visible;border:none}}
  table.ficha-tabla tr{{page-break-inside:avoid}}
}}
@media (prefers-color-scheme: dark){{
  body{{background:#12201e;color:#e8ede9}}
  main{{background:#1b2926;box-shadow:0 6px 18px rgba(0,0,0,.5)}}
  header{{background:#1e352e}}
  h2{{color:#8ba39c;border-bottom-color:#30423e}}
  table.ficha-tabla th,table.ficha-tabla td{{border-bottom-color:#30423e}}
  table.ficha-tabla thead th,table.ficha-tabla tbody th{{background:#1e352e;color:#e8ede9}}
  table.ficha-tabla tbody tr:nth-child(even) td,table.ficha-tabla tbody tr:nth-child(even) th{{background:#20302c}}
  .tabla-scroll{{border-color:#30423e}}
  .pos{{color:#5fd9b0}}
  .neg{{color:#f2836a}}
  footer{{background:#1e352e;border-top-color:#30423e;color:#9db3ac}}
  .nota{{color:#9db3ac}}
}}
</style></head>
<body><main>
<header>
<h1>{escape(titulo)}</h1>
<div class="meta">Ticker: <strong>{escape(ticker)}</strong> · Periodo: {escape(periodo_texto)} · Consulta de datos: {fecha_consulta:%d/%m/%Y %H:%M}</div>
</header>
<div class="section">
{cuerpo_html}
</div>
<footer>
Fuente de los datos: {escape(fuente)}.
<div class="nota">{escape(nota_metodologica)}</div>
<div class="disclaimer">Esta ficha es de carácter informativo y no constituye una recomendación de inversión.</div>
</footer>
</main>
<script>
(function () {{
  function valorOrdenable(texto) {{
    var limpio = texto.replace(/[^0-9.,+-]/g, "").replace(/,/g, "");
    var numero = parseFloat(limpio);
    return isNaN(numero) ? texto.toLowerCase() : numero;
  }}
  document.querySelectorAll("table.ordenable").forEach(function (tabla) {{
    var thead = tabla.tHead;
    if (!thead) return;
    Array.prototype.forEach.call(thead.rows[0].cells, function (encabezado, indice) {{
      encabezado.addEventListener("click", function () {{
        var tbody = tabla.tBodies[0];
        var filas = Array.prototype.slice.call(tbody.rows);
        var ascendente = encabezado.getAttribute("data-orden") !== "asc";
        filas.sort(function (a, b) {{
          var va = valorOrdenable(a.cells[indice].textContent);
          var vb = valorOrdenable(b.cells[indice].textContent);
          if (va < vb) return ascendente ? -1 : 1;
          if (va > vb) return ascendente ? 1 : -1;
          return 0;
        }});
        Array.prototype.forEach.call(thead.rows[0].cells, function (otro) {{ otro.removeAttribute("data-orden"); }});
        encabezado.setAttribute("data-orden", ascendente ? "asc" : "desc");
        filas.forEach(function (fila) {{ tbody.appendChild(fila); }});
      }});
    }});
  }});
}})();
</script>
</body></html>"""


def exportar_ficha_html(
    contenido,
    titulo: str,
    descripcion: str,
    ticker: str,
    periodo: str,
    fecha_consulta: datetime,
    carpeta_salida: Path,
    periodo_texto: Optional[str] = None,
    nota_metodologica: str = "",
    fuente: str = "AMEFIBRA / Yahoo Finance (yfinance)",
) -> Path:
    """Exporta `contenido` a un archivo HTML autocontenido y responsivo, apto para
    entrega a cliente (celdas 19, 23, 25 y 27 de `analysis-one-FIBRA`).

    `contenido` puede ser un DataFrame, una lista de DataFrames, una lista de
    `(titulo_seccion, DataFrame)`, o HTML ya construido (str) para casos que no
    encajan en una tabla genérica (ver `armar_tabla_html_multiperiodo`). En
    cualquier caso debe construirse a partir del mismo objeto ya calculado que se
    muestra en la celda (p. ej. el `datos` que devuelve `mostrar_ficha_rendimiento`
    vía `armar_resumen_rendimiento`), nunca de una reconstrucción paralela.

    `fecha_consulta` es obligatorio: es la fecha/hora en que se consultaron los
    datos (típicamente `extraer_fecha_consulta(ruta_ficha)`), no el momento de esta
    exportación; se usa tanto en el encabezado como en el nombre de archivo, para
    quedar alineada con `exportar_ficha_a_pdf` de la misma ficha. Si `contenido`
    viene vacío/`None` o falta `fecha_consulta`, se lanza `ValueError` en vez de
    generar un HTML en blanco o con fecha incorrecta.

    El nombre de archivo sigue el mismo esquema que el PDF, solo cambiando la
    extensión: `AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.html` (máximo
    cuatro palabras en `descripcion`); ante un nombre duplicado, se sobrescribe,
    igual que en `exportar_ficha_a_pdf`. Devuelve la ruta absoluta del archivo.
    """
    if isinstance(contenido, pd.DataFrame):
        vacio = contenido.empty
    elif isinstance(contenido, list):
        vacio = len(contenido) == 0
    elif isinstance(contenido, str):
        vacio = not contenido.strip()
    elif contenido is None:
        vacio = True
    else:
        raise TypeError(f"Tipo de `contenido` no soportado: {type(contenido)!r}.")
    if vacio:
        raise ValueError("`contenido` no puede estar vacío: no se genera un HTML en blanco.")
    if fecha_consulta is None:
        raise ValueError("`fecha_consulta` es obligatorio (fecha/hora de la consulta de datos, no la de esta exportación).")

    if isinstance(contenido, str):
        cuerpo_html = contenido
    elif isinstance(contenido, pd.DataFrame):
        cuerpo_html = _tabla_html_generica(contenido)
    else:
        partes = []
        for elemento in contenido:
            if isinstance(elemento, tuple):
                titulo_seccion, df = elemento
                partes.append(f"<h2>{escape(titulo_seccion)}</h2>{_tabla_html_generica(df)}")
            else:
                partes.append(_tabla_html_generica(elemento))
        cuerpo_html = "".join(partes)

    html = _plantilla_html_ficha(
        titulo, ticker, periodo_texto or str(periodo), fecha_consulta, cuerpo_html, nota_metodologica, fuente
    )

    palabras = str(descripcion).strip().lower().split()
    if not palabras:
        raise ValueError("La descripción breve no puede estar vacía.")
    if len(palabras) > 4:
        raise ValueError("La descripción breve debe tener máximo cuatro palabras.")
    descripcion_normalizada = "-".join(palabras)
    ticker_base = _normalizar_ticker(ticker)

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    ruta = carpeta_salida / f"{fecha_consulta:%Y-%m-%d_%H%M}_{ticker_base}_{descripcion_normalizada}_{periodo}.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta


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


def _tabla_html_comparativa(tickers_ok: list[str], resumenes: dict[str, pd.DataFrame]) -> str:
    """Arma el `<thead>`/`<tbody>` de una tabla comparativa (indicadores en filas,
    FIBRAs en columnas) a partir de un resumen Indicador/Valor/`_clase` ya armado
    por ticker (`armar_resumen_rendimiento` o `armar_resumen_ficha_completa`).

    Todas las FIBRAs de un mismo comparativo comparten año/ventana, así que sus
    resúmenes traen las mismas etiquetas en el mismo orden; se toman de cualquiera
    de ellos. `_clase` ("pos"/"neg"/"") resalta la celda con la clase CSS del mismo
    nombre ya definida en la plantilla, en vez de un color inline por celda.
    Compartida por `crear_comparativo_rendimiento` y `crear_comparativo_completo_cliente`
    para que ambas tablas comparativas se vean y se comporten igual.
    """
    indexados = {ticker: resumen.set_index("Indicador") for ticker, resumen in resumenes.items()}
    etiquetas = next(iter(resumenes.values()))["Indicador"]
    encabezados = "".join(f"<th>{escape(t)}</th>" for t in tickers_ok)
    filas = []
    for indicador in etiquetas:
        celdas = []
        for ticker in tickers_ok:
            fila = indexados[ticker].loc[indicador]
            texto = escape(str(fila["Valor"]))
            if fila["_clase"]:
                texto = f'<span class="{fila["_clase"]}">{texto}</span>'
            celdas.append(f"<td>{texto}</td>")
        filas.append(f"<tr><th>{escape(indicador)}</th>{''.join(celdas)}</tr>")
    return f"<thead><tr><th>Indicador</th>{encabezados}</tr></thead><tbody>{''.join(filas)}</tbody>"


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

    resumenes = {ticker: armar_resumen_rendimiento(datos_por_ticker[ticker]) for ticker in tickers_ok}
    tabla_resumen_html = _tabla_html_comparativa(tickers_ok, resumenes)

    filas_pagos = []
    for ticker in tickers_ok:
        detalle = armar_detalle_pagos_ficha(datos_por_ticker[ticker]["pagos"])
        for fecha, monto, rendimiento in detalle.itertuples(index=False, name=None):
            filas_pagos.append(f"<tr><td>{escape(ticker)}</td><td>{escape(fecha)}</td><td>{escape(monto)}</td><td>{escape(rendimiento)}</td></tr>")
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
th,td{{padding:10px 14px;border-bottom:1px solid #30423e;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
th{{color:#8ba39c;font-weight:600}}
tbody th{{text-align:left;color:#e8ede9;background:#1e352e;position:sticky;left:0;z-index:1;font-variant-numeric:normal}}
thead th:first-child{{text-align:left;position:sticky;left:0;background:#1b2926;z-index:2}}
tbody tr:nth-child(even) td{{background:#1e2c29}}
.pos{{color:#5fd9b0;font-weight:600}}
.neg{{color:#f2836a;font-weight:600}}
.notice{{margin-top:28px;font:12px sans-serif;color:#8ba39c}}
@media(max-width:650px){{main{{margin:0;padding:18px}}h1{{font-size:24px}}}}
</style></head><body><main>
<h1>Comparativo de rendimiento de FIBRAs</h1>
<div class="subtitle">{referencia['etiqueta_periodo']} · {len(tickers_ok)} FIBRAs</div>
<div class="tabla-scroll"><table>{tabla_resumen_html}</table></div>
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

    resumenes = {ticker: armar_resumen_ficha_completa(datos_por_ticker[ticker], capital_invertido) for ticker in tickers_ok}
    tabla_resumen_html = _tabla_html_comparativa(tickers_ok, resumenes)

    encabezados_meses_html = "".join(f"<th>{escape(m)}</th>" for m in referencia["etiquetas_meses"])
    filas_mensual_html = "".join(
        f"<tr><th>{escape(t)}</th>" + "".join(f"<td>{_fmt_moneda(valor)}</td>" for valor in datos_por_ticker[t]["pagos_por_mes"].tolist()) + "</tr>"
        for t in tickers_ok
    )

    seccion_riesgo_html = ""
    if referencia["usar_ventana_movil"]:
        filas_riesgo_html = "".join(
            f"<tr><th>{escape(t)}</th>" + "".join(
                f'<td><span class="{_clase_signo(retorno)}">{_fmt_pct(retorno)}</span></td>'
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
        detalle = armar_detalle_pagos_ficha(datos_por_ticker[t]["detalle_pagos"])
        for fecha, monto, rendimiento in detalle.itertuples(index=False, name=None):
            filas_detalle.append(f"<tr><td>{escape(t)}</td><td>{escape(fecha)}</td><td>{escape(monto)}</td><td>{escape(rendimiento)}</td></tr>")
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
th,td{{padding:9px 12px;border-bottom:1px solid #eef2f0;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
th{{color:#55675f;font-size:11px;text-transform:uppercase;letter-spacing:.3px}}
tbody th{{text-align:left;color:#1c2a25;background:#f7faf8;position:sticky;left:0;z-index:1;text-transform:none;font-weight:600;font-variant-numeric:normal}}
thead th:first-child{{text-align:left;position:sticky;left:0;background:#ffffff;z-index:2}}
tbody tr:nth-child(even) td{{background:#f7faf8}}
.pos{{color:#2f8f6f;font-weight:600}}
.neg{{color:#c0503c;font-weight:600}}
.period-note{{font-size:11px;color:#55675f;font-style:italic;margin-top:8px}}
.disclaimer{{font-size:9px;color:#5c6b65;text-align:center;padding:0 22px 12px;line-height:1.4}}
.footer{{background:#22463c;color:#fff;text-align:center;padding:12px;font-size:12px;letter-spacing:2px}}
@media(max-width:650px){{.section{{padding:14px}}.header h1{{font-size:20px}}}}
</style></head>
<body><main>
<div class="header"><h1>Comparativo de FIBRAs</h1><div class="subtitle">{referencia['etiqueta_periodo']} · Capital de referencia: ${capital_invertido:,.0f} · {len(tickers_ok)} FIBRAs</div></div>
<div class="section">
<h2 class="section-title">Resumen del escenario de inversión</h2>
<div class="tabla-scroll"><table>{tabla_resumen_html}</table></div>
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


# --- Escenario de inversión multianual (2/3/5/10 años) ---

# Filas del "Resumen del escenario de inversión" multianual. Réplica del resumen de
# la ficha completa de los últimos 12 meses (`armar_resumen_ficha_completa`, modo
# ventana móvil) con tres filas nuevas insertadas: "Distribución promedio anual"
# antes de "Distribuciones totales", y "Rendimiento promedio anual — CAGR / simple"
# antes de "Rendimiento total (%)". `(clave, etiqueta, formato, colorear_por_signo)`.
_FILAS_RESUMEN_ESCENARIO_MULTIANUAL = [
    ("precio_compra", "Precio inicial", "moneda", False),
    ("precio_actual", "Precio final", "moneda", False),
    ("capital_invertido", "Capital de referencia", "moneda0", False),
    ("titulos", "Títulos adquiridos", "entero", False),
    ("valor_final_posicion", "Valor final de la posición", "moneda", False),
    ("plusvalia", "Plusvalía / minusvalía de capital", "moneda_signo", True),
    ("plusvalia_pct", "Plusvalía / minusvalía de capital (%)", "pct", True),
    ("dividendo_por_titulo", "Distribución por título", "moneda4", False),
    ("distribucion_promedio_anual", "Distribución promedio anual", "moneda", False),
    ("distribuciones_totales", "Distribuciones totales", "moneda", False),
    ("retorno_total", "Ganancia total", "moneda_signo", True),
    ("cagr_pct", "Rendimiento promedio anual — CAGR (%)", "pct_na", True),
    ("rendimiento_anual_simple_pct", "Rendimiento promedio anual — simple (%)", "pct", True),
    ("rendimiento_total_pct", "Rendimiento total (%)", "pct", True),
    ("volatilidad_mensual_pct", "Volatilidad mensual promedio (%)", "pct", False),
    ("volatilidad_anualizada_pct", "Volatilidad anualizada (%)", "pct", False),
]

_NOTAS_METODOLOGICAS_ESCENARIO_MULTIANUAL = [
    "La ventana es móvil hacia atrás desde la última fecha con precio disponible común "
    "a las FIBRAs analizadas (no años calendario): para N años, [fecha final − N×12 meses, fecha final].",
    "Precio inicial (P0): primer cierre disponible en la fecha de inicio de la ventana o posterior; "
    "mismo criterio para todas las FIBRAs.",
    "Distribuciones totales: suma del efectivo recibido (amount_mxn) de todos los pagos con ex_date dentro "
    "de la ventana, sin importar su tratamiento fiscal. Los yield_pct individuales de cada pago no se suman: "
    "todo rendimiento parte de montos en MXN sobre P0.",
    "El escenario asume que las distribuciones se reciben en efectivo y no se reinvierten "
    "(misma convención que la ficha de los últimos 12 meses).",
    "CAGR = ((1 + rendimiento_total/100)^(1/N) − 1) × 100: tasa compuesta anual equivalente, comparable "
    "contra CETES o inflación. Rendimiento promedio anual simple = rendimiento_total / N; la brecha entre "
    'ambos refleja el efecto de la capitalización. Si 1 + rendimiento_total/100 ≤ 0, el CAGR se muestra como "n/a".',
    "Información histórica e informativa. No constituye una recomendación de inversión; "
    "los rendimientos pasados no garantizan rendimientos futuros.",
]


def armar_resumen_escenario_multianual(datos: dict) -> pd.DataFrame:
    """Tabla resumen (Indicador/Valor/`_clase`) del escenario multianual de un ticker.

    Parte del diccionario de `procesamiento.calcular_escenario_multianual` (no
    repite ningún cálculo) y formatea los números con las mismas reglas financieras
    del resto de las fichas exportadas (moneda/porcentaje con signo, "—" para datos
    faltantes, "n/a" para el CAGR cuando la pérdida total es ≥ 100%). El formato es
    el mismo de `armar_resumen_ficha_completa` para que `_tabla_html_comparativa`
    arme una tabla idéntica en estilo a la de la celda de los últimos 12 meses.
    """
    filas = []
    for clave, etiqueta, formato, colorear in _FILAS_RESUMEN_ESCENARIO_MULTIANUAL:
        valor = datos[clave]
        if formato == "moneda":
            texto = _fmt_moneda(valor)
        elif formato == "moneda0":
            texto = _fmt_moneda(valor, decimales=0)
        elif formato == "moneda4":
            texto = _fmt_moneda(valor, decimales=4)
        elif formato == "moneda_signo":
            texto = _fmt_moneda(valor, signo=True)
        elif formato == "entero":
            texto = f"{int(valor):,}"
        elif formato == "pct_na":
            texto = "n/a" if (valor is None or pd.isna(valor)) else _fmt_pct(valor)
        else:  # "pct"
            texto = _fmt_pct(valor)
        filas.append((etiqueta, texto, _clase_signo(valor) if colorear else ""))
    return pd.DataFrame(filas, columns=["Indicador", "Valor", "_clase"])


def _preparar_escenario_multianual(tickers_seleccionados: pd.DataFrame, historiales: dict) -> dict:
    """Descarga una sola vez el historial de precios completo de cada FIBRA seleccionada
    con historial de dividendos y fija la "fecha final" común al universo analizado.

    Devuelve un contexto reutilizable por cualquier horizonte: al cambiar de
    horizonte (2/3/5/10 años) no se vuelve a descargar nada, solo se recorta la
    ventana. `fecha_final` es la última fecha de precio disponible en TODAS las
    FIBRAs (mínimo de las últimas fechas de cada una), para que la ventana sea
    común y reproducible.
    """
    precios_por_ticker: dict[str, pd.Series] = {}
    pagos_por_ticker: dict[str, pd.DataFrame] = {}
    primer_precio: dict[str, pd.Timestamp] = {}
    ultima_fecha: dict[str, pd.Timestamp] = {}
    for ticker in tickers_seleccionados["ticker"]:
        historial = historiales.get(ticker)
        if historial is None or historial.empty:
            print(f"Aviso: se omite {ticker} del escenario multianual: sin historial de dividendos disponible.")
            continue
        ticker_base = _normalizar_ticker(ticker)
        try:
            serie = _descargar_historico_completo(f"{ticker_base}.MX").sort_index()
        except Exception as error:  # noqa: BLE001 - tolerancia a fallos por ticker, a propósito
            print(f"Aviso: no se pudo descargar el historial de precios de {ticker}: {error}")
            continue
        if serie.empty:
            continue
        pagos = historial.copy()
        pagos["ex_date"] = pd.to_datetime(pagos["ex_date"], errors="coerce")
        pagos["amount_mxn"] = pd.to_numeric(pagos["amount_mxn"], errors="coerce")
        pagos = pagos[pagos["ticker"].astype(str).str.upper() == ticker_base]
        precios_por_ticker[ticker_base] = serie
        pagos_por_ticker[ticker_base] = pagos
        primer_precio[ticker_base] = serie.index.min()
        ultima_fecha[ticker_base] = serie.index.max()
    if not precios_por_ticker:
        raise ValueError(
            "No hay FIBRAs con historial de precios y de distribuciones para armar el escenario multianual."
        )
    fecha_final = pd.Timestamp(min(ultima_fecha.values()))
    return {
        "precios_por_ticker": precios_por_ticker,
        "pagos_por_ticker": pagos_por_ticker,
        "primer_precio": primer_precio,
        "fecha_final": fecha_final,
        "tickers": list(precios_por_ticker),
    }


def _elegibilidad_escenario_multianual(
    contexto: dict, años: int
) -> tuple[list[str], list[tuple[str, pd.Timestamp]], pd.Timestamp]:
    """Separa las FIBRAs del contexto en elegibles / excluidas para el horizonte de `años` años.

    Una FIBRA es elegible solo si su primer precio disponible es anterior o igual al
    inicio de la ventana de N años (historial de precio completo cubriendo todo el
    horizonte). Devuelve `(elegibles, excluidas, fecha_inicio)`, con `excluidas`
    como lista de `(ticker, primer_precio_disponible)` para la nota informativa.
    """
    fecha_inicio, _ = calcular_ventana_multianual(contexto["fecha_final"], años)
    elegibles: list[str] = []
    excluidas: list[tuple[str, pd.Timestamp]] = []
    for ticker_base in contexto["tickers"]:
        if contexto["primer_precio"][ticker_base] <= fecha_inicio:
            elegibles.append(ticker_base)
        else:
            excluidas.append((ticker_base, contexto["primer_precio"][ticker_base]))
    return elegibles, excluidas, fecha_inicio


def crear_escenario_multianual(
    contexto: dict,
    años: int,
    tickers_marcados,
    carpeta_salida: Path,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
) -> tuple[Optional[Path], list[str]]:
    """Calcula y exporta el "Resumen del escenario de inversión" multianual del horizonte de `años` años.

    Toma el contexto de `_preparar_escenario_multianual`, filtra los tickers
    marcados a los elegibles para el horizonte, y arma una sola tabla comparativa
    (FIBRAs en columnas) con el mismo estilo que la ficha completa de los últimos
    12 meses. Devuelve `(ruta_html | None, notas)`: `notas` incluye las FIBRAs
    excluidas por historial insuficiente, la advertencia del CAGR "n/a" si aplica,
    y el caso borde de que ninguna FIBRA elegible quede seleccionada.
    """
    años = int(años)
    fecha_final = contexto["fecha_final"]
    elegibles, excluidas, fecha_inicio = _elegibilidad_escenario_multianual(contexto, años)
    marcados = [_normalizar_ticker(t) for t in tickers_marcados]
    seleccion = [t for t in contexto["tickers"] if t in elegibles and t in marcados]

    notas: list[str] = []
    if excluidas:
        detalle = ", ".join(f"{t} (inicio de cotización: {fecha:%Y-%m})" for t, fecha in excluidas)
        notas.append(f"Excluidas por historial insuficiente para {años} años: {detalle}.")

    if not elegibles:
        notas.append(
            f"Ninguna de las FIBRAs analizadas tiene historial de precios suficiente para un horizonte de {años} años."
        )
        return None, notas
    if not seleccion:
        notas.append(
            f"No hay ninguna FIBRA elegible marcada para el horizonte de {años} años "
            f"(elegibles: {', '.join(elegibles)})."
        )
        return None, notas

    datos_por_ticker: dict[str, dict] = {}
    for ticker_base in seleccion:
        try:
            datos_por_ticker[ticker_base] = calcular_escenario_multianual(
                contexto["precios_por_ticker"][ticker_base],
                contexto["pagos_por_ticker"][ticker_base],
                fecha_final,
                años,
                capital_invertido,
            )
        except Exception as error:  # noqa: BLE001 - tolerancia a fallos por ticker, a propósito
            notas.append(f"No se pudo calcular el escenario de {ticker_base} para {años} años: {error}")
    if not datos_por_ticker:
        return None, notas

    tickers_ok = list(datos_por_ticker)
    resumenes = {t: armar_resumen_escenario_multianual(datos_por_ticker[t]) for t in tickers_ok}
    tabla_resumen_html = _tabla_html_comparativa(tickers_ok, resumenes)

    if any(pd.isna(datos_por_ticker[t]["cagr_pct"]) for t in tickers_ok):
        notas.append(
            'El CAGR aparece como "n/a" en las FIBRAs cuya pérdida total del periodo es ≥ 100% '
            "(1 + rendimiento total ≤ 0): no existe una tasa compuesta anual real en ese caso."
        )

    ventana_txt = f"{fecha_inicio:%Y-%m-%d} a {fecha_final:%Y-%m-%d}"
    encabezado = f"Resumen del escenario de inversión — Últimos {años} años ({ventana_txt})"
    nota_exclusion_html = f'<div class="period-note">{escape(notas[0])}</div>' if excluidas else ""
    pie_metodologico_html = "".join(
        f"<li>{escape(linea)}</li>" for linea in _NOTAS_METODOLOGICAS_ESCENARIO_MULTIANUAL
    )

    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Escenario de inversión {años} años {fecha_final:%Y%m%d}</title>
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
th,td{{padding:9px 12px;border-bottom:1px solid #eef2f0;text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}}
th{{color:#55675f;font-size:11px;text-transform:uppercase;letter-spacing:.3px}}
tbody th{{text-align:left;color:#1c2a25;background:#f7faf8;position:sticky;left:0;z-index:1;text-transform:none;font-weight:600;font-variant-numeric:normal}}
thead th:first-child{{text-align:left;position:sticky;left:0;background:#ffffff;z-index:2}}
tbody tr:nth-child(even) td{{background:#f7faf8}}
.pos{{color:#2f8f6f;font-weight:600}}
.neg{{color:#c0503c;font-weight:600}}
.period-note{{font-size:11px;color:#55675f;font-style:italic;margin-top:8px}}
.metodologia{{font-size:11px;color:#55675f;margin:12px 0 0;padding-left:18px;line-height:1.5}}
.disclaimer{{font-size:9px;color:#5c6b65;text-align:center;padding:0 22px 12px;line-height:1.4}}
.footer{{background:#22463c;color:#fff;text-align:center;padding:12px;font-size:12px;letter-spacing:2px}}
@media(max-width:650px){{.section{{padding:14px}}.header h1{{font-size:20px}}}}
</style></head>
<body><main>
<div class="header"><h1>Escenario de inversión multianual</h1><div class="subtitle">{escape(encabezado)} · Capital de referencia: ${capital_invertido:,.0f} · {len(tickers_ok)} FIBRAs</div></div>
<div class="section">
<h2 class="section-title">Resumen del escenario de inversión</h2>
<div class="tabla-scroll"><table>{tabla_resumen_html}</table></div>
{nota_exclusion_html}
<h2 class="section-title">Notas metodológicas</h2>
<ul class="metodologia">{pie_metodologico_html}</ul>
</div>
<div class="disclaimer">Ficha informativa basada en datos históricos.<br>No constituye recomendaciones de inversión ni ofertas de compra o venta de activos financieros.<br>Rendimientos pasados no garantizan rendimientos futuros.</div>
<div class="footer">{escape(marca)}</div>
</main></body></html>"""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    momento = datetime.now()
    ruta = carpeta_salida / f"{momento:%Y%m%d_%H%M%S}_escenario_{años}a_{fecha_final:%Y%m%d}.html"
    ruta.write_text(html, encoding="utf-8")
    return ruta, notas


def mostrar_escenario_multianual(
    tickers_seleccionados: pd.DataFrame,
    historiales: dict,
    carpeta_salida: Path,
    carpeta_export: Path,
    capital_invertido: float = 10000.0,
    marca: str = "ZAMUDIO INVESTORS",
    horizonte_inicial: int = 5,
    horizontes_simulados: Optional[list[int]] = None,
):
    """Escenario de inversión multianual interactivo (horizontes de 2, 3, 5 y 10 años).

    Replica el "Resumen del escenario de inversión" de la ficha completa de los
    últimos 12 meses, pero sobre ventanas móviles más largas contadas hacia atrás
    desde la última fecha con datos común a las FIBRAs analizadas. Muestra un
    selector de horizonte y una lista de casillas de FIBRAs: al cambiar el
    horizonte, la tabla se recalcula al vuelo y la lista de FIBRAs elegibles se
    actualiza (una FIBRA sin historial suficiente para el horizonte se deshabilita
    y se deselecciona, y queda documentada en una nota). En cada render se exporta
    el HTML a `carpeta_export`.

    `horizontes_simulados` (para pruebas automatizadas, sin widgets) renderiza esos
    horizontes de una vez con todas las FIBRAs elegibles y devuelve
    `{años: ruta_html}`; en uso interactivo devuelve el `Dropdown` de horizonte.
    """
    contexto = _preparar_escenario_multianual(tickers_seleccionados, historiales)
    print(
        "Fecha final común al universo analizado (última fecha con precio en todas las FIBRAs): "
        f"{contexto['fecha_final']:%Y-%m-%d}"
    )
    seleccion_inicial = list(contexto["tickers"])

    if horizontes_simulados is not None:
        rutas: dict[int, Path] = {}
        for años in horizontes_simulados:
            print(f"\n=== Horizonte de {años} años ===")
            ruta, notas = crear_escenario_multianual(
                contexto, años, seleccion_inicial, carpeta_salida, capital_invertido, marca
            )
            for nota in notas:
                print(f"  - {nota}")
            if ruta is not None:
                display(HTML(ruta.read_text(encoding="utf-8")))
                ruta_export = exportar_comparativo_a_html(ruta, "escenario multianual", f"{años}a", carpeta_export)
                print(f"  HTML exportado: {ruta_export}")
                rutas[años] = ruta
        return rutas

    selector_horizonte = widgets.Dropdown(
        options=[(f"{n} años", n) for n in HORIZONTES_ESCENARIO_MULTIANUAL],
        value=horizonte_inicial,
        description="Horizonte:",
    )
    casillas = {
        t: widgets.Checkbox(value=(t in seleccion_inicial), description=t, indent=False)
        for t in contexto["tickers"]
    }
    salida = widgets.Output()

    def _render(*_):
        años = selector_horizonte.value
        elegibles, _, _ = _elegibilidad_escenario_multianual(contexto, años)
        for t, casilla in casillas.items():
            casilla.unobserve(_render, "value")
            if t not in elegibles:
                casilla.value = False
                casilla.disabled = True
            else:
                casilla.disabled = False
            casilla.observe(_render, "value")
        marcados = [t for t, casilla in casillas.items() if casilla.value]
        with salida:
            salida.clear_output(wait=True)
            ruta, notas = crear_escenario_multianual(
                contexto, años, marcados, carpeta_salida, capital_invertido, marca
            )
            if ruta is not None:
                display(HTML(ruta.read_text(encoding="utf-8")))
                ruta_export = exportar_comparativo_a_html(ruta, "escenario multianual", f"{años}a", carpeta_export)
                print(f"HTML exportado: {ruta_export}")
            for nota in notas:
                print(nota)

    selector_horizonte.observe(_render, "value")
    for casilla in casillas.values():
        casilla.observe(_render, "value")
    display(
        widgets.VBox(
            [
                selector_horizonte,
                widgets.HTML("<b>FIBRAs a incluir</b> (solo se pueden marcar las elegibles para el horizonte):"),
                *casillas.values(),
            ]
        )
    )
    display(salida)
    _render()
    return selector_horizonte
