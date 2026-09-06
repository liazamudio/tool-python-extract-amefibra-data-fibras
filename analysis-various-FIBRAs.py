# ---
# Generado automáticamente a partir de `analysis-various-FIBRAs.ipynb`.
# Formato de celdas "percent" (# %%), compatible con VS Code / Jupytext:
# cada bloque se puede correr de forma independiente como celda en el
# Interactive Window de VS Code, igual que en el notebook original.
# No editar a mano: los cambios deben hacerse en el notebook y volver a exportar
# (`python -m jupytext --to py:percent analysis-various-FIBRAs.ipynb`).
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
    armar_tabla_tickers_seleccionados,
    descargar_historiales_dividendos,
    ejecutar_extraccion_indice,
    exportar_csv_excel,
    exportar_xlsx,
    mostrar_comparativo_completo_cliente,
    mostrar_comparativo_rendimiento,
    mostrar_emisoras,
    mostrar_escenario_multianual,
    resumen_precio_periodicidad,
    seleccionar_anio_interactivo,
    seleccionar_tickers_interactivo,
)
from modules.procesamiento import calcular_ventana_movil_12_meses, obtener_anios_disponibles_comunes

# %%
# Aplicar tema oscuro al notebook
aplicar_tema_oscuro_notebook()

# Configuración de rutas de salida
CARPETA_SALIDA = Path.cwd() / "output"
CARPETA_FICHAS_EXPORT = CARPETA_SALIDA / "fichas"

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
# ### CONSULTA DE EMISORAS
#
# Marca una o más FIBRAs en la lista de casillas (mismo listado de la sección "Consulta de emisoras"): un clic por cada ticker que quieras incluir. Al correr esta celda se despliega la lista; ajusta las casillas y luego corre la celda de abajo para consultar los tickers elegidos.

# %%
# Si df no está definido, inicializarlo como None
try:
    df
except NameError:
    df = None

df_emisoras = mostrar_emisoras(df, CARPETA_SALIDA)

selector_tickers = seleccionar_tickers_interactivo(df_emisoras["Emisora"])

# %%
# Armamos el DataFrame de tickers seleccionados (con la cotización de AMEFIBRA de esta
# corrida como metadato, si se ejecutó la extracción). Sobre él descargamos el historial
# de dividendos de cada ticker y mostramos precio actual y periodicidad en una sola tabla.
try:
    df
except NameError:
    df = None

tickers_seleccionados = armar_tabla_tickers_seleccionados(selector_tickers.value, df_emisoras["Emisora"], df)

historiales = descargar_historiales_dividendos(tickers_seleccionados["ticker"], df_emisoras["Emisora"], CARPETA_SALIDA)
resumen_tickers = resumen_precio_periodicidad(tickers_seleccionados, historiales)

# %% [markdown]
# ## FICHA DE RENDIMIENTO ANUAL PERSONALIZADO
#
# La ficha usa el **año calendario** (`1 de enero` a `31 de diciembre`). Los pagos se filtran por `ex_date`, que es la fecha disponible en el historial de `yfinance`; no se inventa una fecha de pago que la fuente no proporciona. Los precios inicial y final son el primer y último cierre disponible dentro del año. El rendimiento por dividendos se calcula contra el precio inicial, y el rendimiento de capital contra la variación entre precio final e inicial. La ficha es informativa y no constituye una recomendación de inversión.

# %% [markdown]
# ### Año a consultar
#
# Elige, del desplegable, el año a consultar. Solo se muestran los años con distribuciones disponibles para **todos** los tickers seleccionados (intersección); el año elegido se usa para el comparativo de todas las FIBRAs seleccionadas.

# %%
# Calculamos la ventana móvil de 12 meses para cada historial de dividendos, y la agregamos.
AÑOS_DISPONIBLES = obtener_anios_disponibles_comunes(historiales)
selector_anio = seleccionar_anio_interactivo(AÑOS_DISPONIBLES)

# %% [markdown]
# ### Comparativo de FIBRAs del año seleccionado (ficha completa para cliente)
#
# Comparativo de FIBRAs pensado como entregable final para el cliente (escenario de inversión, distribuciones mensuales y rendimiento total en el año), con un diseño distinto al del comparativo de rendimiento anterior. Junta en una sola tabla a todas las FIBRAs seleccionadas, con el año ya elegido arriba y los datos reales de cada una; no inventa cifras. Es informativa y no constituye una recomendación de inversión.

