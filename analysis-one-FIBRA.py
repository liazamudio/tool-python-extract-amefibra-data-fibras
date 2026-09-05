# ---
# Generado automáticamente a partir de `analysis-one-FIBRA.ipynb`.
# Formato de celdas "percent" (# %%), compatible con VS Code / Jupytext:
# cada bloque se puede correr de forma independiente como celda en el
# Interactive Window de VS Code, igual que en el notebook original.
# No editar a mano: los cambios deben hacerse en el notebook y volver a exportar
# (`python -m jupytext --to py:percent analysis-one-FIBRA.ipynb`).
# ---

# %% [markdown]
# # Índice FIBRAS de AMEFIBRA
#
# Notebook para extraer la tabla pública del Índice FIBRAS. La página carga los datos dentro de un `iframe` mediante JavaScript y WebSocket, por lo que se utiliza Playwright con Chromium.
#
# > La información se ofrece únicamente para consulta y análisis. AMEFIBRA indica que los datos tienen aproximadamente 20 minutos de retraso y no deben usarse como base única para decisiones de inversión.

# %%
# %load_ext autoreload
# %autoreload 2

import sys
from pathlib import Path

import pandas as pd

try:
    # VS Code inyecta esta variable con la ruta absoluta del propio notebook,
    # así que la raíz del proyecto queda anclada a dónde vive el archivo .ipynb,
    # sin importar cuál sea el directorio de trabajo con el que arrancó el kernel
    # (que puede no ser la raíz del proyecto, según la configuración del editor).
    RAIZ_PROYECTO = Path(__vsc_ipynb_file__).resolve().parent
except NameError:
    RAIZ_PROYECTO = Path.cwd()
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from modules.presentacion import (
    aplicar_tema_oscuro_notebook,
    armar_detalle_pagos_ficha,
    armar_resumen_ficha_completa,
    armar_resumen_rendimiento,
    armar_tabla_html_multiperiodo,
    ejecutar_extraccion_indice,
    exportar_csv_excel,
    exportar_ficha_a_pdf,
    exportar_ficha_html,
    exportar_xlsx,
    extraer_fecha_consulta,
    mostrar_emisoras,
    mostrar_ficha_completa_cliente,
    mostrar_ficha_multiperiodo,
    mostrar_ficha_rendimiento,
    probar_historial_dividendos,
    seleccionar_anio_interactivo,
    seleccionar_ticker_interactivo,
)
from modules.procesamiento import calcular_ventana_movil_12_meses, obtener_anios_disponibles

# %%
# Aplicar tema oscuro al notebook
aplicar_tema_oscuro_notebook()

# Configuración de rutas de salida
CARPETA_SALIDA = Path.cwd() / "output"
CARPETA_FICHAS = CARPETA_SALIDA / "fichas"

# Parámetros editables del notebook
HEADLESS = True
TIMEOUT_DATOS_MS = 30000
EXPORTAR_CSV_ANALITICO = True
EXPORTAR_CSV_EXCEL = False
EXPORTAR_XLSX = False
RUTA_CSV_EXCEL = Path.cwd() / "indice_fibras.csv"
RUTA_XLSX = Path.cwd() / "indice_fibras.xlsx"

# %% [markdown]
# ## Ejecutar extracción
# Consultar solo los lunes temprano para hacer un análisis rápido de las FIBRAS y para saber si hubo altas y bajas de emisoras.

# %%
df = ejecutar_extraccion_indice(HEADLESS, TIMEOUT_DATOS_MS, CARPETA_SALIDA, EXPORTAR_CSV_ANALITICO)

# %% [markdown]
# ### Exportar a archivo de Excel - xlsx (Ejecución opcional)

# %%
if EXPORTAR_CSV_EXCEL:
    ruta_csv_excel = exportar_csv_excel(df, RUTA_CSV_EXCEL)
    print(f"CSV compatible con Excel guardado en: {ruta_csv_excel}")

if EXPORTAR_XLSX:
    ruta_xlsx = exportar_xlsx(df, RUTA_XLSX)
    print(f"Excel guardado en: {ruta_xlsx}")

