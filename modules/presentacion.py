"""Funciones de presentación y exportación de resultados de FIBRAs (CSV, Excel, fichas HTML)."""

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Optional

import pandas as pd

from .extraccion import _descargar_cierres_anuales, obtener_distribuciones
from .procesamiento import _normalizar_ticker, normalizar_para_analisis


def exportar_csv_analitico(df: pd.DataFrame, carpeta_salida: Path) -> Path:
    """Normaliza `df` para análisis y lo exporta a un CSV "profesional" dentro de `carpeta_salida`."""
    momento = datetime.now()
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    nombre = f"{momento:%Y%m%d_%H%M%S}_indice_fibras_amefibra.csv"
    ruta = carpeta_salida / nombre
    normalizar_para_analisis(df, momento).to_csv(ruta, index=False, encoding="utf-8")
    return ruta


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
    color_capital = "#c4513d" if variacion_capital < 0 else "#2f7d68"
    color_total = "#c4513d" if rendimiento_total < 0 else "#1e5b52"
    tabla_pagos = pagos[["ex_date", "amount_mxn", "yield_pct"]].sort_values("ex_date").copy()
    tabla_pagos["ex_date"] = tabla_pagos["ex_date"].dt.strftime("%Y-%m-%d")
    tabla_pagos["amount_mxn"] = tabla_pagos["amount_mxn"].map(lambda valor: f"${valor:,.4f}")
    tabla_pagos["yield_pct"] = tabla_pagos["yield_pct"].map(lambda valor: f"{valor:,.2f}%")
    tabla_html = tabla_pagos.to_html(index=False, classes="payments", border=0, justify="left")
    html = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Ficha {escape(ticker_base)} {año}</title>
<style>
body{{margin:0;background:#f3f0ea;color:#183b3a;font-family:Georgia,serif}}main{{max-width:900px;margin:32px auto;padding:32px;background:#fffdf8;box-shadow:0 8px 24px #183b3a18}}h1{{margin:0 0 6px;font-size:36px}}.subtitle{{color:#66817a;margin-bottom:28px}}.metrics{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.metric{{border-top:3px solid #d8a24a;padding:12px 0}}.label{{font:12px sans-serif;text-transform:uppercase;letter-spacing:1px;color:#66817a}}.value{{font-size:24px;margin-top:6px}}.total{{margin:28px 0;padding:18px;background:#e6f0e9;border-left:5px solid {color_total}}}.total strong{{font-size:34px;color:{color_total}}}.bar{{height:28px;display:flex;margin:12px 0 8px;background:#eadfd1}}.bar div{{height:100%}}.legend{{font:14px sans-serif;color:#49635e}}table{{width:100%;border-collapse:collapse;font:14px sans-serif;margin-top:20px}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}th{{color:#66817a}}.notice{{margin-top:28px;font:12px sans-serif;color:#66817a}}@media(max-width:650px){{main{{margin:0;padding:22px}}h1{{font-size:29px}}.metrics{{grid-template-columns:1fr 1fr}}}}
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
