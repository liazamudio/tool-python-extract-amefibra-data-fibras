# AMEFIBRA Índice FIBRAS — Notebook de extracción y análisis

Notebook de Jupyter (con su equivalente en script `.py`) que extrae el Índice FIBRAS de AMEFIBRA en tiempo real, consulta el listado de emisoras, descarga el historial de dividendos de cada FIBRA vía `yfinance`, genera una ficha de rendimiento anual (dividendos + variación de capital) y una ficha completa anual para el cliente por ticker, exporta ambas a PDF con nombre de archivo estandarizado, y ofrece además una variante de ambas fichas sobre una ventana móvil de los últimos 12 meses con el riesgo mensual del periodo (volatilidad del retorno total mensual).

<!-- COMPLETAR: agregar un GIF o captura de pantalla mostrando una corrida del notebook (tabla del índice, selector de ticker/año y la ficha HTML de rendimiento). No se pudo generar automáticamente porque requiere una grabación de pantalla. -->

## Problema / Motivación

La tabla de indicadores del Índice FIBRAS no viene en el HTML de la página de AMEFIBRA: está incrustada en un `<iframe>` que arma la tabla vía JavaScript y actualiza los precios en tiempo real por WebSocket (con ~20 minutos de retraso, según el propio sitio). Una petición HTTP simple (`requests.get`) solo trae la plantilla vacía, sin datos, por lo que se necesita un navegador real para renderizarla y poder extraerla de forma automatizada.

Además, ninguna fuente pública ofrece una API homogénea y gratuita de historial de distribuciones para tickers BMV (ver la comparativa de fuentes evaluadas dentro del propio notebook), así que se usa `yfinance` como respaldo reproducible para esa parte del análisis.

## Demo

<!-- COMPLETAR: no hay una versión en vivo desplegada (es un notebook de análisis, no una app web). Si se desea, agregar aquí un GIF o capturas de la tabla en pantalla, el selector interactivo y la ficha HTML generada en output/. -->

## Stack técnico

