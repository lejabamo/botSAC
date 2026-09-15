# Objetivo: BOTSAC / FUNDACIÓN SEGURA + PRIMER VERTICAL SLICE REAL

Este plan reemplaza las iteraciones anteriores en Node.js y establece la nueva base tecnológica en **Python 3.12+**, utilizando **Playwright**, **pytest**, y **Streamlit**. Se seguirá una metodología estricta de validación paso a paso para asegurar la integridad, seguridad (solo lectura) y trazabilidad, tal como fue requerido.

## User Review Required

> [!IMPORTANT]
> Se eliminarán los archivos y directorios de la prueba anterior en Node.js (`package.json`, `package-lock.json`, `node_modules`, `src/`, y archivos JS en `scripts/`) ya que entraremos de lleno en la arquitectura de Python.
> 
> Confirmaré la existencia del archivo `.env` local para asegurar que las credenciales no sean expuestas ni manipuladas.

## Open Questions

Ninguna por el momento. Avanzaremos ejecutando y validando los tests enumerados.

## Proposed Changes

### 1. Limpieza del Entorno Anterior
- **[DELETE]** `package.json`
- **[DELETE]** `package-lock.json`
- **[DELETE]** `node_modules/`
- **[DELETE]** `src/` (y su contenido Node)
- **[DELETE]** scripts de Node antiguos.

### 2. Creación del Entorno Virtual y Dependencias
- Creación de entorno `.venv` utilizando Python 3.12+.
- Instalación de dependencias base: `playwright`, `pytest`, `pytest-playwright`, `python-dotenv`, `streamlit`.
- Generación de `requirements.txt`.
- Instalación de navegadores Playwright (`playwright install chromium`).

### 3. Estructura del Monolito Modular
Se creará la siguiente estructura de directorios en `C:\Users\jefes\OneDrive\Desktop\botSAC`:
```text
botSAC/
├── app/
│   └── dashboard.py
├── botsac/
│   ├── config/
│   ├── security/
│   ├── logging/
│   ├── sac/
│   │   ├── client/
│   │   ├── auth/
│   │   ├── navigation/
│   │   ├── radicados/
│   │   └── documents/
│   ├── ingestion/
│   ├── storage/
│   ├── analysis/
│   └── models/
├── scripts/
│   └── acquire.py
├── data/
│   ├── raw/
│   ├── documents/
│   ├── ingested/
│   ├── analysis/
│   ├── manifests/
│   ├── state/
│   └── logs/
├── tests/
├── .gitignore
├── requirements.txt
└── README.md
```

### 4. Implementación y Pruebas Paso a Paso
El desarrollo se guiará estrictamente por la secuencia de los 19 Tests indicados en el prompt. No se avanzará a un test sin haber asegurado el anterior.

* **TEST 0 & 1:** Python + virtualenv funcionando y Playwright funcional.
* **TEST 2 & 3:** Apertura del portal SAC y selección de "SE CAUCA".
* **TEST 4 & 5:** Login real y verificación del panel autenticado (Action Guard Activo: Solo lectura).
* **TEST 6 a 10:** Navegación por dependencias (Mis Sub-Dependencias -> Infraestructura Educativa -> Funcionarios -> Vencidos).
* **TEST 11 a 13:** Apertura del primer radicado, extracción de metadata y contenido de solicitud.
* **TEST 14 a 16:** Identificación y descarga de documentos reales, y cálculo de SHA-256.
* **TEST 17 a 19:** Persistencia (expediente y `manifest.json`) y verificación de integridad de solo lectura.

### 5. Interfaz Streamlit
Desarrollo de `app/dashboard.py` (Streamlit) en modo de solo lectura (consumiendo archivos locales) para visualizar el expediente descargado (Acquisition ID, Radicado, Metadata, Documentos).

## Verification Plan

### Automated Tests
- Se utilizará `pytest` para verificar los **TEST 0 a 19** secuencialmente. 
- Cada prueba dejará un registro (`[ACTION_BLOCKED]`, `[LOGIN]`, `[NAVIGATION]`, etc.) según las reglas establecidas.

### Manual Verification
- Comprobaremos mediante la interfaz de Streamlit local que los datos extraídos (metadata y documentos) corresponden al portal sin haber modificado la fuente original (Regla de Solo Lectura).
- Verificaremos el `manifest.json` y los reportes de logging para confirmar que no se realizó ninguna acción mutativa (Security Guard).
