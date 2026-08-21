# Índice FIBRAS — AMEFIBRA Scraper

Script en Python que extrae la tabla del **Índice FIBRAS** publicada por
[AMEFIBRA](https://amefibra.com/el-mercado/indice-fibras/) (Asociación Mexicana
de FIBRAs Inmobiliarias y de Infraestructura) y la deja lista para usarse como
`DataFrame` de pandas, CSV o Excel.

## ¿Por qué no basta con `requests.get(...)`?

La tabla de indicadores no viene en el HTML de la página. Está incrustada en un
`<iframe>` que apunta a `amefibra.edimex.com.mx/Emisora/Reportes`, y esa página
arma la tabla vía JavaScript y actualiza los precios en tiempo real por
WebSocket (dato con ~20 minutos de retraso, según el propio sitio). Una
petición HTTP simple solo trae la plantilla vacía, sin datos.

Por eso este script usa **Playwright** para abrir la página en un navegador
real (headless), esperar a que el WebSocket llene la tabla, y luego extraer
esa tabla ya renderizada con **pandas**.

## Características

- Localiza automáticamente el iframe correcto entre los tres que expone la
  página (tabla de indicadores, gráfica y marquesina).
- Espera activamente a que lleguen datos en vivo antes de leer la tabla, con
  timeout configurable.
- Limpia encabezados (quita flechas de ordenamiento `↑↓` y espacios extra).
- Descarta columnas totalmente vacías (p. ej. el ícono de tendencia).
- Exporta a CSV (`utf-8-sig`, compatible con Excel) y/o XLSX.
- Modo visible (`--show-browser`) para depurar el scraping viendo el navegador.
- Solo lee información pública, sin credenciales ni endpoints privados.

## Requisitos

- Python 3.10 o superior.
- Google Chrome/Chromium (lo instala Playwright, ver abajo).

## Instalación

### 1. Crear y activar el entorno virtual

Si el proyecto aún no tiene un entorno virtual `venv`, créalo desde la raíz
del proyecto:

```powershell
python -m venv venv
```

Actívalo según tu shell:

```powershell
# PowerShell
.\venv\Scripts\Activate.ps1
```

```bat
:: cmd.exe
venv\Scripts\activate.bat
```

```bash
# Git Bash / WSL / Linux / macOS
source venv/Scripts/activate   # Windows (Git Bash)
source venv/bin/activate       # Linux / macOS
```

Al activarse correctamente, el prompt debe mostrar el prefijo `(venv)`.

> **El entorno no se activa o no lo reconoce el sistema (PowerShell)**
> Si `Activate.ps1` falla con un error de política de ejecución de scripts,
> habilita la ejecución para el usuario actual y vuelve a intentarlo:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> .\venv\Scripts\Activate.ps1
> ```
>
> Si el entorno se corrompió o quieres empezar de cero, elimínalo y créalo de
> nuevo:
> ```powershell
> Remove-Item -Recurse -Force venv
> python -m venv venv
> .\venv\Scripts\Activate.ps1
> ```
>
> Como alternativa, siempre puedes invocar el intérprete del `venv`
> directamente sin activarlo, tanto para instalar dependencias como para
> ejecutar el script:
> ```powershell
> venv\Scripts\python.exe -m pip install -r requirements.txt
> venv\Scripts\python.exe amefibra-indice.fibras.py
> ```

### 2. Instalar las librerías

Con el entorno activado:

```bash
pip install -r requirements.txt
```

### 3. Instalar el navegador de Playwright

Playwright necesita descargar su propio binario de Chromium (no usa el Chrome
del sistema):

```bash
playwright install chromium
```

## Uso

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

### Argumentos disponibles

| Argumento        | Descripción                                                          |
|-------------------|-----------------------------------------------------------------------|
| `--csv ARCHIVO.csv`   | Ruta donde guardar un CSV (opcional)                              |
| `--xlsx ARCHIVO.xlsx` | Ruta donde guardar un Excel (opcional)                            |
| `--show-browser`      | Corre con el navegador visible en vez de headless                |
| `--timeout MS`        | Milisegundos a esperar los datos en vivo (default: `30000`)       |

## Notas

- El sitio aclara que la información es solo para consulta/análisis, no como
  base para decisiones de inversión. Este script respeta eso: solo lee lo que
  ya se publica públicamente en la página, sin usar credenciales ni endpoints
  privados.
- Si AMEFIBRA/Economatica cambian el HTML o el proveedor de datos, el script
  puede requerir ajustes (ver la función `_extraer_html_tabla`).

## Licencia

Este proyecto está bajo la licencia MIT. Ver [LICENSE](LICENSE) para más
detalles.