# %%
# Generamos y exportamos (HTML responsivo) el "Comparativo de FIBRAs" (ficha completa
# anual para el cliente) de todas las FIBRAs seleccionadas, con el año elegido arriba.
AÑO_SELECCIONADO = selector_anio.value
ruta_comparativo_completo_anual = mostrar_comparativo_completo_cliente(
    tickers_seleccionados, historiales, CARPETA_SALIDA, CARPETA_FICHAS_EXPORT, año=AÑO_SELECCIONADO
)

# %% [markdown]
# ## FICHA DE RENDIMIENTO Y RIESGO DE LOS ÚLTIMOS 12 MESES
#
# Misma ficha de rendimiento de arriba, pero calculada sobre la ventana móvil de los últimos 12 meses completos (en vez de año calendario), con el riesgo mensual promedio del periodo (volatilidad del retorno total mensual: variación de precio + dividendos del mes) agregado como cifra destacada junto al rendimiento total.

# %%
# Fecha de referencia para la ventana móvil de 12 meses (fecha_fin del periodo).
# None = usa la fecha actual; fijar una fecha (ej. "2025-12-31") permite correr el
# análisis de forma retrospectiva, útil para pruebas. La ventana es única y se aplica
# por igual a todos los tickers seleccionados. El flujo de año calendario de las celdas
# anteriores no se modifica y sigue disponible como antes.
FECHA_REFERENCIA_12M = None
FECHA_INICIO_12M, FECHA_FIN_12M = calcular_ventana_movil_12_meses(FECHA_REFERENCIA_12M)
print(f"Ventana de análisis (única para todos los tickers seleccionados): {FECHA_INICIO_12M:%Y-%m-%d} a {FECHA_FIN_12M:%Y-%m-%d}")

# %% [markdown]
# ### Comparativo de FIBRAs de los últimos 12 meses (ficha completa para cliente)
#
# Mismo comparativo de arriba, pero sobre la ventana móvil de últimos 12 meses: agrega una tabla de riesgo del periodo con la volatilidad anualizada y mensual promedio, y el retorno total mensual de cada FIBRA (verde = mes positivo, rojo = mes negativo), junto al desglose de rendimiento (plusvalía vs. distribuciones).

# %%
# Generamos y exportamos (HTML responsivo) el "Comparativo de FIBRAs" (ficha completa
# de los últimos 12 meses) para el cliente de todas las FIBRAs seleccionadas.
ruta_comparativo_completo_12m = mostrar_comparativo_completo_cliente(
    tickers_seleccionados, historiales, CARPETA_SALIDA, CARPETA_FICHAS_EXPORT, fecha_referencia=FECHA_REFERENCIA_12M
)

# %% [markdown]
# ## ANÁLISIS A MÁS AÑOS
#
# Escenario de inversión sobre ventanas móviles de **2, 3, 5 y 10 años**, contadas hacia atrás desde la última fecha con precio disponible común a las FIBRAs seleccionadas. Replica el *Resumen del escenario de inversión* de la ficha completa de los últimos 12 meses (misma metodología y formato) y agrega la distribución promedio anual, el rendimiento promedio anual compuesto (CAGR) y el simple.
#
# El horizonte es interactivo: al cambiarlo, la tabla se recalcula y la lista de FIBRAs elegibles se actualiza. Una FIBRA sin historial de precio suficiente para cubrir todo el horizonte se omite de ese periodo (se deshabilita y se deselecciona), con una nota que indica su inicio de cotización.

# %%
# Escenario de inversión multianual (2/3/5/10 años). Reutiliza los tickers ya
# seleccionados y sus historiales de dividendos; descarga el historial de precios
# completo de cada FIBRA una sola vez. Cambia el horizonte en el desplegable y
# marca/desmarca FIBRAs: la tabla y la lista de elegibles se recalculan al vuelo.
selector_horizonte = mostrar_escenario_multianual(
    tickers_seleccionados, historiales, CARPETA_SALIDA, CARPETA_FICHAS_EXPORT
)
