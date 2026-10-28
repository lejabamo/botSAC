# Auditoría del Estado Actual y Reconciliación ETL — BotSAC Enterprise

**Fecha de Auditoría:** 15 de Octubre de 2026  
**Entorno:** Oracle 19c (esquema `BOTSAC` en `pdb_dev.educauca.gov.co`), FastAPI Backend (`http://127.0.0.1:8000`), React Vite Frontend (`http://localhost:5173`).  
**Artefacto Complementario:** `data/document_reconciliation_report.csv` (65 registros auditados).

---

## 1. Resumen Ejecutivo de la Auditoría

Se realizó una inspección exhaustiva de código, base de datos Oracle institucional, sistema de archivos local (`data/documents`, `data/analysis`, `data/raw`), registros de transacciones y componentes de interfaz.

El diagnóstico revela **cuatro hallazgos estructurales críticos** que originaban las discrepancias reportadas por el usuario:

1. **Discrepancia de Estados (Caso A - `CAU2026ER032828`):**  
   En la bandeja de trabajo, la tarjeta del radicado figuraba con `ESTADO_BOTSAC = 'LISTO'`, pero al ingresar al detalle se mostraba `⏳ RESPUESTA EN COLA DE EXTRACCIÓN` y `SIN RESPUESTA`.  
   *Causa Raíz:* La consulta de la bandeja (`get_inbox_from_oracle`) leía el estado directamente de `SAC_RADICADOS.ESTADO_BOTSAC` (donde figuraba 'LISTO' por una inserción previa), mientras que el endpoint de detalle (`get_radicado_detail_from_oracle`) tenía la clave `"respuesta_actual": ""` fijada en cadena vacía en lugar de consultar la tabla `SAC_RESPUESTAS`. Al recibir cadena vacía en un radicado `POR APROBAR`, el componente React `DetailPage.tsx` mostraba la etiqueta de espera.

2. **Inexistencia Física del PDF de Respuesta (Caso B):**  
   Para los 20 radicados en estado `POR APROBAR`, existían registros en Oracle `SAC_DOCUMENTOS` titulados `OFICIO_RESPUESTA_{radicado}.pdf` con un hash sintético y `UBICACION_FISICA = NULL`. Dichos archivos **nunca fueron descargados físicamente del portal SAC institucional**. Al intentar abrirlos en el visor de documentos, el backend respondía con error `404: Archivo visualizable no encontrado`.

3. **Límite Aparente de 33 Radicados en Bandeja (Caso C):**  
   La bandeja de BotSAC mostraba 33 radicados activos (20 en `POR APROBAR` + 13 en `EN TRAMITE`), a pesar de que el portal institucional SAC registraba 39 casos en la sección "POR APROBAR".  
   *Causa Raíz:* En `scripts/sync_sac_por_aprobar_lightweight.py`, la cuadrícula de ScriptCase pagina de a 20 registros (`[1 a 20 de 39]`). El selector de paginación `next_btn` no coincidía con el enlace de avance de ScriptCase en el DOM, provocando que la ingesta liviana se detuviera tras procesar únicamente la página 1 (20 registros), omitiendo los 19 casos de la página 2.

4. **Multiplicación de Documentos por Reintentos (Caso D - `CAU2026ER032558`):**  
   El radicado `CAU2026ER032558` mostraba 9 documentos en lugar de los 3 reales del SAC.  
   *Causa Raíz:* En `scripts/acquire_radicado.py`, la rutina de guardado ejecutaba `while os.path.exists(local_path): counter += 1`. Al reintentar o re-ejecutar la descarga sobre la misma carpeta, los archivos preexistentes no se reutilizaban ni sobrescribían, sino que se renombraban secuencialmente como `_1.pdf` y `_2.pdf`. Una migración posterior insertó cada archivo físico en Oracle `SAC_DOCUMENTOS`, inflando el conteo a 9 registros idénticos por triplicado.

---

## 2. Inspección de Archivos y Componentes

