# Plan de Implementación: Validación Funcional del MVP (Prompt 30)

Este plan aborda la recolección íntegra de los 20 radicados, la deduplicación, la validación de UTF-8 y las pruebas de caché de adquisición profunda.

## 1. Auditoría de la Bandeja y Regla de los 20
El problema de obtener solo 11 radicados en el paso anterior se debió a que el script de automatización (`test_29`) perdía la referencia al marco de "ASIGNADOS POR FUNCIONARIOS" después de extraer los datos del primer funcionario (Andrea Vanessa). 
**Cambios propuestos:**
- Crear `tests/test_30_mvp_flow.py`.
- **Ruta estable:** Al iterar sobre los funcionarios, en lugar de usar referencias de marcos oxidadas, el script buscará *dinámicamente* el frame de `ASIGNADOS POR DEPENDENCIAS` y hará clic en "Infraestructura Educativa" en cada iteración para forzar la recarga limpia de la lista de funcionarios antes de hacer clic en el siguiente.
- Se recolectarán *todos* los radicados "SIN FINALIZAR" de todos los funcionarios.
- **Tabla de Diagnóstico:** Se imprimirá en consola un reporte detallado: `FUNCIONARIO | USUARIO | SIN FINALIZAR EN SAC | OBTENIDOS POR BOTSAC`.
- **Regla de los 20:** Una vez extraídos todos los radicados de la dependencia, se unificarán en una sola lista, se **deduplicarán** basándose estrictamente en la clave `"radicado"`, se ordenarán por fecha de creación descendente (si está disponible y parseable) y se recortarán a exactamente los últimos 20 pendientes. Se sobrescribirá `data/dashboard_inbox.json`.

## 2. Validación de Adquisición (CAU2026ER032558)
Dentro de `test_30_mvp_flow.py`, se incluirá un bloque para probar programáticamente el módulo de adquisición (`scripts/acquire_radicado.py`):
- Se ejecutará el script apuntando a `CAU2026ER032558`.
- Se afirmará (assert) que el documento PDF existe, que `manifest.json` guarda el `SHA-256`, y que `botsac_review.json` fue creado localmente.
- Se verificará que ninguna inferencia de Qwen fue invocada en el proceso (Zero-LLM).

## 3. Validación de Caché
El test verificará el comportamiento local:
- Se instanciará la lógica de `app/dashboard.py` (usando `load_radicado_data`) para `CAU2026ER032558` y `CAU2026ER032723`.
- Se comprobará que ambos devuelven información válida al instante, sin lanzar adquisiciones repetidas.
- Se confirmará que `CAU2026ER032723` preserva los resúmenes y análisis originales realizados en pasos previos (su metadata generada por LLM sigue viva).

## 4. Validación UTF-8
Se incluirán aserciones explícitas (`assert`) para verificar la existencia de palabras acentuadas correctamente en el JSON resultante:
- "Gobernación"
- "Educación"
Sin el uso de `replace()` manual, asegurando que la recodificación `latin1 -> utf-8` en la capa de Scraping es robusta.

## Open Questions

> [!NOTE]
> **Ordenamiento por Fecha:** En Scriptcase, el formato de fecha suele ser `DD/MM/YYYY`. El script parseará estas fechas a objetos `datetime` para realizar un ordenamiento descendente matemático antes de recortar a 20. ¿Deseas que los casos sin fecha (o con fecha errónea) se prioricen al principio o al final de la lista de 20? (Por defecto, los enviaré al final).

## Verification Plan
1. Ejecutar `pytest tests/test_30_mvp_flow.py -s`.
2. Analizar la salida en consola (la tabla de diagnóstico).
3. Verificar que `data/dashboard_inbox.json` contiene exactamente 20 elementos (o el máximo disponible si es menor a 20), sin duplicados, y con UTF-8 correcto.
4. Generar el reporte final en el `walkthrough.md` documentando el motivo real de la limitación anterior y detallando el éxito de la nueva extracción.
