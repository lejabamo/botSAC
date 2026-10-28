# INFORME TÉCNICO: INGESTA LIVIANA SAC Y BANDEJA POR APROBAR EN ORACLE

**Proyecto:** BotSAC Enterprise  
**Fecha:** 2026-10-09  
**Esquema:** BOTSAC (Oracle AI Database 23ai institucional - `172.16.0.10:1521/pdb_dev.educauca.gov.co`)

---

## 1. Arquitectura Implementada

Se implementó un patrón de **Ingesta en Dos Fases (Two-Stage / Staged Lazy Ingestion)** que separa completamente la adquisición de metadatos de la bandeja frente al procesamiento documental pesado:

1. **Fase 1: Ingesta Liviana (Lightweight Sync):**
   * Automatización Playwright dirigida directamente a la bandeja central **"POR APROBAR"**.
   * Extracción en una sola pasada de la cuadrícula de datos visibles (sin abrir expedientes individuales, sin descargar documentos ni ejecutar conversiones pesadas).
   * Persistencia idempotente (`INSERT` o `UPDATE` selectivo) directo en la base de datos Oracle institucional (`SAC_RADICADOS`).
   * Tiempo de sincronización: **14 a 18 segundos** para la bandeja completa.

2. **Fase 2: Adquisición Pesada Asíncrona (Desacoplada):**
   * Los procesos de descarga de archivos Word/PDF, conversión COM, OCR y análisis con LLM (`acquire_radicado.py` y `analyze_radicado.py`) operan como workers independientes bajo demanda o por cola de prioridad.
   * La consulta y navegación en la bandeja de usuario nunca se bloquea esperando descargas pesadas.

```
   [Portal SAC Institucional]
              │
              ▼ (Playwright - Lectura rápida de cuadrícula: ~2.5s)
   [Normalización de Metadatos]
              │
              ▼ (SQLAlchemy / Thick Mode: ~0.67s)
   [Oracle Database (SAC_RADICADOS)]
              ▲
              │ (Consulta agregada en una sola pasada: ~6.8ms)
   [FastAPI: GET /api/inbox]
              ▲
              │ (HTTP JSON Contract)
   [Frontend React / Vite (Dashboard)]
```

---

## 2. Archivos Modificados y Creados

| Archivo | Acción | Propósito |
| :--- | :--- | :--- |
| `backend/oracle_service.py` | Creado | Capa de servicio Oracle: persistencia idempotente (`persist_radicados_lightweight`), consulta agregada rápida de bandeja (`get_inbox_from_oracle`) y detalle (`get_radicado_detail_from_oracle`). |
| `scripts/sync_sac_por_aprobar_lightweight.py` | Creado | Automatización ligera con Playwright de la vista institucional "POR APROBAR", con paginación, métricas de tiempo y persistencia directa. |
| `app/services.py` | Modificado | Conectado a Oracle como **Fuente Primaria de Verdad** para `get_inbox_data()` y `get_radicado_detail()`, manteniendo respaldo local en caso de desconexión. |
| `app/api.py` | Modificado | Conectado a Oracle vía `services` y añadido endpoint `POST /api/sync/lightweight`. |
| `data/oracle_lightweight_sync.log` | Creado | Registro de auditoría independiente de ejecución sin credenciales ni datos sensibles. |
| `.gitignore` | Modificado | Ignorado el directorio binario `instantclient/`. |

---

## 3. Tablas y Campos Oracle Utilizados

Se utilizó estrictamente el esquema DDL institucional existente sin alterar tablas, restricciones ni tipos de datos:

### Tabla Principal: `SAC_RADICADOS`
* `ID_RADICADO`: Identificador único institucional (PK, ej. `CAU2026ER032853`).
* `ASUNTO`: Asunto administrativo reportado en la cuadrícula de SAC.
* `CODIGO_DANE_MUNICIPIO` / `MUNICIPIO_HISTORICO`: Localización administrativa reportada.
* `NOMBRE_FUNCIONARIO_HIST`: Nombre del funcionario asignado en la cuadrícula (ej. `jclopez`, `y.anacona`, `gmacias`).
* `ID_USUARIO_ASIGNADO`: Llave foránea a `SAC_USUARIOS`. Se mantiene en `NULL` respetando la integridad referencial si el usuario institucional no existe en la tabla de usuarios.
* `REMITENTE`: Ciudadano o institución solicitante (columna *Ciudadano* en SAC).
* `CATEGORIA`: Tipo de requerimiento (columna *Tipo de Requerimiento* en SAC).
* `FECHA_CREACION`: Timestamp de creación administrativa.
* `FECHA_VENCIMIENTO`: Timestamp de vencimiento administrativo.
* `ESTADO_SAC`: Estado administrativo institucional (`POR APROBAR` / `EN TRAMITE`).
* `ESTADO_BOTSAC`: Estado interno de BotSAC (`PENDIENTE`), respetando la restricción `CHK_ESTADO_BOTSAC IN ('PENDIENTE', 'PREPARANDO', 'LISTO', 'ERROR')`.
* `ES_VENCIDO`: Indicador booleano numérico (0 / 1).
* `CREATED_AT` / `UPDATED_AT`: Auditoría de tiempos.

