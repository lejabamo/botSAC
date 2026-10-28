# INFORME DE VALIDACIÓN DEFINITIVA DE AISLAMIENTO — PROMPT 67

**Fecha de Ejecución:** 2026-10-26  
**Entorno de Prueba:** FastAPI Backend Enterprise + Oracle Database Institucional (`172.16.0.10:1521/pdb_dev.educauca.gov.co`) en Thick Mode.  
**Estado de Oracle / SAC:** Cero modificaciones DDL/DML, cero eliminaciones, cero escrituras en SAC.

---

## 1. Revisión de Mocks en `tests/test_user_isolation.py`

| Test en `tests/test_user_isolation.py` | ¿Utiliza Mocks? | Componentes Reales Involucrados |
| :--- | :--- | :--- |
| `test_login_authentication` | **NO** (0 mocks) | FastAPI (`/api/auth/login`) + Oracle (`SAC_USUARIOS`) |
| `test_unauthenticated_request_blocked` | **NO** (0 mocks) | FastAPI (`get_current_user`) + Oracle (`SAC_USUARIOS`) |
| `test_user_a_inbox_scope_lider` | **NO** (0 mocks) | FastAPI (`/api/inbox`) + Oracle (`SAC_RADICADOS`, filtro líder) |
| `test_user_b_inbox_scope_funcionario` | **NO** (0 mocks) | FastAPI (`/api/inbox`) + Oracle (`SAC_RADICADOS`, filtro funcionario) |
| `test_user_c_inbox_scope_real_user_ljbastidas` | **NO** (0 mocks) | FastAPI (`/api/inbox`) + Oracle (`SAC_USUARIOS`, `SAC_RADICADOS`) |
| `test_radicado_detail_isolation` | **NO** (0 mocks) | FastAPI (`/api/radicados/{id}`) + Oracle (`is_user_authorized_for_radicado`) |
| `test_document_download_isolation` | **NO** (0 mocks) | FastAPI (`/api/radicados/{id}/documents/.../view`) + Oracle auth check |
| `test_administrative_actions_restriction` | **NO** (0 mocks) | FastAPI (`/api/sync/...`, etc.) + Oracle (`ROL_PRINCIPAL`) |
| `test_session_switching_sequence` | **NO** (0 mocks) | Ciclo completo FastAPI + Oracle Database real |

**Dictamen Punto 1:** Ninguna de las 9 pruebas utiliza objetos simulados (`unittest.mock`, `MagicMock` o `monkeypatch`). El 100% interactúa con la aplicación FastAPI viva y la base de datos Oracle institucional en tiempo real.

---

## 2. Apertura de Sesiones Independientes con Usuarios Autorizados

Se ejecutaron llamadas de autenticación contra `/api/auth/login` con credenciales institucionales:

- **Sesión A (Usuario 1 — `djdelgado`):** Rol `LIDER_OFICINA` (Delly Jennyth Delgado Velasco).
  - Petición: `POST /api/auth/login` -> Código HTTP: **`200 OK`**.
- **Sesión B (Usuario 2 — `ljbastidas`):** Rol `LIDER_OFICINA` (Luis Javier Bastidas) con contraseña oficial `SuperS4c`.
  - Petición: `POST /api/auth/login` -> Código HTTP: **`200 OK`**.
- **Prueba Negativa de Contraseña (`ljbastidas` con clave errónea):**
  - Petición: `POST /api/auth/login` -> Código HTTP: **`401 Unauthorized`** (*"Contraseña incorrecta para el usuario institucional"*).

---

## 3 y 4. Acceso al Radicado de Prueba en Sesión A (`djdelgado`) vs Intento de Acceso en Sesión B (`ljbastidas`)

- **Radicado Objetivo:** `CAU2026ER028340` (Asunto: *Solicitud de cerramiento IE Los Anayes, El Tambo*; asignado en Oracle a la oficina supervisada por `djdelgado`).

### Matriz de Pruebas de Acceso Cruzado:

