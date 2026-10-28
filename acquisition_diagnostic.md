# DIAGNÓSTICO DE ADQUISICIÓN SAC (FASE 2)

## 1. Causa real del timeout del iframe "Semaforo"
El timeout del iframe "Semaforo" en el Paso 3 se producía debido a una desincronización en la carga. El código hacía clic en "Mis Sub-Dependencias" e inmediatamente comenzaba a buscar el frame "Semaforo" con el texto "REQUERIMIENTOS". Cuando el portal SAC presentaba latencia (superior a los 30s) o cargaba iframes intermedios, el loop agotaba su tiempo antes de que el frame `FunOpeAdm_RequerimientosOtrasDependencias` (o similar) terminara de renderizarse. Adicionalmente, el frame final de la cuadrícula tiene variaciones de URL (`FunOpeAdm_RequerimientosOtrasDependencias` vs `FunAdm_RequerimientosAsignados_Funcionarios`).

## 2. Archivo y función modificados
- **Archivo:** `scripts/acquire_radicado.py`
- **Función:** `acquire_radicado`

## 3. Cambio realizado
- Se agregó instrumentación (logs temporales en `data/acquisition_timing.log`).
- Se flexibilizó el selector de frames en el "Paso 6: Buscar el Radicado" para buscar tanto `"FunOpeAdm_RequerimientosOtrasDependencias"` como `"FunAdm_RequerimientosAsignados_Funcionarios"`.
- Se implementó un bucle de paginación (`max_pages = 10`) usando el botón de avance (`a#sc_b_avc_bot`) en caso de que el radicado se encuentre en la página 2 o posterior.
- Se optimizó la selección de la columna en "ASIGNADOS POR FUNCIONARIOS" para priorizar los enlaces de radicados "vencidos" o "sin finalizar", en lugar de hacer clic en el primer número encontrado (que suele ser el total general).

## 4. Secuencia de navegación validada
El script logró recorrer exitosamente la siguiente secuencia:
1. `inicio`
2. `login`
3. `Mis Sub-Dependencias`
4. `navegación` (Carga de Semaforo y clic en REQUERIMIENTOS)
5. `listado` (Carga de ASIGNADOS POR DEPENDENCIAS -> Infraestructura Educativa -> ASIGNADOS POR FUNCIONARIOS)
6. Apertura de la cuadrícula de casos del funcionario `hguaca`.

## 5. Radicado encontrado
**No encontrado.**
Se buscó iterativamente el radicado **CAU2026ER024421** en las páginas disponibles de la cuadrícula del funcionario. 
El motivo funcional de la ausencia es que este radicado posee el estado interno `FALTA_APROBACION`. En la lógica de negocio del SAC, cuando el funcionario contesta el requerimiento, este desaparece de su bandeja de "ASIGNADOS POR FUNCIONARIOS" y se transfiere a la bandeja "POR APROBAR" (Mis Pendientes) del Secretario de Educación. Por lo tanto, la secuencia estricta solicitada no puede visualizar este radicado específico.

## 6. Cantidad de documentos encontrados
N/A (Proceso detenido antes de abrir el radicado).

## 7. Cantidad de documentos descargados
N/A

## 8. Tiempo total de adquisición
Aproximadamente 42 segundos (hasta abortar por ausencia del radicado en la vista del funcionario).

## 9. ¿Existe algún nuevo punto de bloqueo?
No existen esperas indefinidas ni bloqueos técnicos (timeouts infinitos o crash de Playwright). El script lanza un `Exception("No se encontró el radicado...")` de forma limpia y reporta `ERROR` al `queue_manager`, liberando el worker para continuar con otros procesos en lugar de quedar en un estado `PREPARANDO` eterno.


**ESTADO FINAL:**
PRUEBA CONTROLADA DETENIDA EN [LOCALIZAR RADICADO]