| Ruta de Archivo | Estado Físico | Rol e Inspección |
| :--- | :---: | :--- |
| `scripts/acquire_radicado.py` | Presente (33.7 KB) | Script Playwright de adquisición profunda. Presentaba acumulación de sufijos `_1`, `_2` en re-ejecuciones. |
| `scripts/sync_inbox.py` | Presente (15.1 KB) | Sincronización histórica de bandeja general. |
| `scripts/sync_aprobaciones.py` | Presente (22.7 KB) | Extracción de casos por aprobar. Extraía texto HTML en span, pero no descargaba el PDF binario oficial de respuesta. |
| `scripts/analyze_radicado.py` | Presente (30.8 KB) | Pipeline de análisis documental, extracción de hechos y sedes. |
| `scripts/preprocess_worker.py` | Presente (4.2 KB) | Worker basado en SQLite local (`queue_manager.py`). No reportaba a la tabla Oracle `SAC_PROCESAMIENTO`. |
| `backend/database.py` | Presente (2.2 KB) | Configuración de SQLAlchemy con Oracle Instant Client Thick Mode. Optimizado recientemente con `pool_recycle=60` y `pool_pre_ping=True`. |
| `backend/oracle_service.py` | Presente (16.5 KB) | Consultas institucionales. Tenía omisión de `SAC_RESPUESTAS` en el detalle y conteo `COUNT(*)` sin deduplicación. |
| `backend/models.py` | Presente (10.4 KB) | Modelos ORM completos (`SAC_RADICADOS`, `SAC_DOCUMENTOS`, `SAC_DOCUMENTOS_DERIVADOS`, `SAC_EXTRACCIONES_DOCUMENTO`, `SAC_EVIDENCIAS`, `SAC_HALLAZGOS`, `SAC_RESPUESTAS`, `SAC_PROCESAMIENTO`, `SAC_TRAZABILIDAD`). |
| `app/api.py` | Presente (3.0 KB) | Endpoints FastAPI. Operativo en puerto 8000. |
| `app/services.py` | Presente (19.7 KB) | Capa intermedia de negocio y resolución de rutas de visualización PDF. |
| `frontend/src/pages/InboxPage.tsx` | Presente (27.2 KB) | Bandeja de trabajo React. Pestañas activas: *Todos los pendientes (33)*, *Por Aprobar (20)*, *No Diligenciados (13)*. |
| `frontend/src/pages/DetailPage.tsx` | Presente (14.2 KB) | Vista de expediente. Dependía de `respuesta_actual` para mostrar u ocultar la pre-respuesta. |
| `frontend/src/services/api.ts` | Presente (4.6 KB) | Cliente Axios/Fetch para FastAPI. |
| `frontend/src/types/index.ts` | Presente (2.2 KB) | Contratos TypeScript (`InboxItem`, `RadicadoDetail`, `DocumentItem`). |
| `db_oracle/oracle_dba_ddl.sql` | Presente (21.3 KB) | DDL oficial institucional emitido por el DBA. Intacto y preservado. |
| `oracle_dba_specification.md` | Presente (19.8 KB) | Especificación de arquitectura y persistencia de Oracle. |

---

## 3. Estado de la Persistencia Oracle (`BOTSAC`)

A la fecha de la auditoría:
- **`SAC_RADICADOS`:** 38 filas totales.
  - 20 con `ESTADO_SAC = 'POR APROBAR'` y `ESTADO_BOTSAC = 'LISTO'`.
  - 13 con `ESTADO_SAC = 'EN TRAMITE'` y `ESTADO_BOTSAC = 'LISTO'`.
  - 5 con `ESTADO_SAC = 'TRAMITADO'` (excluidos de la bandeja de trabajo activa).
- **`SAC_DOCUMENTOS`:** 65 filas registradas.
  - 43 documentos conciliados con archivo físico existente y hash verificado.
  - 22 documentos registrados lógicamente pero sin archivo físico descargado en disco (`DISCREPANCIA_SOLO_ORACLE`, correspondientes a los 20 placeholders `OFICIO_RESPUESTA_...pdf` y 2 oficios de prueba).
- **`SAC_DOCUMENTOS_DERIVADOS`:** 0 filas en Oracle (los PDFs derivados de `.doc` existen localmente en `data/analysis/` pero no habían sido sincronizados a la tabla de derivados).
- **`SAC_RESPUESTAS`:** 3 registros (`CAU2026ER024421`, `CAU2026ER032828`, y respuesta previa).
- **`SAC_PROCESAMIENTO`:** 0 filas (las etapas del pipeline no se persistían en Oracle).

---

## 4. Acciones Requeridas para el ETL Canónico (Plan de Implementación)

Conforme a las directrices de no destrucción y rigor institucional:

1. **Identidad Canónica e Idempotencia:**
   - La adquisición documental debe verificar por hash SHA-256 antes de crear cualquier copia física.
   - Si el archivo existe físicamente y su hash coincide con SAC, no se re-descarga.
   - Los archivos `.doc` convertidos a `.pdf` deben registrarse en `SAC_DOCUMENTOS_DERIVADOS` con su herramienta de conversión y hash derivado, nunca como adjunto original adicional.

2. **Recuperación del PDF Real de Respuesta (Bandeja Por Aprobar):**
   - Implementar la rutina Playwright verificable para la columna `RESPUESTA` en la cuadrícula de SAC "POR APROBAR".
   - Descargar el archivo PDF binario real que contiene la respuesta radicada por el funcionario.
   - Extraer su texto, validar que mencione el radicado actual y al funcionario asignado.
   - Persistir el PDF en `data/documents/.../` y registrar su texto en `SAC_RESPUESTAS`.

3. **Cálculo Canónico Unificado de Estados (Backend):**
   - Una única función de proyección en backend (`compute_radicado_state`) que evalúa: metadatos, documentos físicos, extracciones y respuesta válida.
   - Si a un radicado en `POR APROBAR` le falta el PDF de respuesta o su texto, su estado proyectado es `EN_PROCESO` o `PENDIENTE_RESPUESTA`, **nunca `LISTO`**.
   - Garantizar concordancia total: la bandeja y el detalle deben proyectar exactamente el mismo estado.

4. **Paginación Completa de SAC (Resolver 33 vs 39):**
   - Corregir el selector de avance de página en ScriptCase para leer todas las páginas o forzar la vista de 50 registros por página en la sesión institucional.

5. **Auditoría Continua y Bitácora:**
   - Todo avance se registrará en `data/etl_pipeline.log` y en `SAC_PROCESAMIENTO` sin tocar el DDL institucional.