### Tablas Relacionadas Consultadas para Métricas
* `SAC_DOCUMENTOS` (Conteo de documentos asociados; retorna 0 si no hay documentos descargados).
* `SAC_HALLAZGOS` (Conteo de hallazgos; retorna 0 sin análisis).
* `SAC_ALERTAS` (Conteo de alertas activas; retorna 0 sin análisis).
* `SAC_SEDES_AFECTADAS` (Conteo de sedes identificadas).

---

## 4. Flujo Real de Sincronización

1. **Autenticación:** Login en el portal oficial SAC seleccionando entidad `SE CAUCA`.
2. **Cierre de Modales:** Descarte automático de mensajes institucionales emergentes.
3. **Navegación Directa:** Clic en el enlace/resumen **"POR APROBAR"** del Dashboard principal.
4. **Localización de Cuadrícula:** Detección del iframe de ScriptCase con encabezados `RADICADO`, `FECHA CREACIÓN`, `CIUDADANO`, `TIPO DE REQUERIMIENTO`, `ASUNTO`, `FECHA VENCIMIENTO`, `FUNCIONARIO ASIGNADO`, `DÍAS DE PLAZO`.
5. **Lectura Inmediata:** Extracción de las 21 filas de la cuadrícula sin entrar al detalle de cada expediente.
6. **Normalización:** Limpieza de texto, corrección de codificación Latin-1/UTF-8 y parseo de fechas a timestamps.
7. **Persistencia Idempotente:** Inserción y actualización segura en `SAC_RADICADOS`.
8. **Cierre Seguro:** Destrucción del contexto y proceso del navegador Chromium.

---

## 5. Contrato de API Preservado

El endpoint `GET /api/inbox` mantiene con absoluta fidelidad la estructura esperada por el frontend de React (`InboxResponse`):

```json
{
  "updated_at": "2026-10-09 18:05:02",
  "summary": {
    "pending_sac": 21,
    "ready": 0,
    "preparing": 0,
    "error": 0
  },
  "items": [
    {
      "radicado": "CAU2026ER032853",
      "asunto": "INFORME AFECTACION",
      "municipio": "Cauca",
      "funcionario": "jclopez",
      "remitente": "INSTITUCION EDUCATIVA INSTITUTO NACIONAL MIXTO...",
      "categoria": "PETICIÓN",
      "fecha_creacion": "19/08/2026",
      "dias_plazo": "VENCIDO (30 d)",
      "estado_sac": "POR APROBAR",
      "estado_botsac": "PENDIENTE",
      "is_vencido": false,
      "resumen_preview": "Radicado sincronizado desde SAC. Listo para revisión o adquisición profunda.",
      "sedes_count": 0,
      "etapa_tramite": "FALTA_APROBACION",
      "etapa_label": "Por Aprobar (Revisión)",
      "respuesta_actual": "",
      "stats": {
        "docs_count": 0,
        "hallazgos_count": 0,
        "alerts_count": 0
      }
    }
  ]
}
```

---

## 6. Pruebas Ejecutadas y Resultados

| Prueba | Objetivo | Resultado |
| :--- | :--- | :--- |
| **Prueba 1: Conexión Oracle** | Verificar conectividad a Oracle AI Database y presencia de las 17 tablas institucionales. | **PASÓ** (17 tablas verificadas en Thick Mode). |
| **Prueba 2: Consulta de Bandeja** | Validar que `GET /api/inbox` retorne el JSON esperado leyendo desde Oracle. | **PASÓ** (21 registros devueltos, estructura 100% compatible). |
| **Prueba 3: Sincronización Real** | Ejecutar extracción real contra el portal SAC institucional y persistir. | **PASÓ** (21 radicados leídos y persistidos en 18.8s). |
| **Prueba 4: Idempotencia** | Reejecutar la sincronización sobre los mismos registros. | **PASÓ** (Leídos: 21, Insertados: 0, Actualizados: 21, Cero duplicados). |
| **Prueba 5: Paginación** | Control de avance de página y límites máximos. | **PASÓ** (Manejo de selectores `sc_b_avc_bot`). |
| **Prueba 6: API y React** | Compilación de TypeScript (`tsc -b && vite build`) y endpoints. | **PASÓ** (Build en 1.51s, 0 errores tipográficos). |
| **Prueba 7: Rendimiento** | Medición de tiempos de respuesta del endpoint vs meta de 500ms. | **PASÓ** (Latencia del endpoint en pool caliente: **6.8 ms**). |
| **Prueba 8: Errores y Recuperación**| Validar 404 en radicados inexistentes y descarte de registros inválidos. | **PASÓ** (404 validado, descartes controlados sin fallos). |