# %% [markdown]
# ## Consulta de emisoras

# %%
try:
    df
except NameError:
    df = None

df_emisoras = mostrar_emisoras(df, CARPETA_SALIDA)

# %% [markdown]
# ## Historial de distribuciones por FIBRA
#
# ### Fuentes evaluadas
#
# | Fuente | Cobertura BMV | Datos de distribuciones | Acceso y límites |
# |---|---|---|---|
# | Relación con Inversionistas del emisor | Sí, por emisora | Fuente primaria; puede incluir fechas, importe y componentes fiscales en PDF/XLSX | Gratuita, sin API uniforme; requiere localizar y procesar reportes de cada emisor |
# | AMEFIBRA | Sí, índice agregado | Cotización e indicadores del índice; no publica aquí un histórico normalizado de distribuciones | Consulta web pública; no se expone una API de dividendos en esta tabla |
# | BMV/BIVA | Sí | Información oficial de emisoras y eventos, según disponibilidad del portal | Consulta pública, pero sin una API gratuita y estable para este flujo |
# | FMP, Alpha Vantage, Twelve Data, EODHD, Nasdaq Data Link y Polygon | Cobertura mexicana variable | La cobertura y profundidad de dividendos para tickers BMV no está garantizada en el plan gratuito | Requieren revisar ticker, API key y límites por proveedor |
# | `yfinance` | Sí para tickers Yahoo con sufijo `.MX`, cuando Yahoo dispone del evento | Fecha ex-dividendo y monto; no garantiza fecha de registro, pago ni componentes fiscales | Gratis y sin API key, pero es un cliente no oficial de Yahoo Finance y está sujeto a cambios y límites |
#
# Se usa `yfinance` como respaldo reproducible porque las fuentes primarias no ofrecen una API homogénea. El resultado contiene la fecha ex-dividendo y el importe disponible en Yahoo; la fecha de registro, fecha de pago y componentes fiscales no se incluyen porque esta fuente no los entrega de forma confiable. El histórico se ordena del más antiguo al más reciente. `yield_pct` es el rendimiento de cada distribución respecto al cierre de su fecha ex-dividendo; `annualized_yield_pct` anualiza ese rendimiento usando `365 / días_del_periodo`. Para la primera fila se usa la mediana histórica de días entre distribuciones.

# %% [markdown]
# ### Ticker a consultar
#
# Elige, del desplegable, el ticker a consultar (mismo listado de la sección "Consula de emisoras"). Al correr esta celda se despliega el selector; cambia la selección y luego corre la celda de abajo para consultar el ticker elegido.

# %%
selector_ticker = seleccionar_ticker_interactivo(df_emisoras["Emisora"])

# %%
TICKER_SELECCIONADO = selector_ticker.value
historial_dividendos = probar_historial_dividendos(TICKER_SELECCIONADO, df_emisoras["Emisora"], CARPETA_SALIDA)

# %% [markdown]
# ## FICHA DE RENDIMIENTO ANUAL PERSONALIZADO
#
# La ficha usa el **año calendario** (`1 de enero` a `31 de diciembre`). Los pagos se filtran por `ex_date`, que es la fecha disponible en el historial de `yfinance`; no se inventa una fecha de pago que la fuente no proporciona. Los precios inicial y final son el primer y último cierre disponible dentro del año. El rendimiento por dividendos se calcula contra el precio inicial, y el rendimiento de capital contra la variación entre precio final e inicial. La ficha es informativa y no constituye una recomendación de inversión.

# %% [markdown]
# ### Año a consultar
#
# Elige, del desplegable, el año a consultar (solo se muestran los años con distribuciones disponibles para el ticker). Al correr esta celda se despliega el selector; cambia la selección y luego corre la celda de abajo para generar la ficha con el año elegido.

# %%
AÑOS_DISPONIBLES = obtener_anios_disponibles(historial_dividendos)
selector_anio = seleccionar_anio_interactivo(AÑOS_DISPONIBLES)

# %%
# Generamos la ficha de rendimiento anual y la exportamos a PDF
AÑO_SELECCIONADO = selector_anio.value
ruta_ficha, _datos_rendimiento_anual = mostrar_ficha_rendimiento(TICKER_SELECCIONADO, AÑO_SELECCIONADO, CARPETA_SALIDA, historial_dividendos)