- **Lenguaje:** Python 3
- **Entorno de trabajo:** Jupyter Notebook (`.ipynb`), pensado para correrse celda por celda en VS Code (Jupyter/Interactive Window) o Jupyter Lab/Notebook
- **Automatización de navegador:** [Playwright](https://playwright.dev/python/) (Chromium headless) — para esperar el WebSocket y renderizar la tabla del índice
- **Datos de mercado/dividendos:** [yfinance](https://pypi.org/project/yfinance/) — historial de distribuciones y cierres diarios de cada FIBRA (tickers `.MX`)
- **Procesamiento de datos:** [pandas](https://pandas.pydata.org/) + [lxml](https://lxml.de/) (parseo de la tabla HTML renderizada)
- **Widgets interactivos:** [ipywidgets](https://ipywidgets.readthedocs.io/) — selectores de ticker y año dentro del notebook
- **Exportación:** [openpyxl](https://openpyxl.readthedocs.io/) (Excel `.xlsx`), CSV nativo de pandas, HTML para las fichas y PDF (vía `page.pdf()` de Playwright, reutilizando el mismo Chromium headless ya usado para el scraping, sin dependencias adicionales)
- **Base de datos:** No aplica — el notebook no persiste datos en una BD, solo exporta a archivos locales en `output/`
- **Infraestructura/Deploy:** No aplica — notebook/script de ejecución local, sin pipeline de CI/CD ni despliegue configurado en el repositorio

## Características principales

- Localiza automáticamente el `<iframe>` correcto de la tabla de indicadores entre los tres que expone la página (tabla, gráfica y marquesina) y espera activamente a que lleguen datos en vivo por WebSocket, con timeout configurable
- Limpia encabezados de columna y descarta columnas totalmente vacías (p. ej. el ícono de tendencia)
- En cada corrida archiva automáticamente un CSV "analítico" del índice completo en `output/`, con nombre `AAAAMMDD_HHMMSS_indice_fibras_amefibra.csv`: encabezados en snake_case, porcentajes como `float`, y columnas `fecha_hora_extraccion`/`fuente_datos` para trazabilidad
- Exporta también el listado de emisoras a `output/AAAAMMDD_HHMMSS_list_of_tickers.csv` en cada corrida, conservando un historial de corridas
- **Fallback sin depender de AMEFIBRA:** si no se ejecutó la extracción en vivo (celdas de extracción no corridas), la consulta de emisoras reutiliza automáticamente el CSV `list_of_tickers` más reciente de `output/` en vez de fallar, e indica en pantalla cuál de las dos fuentes se usó
- Selectores interactivos (`ipywidgets`) para elegir, del listado de emisoras ya extraído, qué ticker y qué año consultar
- Descarga y valida el historial de dividendos de la FIBRA elegida (fecha ex-dividendo, monto, rendimiento y rendimiento anualizado), archivado también en `output/`
- Genera una ficha HTML de rendimiento total por año calendario (dividendos + variación de capital vs. precio inicial/final), guardada en `output/`
- Genera además la ficha completa anual para el cliente, con un diseño distinto (escenario de inversión sobre un capital de referencia, gráfica de distribuciones mensuales, tabla de detalle fecha/monto/rendimiento y rendimiento total destacado), pensada como entregable final
- **Variante de ventana móvil de últimos 12 meses:** alternativa al año calendario que coexiste con él (no lo reemplaza) — calcula el rendimiento sobre los 12 meses completos más recientes contados desde una fecha de referencia configurable (por defecto, hoy), y agrega el **riesgo del periodo**: la volatilidad del retorno total mensual (variación de precio + dividendos de cada mes), mostrada como cifra destacada en la ficha sencilla (versión mensual) y como volatilidad anualizada más una gráfica de barras de los 12 retornos mensuales (verde/rojo según el signo) en la ficha completa
- Exporta ambas fichas —de año calendario o de ventana móvil de 12 meses— a PDF en `output/fichas/`, con nombre de archivo estandarizado (`AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.pdf`) que permite identificarlas y ordenarlas cronológicamente sin abrirlas
- Cachea en memoria los cierres (anuales o de la ventana móvil) ya cerrados, para no volver a descargar de Yahoo Finance los mismos precios cuando se generan varias fichas del mismo ticker/periodo en una misma corrida (el periodo en curso —el año actual, o una ventana que termina hoy— nunca se cachea, porque sus cierres siguen cambiando)
- Exporta opcionalmente el índice completo a CSV compatible con Excel (`utf-8-sig`) y/o XLSX
- Solo lee información pública ya publicada en las páginas/fuentes consultadas, sin credenciales ni endpoints privados

## Estructura del repositorio

```text
tool-python-extract-amefibra-data-fibras/
├── amefibra-indice-fibras.ipynb   # Notebook principal: extracción, emisoras, dividendos y ficha de rendimiento
├── amefibra-indice-fibras.py      # Mismo contenido exportado en formato "percent" (# %%), para correr celda por celda desde un editor sin abrir el .ipynb
├── modules/                       # Lógica reutilizable importada por el notebook (mantiene las celdas simples)
│   ├── __init__.py
│   ├── extraccion.py              # Scraping del índice (Playwright) y descarga de dividendos/precios (yfinance)
│   ├── procesamiento.py           # Normalización de DataFrames (snake_case, tipos, periodicidad), ventana móvil de 12 meses y riesgo mensual
│   └── presentacion.py            # Despliegue en notebook, fichas HTML/PDF y exportación a CSV/XLSX, selectores interactivos
├── output/                        # Generado en cada corrida (CSV/XLSX/HTML); no versionado, ver .gitignore
│   └── fichas/                    # PDFs exportados de las fichas, con nombre de archivo estandarizado
├── requirements.txt                # Dependencias de Python
├── LICENSE
└── README.md
```

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

Variables de entorno: no aplica — el notebook no requiere configuración por variables de entorno ni credenciales.

### Ejecutar el notebook

Abre `amefibra-indice-fibras.ipynb` en VS Code (extensión Jupyter) o Jupyter Lab/Notebook, selecciona el kernel del `venv` creado arriba, y corre las celdas en orden:

1. **Setup e imports** — agrega el proyecto a `sys.path` e importa las funciones de `modules/`.
2. **Parámetros editables** — `HEADLESS`, `TIMEOUT_DATOS_MS`, y los interruptores `EXPORTAR_CSV_ANALITICO` / `EXPORTAR_CSV_EXCEL` / `EXPORTAR_XLSX`.
3. **Ejecutar extracción** — descarga el Índice FIBRAS en vivo desde AMEFIBRA (tarda porque abre un navegador headless y espera datos por WebSocket).
4. **Consulta de emisoras** — si no quieres esperar la extracción en vivo, puedes saltarte el paso 3 y correr directo esta celda: reutiliza automáticamente el `list_of_tickers` más reciente de `output/`.
5. **Selector de ticker** — despliega un dropdown con las emisoras disponibles; cambia la selección y corre la celda siguiente para descargar su historial de dividendos.
6. **Selector de año** — despliega un dropdown con los años que tienen distribuciones para el ticker elegido; cambia la selección y corre la celda siguiente para generar la ficha de rendimiento de ese año.
7. **Ficha de rendimiento anual** y **ficha completa anual para el cliente** — cada una se genera en HTML, se muestra directamente en el notebook y se exporta a PDF en `output/fichas/` (ruta impresa en pantalla), usando el mismo ticker y año ya elegidos arriba.
8. **Ficha de rendimiento y riesgo de los últimos 12 meses** — sección aparte, independiente del año elegido en el paso 6: define una fecha de referencia (`FECHA_REFERENCIA_12M`, `None` = hoy) y genera la misma ficha sencilla y la misma ficha completa, pero sobre la ventana móvil de los últimos 12 meses y con el riesgo del periodo agregado; también se exportan a PDF.

Cada corrida relevante queda archivada en `output/` (CSV del índice, CSV de emisoras, CSV de dividendos y las fichas HTML de rendimiento y completa para el cliente, de año calendario o de ventana móvil de 12 meses) y en `output/fichas/` (los PDF de todas las fichas), con nombre `AAAAMMDD_HHMMSS_descripción` (HTML/CSV) o `AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo` (PDF) para no sobrescribir corridas anteriores.

### Alternativa: `amefibra-indice-fibras.py`

Es el mismo contenido del notebook, exportado en formato de celdas "percent" (`# %%`, compatible con VS Code/Jupytext). Sirve para correrlo celda por celda desde el editor sin abrir el `.ipynb`, pero **no está pensado para ejecutarse de punta a punta con `python amefibra-indice-fibras.py`**: incluye magics de IPython (`%load_ext autoreload`) y celdas con selectores interactivos (`ipywidgets`) que esperan una selección manual entre una celda y la siguiente, igual que en el notebook. No se edita a mano — se vuelve a generar a partir del notebook cuando este cambia.

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
- **Notebook + `modules/` en vez de un único script:** la lógica de extracción, procesamiento y presentación/exportación vive en `modules/` como funciones reutilizables; las celdas del notebook solo orquestan llamadas a esas funciones, para poder inspeccionar resultados intermedios (tablas, selectores) entre paso y paso sin perder legibilidad ni duplicar lógica entre el notebook y el script exportado.
- **`yfinance` para dividendos:** ninguna fuente primaria (BMV/BIVA, relación con inversionistas de cada emisor, AMEFIBRA) expone una API homogénea y gratuita de historial de distribuciones; `yfinance` es un cliente no oficial de Yahoo Finance, gratuito y sin API key, a costa de no garantizar fecha de registro, fecha de pago ni componentes fiscales.
- **Fallback al CSV histórico de emisoras:** la extracción en vivo del índice (Playwright) es la parte más lenta del flujo; si ya existe una corrida reciente archivada en `output/`, la consulta de emisoras la reutiliza en vez de forzar una nueva extracción, e indica en pantalla cuál de las dos fuentes usó.
- **Nombres de archivo `AAAAMMDD_HHMMSS_descripción`:** el prefijo de fecha/hora (formato ordenable lexicográficamente) permite listar `output/` y ver las corridas en orden cronológico sin depender de la metadata del sistema de archivos, y evita que corridas repetidas se sobrescriban entre sí.
- **PDF vía Playwright en vez de una librería nueva:** para exportar las fichas a PDF se reutiliza `page.pdf()` del mismo Chromium headless que ya usa el scraping del índice, en vez de agregar una dependencia adicional (p. ej. weasyprint o un binario externo como wkhtmltopdf). El nombre del PDF (`AAAA-MM-DD_HHMM_TICKER_descripcion-breve_periodo.pdf`) toma la fecha/hora del propio nombre del HTML de origen —el momento en que se consultaron los datos—, no el momento de la exportación ni la fecha de modificación en disco (que, igual que en el resto del proyecto, no es confiable).
- **Cierres anuales cacheados solo para años cerrados:** la ficha de rendimiento y la ficha completa para el cliente consultan, segundos aparte, los mismos cierres del mismo ticker/año; cachear esa descarga en memoria evita duplicarla. El año en curso queda deliberadamente fuera del cache porque sus cierres cambian mientras avanza el año (el último cierre disponible es el "precio actual" de la ficha).
- **Ventana móvil de 12 meses como modo adicional, no un reemplazo:** el año calendario sigue siendo el flujo por defecto y no se modificó; la ventana móvil vive en funciones y celdas separadas que reutilizan las mismas fichas (mismo HTML/CSS, mismos cálculos base), activadas con un parámetro (`fecha_referencia`) en vez de duplicar las funciones de ficha completas.
- **Riesgo con retorno total mensual, no solo de precio:** la volatilidad del periodo se calcula sobre el retorno mensual total (variación de precio + dividendos pagados ese mes), porque es la volatilidad que efectivamente percibe quien invierte, no solo la del precio. Se reporta en su forma mensual en la ficha sencilla (más intuitiva) y anualizada (mensual × √12) en la ficha completa (más comparable con benchmarks de mercado).
- **Caché de la ventana móvil con diccionario simple, no `functools.lru_cache`:** a diferencia del caché de cierres anuales (preexistente, sin problema conocido), el de la ventana móvil se implementó con un diccionario en memoria en vez de `@functools.lru_cache`. Se detectó que `%autoreload` de IPython puede dejar en un estado inconsistente una función envuelta por ese decorador (un objeto de C, no una función normal) cuando se le agregan funciones nuevas al módulo durante una sesión larga de notebook, produciendo un `NameError` intermitente que solo aparece en el kernel interactivo, nunca en una ejecución fresca.
- **`annualized_yield_pct` puede quedar `NaN` con una sola distribución histórica:** anualizar un rendimiento requiere estimar el intervalo entre pagos, lo cual es indeterminado con un solo dato (típico de FIBRAs de IPO muy reciente). Se documentó como caso válido en vez de tratarlo como dato corrupto: la validación de `probar_historial_dividendos` solo exige ese campo poblado cuando hay dos o más distribuciones.

<!-- COMPLETAR: agregar trade-offs adicionales que solo el autor conoce, por ejemplo: por qué Playwright y no Selenium/Puppeteer, por qué lanzar un navegador nuevo por ejecución en vez de mantener una sesión persistente, o por qué no se cachean/persisten los datos entre corridas más allá del historial en output/. No se pudo inferir del código porque no hay comentarios ni commits que lo documenten. -->

## Estado del proyecto

Activo en proceso de desarrollo — historial de git con 27 commits hasta la fecha, actividad reciente centrada en migrar el script original a un notebook con `modules/` reutilizables, agregar la consulta de dividendos/ficha de rendimiento, el fallback de emisoras sin depender de AMEFIBRA, la ficha completa anual para el cliente, la exportación de ambas fichas a PDF, corregir el contraste de texto de las fichas, y agregar la variante de ventana móvil de últimos 12 meses con riesgo mensual/anualizado.

## Autor / Rol

**Alex Zamudio** ([liazamudio@gmail.com](mailto:liazamudio@gmail.com)) — único autor y contribuidor registrado en el historial de git.

<!-- COMPLETAR: especificar el rol si este proyecto formó parte de un equipo o contexto laboral/freelance más amplio (el historial de git solo muestra un autor, consistente con proyecto individual). -->

## Licencia

MIT — ver [LICENSE](LICENSE).