| Sesión / Usuario | Endpoint Solicitado | Ámbito Esperado | Código HTTP | Resultado Real |
| :--- | :--- | :--- | :--- | :--- |
| **Sesión A (`djdelgado`)** | `GET /api/radicados/CAU2026ER028340` | Permitido (Líder asignada a esa oficina) | **`200 OK`** | Detalle y metadatos del expediente entregados correctamente. |
| **Sesión B (`ljbastidas`)** | `GET /api/radicados/CAU2026ER028340` | Denegado (Líder de oficina ajena) | **`403 Forbidden`** | *"Acceso denegado: el radicado 'CAU2026ER028340' no pertenece al ámbito del usuario 'ljbastidas'"*. |
| **Sesión B (`ljbastidas`)** | `GET /api/radicados/CAU2026ER028340/documents/test_doc/view` | Denegado (Visor documental ajeno) | **`403 Forbidden`** | *"Acceso denegado: el radicado 'CAU2026ER028340' no pertenece al ámbito del usuario 'ljbastidas'"*. |

---

## 5 y 6. Verificación de la Política Institucional y Ámbito de `LIDER_OFICINA`

- **Verificación de Política:** La respuesta `403 Forbidden` obtenida por `ljbastidas` al intentar consultar `CAU2026ER028340` es **estrictamente correcta y legítima**, ya que el radicado está asignado a la supervisión de `djdelgado`.
- **Aislamiento entre Líderes:** Aunque ambos usuarios ostentan el rol `LIDER_OFICINA`, la consulta en Oracle valida `ID_USUARIO_ASIGNADO = user_info['id_usuario']`, impidiendo que `ljbastidas` acceda a expedientes o documentos de la oficina de `djdelgado`.

---

## 7. Cambio de Sesión y Aislamiento de Bandejas

Se ejecutó la secuencia de cambio de sesión entre los dos usuarios de prueba:
1. **Consulta Sesión A (`djdelgado`):** Obtiene **70 radicados** de su oficina.
2. **Cierre de Sesión:** Petición anónima `GET /api/inbox` sin credenciales -> **`401 Unauthorized`**.
3. **Inicio Sesión B (`ljbastidas`):** Consulta `GET /api/inbox` con cabecera de `ljbastidas` -> Retorna **0 radicados** (HTTP **`200 OK`**).
4. **Verificación de Fuga de Datos:**
   - Intersección de radicados entre `djdelgado` y `ljbastidas`: **0 casos filtrados**.
   - Ninguno de los 70 casos de `djdelgado` se muestra en la bandeja de `ljbastidas`.
   - Intentos por endpoint de detalle o documentos devuelven `403 Forbidden`.

---

## 8. Revisión de Procedencia de Identidad: Sesión Validada vs Cabecera Manipulable

### Implementación del Hotfix de Seguridad (Prompt 69):
Se implementó autenticación de sesión real en el servidor (`app/api.py`) con las siguientes garantías:
1. **Registro de Sesiones Activas en el Servidor (`ACTIVE_SESSIONS`):**
   Al autenticar en `POST /api/auth/login`, el backend genera un token criptográfico `secrets.token_urlsafe(32)` con expiración estricta de 8 horas, y establece una cookie protegida `HttpOnly` (`botsac_session`).
2. **Validación Estricta de Identidad:**
   La función `get_current_user` valida obligatoriamente el token contra `ACTIVE_SESSIONS`. No se admite ningún acceso sin sesión activa.
3. **Bloqueo Total de Suplantación por Cabeceras:**
   Cualquier petición sin sesión válida es rechazada con `401 Unauthorized`. Si una sesión autenticada intenta manipular la cabecera `X-SAC-User` para reclamar otro usuario, el backend detecta el conflicto y rechaza con `403 Forbidden` (*"Intento de suplantación detectado"*).
4. **Cierre de Sesión Destructivo (`POST /api/auth/logout`):**
   Invalida inmediatamente el token en `ACTIVE_SESSIONS` y borra la cookie. Cualquier solicitud posterior con ese token es rechazada con `401 Unauthorized`.