# Exportamos los resultados a un archivo pdf y mostramos la ruta del archivo generado
ruta_pdf_rendimiento = exportar_ficha_a_pdf(
    ruta_ficha, TICKER_SELECCIONADO, "rendimiento anual", AÑO_SELECCIONADO, CARPETA_FICHAS
)
print(f"PDF generado: {ruta_pdf_rendimiento}")

# %% [markdown]
# ### Ficha completa del año seleccionado para cliente
#
# Ficha completa anual pensada como entregable final para el cliente (escenario de inversión, distribuciones mensuales y rendimiento total en el año), con un diseño distinto al de la ficha de rendimiento anterior. Usa el mismo ticker y año ya elegidos arriba y los mismos datos reales (`historial_dividendos`); no inventa cifras. Es informativa y no constituye una recomendación de inversión.

# %%
# Generamos la ficha completa anual para el cliente y la exportamos a PDF
CAPITAL_INVERTIDO_REFERENCIA = 10000.0
ruta_ficha_completa_cliente, datos_ficha_completa_anual = mostrar_ficha_completa_cliente(
    TICKER_SELECCIONADO, AÑO_SELECCIONADO, CARPETA_SALIDA, historial_dividendos, CAPITAL_INVERTIDO_REFERENCIA
)

# Exportamos los resultados a un archivo pdf y mostramos la ruta del archivo generado
ruta_pdf_completa_cliente = exportar_ficha_a_pdf(
    ruta_ficha_completa_cliente, TICKER_SELECCIONADO, "ficha completa cliente", AÑO_SELECCIONADO, CARPETA_FICHAS
)
print(f"PDF generado: {ruta_pdf_completa_cliente}")

# Exportamos la misma ficha a HTML responsivo y autocontenido, a partir del mismo
# `datos_ficha_completa_anual` ya calculado arriba (no se recalcula nada). La fecha/hora
# de consulta se extrae del propio nombre de `ruta_ficha_completa_cliente`, para que
# coincida exactamente con la del PDF de esta misma ficha.
fecha_consulta_completa_anual = extraer_fecha_consulta(ruta_ficha_completa_cliente)
periodo_texto_completa_anual = (
    f"Año calendario {AÑO_SELECCIONADO} "
    f"({datos_ficha_completa_anual['fecha_inicial']:%d/%m/%Y} – {datos_ficha_completa_anual['fecha_final']:%d/%m/%Y})"
)
ruta_html_completa_cliente = exportar_ficha_html(
    [
        ("Resumen del escenario de inversión", armar_resumen_ficha_completa(datos_ficha_completa_anual, CAPITAL_INVERTIDO_REFERENCIA)),
        ("Detalle de distribuciones", armar_detalle_pagos_ficha(datos_ficha_completa_anual["detalle_pagos"])),
    ],
    "Ficha completa para cliente",
    "ficha completa cliente",
    TICKER_SELECCIONADO,
    str(AÑO_SELECCIONADO),
    fecha_consulta_completa_anual,
    CARPETA_FICHAS,
    periodo_texto=periodo_texto_completa_anual,
    nota_metodologica=(
        "El rendimiento total incluye plusvalía (variación de precio) y distribuciones "
        "(dividendos) sobre el capital de referencia indicado arriba; los pagos se "
        "identifican por ex_date."
    ),
)
print(f"HTML generado: {ruta_html_completa_cliente}")

# %% [markdown]
# ## FICHA DE RENDIMIENTO Y RIESGO DE LOS ÚLTIMOS 12 MESES
#
# Misma ficha de rendimiento de arriba, pero calculada sobre la ventana móvil de los últimos 12 meses completos (en vez de año calendario), con el riesgo mensual promedio del periodo (volatilidad del retorno total mensual: variación de precio + dividendos del mes) agregado como cifra destacada junto al rendimiento total.

