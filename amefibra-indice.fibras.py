#!/usr/bin/env python3
"""
Scraper del "Índice FIBRAS" de AMEFIBRA
https://amefibra.com/el-mercado/indice-fibras/

¿Por qué no basta con `requests.get(...)`?
-------------------------------------------
La tabla de indicadores NO viene en el HTML de la página. Está incrustada en un
<iframe> que apunta a amefibra.edimex.com.mx/Emisora/Reportes, y esa página arma
la tabla vía JavaScript y actualiza los precios en tiempo real por WebSocket
(dato con ~20 minutos de retraso, según el propio sitio). Una petición HTTP
simple solo trae la plantilla vacía, sin datos.

Por eso este script usa Playwright para abrir la página en un navegador real
(headless), esperar a que el WebSocket llene la tabla, y luego extraer esa
tabla ya renderizada con pandas.

Instalación
-----------
    pip install playwright pandas openpyxl
    playwright install chromium

Uso
---
    python amefibra_indice_fibras.py
    python amefibra_indice_fibras.py --csv indice_fibras.csv --xlsx indice_fibras.xlsx
    python amefibra_indice_fibras.py --show-browser   # para depurar visualmente

Notas
-----
- El sitio aclara que la información es solo para consulta/análisis, no como base
  para decisiones de inversión. Este script respeta eso: solo lee lo que ya se
  publica públicamente en la página, sin usar credenciales ni endpoints privados.
- Si AMEFIBRA/Economatica cambian el HTML o el proveedor de datos, el script
  puede requerir ajustes (ver la función `_extraer_html_tabla`).
"""

import argparse
import io
import re
import sys
from datetime import datetime
from typing import Optional

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL_PAGINA = "https://amefibra.com/el-mercado/indice-fibras/"

# El iframe de la tabla es .../Emisora/Reportes (a secas).
# Hay otros dos iframes hermanos que NO queremos: .../Reportes/Grafica y .../Reportes/Marquesina
PATRON_IFRAME_TABLA = re.compile(r"edimex\.com\.mx/Emisora/Reportes/?(\?.*)?$")


def _limpiar_encabezado(texto: str) -> str:
    """Quita flechas de ordenamiento y espacios sobrantes de los encabezados de columna."""
    texto = re.sub(r"[↑↓]", "", str(texto))
    return re.sub(r"\s+", " ", texto).strip()


def _localizar_frame_tabla(page, intentos=10, espera_ms=1000):
    """Busca, con reintentos, el iframe que contiene la tabla de indicadores."""
    for _ in range(intentos):
        for f in page.frames:
            if PATRON_IFRAME_TABLA.search(f.url or ""):
                return f
        page.wait_for_timeout(espera_ms)
    return None


def _extraer_html_tabla(frame) -> Optional[str]:
    """Dentro del iframe, ubica la tabla con más filas (la de indicadores) y regresa su HTML."""
    return frame.evaluate(
        """() => {
            const tablas = Array.from(document.querySelectorAll('table'));
            let mejor = null, filasMax = -1;
            for (const t of tablas) {
                const n = t.querySelectorAll('tbody tr').length;
                if (n > filasMax) { filasMax = n; mejor = t; }
            }
            return mejor ? mejor.outerHTML : null;
        }"""
    )


def obtener_tabla_fibras(headless: bool = True, timeout_datos_ms: int = 30000) -> pd.DataFrame:
    """Abre la página del Índice FIBRAS y devuelve la tabla de indicadores como DataFrame."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(locale="es-MX")
        page.goto(URL_PAGINA, wait_until="domcontentloaded")

        frame = _localizar_frame_tabla(page)
        if frame is None:
            browser.close()
            raise RuntimeError(
                "No se encontró el iframe con la tabla de FIBRAs. "
                "Es posible que AMEFIBRA haya cambiado la estructura de la página."
            )

        # Las celdas empiezan vacías/"0" hasta que el WebSocket entrega los precios.
        # Esperamos a que la 2a columna (Cotización) de la primera fila tenga contenido real.
        try:
            frame.wait_for_function(
                """() => {
                    const filas = document.querySelectorAll('table tbody tr');
                    if (filas.length === 0) return false;
                    const celda = filas[0].querySelector('td:nth-child(2)');
                    const txt = celda ? celda.textContent.trim() : '';
                    return txt.length > 0 && txt !== '0' && txt !== '0.00';
                }""",
                timeout=timeout_datos_ms,
            )
        except PWTimeout:
            print(
                "Aviso: tiempo de espera agotado esperando datos en vivo; "
                "se continuará con lo que se haya podido cargar.",
                file=sys.stderr,
            )

        html_tabla = _extraer_html_tabla(frame)
        browser.close()

    if not html_tabla:
        raise RuntimeError("No se pudo extraer la tabla de indicadores del iframe.")

    df = pd.read_html(io.StringIO(html_tabla))[0]
    df.columns = [_limpiar_encabezado(c) for c in df.columns]
    # A veces pandas arrastra una columna vacía (el ícono de tendencia ↗/→/↘, que no es texto real)
    df = df.dropna(axis=1, how="all")
    return df


def main():
    parser = argparse.ArgumentParser(description="Descarga el Índice FIBRAS de AMEFIBRA (amefibra.com).")
    parser.add_argument("--csv", metavar="ARCHIVO.csv", help="Ruta donde guardar un CSV (opcional)")
    parser.add_argument("--xlsx", metavar="ARCHIVO.xlsx", help="Ruta donde guardar un Excel (opcional)")
    parser.add_argument(
        "--show-browser",
        dest="headless",
        action="store_false",
        default=True,
        help="Muestra la ventana del navegador en vez de correr en modo headless (útil para depurar).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30000,
        help="Milisegundos a esperar a que lleguen los datos en vivo (default: 30000).",
    )
    args = parser.parse_args()

    print(f"Consultando {URL_PAGINA} ...")
    df = obtener_tabla_fibras(headless=args.headless, timeout_datos_ms=args.timeout)

    print(
        f"\nÍndice FIBRAS — {datetime.now():%Y-%m-%d %H:%M} "
        "(dato con ~20 min de retraso, fuente: Economatica México)\n"
    )
    print(df.to_string(index=False))

    if args.csv:
        df.to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"\nGuardado CSV en: {args.csv}")
    if args.xlsx:
        df.to_excel(args.xlsx, index=False)
        print(f"Guardado Excel en: {args.xlsx}")


if __name__ == "__main__":
    main()
    