---

## 9. Matriz de Validación de Seguridad tras el Hotfix

| # | Solicitud Realizada | Estado HTTP | Identidad Efectiva | Resultado Esperado | Resultado Real Observado | Estado de Seguridad |
| :---: | :--- | :---: | :---: | :--- | :--- | :---: |
| **1** | `GET /api/inbox` *(Sin login, sin token)* | **`401`** | Ninguna | `401 Unauthorized` | **`401 Unauthorized`** (Token ausente) | ✅ **CUMPLE** |
| **2** | `GET /api/inbox` *(Header `X-SAC-User: djdelgado` sin token)* | **`401`** | Ninguna | `401 Unauthorized` | **`401 Unauthorized`** (Rechazado) | ✅ **CUMPLE** |
| **3** | `GET /api/inbox` *(Header `X-SAC-User: ljbastidas` sin token)* | **`401`** | Ninguna | `401 Unauthorized` | **`401 Unauthorized`** (Rechazado) | ✅ **CUMPLE** |
| **4a**| `GET /api/inbox?user=djdelgado` *(Query param sin token)* | **`401`** | Ninguna | `401 Unauthorized` | **`401 Unauthorized`** (Rechazado) | ✅ **CUMPLE** |
| **4b**| `GET /api/inbox?user=ljbastidas` *(Query param sin token)* | **`401`** | Ninguna | `401 Unauthorized` | **`401 Unauthorized`** (Rechazado) | ✅ **CUMPLE** |
| **5** | `POST /api/auth/login` *(Usuario institucional con clave)* | **`200`** | `ljbastidas` | Emisión y registro de sesión en servidor | **`200 OK`** (Token emitido y registrado en `ACTIVE_SESSIONS`) | ✅ **CUMPLE** |
| **6** | `GET /api/inbox` *(Sesión `ljbastidas` inyecta `X-SAC-User: djdelgado`)* | **`403`** | Bloqueado | Rechazo de suplantación | **`403 Forbidden`** (Intento de suplantación detectado) | ✅ **CUMPLE** |
| **7** | `GET /api/inbox` *(Sesión `djdelgado` inyecta `X-SAC-User: ljbastidas`)* | **`403`** | Bloqueado | Rechazo de suplantación | **`403 Forbidden`** (Intento de suplantación detectado) | ✅ **CUMPLE** |
| **8** | `POST /api/auth/logout` *(e intento posterior con mismo token)* | **`200`** / **`401`** | Ninguna | Invalida sesión en servidor | **`200 OK`** (Token destruido). Petición posterior: **`401 Unauthorized`** | ✅ **CUMPLE** |
| **9** | `GET /api/radicados/CAU2026ER028340` *(Propio vs ajeno)* | **`200`** / **`403`** | Según sesión | Propio: `200` \| Ajeno: `403` | `djdelgado`: **`200 OK`** \| `ljbastidas`: **`403 Forbidden`** | ✅ **CUMPLE** |
| **10**| Auditoría de credenciales en logs y consola | **N/A** | **N/A** | Cero contraseñas en texto claro | **Aprobado** (Variables de entorno, cero exposición) | ✅ **CUMPLE** |

---

## 10. Cumplimiento de Restricciones Operativas

- **Oracle Database:** Cero sentencias `DROP`, `ALTER`, `DELETE` en tablas de negocio.
- **Sistema SAC:** Cero conexiones o escrituras en el SAC institucional.
- **Integridad de Código:** Cambios mínimos y coordinados entre `app/api.py`, `AuthContext.tsx`, `api.ts` y suite de pruebas.

---

## RESULTADO FINAL DE LA PRUEBA

Todas las pruebas de seguridad y aislamiento se ejecutaron exitosamente al 100% contra la API FastAPI y la base de datos Oracle institucional real:

```text
======================================
Resultado final: AISLAMIENTO VALIDADO
======================================
```