# %%
# Fecha de referencia para la ventana móvil de 12 meses (fecha_fin del periodo).
# None = usa la fecha actual; fijar una fecha (ej. "2025-12-31") permite correr el
# análisis de forma retrospectiva, útil para pruebas. El flujo de año calendario
# de las celdas anteriores no se modifica y sigue disponible como antes.
FECHA_REFERENCIA_12M = None
FECHA_INICIO_12M, FECHA_FIN_12M = calcular_ventana_movil_12_meses(FECHA_REFERENCIA_12M)
print(f"Ventana de análisis: {FECHA_INICIO_12M:%Y-%m-%d} a {FECHA_FIN_12M:%Y-%m-%d}")

# %% [markdown]
# ### Ficha sencilla de los últimos 12 meses

# %%
# Generamos la ficha sencilla de rendimiento de los últimos 12 meses y la exportamos a PDF
ruta_ficha_12m, datos_rendimiento_12m = mostrar_ficha_rendimiento(
    TICKER_SELECCIONADO, None, CARPETA_SALIDA, historial_dividendos, fecha_referencia=FECHA_REFERENCIA_12M
)

# Exportamos los resultados a un archivo pdf y mostramos la ruta del archivo generado
ruta_pdf_12m = exportar_ficha_a_pdf(
    ruta_ficha_12m, TICKER_SELECCIONADO, "rendimiento 12 meses", f"{FECHA_FIN_12M:%Y%m%d}", CARPETA_FICHAS
)
print(f"PDF generado: {ruta_pdf_12m}")

# Exportamos la misma ficha a HTML responsivo y autocontenido, a partir del mismo
# `datos_rendimiento_12m` ya calculado arriba. La fecha/hora de consulta se extrae del
# propio nombre de `ruta_ficha_12m`, para que coincida exactamente con la del PDF.
fecha_consulta_12m = extraer_fecha_consulta(ruta_ficha_12m)
periodo_texto_12m = (
    f"Últimos 12 meses ({pd.Timestamp(datos_rendimiento_12m['fecha_inicial']):%d/%m/%Y} – "
    f"{pd.Timestamp(datos_rendimiento_12m['fecha_final']):%d/%m/%Y})"
)
ruta_html_12m = exportar_ficha_html(
    [
        ("Resumen de rendimiento", armar_resumen_rendimiento(datos_rendimiento_12m)),
        ("Detalle de distribuciones", armar_detalle_pagos_ficha(datos_rendimiento_12m["pagos"])),
    ],
    "Ficha de rendimiento",
    "rendimiento 12 meses",
    TICKER_SELECCIONADO,
    f"{FECHA_FIN_12M:%Y%m%d}",
    fecha_consulta_12m,
    CARPETA_FICHAS,
    periodo_texto=periodo_texto_12m,
    nota_metodologica=(
        "El rendimiento total incluye la variación de precio y las distribuciones "
        "(dividendos) del periodo; los pagos se identifican por ex_date."
    ),
)
print(f"HTML generado: {ruta_html_12m}")

# %% [markdown]
# ### Ficha completa de los últimos 12 meses para cliente
#
# Misma ficha completa de arriba, pero sobre la ventana móvil de últimos 12 meses: agrega una sección de riesgo del periodo con la volatilidad anualizada del retorno total mensual y la serie de los 12 retornos mensuales en barras (verde = mes positivo, rojo = mes negativo), colocada junto al desglose de rendimiento (plusvalía vs. distribuciones).

# %%
# Generamos la ficha completa de los últimos 12 meses para el cliente y la exportamos a PDF
ruta_ficha_completa_12m, datos_ficha_completa_12m = mostrar_ficha_completa_cliente(
    TICKER_SELECCIONADO, None, CARPETA_SALIDA, historial_dividendos,
    CAPITAL_INVERTIDO_REFERENCIA, fecha_referencia=FECHA_REFERENCIA_12M
)

# Exportamos los resultados a un archivo pdf y mostramos la ruta del archivo generado
ruta_pdf_completa_12m = exportar_ficha_a_pdf(
    ruta_ficha_completa_12m, TICKER_SELECCIONADO, "ficha completa 12 meses", f"{FECHA_FIN_12M:%Y%m%d}", CARPETA_FICHAS
)
print(f"PDF generado: {ruta_pdf_completa_12m}")