---

## 7. Comparación de Radicados SAC frente a Oracle

Muestra de los 21 radicados extraídos directamente de la bandeja real institucional y verificados en Oracle:

| Radicado SAC | Asunto Extraído | Funcionario Asignado | Fecha Creación | Estado SAC | Estado BotSAC en Oracle |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CAU2026ER032853` | INFORME AFECTACION | jclopez | 2026-08-19 | POR APROBAR | PENDIENTE |
| `CAU2026ER032840` | Afectaciones en infraestructura ? Sedes | jclopez | 2026-08-19 | POR APROBAR | PENDIENTE |
| `CAU2026ER032637` | Informacion daños por sismo | y.anacona | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032630` | REPORTE AFECTACIONES EN LA INFRAESTRUCTURA | jclopez | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032552` | REPORTES AFECTACIONES TEMBLOR EN IE Y CE | gmacias | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032550` | Reporte afectaciones a causa de sismo 10 | gmacias | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032534` | Adjunto envío oficio reporte daños por t | gmacias | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032498` | Reporte de daños en infraestructura educ | y.anacona | 2026-08-18 | POR APROBAR | PENDIENTE |
| `CAU2026ER032462` | INFORME DE DAÑOS EN INFRAESTRUCTURA EN L | gmacias | 2026-08-17 | POR APROBAR | PENDIENTE |
| `CAU2026ER032369` | informe sobre la infraestructura por cau | y.anacona | 2026-08-14 | POR APROBAR | PENDIENTE |

---

## 8. Tiempos Medidos

* **Login SAC institucional:** 9.40 s – 9.69 s
* **Navegación a vista "POR APROBAR":** 1.35 s – 1.70 s
* **Extracción de cuadrícula (21 radicados):** 2.40 s – 2.51 s
* **Normalización de metadatos:** < 0.01 s
* **Persistencia en Oracle (Batch SQL):** 0.67 s – 0.69 s
* **Tiempo total de sincronización completa:** **14.58 s – 18.80 s** *(Frente a los 6–10 minutos anteriores)*
* **Tiempo de respuesta de `GET /api/inbox` desde Oracle:**
  * Conexión inicial en frío: 828 ms
  * Con pool caliente: **6.8 ms** *(Meta: < 500 ms; Superada con creces)*

---

## 9. Errores Encontrados y Soluciones

1. **Cifrado de Red Nativo de Oracle (NNE):**
   * *Error:* `DPY-3001: Native Network Encryption and Data Integrity is only supported in python-oracledb thick mode`.
   * *Solución:* Se descargó y configuró Oracle Instant Client local (`instantclient_19_32`), inicializando `oracledb.init_oracle_client()` en modo Thick.
2. **Identificador de Servicio vs SID:**
   * *Error:* `ORA-12505: TNS:listener does not currently know of SID`.
   * *Solución:* Se especificó explícitamente `?service_name=pdb_dev.educauca.gov.co` en la URL de SQLAlchemy.
3. **Casing de Columnas en SQLAlchemy Cursor:**
   * *Error:* `NoSuchColumnError` al buscar claves en mayúsculas como `row.ID_RADICADO`.
   * *Solución:* Mapeo mediante `dict(row._mapping)` normalizando a minúsculas según la convención del dialecto de SQLAlchemy.

---

## 10. Limitaciones Pendientes

* La ingesta liviana adquiere los metadatos de cabecera. La descarga de anexos físicos y el análisis OCR/LLM se ejecutan en la Fase 2 bajo demanda cuando el usuario selecciona un radicado.

---

## 11. Confirmación de No Escritura en SAC

> **CERTIFICACIÓN DE INTEGRIDAD:**  
> Se confirma de manera explícita que durante todas las fases de sincronización, automatización y pruebas:
> 1. No se ejecutó ninguna acción de aprobación, rechazo, respuesta, reasignación o cambio de estado en el sistema SAC.
> 2. No se escribieron textos ni se enviaron formularios institucionales en SAC.
> 3. La navegación fue estrictamente de lectura sobre la cuadrícula pública del portal.
> 4. No se alteró el esquema DDL ni las estructuras relacionales de Oracle Database.
