git# AMEFIBRA Índice FIBRAS Scraper

Herramienta de línea de comandos que extrae el Índice FIBRAS de AMEFIBRA en tiempo real y lo entrega como tabla en consola, CSV o Excel, para analistas e inversionistas que necesitan estos datos fuera del navegador.

<!-- COMPLETAR: agregar un GIF o captura de pantalla mostrando la ejecución del script en consola (por ejemplo, grabando `python amefibra-indice.fibras.py` corriendo y su salida). No se pudo generar automáticamente porque requiere una grabación de pantalla. -->

## Problema / Motivación

La tabla de indicadores del Índice FIBRAS no viene en el HTML de la página de AMEFIBRA: está incrustada en un `<iframe>` que arma la tabla vía JavaScript y actualiza los precios en tiempo real por WebSocket (con ~20 minutos de retraso, según el propio sitio). Una petición HTTP simple (`requests.get`) solo trae la plantilla vacía, sin datos, por lo que se necesita un navegador real para renderizarla y poder extraerla de forma automatizada.

## Demo

<!-- COMPLETAR: no hay una versión en vivo desplegada (es un script de CLI, no una app web). Si se desea, agregar aquí un GIF o capturas de la salida en consola / archivos CSV-Excel generados. -->

## Stack técnico

- **Lenguaje:** Python 3
- **Automatización de navegador:** [Playwright](https://playwright.dev/python/) (Chromium headless) — para esperar el WebSocket y renderizar la tabla
- **Procesamiento de datos:** [pandas](https://pandas.pydata.org/) + [lxml](https://lxml.de/) (parseo de la tabla HTML renderizada)
- **Exportación:** [openpyxl](https://openpyxl.readthedocs.io/) (Excel `.xlsx`), CSV nativo de pandas
- **Base de datos:** No aplica — el script no persiste datos, solo exporta a archivo local
- **Infraestructura/Deploy:** No aplica — script de CLI de ejecución local, sin pipeline de CI/CD ni despliegue configurado en el repositorio

## Características principales

- Localiza automáticamente el `<iframe>` correcto de la tabla de indicadores entre los tres que expone la página (tabla, gráfica y marquesina)
- Espera activamente a que lleguen datos en vivo por WebSocket antes de leer la tabla, con timeout configurable (`--timeout`)
- Limpia encabezados de columna (quita flechas de ordenamiento `↑↓` y espacios sobrantes)
- Descarta columnas totalmente vacías (p. ej. el ícono de tendencia)
- En cada corrida archiva automáticamente un CSV "analítico" en `output/`, con nombre `AAAAMMDD_HHMMSS_indice_fibras_amefibra.csv`: encabezados en snake_case, porcentajes como `float`, y columnas `fecha_hora_extraccion`/`fuente_datos` para trazabilidad — listo para pandas/R/BI sin limpieza adicional
- Además, exporta a CSV (`utf-8-sig`, compatible con Excel) y/o XLSX con nombre y ruta a elección en la misma corrida (`--csv`, `--xlsx`)
- Modo con navegador visible (`--show-browser`) para depurar el scraping visualmente
- Solo lee información pública ya publicada en la página, sin credenciales ni endpoints privados

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

# 5. Ejecutar el script
python amefibra-indice.fibras.py
```

Variables de entorno: no aplica — el script no requiere configuración por variables de entorno ni credenciales.

### Opciones de ejecución

```bash
# Imprime la tabla en consola
python amefibra-indice.fibras.py

# Además guarda CSV y/o Excel
python amefibra-indice.fibras.py --csv indice_fibras.csv --xlsx indice_fibras.xlsx

# Muestra la ventana del navegador (útil para depurar)
python amefibra-indice.fibras.py --show-browser

# Ajusta cuánto esperar (en ms) a que lleguen datos en vivo (default: 30000)
python amefibra-indice.fibras.py --timeout 45000
```

| Argumento | Descripción |
|---|---|
| `--csv ARCHIVO.csv` | Ruta donde guardar un CSV (opcional) |
| `--xlsx ARCHIVO.xlsx` | Ruta donde guardar un Excel (opcional) |
| `--show-browser` | Corre con el navegador visible en vez de headless |
| `--timeout MS` | Milisegundos a esperar los datos en vivo (default: `30000`) |

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
venv/Scripts/python.exe amefibra-indice.fibras.py
```

## Decisiones técnicas relevantes

- **Playwright en vez de `requests`:** la tabla se renderiza vía JavaScript y WebSocket del lado del cliente, así que una petición HTTP simple solo devuelve la plantilla vacía. Se necesita un navegador real (aunque sea headless) para esperar a que los datos lleguen antes de leer el DOM.
- **`pd.read_html` sobre `io.StringIO`:** pandas ya no acepta de forma confiable un string de HTML crudo pasado directo a `read_html()` (lo puede interpretar como ruta de archivo); se envuelve explícitamente en `io.StringIO` para evitar ese comportamiento.

<!-- COMPLETAR: agregar trade-offs adicionales que solo el autor conoce, por ejemplo: por qué Playwright y no Selenium/Puppeteer, por qué lanzar un navegador nuevo por ejecución en vez de mantener una sesión persistente, o por qué no se cachean/persisten los datos entre corridas. No se pudo inferir del código porque no hay comentarios ni commits que lo documenten. -->

## Estado del proyecto

<!-- COMPLETAR: confirmar si el proyecto está Activo, Mantenido o Archivado. Basado en el historial de git, la última actividad registrada es el commit "d45abb9 Implementación de LICENSE y README" (repositorio con 3 commits en total, sin CHANGELOG.md); no se puede inferir el estado de mantenimiento real ni la intención a futuro solo del historial. -->

Activo en proceso de desarrollo.

## Autor / Rol

**Alex Zamudio** ([liazamudio@gmail.com](mailto:liazamudio@gmail.com)) — único autor y contribuidor registrado en el historial de git.

<!-- COMPLETAR: especificar el rol si este proyecto formó parte de un equipo o contexto laboral/freelance más amplio (el historial de git solo muestra un autor, consistente con proyecto individual). -->

## Licencia

MIT — ver [LICENSE](LICENSE).