# Exportamos la misma ficha a HTML responsivo y autocontenido, a partir del mismo
# `datos_ficha_completa_12m` ya calculado arriba. La fecha/hora de consulta se extrae del
# propio nombre de `ruta_ficha_completa_12m`, para que coincida exactamente con la del PDF.
fecha_consulta_completa_12m = extraer_fecha_consulta(ruta_ficha_completa_12m)
periodo_texto_completa_12m = (
    f"Últimos 12 meses ({pd.Timestamp(datos_ficha_completa_12m['fecha_inicial']):%d/%m/%Y} – "
    f"{pd.Timestamp(datos_ficha_completa_12m['fecha_final']):%d/%m/%Y})"
)
ruta_html_completa_12m = exportar_ficha_html(
    [
        ("Resumen del escenario de inversión", armar_resumen_ficha_completa(datos_ficha_completa_12m, CAPITAL_INVERTIDO_REFERENCIA)),
        ("Detalle de distribuciones", armar_detalle_pagos_ficha(datos_ficha_completa_12m["detalle_pagos"])),
    ],
    "Ficha completa para cliente",
    "ficha completa 12 meses",
    TICKER_SELECCIONADO,
    f"{FECHA_FIN_12M:%Y%m%d}",
    fecha_consulta_completa_12m,
    CARPETA_FICHAS,
    periodo_texto=periodo_texto_completa_12m,
    nota_metodologica=(
        "El rendimiento total incluye plusvalía (variación de precio) y distribuciones "
        "(dividendos) sobre el capital de referencia indicado arriba; los pagos se "
        "identifican por ex_date."
    ),
)
print(f"HTML generado: {ruta_html_completa_12m}")

# %% [markdown]
# ## ANÁLISIS DE DISTINTOS PERIODOS
#
# Ficha comparativa de rendimiento y riesgo del ticker elegido en 5 ventanas de tiempo a la vez (último año, últimos 2/5/10 años e histórico desde el primer precio disponible), en vez de un solo periodo. Un lapso se omite por completo si el ticker no tiene historial suficiente para cubrirlo (se documenta como nota, no como fila vacía o en cero). El ratio tipo Sharpe usa CETES 28 días (fuente: Banxico) como tasa libre de riesgo; requiere un token gratuito de Banxico en la variable de entorno `BANXICO_SIE_TOKEN` — sin él, ese indicador queda en "N/D" con una nota, y el resto de la ficha se genera igual. Es informativa y no constituye una recomendación de inversión.

# %%
# Generamos la ficha comparativa multi-periodo y la mostramos en el notebook
ruta_ficha_multiperiodo, tabla_multiperiodo = mostrar_ficha_multiperiodo(TICKER_SELECCIONADO, CARPETA_SALIDA, historial_dividendos)

# Exportamos la misma tabla a HTML responsivo y autocontenido, a partir del mismo
# `tabla_multiperiodo` ya mostrado arriba (no se recalcula ningún indicador). La
# fecha/hora de consulta se extrae del propio nombre de `ruta_ficha_multiperiodo`.
fecha_consulta_multiperiodo = extraer_fecha_consulta(ruta_ficha_multiperiodo)
ruta_html_multiperiodo = exportar_ficha_html(
    armar_tabla_html_multiperiodo(tabla_multiperiodo),
    "Ficha comparativa multi-periodo",
    "rendimiento multiperiodo",
    TICKER_SELECCIONADO,
    f"{fecha_consulta_multiperiodo:%Y%m%d}",
    fecha_consulta_multiperiodo,
    CARPETA_FICHAS,
    periodo_texto="5 ventanas de tiempo (1A, 2A, 5A, 10A, Histórico)",
    nota_metodologica=(
        "El rendimiento anual (CAGR) y el riesgo de cada ventana incluyen plusvalía y "
        "distribuciones; el ratio tipo Sharpe usa CETES 28 días como tasa libre de riesgo "
        "cuando hay token de Banxico configurado."
    ),
)
print(f"HTML generado: {ruta_html_multiperiodo}")
