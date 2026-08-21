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

    Cada corrida, además de lo anterior, guarda automáticamente un CSV "analítico"
    en output/AAAAMMDD_HHMMSS_indice_fibras_amefibra.csv (ver `exportar_csv_analitico`):
    encabezados en snake_case, porcentajes como float y columna de timestamp de
    extracción, listo para cargarse en pandas/R/BI sin limpieza adicional.

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
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

URL_PAGINA = "https://amefibra.com/el-mercado/indice-fibras/"

# El iframe de la tabla es .../Emisora/Reportes (a secas).
# Hay otros dos iframes hermanos que NO queremos: .../Reportes/Grafica y .../Reportes/Marquesina
PATRON_IFRAME_TABLA = re.compile(r"edimex\.com\.mx/Emisora/Reportes/?(\?.*)?$")

# Carpeta donde se guarda automáticamente el export "profesional" (analítico) en cada corrida.
# Se mantiene fuera de control de versiones (ver .gitignore): son datos regenerables, no código.
CARPETA_SALIDA = Path(__file__).resolve().parent / "output"

# Fuente de los datos, para dejar trazabilidad en el propio archivo exportado.
FUENTE_DATOS = "AMEFIBRA / Economatica México"


def _limpiar_encabezado(texto: str) -> str:
    """Quita flechas de ordenamiento y espacios sobrantes de los encabezados de columna."""
    texto = re.sub(r"[↑↓]", "", str(texto))
    return re.sub(r"\s+", " ", texto).strip()


def _a_snake_case(texto: str) -> str:
    """Convierte un encabezado de columna a snake_case ASCII (apto para CSV/análisis).

    Ejemplos: "Cotización" -> "cotizacion", "Máx. 52 s." -> "max_52_s",
    "Var. %" -> "var_pct" (el '%' se convierte a la palabra "pct" ANTES de quitar
    acentos/puntuación, para que no colisione con la columna "Var.", que da "var").
    """
    texto = texto.replace("%", "pct")
    # NFKD separa cada letra acentuada en (letra base + acento); al codificar a
    # ASCII ignorando lo no representable, el acento se descarta y queda la letra base.
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "_", sin_acentos).strip("_").lower()


