# AMEFIBRA Índice FIBRAS — Notebooks de extracción y análisis

Dos notebooks de Jupyter (cada uno con su equivalente en script `.py`) que extraen el Índice FIBRAS de AMEFIBRA en tiempo real, consultan el listado de emisoras y descargan el historial de dividendos de cada FIBRA vía `yfinance`. Sobre esa base:

- **`analysis-one-FIBRA`** — análisis de **una** FIBRA a la vez: ficha de rendimiento anual (dividendos + variación de capital), ficha completa anual para el cliente, la variante de ambas sobre una ventana móvil de los últimos 12 meses con el riesgo del periodo (volatilidad del retorno total mensual), y una ficha comparativa que evalúa rendimiento y riesgo en 5 ventanas de tiempo a la vez (1/2/5/10 años e histórico). Cada ficha se exporta a PDF y a HTML con nombre de archivo estandarizado.
- **`analysis-various-FIBRAs`** — comparación de **varias** FIBRAs a la vez: un "Comparativo de FIBRAs" (ficha completa para el cliente) que junta a todas las FIBRAs seleccionadas en una sola tabla, por año calendario y por ventana móvil de 12 meses, y un **escenario de inversión multianual** interactivo sobre horizontes de 2, 3, 5 y 10 años (CAGR, rendimiento anual simple, distribución promedio anual), que filtra automáticamente las FIBRAs sin historial suficiente para cada horizonte. Los comparativos se exportan como HTML responsivo.

<!-- COMPLETAR: agregar un GIF o captura de pantalla mostrando una corrida de alguno de los notebooks (tabla del índice, selectores interactivos y una ficha/comparativo HTML). No se pudo generar automáticamente porque requiere una grabación de pantalla. -->

## Problema / Motivación

La tabla de indicadores del Índice FIBRAS no viene en el HTML de la página de AMEFIBRA: está incrustada en un `<iframe>` que arma la tabla vía JavaScript y actualiza los precios en tiempo real por WebSocket (con ~20 minutos de retraso, según el propio sitio). Una petición HTTP simple (`requests.get`) solo trae la plantilla vacía, sin datos, por lo que se necesita un navegador real para renderizarla y poder extraerla de forma automatizada.

Además, ninguna fuente pública ofrece una API homogénea y gratuita de historial de distribuciones para tickers BMV (ver la comparativa de fuentes evaluadas dentro de los propios notebooks), así que se usa `yfinance` como respaldo reproducible para esa parte del análisis.

## Demo

<!-- COMPLETAR: no hay una versión en vivo desplegada (es un notebook de análisis, no una app web). Si se desea, agregar aquí un GIF o capturas de la tabla en pantalla, el selector interactivo y la ficha HTML generada en output/. -->

## Stack técnico

