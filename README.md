# AMEFIBRA Índice FIBRAS — Notebook de extracción y análisis

Notebook de Jupyter (con su equivalente en script `.py`) que extrae el Índice FIBRAS de AMEFIBRA en tiempo real, consulta el listado de emisoras, descarga el historial de dividendos de cada FIBRA vía `yfinance` y genera una ficha de rendimiento anual (dividendos + variación de capital) por ticker.

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
- **Exportación:** [openpyxl](https://openpyxl.readthedocs.io/) (Excel `.xlsx`), CSV nativo de pandas, HTML para la ficha de rendimiento
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
│   ├── procesamiento.py           # Normalización y transformación de los DataFrames (snake_case, tipos, periodicidad)
│   └── presentacion.py            # Despliegue en notebook y exportación a CSV/XLSX/HTML, selectores interactivos
├── output/                        # Generado en cada corrida (CSV/XLSX/HTML); no versionado, ver .gitignore
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

Cada corrida relevante queda archivada en `output/` (CSV del índice, CSV de emisoras, CSV de dividendos y ficha HTML de rendimiento), con nombre `AAAAMMDD_HHMMSS_descripción` para no sobrescribir corridas anteriores.

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

<!-- COMPLETAR: agregar trade-offs adicionales que solo el autor conoce, por ejemplo: por qué Playwright y no Selenium/Puppeteer, por qué lanzar un navegador nuevo por ejecución en vez de mantener una sesión persistente, o por qué no se cachean/persisten los datos entre corridas más allá del historial en output/. No se pudo inferir del código porque no hay comentarios ni commits que lo documenten. -->

## Estado del proyecto

Activo en proceso de desarrollo — historial de git con 17 commits hasta la fecha, actividad reciente centrada en migrar el script original a un notebook con `modules/` reutilizables, agregar la consulta de dividendos/ficha de rendimiento y el fallback de emisoras sin depender de AMEFIBRA.

## Autor / Rol

**Alex Zamudio** ([liazamudio@gmail.com](mailto:liazamudio@gmail.com)) — único autor y contribuidor registrado en el historial de git.

<!-- COMPLETAR: especificar el rol si este proyecto formó parte de un equipo o contexto laboral/freelance más amplio (el historial de git solo muestra un autor, consistente con proyecto individual). -->

## Licencia

MIT — ver [LICENSE](LICENSE).