def _convertir_columnas_porcentaje(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte a numérico (float) cualquier columna cuyos valores vengan como texto "12.34%".

    pandas.read_html no puede inferir que una celda como "0.35%" es un número: la deja
    como texto. Para análisis de datos, un porcentaje debe ser un `float` (ej. 0.35),
    nunca un string con el símbolo '%', de lo contrario no se puede operar sobre él
    (sumar, promediar, graficar, etc.) sin volver a limpiarlo cada vez.
    """
    for columna in df.columns:
        serie = df[columna]
        # pandas >= 2.x puede tipar el texto como "object" o como el dtype "string"
        # (StringDtype, con o sin backend pyarrow) según la versión; is_string_dtype
        # cubre ambos casos, a diferencia de comparar `serie.dtype == object` a secas.
        if not pd.api.types.is_string_dtype(serie):
            continue
        valores = serie.astype(str).str.strip()
        # Solo se toca la columna si TODOS sus valores traen '%'; así no se arriesga a
        # convertir por error una columna de texto que casualmente contenga ese símbolo.
        if valores.str.endswith("%").all():
            df[columna] = pd.to_numeric(valores.str.rstrip("%"), errors="coerce")
    return df


def normalizar_para_analisis(df: pd.DataFrame, momento_extraccion: Optional[datetime] = None) -> pd.DataFrame:
    """Prepara el DataFrame crudo para un export "listo para análisis" (CSV/BI/notebooks).

    Aplica buenas prácticas comunes en ciencia de datos:
      1. Encabezados en snake_case y sin acentos (portables entre SO, SQL, pandas, R, etc.,
         y sin ambigüedad de encoding al leerlos en otras herramientas).
      2. Columnas de porcentaje convertidas de texto ("0.35%") a numérico (0.35).
      3. Columna `fecha_hora_extraccion` en formato ISO 8601: el dato es "en vivo" (con
         ~20 min de retraso, según AMEFIBRA), así que sin este timestamp no hay forma de
         saber a qué momento corresponde una fila una vez exportada.
      4. Columna `fuente_datos` para dejar la procedencia documentada dentro del propio
         archivo, sin depender de que el nombre de archivo o el README viajen con él.

    No modifica el DataFrame recibido; retorna una copia nueva.
    """
    momento_extraccion = momento_extraccion or datetime.now()

    df_normalizado = df.copy()
    df_normalizado.columns = [_a_snake_case(str(c)) for c in df_normalizado.columns]
    df_normalizado = _convertir_columnas_porcentaje(df_normalizado)

    df_normalizado.insert(0, "fecha_hora_extraccion", momento_extraccion.isoformat(timespec="seconds"))
    df_normalizado.insert(1, "fuente_datos", FUENTE_DATOS)

    return df_normalizado


def _generar_nombre_archivo(descripcion: str, extension: str, momento: Optional[datetime] = None) -> str:
    """Arma un nombre de archivo `AAAAMMDD_HHMMSS_descripcion.ext`.

    Prefijar con fecha y hora (formato ordenable lexicográficamente) permite que, al
    listar la carpeta `output/`, los archivos queden ordenados cronológicamente sin
    necesidad de mirar la metadata del sistema de archivos; útil porque este script se
    puede correr varias veces al día y cada corrida es una "foto" distinta del índice.
    """
    momento = momento or datetime.now()
    return f"{momento:%Y%m%d_%H%M%S}_{descripcion}.{extension}"


def exportar_csv_analitico(
    df: pd.DataFrame,
    carpeta_salida: Path = CARPETA_SALIDA,
    descripcion: str = "indice_fibras_amefibra",
) -> Path:
    """Normaliza `df` para análisis y lo exporta a un CSV "profesional" dentro de `carpeta_salida`.

    Convenciones aplicadas (estándar en pipelines de datos):
      - Encoding UTF-8 sin BOM: es el estándar de facto para intercambio de datos entre
        pandas, R, bases de datos y herramientas de BI (a diferencia de "utf-8-sig", que
        se usa solo cuando el archivo se va a abrir a mano en Excel de Windows).
      - Separador decimal '.' (el default de pandas), consistente sin importar la
        configuración regional de quien genera o consume el archivo.
      - `index=False`: el índice de pandas es un artefacto interno, no un dato del dominio.
      - Nombre de archivo con fecha/hora + descripción (ver `_generar_nombre_archivo`).

    Retorna la ruta completa del archivo generado.
    """
    momento_extraccion = datetime.now()
    df_analitico = normalizar_para_analisis(df, momento_extraccion=momento_extraccion)

    carpeta_salida.mkdir(parents=True, exist_ok=True)
    nombre_archivo = _generar_nombre_archivo(descripcion, "csv", momento=momento_extraccion)
    ruta_archivo = carpeta_salida / nombre_archivo

    df_analitico.to_csv(ruta_archivo, index=False, encoding="utf-8")
    return ruta_archivo


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

    # Export "profesional" automático: cada corrida queda archivada en output/ con
    # encabezados normalizados, tipos numéricos correctos y timestamp de extracción,
    # lista para consumirse desde pandas/R/BI sin limpieza adicional.
    ruta_csv_analitico = exportar_csv_analitico(df)
    print(f"\nGuardado CSV analítico en: {ruta_csv_analitico}")

    if args.csv:
        df.to_csv(args.csv, index=False, encoding="utf-8-sig")
        print(f"Guardado CSV en: {args.csv}")
    if args.xlsx:
        df.to_excel(args.xlsx, index=False)
        print(f"Guardado Excel en: {args.xlsx}")


if __name__ == "__main__":
    main()
    