- **Lenguaje:** Python 3
- **Entorno de trabajo:** Jupyter Notebook (`.ipynb`), pensado para correrse celda por celda en VS Code (Jupyter/Interactive Window) o Jupyter Lab/Notebook. Cada notebook tiene un `.py` "percent" (`# %%`) espejo, mantenido con [jupytext](https://jupytext.readthedocs.io/), para correrlo desde el editor sin abrir el `.ipynb`
- **Automatización de navegador:** [Playwright](https://playwright.dev/python/) (Chromium headless) — para esperar el WebSocket y renderizar la tabla del índice
- **Datos de mercado/dividendos:** [yfinance](https://pypi.org/project/yfinance/) — historial de distribuciones y cierres diarios de cada FIBRA (tickers `.MX`)
- **Procesamiento de datos:** [pandas](https://pandas.pydata.org/) + [lxml](https://lxml.de/) (parseo de la tabla HTML renderizada)
- **Widgets interactivos:** [ipywidgets](https://ipywidgets.readthedocs.io/) — selectores de ticker, año y horizonte dentro de los notebooks
- **Exportación:** [openpyxl](https://openpyxl.readthedocs.io/) (Excel `.xlsx`), CSV nativo de pandas, HTML para las fichas y comparativos, y PDF (vía `page.pdf()` de Playwright, reutilizando el mismo Chromium headless ya usado para el scraping, sin dependencias adicionales)
- **Tasa libre de riesgo (ratio tipo Sharpe):** [API SIE de Banxico](https://www.banxico.org.mx/SieAPIRest/service/v1/) (serie `SF43936`, CETES 28 días) vía `requests`, con un token personal gratuito opcional (ver "Variables de entorno")
- **Base de datos:** No aplica — los notebooks no persisten datos en una BD, solo exportan a archivos locales en `output/`
- **Infraestructura/Deploy:** No aplica — notebooks/scripts de ejecución local, sin pipeline de CI/CD ni despliegue configurado en el repositorio

## Características principales

### Comunes a ambos notebooks

- Localiza automáticamente el `<iframe>` correcto de la tabla de indicadores entre los tres que expone la página (tabla, gráfica y marquesina) y espera activamente a que lleguen datos en vivo por WebSocket, con timeout configurable
- Limpia encabezados de columna y descarta columnas totalmente vacías (p. ej. el ícono de tendencia)
- En cada corrida archiva automáticamente un CSV "analítico" del índice completo en `output/`, con nombre `AAAAMMDD_HHMMSS_indice_fibras_amefibra.csv`: encabezados en snake_case, porcentajes como `float`, y columnas `fecha_hora_extraccion`/`fuente_datos` para trazabilidad
- Exporta también el listado de emisoras a `output/AAAAMMDD_HHMMSS_list_of_tickers.csv` en cada corrida, conservando un historial de corridas
- **Fallback sin depender de AMEFIBRA:** si no se ejecutó la extracción en vivo (celdas de extracción no corridas), la consulta de emisoras reutiliza automáticamente el CSV `list_of_tickers` más reciente de `output/` en vez de fallar, e indica en pantalla cuál de las dos fuentes se usó (más el conteo de emisoras cargadas)
- Descarga y valida el historial de dividendos de cada FIBRA (fecha ex-dividendo, monto, rendimiento y rendimiento anualizado), archivado también en `output/`
- Cachea en memoria los cierres ya cerrados (año calendario o ventana móvil), para no volver a descargar de Yahoo Finance los mismos precios cuando se generan varias fichas del mismo ticker/periodo en una misma corrida (el periodo en curso —el año actual, o una ventana que termina hoy— nunca se cachea, porque sus cierres siguen cambiando)
- Exporta opcionalmente el índice completo a CSV compatible con Excel (`utf-8-sig`) y/o XLSX
- Solo lee información pública ya publicada en las páginas/fuentes consultadas, sin credenciales ni endpoints privados

### `analysis-one-FIBRA` — una FIBRA a la vez

- Selectores interactivos (`ipywidgets`) para elegir, del listado de emisoras, qué ticker y qué año consultar
- **Ficha de rendimiento anual:** rendimiento total por año calendario (dividendos + variación de capital vs. precio inicial/final), en HTML
- **Ficha completa anual para el cliente:** diseño distinto, pensado como entregable final — escenario de inversión sobre un capital de referencia, gráfica de distribuciones mensuales, tabla de detalle fecha/monto/rendimiento y rendimiento total destacado
- **Variante de ventana móvil de últimos 12 meses:** alternativa al año calendario que coexiste con él (no lo reemplaza) — calcula el rendimiento sobre los 12 meses completos más recientes contados desde una fecha de referencia configurable (por defecto, hoy), y agrega el **riesgo del periodo**: la volatilidad del retorno total mensual (variación de precio + dividendos de cada mes), como cifra destacada en la ficha sencilla (versión mensual) y como volatilidad anualizada más una gráfica de barras de los 12 retornos mensuales (verde/rojo según el signo) en la ficha completa
- Exporta cada ficha —de año calendario o de ventana móvil de 12 meses— a PDF en `output/fichas/` y a HTML en `output/`, con nombre de archivo estandarizado (`AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.pdf`) que permite identificarlas y ordenarlas cronológicamente sin abrirlas
- **Ficha comparativa multi-periodo:** evalúa el ticker elegido en 5 ventanas de tiempo a la vez (último año, últimos 2/5/10 años e histórico desde el primer precio disponible), con 13 indicadores por ventana — rendimiento anual (CAGR) y mensual, riesgo anual y mensual, drawdown máximo, ratio tipo Sharpe (usando CETES 28 días de Banxico como tasa libre de riesgo), plusvalía/dividendos/ganancia total acumulados (en MXN y en %) y número de pagos. Un lapso sin historial suficiente para cubrirse completo se omite (no se muestra en cero ni vacío), documentado en una nota al pie; se exporta como HTML responsivo a `output/`
- Sin un token de Banxico configurado (opcional, gratuito), la ficha comparativa se genera igual: el ratio tipo Sharpe queda como "N/D" en vez de bloquear el resto de los indicadores

### `analysis-various-FIBRAs` — varias FIBRAs a la vez

- Selector de casillas para marcar una o varias FIBRAs del listado en un solo paso; una tabla única con el precio actual y la periodicidad de distribuciones de cada una
- Selector de año que solo ofrece los años con distribuciones disponibles para **todas** las FIBRAs marcadas (intersección)
- **Comparativo de FIBRAs (ficha completa para el cliente):** junta a todas las FIBRAs marcadas en una sola tabla —resumen del escenario de inversión, distribuciones mensuales por título y detalle de pagos—, por año calendario y por ventana móvil de 12 meses (esta última agrega el retorno total mensual por FIBRA y la volatilidad del periodo). Se exporta como HTML responsivo a `output/` y a `output/fichas/`
- **Escenario de inversión multianual:** replica el "Resumen del escenario de inversión" de la ficha de 12 meses, pero sobre ventanas móviles de **2, 3, 5 y 10 años** contadas hacia atrás desde la última fecha con precio disponible común a las FIBRAs analizadas. Agrega la distribución promedio anual, el rendimiento promedio anual compuesto (CAGR) y el simple. El horizonte es interactivo: al cambiarlo, la tabla y la lista de FIBRAs elegibles se recalculan al vuelo. Una FIBRA sin historial de precio suficiente para cubrir todo el horizonte se omite de ese periodo (se deshabilita y se deselecciona), con una nota que indica su inicio de cotización; el CAGR se muestra como "n/a" (no `NaN` ni excepción) cuando la pérdida total del periodo es ≥ 100 %

## Estructura del repositorio

```text
tool-python-extract-amefibra-data-fibras/
├── analysis-one-FIBRA.ipynb       # Notebook de análisis de UNA FIBRA (fichas de rendimiento, ventana 12m, multi-periodo)
├── analysis-one-FIBRA.py          # Espejo "percent" (# %%) del anterior, para correr celda por celda desde el editor
├── analysis-various-FIBRAs.ipynb  # Notebook de comparación de VARIAS FIBRAs (comparativo completo + escenario multianual)
├── analysis-various-FIBRAs.py     # Espejo "percent" (# %%) del anterior
├── modules/                       # Lógica reutilizable importada por los notebooks (mantiene las celdas simples)
│   ├── __init__.py
│   ├── extraccion.py              # Scraping del índice (Playwright), dividendos/precios (yfinance) y CETES 28 días (Banxico)
│   ├── procesamiento.py           # Normalización de DataFrames, ventanas móviles (12 meses y 2/3/5/10 años), riesgo mensual, CAGR y tabla comparativa multi-periodo
│   └── presentacion.py            # Despliegue en notebook, fichas y comparativos HTML/PDF, exportación a CSV/XLSX, selectores interactivos
├── previous/                      # Notas y prompts de trabajo personales; no versionado, ver .gitignore
├── output/                        # Generado en cada corrida (CSV/XLSX/HTML); no versionado, ver .gitignore
│   └── fichas/                    # PDFs y comparativos HTML exportados, con nombre de archivo estandarizado
├── requirements.txt                # Dependencias de Python
├── LICENSE
└── README.md
```

Los `.py` no se editan a mano: son un espejo del `.ipynb` para correrlo celda por celda desde el editor. Cuando cambia un notebook, se regenera su `.py` con `python -m jupytext --to py:percent <notebook>.ipynb`.

## Cómo correrlo localmente

Requiere Python 3.10 o superior.

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd tool-python-extract-amefibra-data-fibras

# 2. Crear y activar el entorno virtual
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1
# Windows (cmd.exe)
venv\Scripts\activate.bat
# Linux / macOS
source venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Instalar el navegador que usa Playwright (Chromium)
playwright install chromium
```

Variables de entorno: ninguna es obligatoria. Opcionalmente, `BANXICO_SIE_TOKEN` habilita el ratio tipo Sharpe de la ficha comparativa multi-periodo (tasa de CETES 28 días vía la API SIE de Banxico); se obtiene gratis en el [token de Banxico SIE](https://www.banxico.org.mx/SieAPIRest/service/v1/token) (solo pide un correo). Sin ella, esa ficha se genera igual y ese indicador queda como "N/D".

### Ejecutar los notebooks

Abre el `.ipynb` que quieras en VS Code (extensión Jupyter) o Jupyter Lab/Notebook, selecciona el kernel del `venv` creado arriba y corre las celdas en orden. Ambos notebooks comparten el arranque:

1. **Setup e imports** — agrega el proyecto a `sys.path` e importa las funciones de `modules/`.
2. **Parámetros editables** — `HEADLESS`, `TIMEOUT_DATOS_MS`, y los interruptores `EXPORTAR_CSV_ANALITICO` / `EXPORTAR_CSV_EXCEL` / `EXPORTAR_XLSX`.
3. **Ejecutar extracción** — descarga el Índice FIBRAS en vivo desde AMEFIBRA (tarda porque abre un navegador headless y espera datos por WebSocket). Se puede omitir: la consulta de emisoras reutiliza automáticamente el `list_of_tickers` más reciente de `output/`.

#### Después del arranque, en `analysis-one-FIBRA`

- **Selector de ticker** — dropdown con las emisoras disponibles; cambia la selección y corre la celda siguiente para descargar su historial de dividendos.
- **Selector de año** — dropdown con los años que tienen distribuciones para el ticker elegido.
- **Ficha de rendimiento anual** y **ficha completa anual para el cliente** — cada una se genera en HTML, se muestra en el notebook y se exporta a PDF (`output/fichas/`) y HTML (`output/`), con el ticker y año ya elegidos.
- **Ficha de rendimiento y riesgo de los últimos 12 meses** — sección aparte, independiente del año elegido: define `FECHA_REFERENCIA_12M` (`None` = hoy) y genera la ficha sencilla y la completa sobre la ventana móvil de 12 meses con el riesgo del periodo; también se exportan a PDF y HTML.
- **Ficha comparativa multi-periodo** — para el mismo ticker, compara rendimiento y riesgo en 5 ventanas de tiempo a la vez (1A/2A/5A/10A/Histórico), muestra la tabla en el notebook y la exporta como HTML responsivo a `output/`.

#### Después del arranque, en `analysis-various-FIBRAs`

- **Consulta de emisoras** — despliega la lista de casillas; marca una o varias FIBRAs y corre la celda de abajo para descargar sus historiales de dividendos y ver el precio actual y la periodicidad de cada una.
- **Selector de año** — dropdown con los años que tienen distribuciones para **todas** las FIBRAs marcadas (intersección).
- **Comparativo de FIBRAs (ficha completa para cliente)** — junta a todas las FIBRAs marcadas en una tabla, por año calendario y por ventana móvil de 12 meses; se muestra en el notebook y se exporta como HTML responsivo a `output/` y `output/fichas/`.
- **Escenario de inversión multianual** — para las mismas FIBRAs, escenario de inversión sobre horizontes de 2/3/5/10 años. El horizonte y la lista de FIBRAs son interactivos: la tabla se recalcula al vuelo y se exporta el HTML de cada horizonte.

Cada corrida relevante queda archivada en `output/` (CSV del índice, de emisoras y de dividendos; fichas y comparativos HTML) y en `output/fichas/` (los PDF de las fichas de un solo periodo y las copias HTML de los comparativos), con nombre `AAAAMMDD_HHMMSS_descripción` (HTML/CSV) o `AAAA-MM-DD_HHMM_..._periodo` (PDF/comparativos) para no sobrescribir corridas anteriores.

### Alternativa: los archivos `.py`

`analysis-one-FIBRA.py` y `analysis-various-FIBRAs.py` son el mismo contenido de cada notebook, exportado en formato de celdas "percent" (`# %%`, compatible con VS Code/Jupytext). Sirven para correr celda por celda desde el editor sin abrir el `.ipynb`, pero **no están pensados para ejecutarse de punta a punta con `python <archivo>.py`**: incluyen magics de IPython (`%load_ext autoreload`) y celdas con selectores interactivos (`ipywidgets`) que esperan una selección manual entre una celda y la siguiente. No se editan a mano — se regeneran con `python -m jupytext --to py:percent <notebook>.ipynb` cuando el notebook cambia.

### Si el entorno virtual no se activa

Si `Activate.ps1` falla en PowerShell por política de ejecución de scripts:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
```

Si el entorno quedó corrupto, elimínalo y créalo de nuevo:

```powershell
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\Activate.ps1
```

También puedes invocar el intérprete del `venv` directamente sin activarlo:

```bash
venv/Scripts/python.exe -m pip install -r requirements.txt
```

## Decisiones técnicas relevantes

- **Playwright en vez de `requests`:** la tabla del índice se renderiza vía JavaScript y WebSocket del lado del cliente, así que una petición HTTP simple solo devuelve la plantilla vacía. Se necesita un navegador real (aunque sea headless) para esperar a que los datos lleguen antes de leer el DOM.
- **`pd.read_html` sobre `io.StringIO`:** pandas ya no acepta de forma confiable un string de HTML crudo pasado directo a `read_html()` (lo puede interpretar como ruta de archivo); se envuelve explícitamente en `io.StringIO` para evitar ese comportamiento.
- **Notebooks + `modules/` en vez de un único script:** la lógica de extracción, procesamiento y presentación/exportación vive en `modules/` como funciones reutilizables; las celdas de los notebooks solo orquestan llamadas a esas funciones, para poder inspeccionar resultados intermedios (tablas, selectores) entre paso y paso sin perder legibilidad ni duplicar lógica entre el notebook y el script exportado.
- **Dos notebooks que comparten `modules/`, no uno con ramas:** `analysis-one-FIBRA` (una FIBRA, entregables en PDF por ticker) y `analysis-various-FIBRAs` (comparación de varias, tablas HTML) tienen flujos y salidas distintos; separarlos en dos notebooks mantiene cada uno corto y sin condicionales "¿uno o varios tickers?", a costa de repetir el arranque (extracción + emisoras), que de todos modos son 3 celdas.
- **Escenario multianual como réplica de la ficha de 12 meses, no una fórmula nueva:** `calcular_escenario_multianual` reusa exactamente la metodología de la ficha completa de 12 meses (`_calcular_ficha_completa`, modo ventana móvil) —precio inicial/final, títulos con el capital de referencia, distribuciones a nivel de la posición, dividendos como efectivo— y solo agrega la anualización (CAGR, simple, distribución promedio anual). La ventana de N años usa la misma convención `[fin − N años + 1 día, fin]`, de modo que con N = 1 el CAGR coincide con el rendimiento total de la ficha de 12 meses (control de calidad usado en las pruebas).
- **`yfinance` para dividendos:** ninguna fuente primaria (BMV/BIVA, relación con inversionistas de cada emisor, AMEFIBRA) expone una API homogénea y gratuita de historial de distribuciones; `yfinance` es un cliente no oficial de Yahoo Finance, gratuito y sin API key, a costa de no garantizar fecha de registro, fecha de pago ni componentes fiscales.
- **Fallback al CSV histórico de emisoras:** la extracción en vivo del índice (Playwright) es la parte más lenta del flujo; si ya existe una corrida reciente archivada en `output/`, la consulta de emisoras la reutiliza en vez de forzar una nueva extracción, e indica en pantalla cuál de las dos fuentes usó.
- **Nombres de archivo `AAAAMMDD_HHMMSS_descripción`:** el prefijo de fecha/hora (formato ordenable lexicográficamente) permite listar `output/` y ver las corridas en orden cronológico sin depender de la metadata del sistema de archivos, y evita que corridas repetidas se sobrescriban entre sí.
- **PDF vía Playwright en vez de una librería nueva:** para exportar las fichas a PDF se reutiliza `page.pdf()` del mismo Chromium headless que ya usa el scraping del índice, en vez de agregar una dependencia adicional (p. ej. weasyprint o un binario externo como wkhtmltopdf). El nombre del PDF (`AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.pdf`) toma la fecha/hora del propio nombre del HTML de origen —el momento en que se consultaron los datos—, no el momento de la exportación ni la fecha de modificación en disco (que, igual que en el resto del proyecto, no es confiable).
- **Cierres anuales cacheados solo para años cerrados:** la ficha de rendimiento y la ficha completa para el cliente consultan, segundos aparte, los mismos cierres del mismo ticker/año; cachear esa descarga en memoria evita duplicarla. El año en curso queda deliberadamente fuera del cache porque sus cierres cambian mientras avanza el año (el último cierre disponible es el "precio actual" de la ficha).
- **Ventana móvil de 12 meses como modo adicional, no un reemplazo:** el año calendario sigue siendo el flujo por defecto y no se modificó; la ventana móvil vive en funciones y celdas separadas que reutilizan las mismas fichas (mismo HTML/CSS, mismos cálculos base), activadas con un parámetro (`fecha_referencia`) en vez de duplicar las funciones de ficha completas.
- **Riesgo con retorno total mensual, no solo de precio:** la volatilidad del periodo se calcula sobre el retorno mensual total (variación de precio + dividendos pagados ese mes), porque es la volatilidad que efectivamente percibe quien invierte, no solo la del precio. Se reporta en su forma mensual en la ficha sencilla (más intuitiva) y anualizada (mensual × √12) en la ficha completa (más comparable con benchmarks de mercado).
- **Caché de la ventana móvil con diccionario simple, no `functools.lru_cache`:** a diferencia del caché de cierres anuales (preexistente, sin problema conocido), el de la ventana móvil se implementó con un diccionario en memoria en vez de `@functools.lru_cache`. Se detectó que `%autoreload` de IPython puede dejar en un estado inconsistente una función envuelta por ese decorador (un objeto de C, no una función normal) cuando se le agregan funciones nuevas al módulo durante una sesión larga de notebook, produciendo un `NameError` intermitente que solo aparece en el kernel interactivo, nunca en una ejecución fresca.
- **`annualized_yield_pct` puede quedar `NaN` con una sola distribución histórica:** anualizar un rendimiento requiere estimar el intervalo entre pagos, lo cual es indeterminado con un solo dato (típico de FIBRAs de IPO muy reciente). Se documentó como caso válido en vez de tratarlo como dato corrupto: la validación de `probar_historial_dividendos` solo exige ese campo poblado cuando hay dos o más distribuciones.
- **CAGR de la ficha multi-periodo con dividendos como efectivo, no reinvertidos:** el valor final usado para el CAGR es `precio final + dividendos acumulados del lapso` (suma simple), no un modelo de reinversión nocional que compraría más títulos con cada pago. Es la misma convención que ya usa el resto de las fichas del proyecto (ninguna simula recompra de títulos), elegida por consistencia y simplicidad sobre un modelo de reinversión que añadiría supuestos adicionales (¿se reinvierte al precio de ese día? ¿con qué frecuencia?) sin un beneficio claro para el objetivo de la ficha.
- **Volatilidad con desviación estándar muestral (`ddof=1`):** tanto la ficha de 12 meses como la multi-periodo usan el `ddof=1` que ya es el default de `pandas.Series.std()`, sin cambiarlo a poblacional (`ddof=0`); es la convención más común para series de retornos financieros, que se tratan como una muestra del comportamiento del activo, no como la población completa de sus retornos posibles.
- **CETES 28 días vía Banxico, con degradación explícita si no está disponible:** es la fuente oficial de esa tasa en México, pero su API exige un token personal (gratuito, pero no se puede obtener de forma automatizada). En vez de bloquear toda la ficha comparativa multi-periodo por un solo indicador, `armar_tabla_multiperiodo` captura la falla (`CetesNoDisponibleError` u otra excepción de red) y deja el ratio tipo Sharpe en `NaN` ("N/D" en la ficha) con una nota al pie explicando por qué, calculando con normalidad los otros 12 indicadores.
- **Lapsos fijos omitidos por completo, no en cero:** un lapso (1A/2A/5A/10A) requiere que el primer precio disponible del ticker sea anterior a su fecha de inicio; si no, se omite esa fila entera de la tabla comparativa (documentado como nota), en vez de mostrar un lapso con datos parciales o ceros que podrían confundirse con un rendimiento real de 0%.

<!-- COMPLETAR: agregar trade-offs adicionales que solo el autor conoce, por ejemplo: por qué Playwright y no Selenium/Puppeteer, por qué lanzar un navegador nuevo por ejecución en vez de mantener una sesión persistente, o por qué no se cachean/persisten los datos entre corridas más allá del historial en output/. No se pudo inferir del código porque no hay comentarios ni commits que lo documenten. -->

## Estado del proyecto

Activo en proceso de desarrollo — historial de git con ~45 commits hasta la fecha. La base (extracción del índice, consulta de emisoras con fallback al CSV histórico, historial de dividendos vía `yfinance`, fichas de rendimiento anual y completa para el cliente en PDF/HTML, la variante de ventana móvil de 12 meses con riesgo mensual/anualizado, y la ficha comparativa multi-periodo con CAGR, riesgo, drawdown y ratio tipo Sharpe) está consolidada en `analysis-one-FIBRA`. La actividad reciente se centró en el notebook `analysis-various-FIBRAs` para comparar varias FIBRAs a la vez: el "Comparativo de FIBRAs" (ficha completa para cliente) por año y por ventana de 12 meses, y el escenario de inversión multianual interactivo (2/3/5/10 años) con filtro de FIBRAs por suficiencia de historial.

## Autor / Rol

**Alex Zamudio** ([liazamudio@gmail.com](mailto:liazamudio@gmail.com)) — único autor y contribuidor registrado en el historial de git.

<!-- COMPLETAR: especificar el rol si este proyecto formó parte de un equipo o contexto laboral/freelance más amplio (el historial de git solo muestra un autor, consistente con proyecto individual). -->

## Licencia

MIT — ver [LICENSE](LICENSE).
