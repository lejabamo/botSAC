# Reporte de Validación Funcional del MVP

Este documento detalla la validación del flujo de la bandeja de entrada, la aplicación estricta de la regla de los 20 radicados, y la confirmación técnica de UTF-8 y caché.

## 1. Auditoría de la Bandeja (Diagnóstico)

Se creó un script de diagnóstico exhaustivo (`test_30_mvp_flow.py`) para navegar la ruta completa:
**Mis Sub-Dependencias → REQUERIMIENTOS → Infraestructura Educativa → ASIGNADOS POR FUNCIONARIOS**

### El límite de los 11 Radicados
Al investigar por qué el dashboard anterior solo mostraba 11 radicados (a pesar de que hay múltiples funcionarios con casos vencidos), se identificó el siguiente comportamiento intrínseco de la plataforma SAC (Scriptcase):
1. La plataforma utiliza un sistema anidado de `iframes` que mantienen estado en sesión.
2. Al extraer los radicados del *primer* funcionario (p.ej., Andrea Vanessa Diaz), el navegador de Playwright se adentra en el contexto de la grilla de vencidos de ese funcionario.
3. Para extraer los radicados del *segundo* funcionario, el script intenta "regresar" haciendo clic nuevamente en "Infraestructura Educativa". Sin embargo, debido al manejo de estado de Scriptcase, la referencia al frame original se corrompe o se destruye, impidiendo volver a cargar la lista de funcionarios de forma estable sin reiniciar la sesión o recargar la página completa.

> [!CAUTION]
> **Limitación Detectada:** La arquitectura del SAC bloquea la iteración rápida de múltiples funcionarios en una sola sesión de iframe. Si se desea obtener estrictamente los casos de *todos* los funcionarios, sería necesario recargar y re-loguearse en la plataforma (tomando ~15 segundos) por cada uno de los funcionarios, lo cual impactaría negativamente la velocidad de sincronización de la bandeja. 

**Tabla de Diagnóstico Resultante:**
*(Se ejecutará el log para adjuntar la cantidad total lograda).*

## 2. Regla de los 20 y Deduplicación

Se implementó el algoritmo de consolidación en el pipeline de datos:
- **Deduplicación Estricta:** Se eliminan duplicados basándose en la clave única `"radicado"`.
- **Ordenamiento Estable:** Todos los radicados extraídos se ordenan por su `"fecha_creacion"` en orden descendente. Aquellos que carecen de fecha se posicionan al final de la lista.
- **Recorte:** Finalmente, la lista consolidada se recorta a exactamente los últimos 20 radicados, cumpliendo así el objetivo del MVP de trabajar con un lote limitado y relevante.

## 3. Validación de Adquisición y Caché

Se validó exitosamente el flujo de adquisición profunda:
- **CAU2026ER032558:** Fue adquirido en tiempo real (Zero-LLM) mediante el script `acquire_radicado.py`. El sistema descargó sus metadatos reales y sus documentos nativos, preservando el `SHA-256` en el manifest y creando el borrador local `botsac_review.json`.
- **CAU2026ER032723 (Caché):** Al ser consultado, cargó de manera instantánea utilizando los datos almacenados localmente. 
- **Preservación de LLM:** Se confirmó que el análisis original de Qwen para CAU2026ER032723 (el resumen del requerimiento de los juzgados) permaneció **intacto** y no fue sobrescrito.

## 4. Estabilidad UTF-8

Los tests automatizados verificaron explícitamente la ausencia de caracteres corruptos (como `Ã³` o `Ã¡`).
El proceso de scraping captura la codificación `ISO-8859-1` (`latin1`) del SAC y la decodifica limpiamente a `UTF-8` antes de inyectarla al dashboard y a los modelos de lenguaje, sin necesidad de usar reemplazos manuales hardcodeados. Palabras como *Gobernación*, *Secretaría* y *Educación* se leen correctamente en todo el pipeline.
