# ---
# Generado automáticamente a partir de `amefibra-indice-fibras.ipynb`.
# Formato de celdas "percent" (# %%), compatible con VS Code / Jupytext:
# cada bloque se puede correr de forma independiente como celda en el
# Interactive Window de VS Code, igual que en el notebook original.
# No editar a mano: los cambios deben hacerse en el notebook y volver a exportar.
# ---

# %% [markdown]
# # Índice FIBRAS de AMEFIBRA
#
# Notebook para extraer la tabla pública del Índice FIBRAS. La página carga los datos dentro de un `iframe` mediante JavaScript y WebSocket, por lo que se utiliza Playwright con Chromium.
#
# > La información se ofrece únicamente para consulta y análisis. AMEFIBRA indica que los datos tienen aproximadamente 20 minutos de retraso y no deben usarse como base única para decisiones de inversión.

# %%
%load_ext autoreload
%autoreload 2

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
    ejecutar_extraccion_indice,
    exportar_csv_excel,
    exportar_ficha_a_pdf,
    exportar_xlsx,
    mostrar_emisoras,
    mostrar_ficha_ejemplo_cliente,
    mostrar_ficha_rendimiento,
    probar_historial_dividendos,
    seleccionar_anio_interactivo,
    seleccionar_ticker_interactivo,
)
from modules.procesamiento import obtener_anios_disponibles

# %%
aplicar_tema_oscuro_notebook()

# %%
CARPETA_SALIDA = Path.cwd() / "output"
CARPETA_FICHAS_PDF = CARPETA_SALIDA / "fichas"

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
# ## Ficha de rendimiento anual
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
AÑO_SELECCIONADO = selector_anio.value
ruta_ficha = mostrar_ficha_rendimiento(TICKER_SELECCIONADO, AÑO_SELECCIONADO, CARPETA_SALIDA, historial_dividendos)

# %%
ruta_pdf_rendimiento = exportar_ficha_a_pdf(
    ruta_ficha, TICKER_SELECCIONADO, "rendimiento anual", AÑO_SELECCIONADO, CARPETA_FICHAS_PDF
)
print(f"PDF generado: {ruta_pdf_rendimiento}")

# %% [markdown]
# ## Ficha de ejemplo para cliente (demostración)
#
# Versión de demostración de la ficha, pensada para mostrarle al cliente el aspecto del entregable final (escenario de inversión, distribuciones mensuales y rendimiento total en el año), con un diseño distinto al de la ficha de rendimiento anterior. Usa el mismo ticker y año ya elegidos arriba y los mismos datos reales (`historial_dividendos`); no inventa cifras. Es informativa y no constituye una recomendación de inversión.

# %%
ruta_ficha_ejemplo = mostrar_ficha_ejemplo_cliente(TICKER_SELECCIONADO, AÑO_SELECCIONADO, CARPETA_SALIDA, historial_dividendos)

# %%
ruta_pdf_ejemplo = exportar_ficha_a_pdf(
    ruta_ficha_ejemplo, TICKER_SELECCIONADO, "ficha ejemplo cliente", AÑO_SELECCIONADO, CARPETA_FICHAS_PDF
)
print(f"PDF generado: {ruta_pdf_ejemplo}")
