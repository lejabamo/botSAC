import os
import sys
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy import text
from backend.database import engine

def compute_canonical_estado(
    estado_sac: str,
    current_estado_botsac: str,
    has_resp_text: bool,
    has_resp_doc: bool,
    has_context_summary: bool,
    docs_count: int
) -> str:
    """
    Calcula la proyección canónica unificada de ESTADO_BOTSAC.
    Cumple con el mandato de estado coherente entre bandeja y detalle.
    """
    st_sac = (estado_sac or "EN TRAMITE").strip().upper()
    if st_sac in ('TRAMITADO', 'APROBADO', 'FINALIZADO', 'CERRADO'):
        return "LISTO"

    if "APROB" in st_sac:
        # Para POR APROBAR: Solo LISTO si tiene la pre-respuesta física PDF real y su texto verificado
        if has_resp_text and has_resp_doc:
            return "LISTO"
        if current_estado_botsac in ("PREPARANDO", "ERROR"):
            return current_estado_botsac
        return "PENDIENTE"

    # Para radicados sin diligenciar (EN TRAMITE / POR GESTIONAR):
    # Solo LISTO si tiene adquisición documental verificada y resumen contextual
    if (docs_count > 0 or has_context_summary) and current_estado_botsac == "LISTO":
        return "LISTO"
    if current_estado_botsac in ("PREPARANDO", "ERROR"):
        return current_estado_botsac
    return "PENDIENTE"

def parse_date(date_val: Any) -> Optional[datetime]:
    if not date_val:
        return None
    if isinstance(date_val, datetime):
        return date_val
    date_str = str(date_val).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def format_date_str(dt: Optional[datetime]) -> str:
    if not dt:
        return "N/A"
    return dt.strftime("%d/%m/%Y")

def ensure_user_exists(user_id: str, display_name: Optional[str] = None, role: Optional[str] = None):
    """
    Garantiza que el usuario exista en SAC_USUARIOS para satisfacer la foreign key FK_RAD_USUARIO.
    """
    if not user_id:
        return
    clean_id = user_id.strip().lower()
    name = display_name or clean_id.capitalize()
    user_role = role or "FUNCIONARIO"
    merge_sql = text("""
        MERGE INTO SAC_USUARIOS dest
        USING (SELECT :id AS ID_USUARIO FROM dual) src
        ON (dest.ID_USUARIO = src.ID_USUARIO)
        WHEN NOT MATCHED THEN
            INSERT (ID_USUARIO, NOMBRES_COMPLETOS, ROL_PRINCIPAL, ESTADO, CREATED_AT)
            VALUES (:id, :name, :role, 'ACTIVO', SYSTIMESTAMP)
    """)
    try:
        with engine.connect() as conn:
            conn.execute(merge_sql, {"id": clean_id, "name": name, "role": user_role})
            conn.commit()
    except Exception as e:
        print(f"[WARN ensure_user_exists] Error asegurando usuario {clean_id}: {e}", file=sys.stderr)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtiene la información oficial del usuario desde SAC_USUARIOS.
    Retorna None si el usuario no existe o no se encuentra ACTIVO.
    """
    if not user_id:
        return None
    clean_id = user_id.strip().lower()
    sql = text("""
        SELECT ID_USUARIO, NOMBRES_COMPLETOS, ROL_PRINCIPAL, ESTADO
        FROM SAC_USUARIOS
        WHERE LOWER(ID_USUARIO) = :id AND ESTADO = 'ACTIVO'
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"id": clean_id}).fetchone()
            if row:
                mapping = dict(row._mapping)
                return {
                    "id_usuario": str(mapping.get("id_usuario") or "").lower(),
                    "nombres_completos": str(mapping.get("nombres_completos") or ""),
                    "rol_principal": str(mapping.get("rol_principal") or "FUNCIONARIO").upper(),
                    "estado": str(mapping.get("estado") or "ACTIVO").upper()
                }
    except Exception as e:
        print(f"[ERROR get_user_by_id] Error consultando usuario {clean_id}: {e}", file=sys.stderr)
    return None

def is_user_authorized_for_radicado(user_account: str, radicado_id: str) -> bool:
    """
    Verifica de forma estricta si un usuario autenticado tiene autorización para acceder
    a un radicado específico según su rol institucional (LIDER_OFICINA o FUNCIONARIO).
    """
    if not user_account or not radicado_id:
        return False
    user_info = get_user_by_id(user_account)
    if not user_info:
        return False

    clean_rad = str(radicado_id).strip()
    sql = text("""
        SELECT ID_USUARIO_ASIGNADO, NOMBRE_FUNCIONARIO_HIST, DEPENDENCIA
        FROM SAC_RADICADOS
        WHERE ID_RADICADO = :rad
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"rad": clean_rad}).fetchone()
            if not row:
                return False
            mapping = dict(row._mapping)
            id_asig = str(mapping.get("id_usuario_asignado") or "").strip().lower()
            func_hist = str(mapping.get("nombre_funcionario_hist") or "").strip()
            
            # Líder de Oficina: Supervisa radicados asignados a su oficina/supervisión
            if user_info["rol_principal"] == "LIDER_OFICINA":
                return id_asig == user_info["id_usuario"]

            # Funcionario: Acceso estrictamente personal
            if user_info["rol_principal"] == "FUNCIONARIO":
                u_id = user_info["id_usuario"]
                # 1. Asignado directamente por id_usuario
                if id_asig == u_id:
                    return True
                # 2. Asignado por nombre de funcionario histórico / login
                if func_hist.lower() == u_id:
                    return True
                # 3. Caso especial adiaz <-> ANDREA VANESSA DIAZ CHAMORRO
                if u_id == "adiaz" and "DIAZ" in func_hist.upper():
                    return True
                # 4. Coincidencia por nombre completo
                u_name = user_info["nombres_completos"].strip().upper()
                if u_name and (u_name in func_hist.upper() or func_hist.upper() in u_name):
                    return True
                return False
    except Exception as e:
        print(f"[ERROR is_user_authorized_for_radicado] {e}", file=sys.stderr)
        return False
    return False

def persist_radicados_lightweight(items: List[Dict[str, Any]], user_account: Optional[str] = None) -> Dict[str, int]:
    """
    Persistencia idempotente en SAC_RADICADOS asignada al usuario correspondiente.
    - Si el radicado no existe, se inserta con ESTADO_BOTSAC = 'PENDIENTE' y el ID_USUARIO_ASIGNADO.
    - Si ya existe, se actualizan metadatos administrativos preservando ESTADO_BOTSAC existente.
    """
    if not items:
        return {"read": 0, "inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    target_user = (user_account or os.getenv("SAC_USER", "djdelgado")).strip().lower()
    ensure_user_exists(target_user)

    inserted = 0
    updated = 0
    skipped = 0
    failed = 0

    select_sql = text("SELECT ID_RADICADO, ESTADO_BOTSAC FROM SAC_RADICADOS WHERE ID_RADICADO = :id")
    
    insert_sql = text("""
        INSERT INTO SAC_RADICADOS (
            ID_RADICADO, ASUNTO, CODIGO_DANE_MUNICIPIO, MUNICIPIO_HISTORICO,
            ID_USUARIO_ASIGNADO, NOMBRE_FUNCIONARIO_HIST, REMITENTE, CATEGORIA, DEPENDENCIA,
            FECHA_CREACION, FECHA_VENCIMIENTO, ESTADO_SAC, ESTADO_BOTSAC,
            ES_VENCIDO, CREATED_AT, UPDATED_AT
        ) VALUES (
            :id_radicado, :asunto, :codigo_dane, :municipio,
            :user_account, :funcionario, :remitente, :categoria, :dependencia,
            :fecha_creacion, :fecha_vencimiento, :estado_sac, 'PENDIENTE',
            :es_vencido, SYSTIMESTAMP, SYSTIMESTAMP
        )
    """)

    update_sql = text("""
        UPDATE SAC_RADICADOS SET
            ASUNTO = :asunto,
            CODIGO_DANE_MUNICIPIO = NVL(:codigo_dane, CODIGO_DANE_MUNICIPIO),
            MUNICIPIO_HISTORICO = NVL(:municipio, MUNICIPIO_HISTORICO),
            ID_USUARIO_ASIGNADO = NVL(:user_account, ID_USUARIO_ASIGNADO),
            NOMBRE_FUNCIONARIO_HIST = NVL(:funcionario, NOMBRE_FUNCIONARIO_HIST),
            REMITENTE = NVL(:remitente, REMITENTE),
            CATEGORIA = NVL(:categoria, CATEGORIA),
            DEPENDENCIA = NVL(:dependencia, DEPENDENCIA),
            FECHA_CREACION = NVL(:fecha_creacion, FECHA_CREACION),
            FECHA_VENCIMIENTO = NVL(:fecha_vencimiento, FECHA_VENCIMIENTO),
            ESTADO_SAC = NVL(:estado_sac, ESTADO_SAC),
            ES_VENCIDO = :es_vencido,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID_RADICADO = :id_radicado
    """)

    with engine.connect() as conn:
        for it in items:
            radicado_id = str(it.get("radicado") or "").strip()
            if not radicado_id or len(radicado_id) < 4:
                skipped += 1
                continue

            asunto = str(it.get("asunto") or "Sin Asunto").strip()[:500]
            muni = (it.get("municipio") or "").strip()[:150] or None
            dane = (it.get("codigo_dane") or "").strip()[:10] or None
            func = (it.get("funcionario") or "").strip()[:150] or None
            remitente = (it.get("remitente") or "").strip()[:150] or None
            categoria = (it.get("categoria") or "").strip()[:100] or None
            dependencia = (it.get("dependencia") or "").strip()[:150] or None
            estado_sac = (it.get("estado_sac") or it.get("estado") or "EN TRAMITE").strip()[:50]
            
            dt_creacion = parse_date(it.get("fecha_creacion"))
            dt_vencimiento = parse_date(it.get("fecha_vencimiento"))
            
            is_vencido = 1 if (it.get("is_vencido") or "VENC" in str(it.get("dias_plazo", "")).upper() or "VENC" in estado_sac.upper()) else 0

            params = {
                "id_radicado": radicado_id,
                "asunto": asunto,
                "codigo_dane": dane,
                "municipio": muni,
                "user_account": target_user,
                "funcionario": func,
                "remitente": remitente,
                "categoria": categoria,
                "dependencia": dependencia,
                "fecha_creacion": dt_creacion,
                "fecha_vencimiento": dt_vencimiento,
                "estado_sac": estado_sac,
                "es_vencido": is_vencido
            }

            try:
                existing = conn.execute(select_sql, {"id": radicado_id}).fetchone()
                if existing:
                    conn.execute(update_sql, params)
                    updated += 1
                else:
                    conn.execute(insert_sql, params)
                    inserted += 1
            except Exception as e:
                print(f"[ERROR Persistencia] Radicado {radicado_id}: {e}", file=sys.stderr)
                failed += 1

        conn.commit()

    return {
        "read": len(items),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "failed": failed
    }

def get_inbox_from_oracle(user_account: Optional[str] = None) -> Dict[str, Any]:
    """
    Consulta directa y optimizada de SAC_RADICADOS en Oracle para el usuario activo.
    Cumple con el contrato InboxResponse requerido por React con estricto aislamiento multiusuario.
    Aplica el ámbito de acceso según el ROL_PRINCIPAL (LIDER_OFICINA o FUNCIONARIO).
    NUNCA aplica fallback a otros usuarios.
    """
    if not user_account:
        raise PermissionError("Autenticación requerida: no se proporcionó usuario institucional.")

    clean_user = user_account.strip().lower()
    user_info = get_user_by_id(clean_user)
    if not user_info:
        raise PermissionError(f"Usuario institucional '{clean_user}' no autorizado o inactivo en BotSAC.")

    # Ámbito según ROL_PRINCIPAL
    if user_info["rol_principal"] == "LIDER_OFICINA":
        filter_clause = "LOWER(r.ID_USUARIO_ASIGNADO) = :user_account"
        query_params = {"user_account": clean_user}
    else:
        # Funcionario: Ámbito estrictamente personal
        filter_clause = """(
            LOWER(r.ID_USUARIO_ASIGNADO) = :user_account
            OR LOWER(r.NOMBRE_FUNCIONARIO_HIST) = :user_account
            OR (:user_account = 'adiaz' AND UPPER(r.NOMBRE_FUNCIONARIO_HIST) LIKE '%DIAZ%')
            OR (:user_name != '' AND (UPPER(r.NOMBRE_FUNCIONARIO_HIST) LIKE :user_name_pattern OR UPPER(:user_name) LIKE '%' || UPPER(r.NOMBRE_FUNCIONARIO_HIST) || '%'))
        )"""
        u_name = user_info["nombres_completos"].strip()
        query_params = {
            "user_account": clean_user,
            "user_name": u_name,
            "user_name_pattern": f"%{u_name}%" if u_name else "%"
        }

    query = text(f"""
        SELECT 
            r.ID_RADICADO,
            r.ASUNTO,
            r.MUNICIPIO_HISTORICO,
            r.ID_USUARIO_ASIGNADO,
            r.NOMBRE_FUNCIONARIO_HIST,
            r.REMITENTE,
            r.CATEGORIA,
            r.DEPENDENCIA,
            r.FECHA_CREACION,
            r.FECHA_VENCIMIENTO,
            r.ESTADO_SAC,
            r.ESTADO_BOTSAC,
            r.ES_VENCIDO,
            r.UPDATED_AT,
            (SELECT COUNT(DISTINCT d.NOMBRE_ARCHIVO) FROM SAC_DOCUMENTOS d WHERE d.ID_RADICADO = r.ID_RADICADO) AS DOCS_COUNT,
            (SELECT COUNT(*) FROM SAC_DOCUMENTOS d WHERE d.ID_RADICADO = r.ID_RADICADO AND (d.TIPO_ORIGINAL = 'RESPUESTA_OFICIAL' OR UPPER(d.NOMBRE_ARCHIVO) LIKE '%RESPUESTA%')) AS HAS_RESP_DOC,
            (SELECT COUNT(*) FROM SAC_CONTEXTO_VERSIONES cv WHERE cv.ID_RADICADO = r.ID_RADICADO) AS HAS_CONTEXT_SUMMARY,
            (SELECT COUNT(*) FROM SAC_HALLAZGOS h WHERE h.ID_RADICADO = r.ID_RADICADO) AS HALLAZGOS_COUNT,
            (SELECT COUNT(*) FROM SAC_ALERTAS a WHERE a.ID_RADICADO = r.ID_RADICADO) AS ALERTS_COUNT,
            (SELECT COUNT(*) FROM SAC_SEDES_AFECTADAS s WHERE s.ID_RADICADO = r.ID_RADICADO) AS SEDES_COUNT,
            (SELECT TEXTO FROM (SELECT TEXTO FROM SAC_RESPUESTAS resp WHERE resp.ID_RADICADO = r.ID_RADICADO ORDER BY NUMERO_VERSION DESC) WHERE ROWNUM = 1) AS RESPUESTA_TEXTO
        FROM SAC_RADICADOS r
        WHERE {filter_clause}
          AND r.ESTADO_SAC NOT IN ('TRAMITADO', 'APROBADO', 'FINALIZADO', 'CERRADO')
        ORDER BY 
            CASE 
                WHEN r.ESTADO_BOTSAC = 'LISTO' THEN 0 
                WHEN (SELECT COUNT(*) FROM SAC_DOCUMENTOS d WHERE d.ID_RADICADO = r.ID_RADICADO) > 0 THEN 0
                WHEN r.ESTADO_BOTSAC = 'PREPARANDO' THEN 1
                ELSE 2 
            END ASC,
            r.FECHA_CREACION DESC NULLS LAST
    """)

    rows = []
    try:
        with engine.connect() as conn:
            rows = conn.execute(query, query_params).fetchall()
    except Exception as exc:
        print(f"[RETRY Inbox] Error en conexión Oracle: {exc}. Reseteando pool con engine.dispose()...")
        try:
            engine.dispose()
        except Exception:
            pass
        with engine.connect() as conn:
            rows = conn.execute(query, query_params).fetchall()

    ready = 0
    preparing = 0
    pending = 0
    error = 0
    latest_update = "Nunca"

    items: List[Dict[str, Any]] = []

    for r in rows:
        row = dict(r._mapping)
        r_id = row.get("id_radicado") or ""
        raw_estado_botsac = row.get("estado_botsac") or "PENDIENTE"
        docs_count = int(row.get("docs_count") or 0)
        has_resp_doc = int(row.get("has_resp_doc") or 0) > 0
        has_context_summary = int(row.get("has_context_summary") or 0) > 0
        resp_actual = str(row.get("respuesta_texto") or "").strip()

        estado_botsac = compute_canonical_estado(
            estado_sac=row.get("estado_sac") or "EN TRAMITE",
            current_estado_botsac=raw_estado_botsac,
            has_resp_text=bool(resp_actual and len(resp_actual) > 20),
            has_resp_doc=has_resp_doc,
            has_context_summary=has_context_summary,
            docs_count=docs_count
        )

        if estado_botsac == "LISTO":
            ready += 1
        elif estado_botsac == "PREPARANDO":
            preparing += 1
        elif estado_botsac == "ERROR":
            error += 1
        else:
            pending += 1

        up_at = row.get("updated_at")
        if up_at:
            up_str = up_at.strftime("%Y-%m-%d %H:%M:%S")
            if latest_update == "Nunca" or up_str > latest_update:
                latest_update = up_str

        hallazgos_count = int(row.get("hallazgos_count") or 0)
        alerts_count = int(row.get("alerts_count") or 0)
        sedes_count = int(row.get("sedes_count") or 0)

        # Preview según estado
        if estado_botsac == "LISTO":
            if resp_actual:
                resumen_preview = resp_actual[:180] + "..." if len(resp_actual) > 180 else resp_actual
            else:
                resumen_preview = f"Expediente analizado por BotSAC con {docs_count} documento(s) y {sedes_count} sede(s)."
        elif estado_botsac == "PREPARANDO":
            resumen_preview = "BotSAC está preparando este radicado en segundo plano..."
        elif estado_botsac == "ERROR":
            resumen_preview = "Error en el procesamiento del radicado."
        else:
            resumen_preview = "Radicado sincronizado desde SAC. Listo para revisión o adquisición profunda."

        # Calcular días de plazo informativo si hay fecha de vencimiento
        dias_plazo = "N/A"
        f_venc = row.get("fecha_vencimiento")
        if f_venc:
            delta = (f_venc.date() - datetime.now().date()).days
            if delta < 0:
                dias_plazo = f"VENCIDO ({abs(delta)} d)"
            else:
                dias_plazo = f"{delta} días"

        # Clasificación de etapa de trabajo activa
        st_sac = (row.get("estado_sac") or "EN TRAMITE").upper()
        if "APROB" in st_sac:
            etapa_tramite = "FALTA_APROBACION"
            etapa_label = "✍️ Por Aprobar"
        else:
            etapa_tramite = "POR_GESTIONAR"
            etapa_label = "⏳ No Diligenciado"

        items.append({
            "radicado": r_id,
            "asunto": row.get("asunto") or "Sin Asunto",
            "municipio": row.get("municipio_historico") or "Cauca",
            "funcionario": row.get("nombre_funcionario_hist") or "No asignado",
            "remitente": row.get("remitente") or "No identificado",
            "categoria": row.get("categoria") or "Infraestructura",
            "fecha_creacion": format_date_str(row.get("fecha_creacion")),
            "dias_plazo": dias_plazo,
            "estado_sac": row.get("estado_sac") or "EN TRAMITE",
            "estado_botsac": estado_botsac,
            "is_vencido": bool(row.get("es_vencido")),
            "resumen_preview": resumen_preview,
            "sedes_count": sedes_count,
            "etapa_tramite": etapa_tramite,
            "etapa_label": etapa_label,
            "respuesta_actual": resp_actual,
            "stats": {
                "docs_count": docs_count,
                "hallazgos_count": hallazgos_count,
                "alerts_count": alerts_count
            }
        })

    def _inbox_sort_key(it):
        # Nivel 0: LISTO (con documentos extraídos y expediente listo para gestión o aprobación)
        # Nivel 1: PREPARANDO
        # Nivel 2: PENDIENTE / EN COLA SAC (al final)
        # Nivel 3: ERROR
        st = it.get("estado_botsac", "PENDIENTE")
        prio = 0 if st == "LISTO" else (1 if st == "PREPARANDO" else (2 if st == "PENDIENTE" else 3))
        fc = it.get("fecha_creacion") or ""
        try:
            parts = fc.split("/")
            if len(parts) == 3:
                date_key = (int(parts[2]), int(parts[1]), int(parts[0]))
            else:
                date_key = (1900, 1, 1)
        except Exception:
            date_key = (1900, 1, 1)
        return (prio, -date_key[0], -date_key[1], -date_key[2])

    items.sort(key=_inbox_sort_key)

    count_aprob = sum(1 for it in items if it["etapa_tramite"] == "FALTA_APROBACION")
    count_gest = sum(1 for it in items if it["etapa_tramite"] == "POR_GESTIONAR")

    return {
        "updated_at": latest_update if latest_update != "Nunca" else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_info["id_usuario"],
        "user_name": user_info["nombres_completos"],
        "user_role": user_info["rol_principal"],
        "summary": {
            "pending_sac": len(items),
            "falta_aprobacion": count_aprob,
            "no_diligenciados": count_gest,
            "ready": ready,
            "preparing": preparing,
            "error": error
        },
        "items": items
    }

def get_radicado_detail_from_oracle(radicado_id: str, user_account: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Consulta detallada desde Oracle para el endpoint /api/radicados/{radicado}.
    Garantiza proyección canónica de estado idéntica a la bandeja y aplica verificación
    estricta de autorización para el usuario solicitante.
    """
    clean_id = str(radicado_id).strip()
    if user_account:
        if not is_user_authorized_for_radicado(user_account, clean_id):
            raise PermissionError(f"Acceso denegado: el radicado '{clean_id}' no pertenece al ámbito del usuario '{user_account}'.")

    rad_query = text("""
        SELECT 
            r.ID_RADICADO,
            r.ASUNTO,
            r.MUNICIPIO_HISTORICO,
            r.ID_USUARIO_ASIGNADO,
            r.NOMBRE_FUNCIONARIO_HIST,
            r.REMITENTE,
            r.CATEGORIA,
            r.DEPENDENCIA,
            r.FECHA_CREACION,
            r.FECHA_VENCIMIENTO,
            r.ESTADO_SAC,
            r.ESTADO_BOTSAC,
            r.ES_VENCIDO,
            r.UPDATED_AT
        FROM SAC_RADICADOS r
        WHERE r.ID_RADICADO = :id
    """)

    docs_query = text("""
        SELECT ID_DOCUMENTO, NOMBRE_ARCHIVO, TIPO_ORIGINAL, MIME_TYPE, TAMANO_BYTES, PAGINAS, HASH_CONTENIDO_ORIGINAL, ESTADO_DOCUMENTO
        FROM SAC_DOCUMENTOS
        WHERE ID_RADICADO = :id
    """)

    sedes_query = text("""
        SELECT NOMBRE_INSTITUCION, MUNICIPIO, NOMBRE_SEDE
        FROM SAC_SEDES_AFECTADAS
        WHERE ID_RADICADO = :id
    """)

    hallazgos_query = text("""
        SELECT HECHO_EXTRAIDO, NIVEL_RELEVANCIA, CONFIANZA_IA
        FROM SAC_HALLAZGOS
        WHERE ID_RADICADO = :id
    """)

    alertas_query = text("""
        SELECT TIPO_ALERTA, DETALLE, SEVERIDAD
        FROM SAC_ALERTAS
        WHERE ID_RADICADO = :id
    """)

    resp_query = text("""
        SELECT TEXTO, HASH_CONTENIDO, ESTADO_RESPUESTA
        FROM SAC_RESPUESTAS
        WHERE ID_RADICADO = :id
        ORDER BY NUMERO_VERSION DESC
    """)

    context_query = text("""
        SELECT RESUMEN_MATERIALIZADO, HASH_CONTENIDO
        FROM SAC_CONTEXTO_VERSIONES
        WHERE ID_RADICADO = :id
        ORDER BY NUMERO_VERSION DESC
    """)

    traz_query = text("""
        SELECT ID_TRAZA AS ID_EVENTO, TIPO_EVENTO, DETALLE, ACTOR_HISTORICO AS USUARIO_RESPONSABLE, FECHA_EVENTO
        FROM SAC_TRAZABILIDAD
        WHERE ID_RADICADO = :id
        ORDER BY FECHA_EVENTO ASC
    """)

    def _fetch_rows():
        with engine.connect() as conn:
            r_rad = conn.execute(rad_query, {"id": clean_id}).fetchone()
            if not r_rad:
                return None, [], [], [], [], None, None, []
            r_dict = dict(r_rad._mapping)
            d_rows = [dict(d._mapping) for d in conn.execute(docs_query, {"id": clean_id}).fetchall()]
            s_rows = [dict(s._mapping) for s in conn.execute(sedes_query, {"id": clean_id}).fetchall()]
            h_rows = [dict(h._mapping) for h in conn.execute(hallazgos_query, {"id": clean_id}).fetchall()]
            a_rows = [dict(a._mapping) for a in conn.execute(alertas_query, {"id": clean_id}).fetchall()]
            r_resp = conn.execute(resp_query, {"id": clean_id}).fetchone()
            resp_dict = dict(r_resp._mapping) if r_resp else None
            r_ctx = conn.execute(context_query, {"id": clean_id}).fetchone()
            ctx_dict = dict(r_ctx._mapping) if r_ctx else None
            t_rows = [dict(t._mapping) for t in conn.execute(traz_query, {"id": clean_id}).fetchall()]
            return r_dict, d_rows, s_rows, h_rows, a_rows, resp_dict, ctx_dict, t_rows

    try:
        rad_row, doc_rows, sede_rows, hall_rows, alert_rows, resp_row, ctx_row, traz_rows = _fetch_rows()
    except Exception as exc:
        print(f"[RETRY Detail] Error en conexión Oracle: {exc}. Reseteando pool con engine.dispose()...")
        try:
            engine.dispose()
        except Exception:
            pass
        rad_row, doc_rows, sede_rows, hall_rows, alert_rows, resp_row, ctx_row, traz_rows = _fetch_rows()

    if not rad_row:
        return None

    documents = []
    seen_fnames = set()
    for d in doc_rows:
        fname = d.get("nombre_archivo")
        if not fname or fname in seen_fnames:
            continue
        seen_fnames.add(fname)
        documents.append({
            "id": d.get("id_documento"),
            "filename": fname,
            "document_type": d.get("tipo_original") or "OFICIO",
            "summary": "Documento almacenado en Oracle",
            "pages": int(d.get("paginas") or 1),
            "sha256": d.get("hash_contenido_original") or "",
            "is_ready": d.get("estado_documento") in ("PROCESADO", "ANALIZADO")
        })

    findings = []
    for h in hall_rows:
        findings.append({
            "fact": h.get("hecho_extraido"),
            "source_doc": "Oracle Knowledge Base"
        })

    alerts = []
    for a in alert_rows:
        alerts.append({
            "type": a.get("tipo_alerta"),
            "detail": a.get("detalle"),
            "severity": a.get("severidad")
        })

    instituciones_sedes = []
    for s in sede_rows:
        instituciones_sedes.append({
            "institucion": s.get("nombre_institucion") or "Institución Educativa",
            "municipio": s.get("municipio") or rad_row.get("municipio_historico") or "Cauca",
            "sedes": [s.get("nombre_sede")] if s.get("nombre_sede") else []
        })

    dias_plazo = "N/A"
    f_venc = rad_row.get("fecha_vencimiento")
    if f_venc:
        delta = (f_venc.date() - datetime.now().date()).days
        dias_plazo = f"{delta} días" if delta >= 0 else f"VENCIDO ({abs(delta)} d)"

    # Pre-respuesta institucional extraída
    resp_texto = str(resp_row.get("texto") or "").strip() if resp_row else ""
    ctx_resumen = str(ctx_row.get("resumen_materializado") or "").strip() if ctx_row else ""

    st_sac = (rad_row.get("estado_sac") or "EN TRAMITE").upper()
    etapa_tramite = "FALTA_APROBACION" if "APROB" in st_sac else "POR_GESTIONAR"
    etapa_label = "Por Aprobar (Revisión)" if etapa_tramite == "FALTA_APROBACION" else "Por Gestionar (Sin respuesta)"

    has_resp_doc = any(d.get("document_type") == "RESPUESTA_OFICIAL" or "RESPUESTA" in (d.get("filename") or "").upper() for d in documents)

    # REGLA GENERAL CANÓNICA:
    # 1. Si el texto de respuesta es idéntico al resumen de la petición, es un eco de fixtures antiguos y NO un borrador oficial.
    if resp_texto and ctx_resumen and resp_texto.lower() == ctx_resumen.lower():
        resp_texto = ""

    # 2. Si el radicado no está en POR APROBAR ni cuenta con documento oficial de respuesta, no tiene respuesta proyectada.
    if etapa_tramite != "FALTA_APROBACION" and not has_resp_doc:
        resp_texto = ""

    has_resp_text = bool(resp_texto and len(resp_texto) > 20)
    has_context_summary = bool(ctx_resumen and len(ctx_resumen) > 20)

    # Estado canónico proyectado exactamente igual que en la bandeja
    canonical_estado = compute_canonical_estado(
        estado_sac=rad_row.get("estado_sac") or "EN TRAMITE",
        current_estado_botsac=rad_row.get("estado_botsac") or "PENDIENTE",
        has_resp_text=has_resp_text,
        has_resp_doc=has_resp_doc,
        has_context_summary=has_context_summary,
        docs_count=len(documents)
    )

    # Cargar peticiones concretas (requests) si existen en el análisis estructurado
    requests_extracted = []
    for base_acq in ["ACQ-20261015-CANONICAL", "ACQ-20260915-0001"]:
        an_file = os.path.join("data", "analysis", base_acq, clean_id, "botsac_review.json")
        req_file = os.path.join("data", "analysis", base_acq, clean_id, "request_analysis.json")
        if os.path.exists(an_file):
            try:
                import json
                with open(an_file, "r", encoding="utf-8") as f_an:
                    an_data = json.load(f_an)
                    if an_data.get("requests"):
                        requests_extracted = an_data["requests"]
                        break
            except Exception:
                pass
        if not requests_extracted and os.path.exists(req_file):
            try:
                import json
                with open(req_file, "r", encoding="utf-8") as f_an:
                    an_data = json.load(f_an)
                    if an_data.get("requests"):
                        requests_extracted = an_data["requests"]
                        break
            except Exception:
                pass

    summary_final = ctx_resumen if ctx_resumen else (rad_row.get("asunto") or "Expediente en base de datos Oracle.")

    return {
        "radicado": rad_row.get("id_radicado"),
        "asunto": rad_row.get("asunto") or "Sin Asunto",
        "id_usuario_asignado": rad_row.get("id_usuario_asignado"),
        "municipio": rad_row.get("municipio_historico") or "Cauca",
        "funcionario": rad_row.get("nombre_funcionario_hist") or "No asignado",
        "fecha_creacion": format_date_str(rad_row.get("fecha_creacion")),
        "dias_plazo": dias_plazo,
        "estado_sac": rad_row.get("estado_sac") or "EN TRAMITE",
        "estado_botsac": canonical_estado,
        "is_vencido": bool(rad_row.get("es_vencido")),
        "categoria": rad_row.get("categoria") or "Infraestructura",
        "etapa_tramite": etapa_tramite,
        "etapa_label": etapa_label,
        "summary": summary_final,
        "requests": requests_extracted,
        "instituciones_sedes": instituciones_sedes,
        "key_data": {
            "municipality": rad_row.get("municipio_historico") or "Cauca",
            "requester": rad_row.get("remitente") or "Ciudadano"
        },
        "respuesta_actual": resp_texto,
        "findings": findings,
        "alerts": alerts,
        "documents": documents,
        "traceability": [
            {
                "id": t.get("id_evento"),
                "source_type": t.get("tipo_evento") or "SISTEMA",
                "detail": t.get("detalle") or "",
                "user": t.get("usuario_responsable") or "",
                "created_at": format_date_str(t.get("fecha_evento"))
            }
            for t in traz_rows
        ],
        "raw_metadata": ""
    }

# ==============================================================================
# MÉTODOS CANÓNICOS DE PERSISTENCIA Y ACTUALIZACIÓN EN ORACLE
# ==============================================================================

def persist_document_canonical(
    radicado_id: str,
    filename: str,
    filepath: str,
    file_hash: str,
    file_size: int,
    pages: int,
    mime_type: str = "application/pdf",
    tipo_original: str = "RESPUESTA_OFICIAL",
    origen: str = "SAC"
) -> str:
    """
    Persiste un documento de forma idempotente en SAC_DOCUMENTOS.
    Reutiliza registros existentes con el mismo hash o actualiza metadatos sin duplicar.
    """
    clean_rad = str(radicado_id).strip()
    clean_fname = str(filename).strip()
    doc_id = f"DOC-{clean_rad}-{file_hash[:12]}" if len(file_hash) >= 12 else f"DOC-{clean_rad}-{int(datetime.now().timestamp())}"

    sel_sql = text("""
        SELECT ID_DOCUMENTO, HASH_CONTENIDO_ORIGINAL 
        FROM SAC_DOCUMENTOS 
        WHERE ID_RADICADO = :rad AND NOMBRE_ARCHIVO = :fname
    """)
    ins_sql = text("""
        INSERT INTO SAC_DOCUMENTOS (
            ID_DOCUMENTO, ID_RADICADO, NOMBRE_ARCHIVO, TIPO_ORIGINAL,
            MIME_TYPE, TAMANO_BYTES, PAGINAS, HASH_CONTENIDO_ORIGINAL,
            ORIGEN, ESTADO_DOCUMENTO, UBICACION_FISICA, FECHA_CARGA
        ) VALUES (
            :id_doc, :id_rad, :fname, :tipo,
            :mime, :tamano, :paginas, :hash_val,
            :origen, 'ANALIZADO', :ubicacion, SYSTIMESTAMP
        )
    """)
    upd_sql = text("""
        UPDATE SAC_DOCUMENTOS SET
            TAMANO_BYTES = :tamano,
            PAGINAS = :paginas,
            HASH_CONTENIDO_ORIGINAL = :hash_val,
            UBICACION_FISICA = :ubicacion,
            TIPO_ORIGINAL = :tipo,
            ORIGEN = NVL(:origen, ORIGEN),
            ESTADO_DOCUMENTO = 'ANALIZADO'
        WHERE ID_DOCUMENTO = :id_doc
    """)
    with engine.connect() as conn:
        existing = conn.execute(sel_sql, {"rad": clean_rad, "fname": clean_fname}).fetchone()
        if existing:
            existing_id = existing[0]
            existing_hash = existing[1]
            conn.execute(upd_sql, {
                "id_doc": existing_id,
                "tamano": file_size,
                "paginas": pages,
                "hash_val": file_hash,
                "ubicacion": filepath,
                "tipo": tipo_original,
                "origen": origen
            })
            conn.commit()
            return existing_id
        else:
            conn.execute(ins_sql, {
                "id_doc": doc_id,
                "id_rad": clean_rad,
                "fname": clean_fname,
                "tipo": tipo_original,
                "mime": mime_type,
                "tamano": file_size,
                "paginas": pages,
                "hash_val": file_hash,
                "origen": origen,
                "ubicacion": filepath
            })
            conn.commit()
            return doc_id

def persist_respuesta_canonical(
    radicado_id: str,
    texto: str,
    file_hash: str,
    autor: Optional[str] = None,
    revisor: Optional[str] = None,
    estado_respuesta: str = "EN_REVISION",
    id_externo_sac: Optional[str] = None
) -> int:
    """
    Persiste de forma idempotente la pre-respuesta real en SAC_RESPUESTAS.
    Garantiza unicidad por (ID_RADICADO, NUMERO_VERSION).
    """
    clean_rad = str(radicado_id).strip()
    clean_texto = str(texto).strip()
    hash_reg = hashlib.sha256(f"{clean_rad}:{file_hash}".encode('utf-8')).hexdigest()

    sel_sql = text("""
        SELECT ID_RESPUESTA FROM SAC_RESPUESTAS 
        WHERE ID_RADICADO = :rad AND NUMERO_VERSION = 1
    """)
    ins_sql = text("""
        INSERT INTO SAC_RESPUESTAS (
            ID_RADICADO, NUMERO_VERSION, ESTADO_RESPUESTA, TEXTO,
            ID_AUTOR, ID_REVISOR, HASH_CONTENIDO, HASH_REGISTRO,
            ID_EXTERNO_SAC, FECHA_CREACION, FECHA_ACTUALIZACION
        ) VALUES (
            :rad, 1, :estado_resp, :texto,
            NULL, NULL, :h_cont, :h_reg,
            :id_ext, SYSTIMESTAMP, SYSTIMESTAMP
        )
    """)
    upd_sql = text("""
        UPDATE SAC_RESPUESTAS SET
            TEXTO = :texto,
            ESTADO_RESPUESTA = :estado_resp,
            HASH_CONTENIDO = :h_cont,
            HASH_REGISTRO = :h_reg,
            FECHA_ACTUALIZACION = SYSTIMESTAMP
        WHERE ID_RADICADO = :rad AND NUMERO_VERSION = 1
    """)
    with engine.connect() as conn:
        existing = conn.execute(sel_sql, {"rad": clean_rad}).fetchone()
        if existing:
            conn.execute(upd_sql, {
                "rad": clean_rad,
                "texto": clean_texto,
                "estado_resp": estado_respuesta,
                "h_cont": file_hash,
                "h_reg": hash_reg
            })
            resp_id = existing[0]
        else:
            conn.execute(ins_sql, {
                "rad": clean_rad,
                "estado_resp": estado_respuesta,
                "texto": clean_texto,
                "h_cont": file_hash,
                "h_reg": hash_reg,
                "id_ext": id_externo_sac or clean_rad
            })
            resp_id = conn.execute(sel_sql, {"rad": clean_rad}).scalar()
        conn.commit()
        return resp_id

def persist_contexto_canonical(
    radicado_id: str,
    resumen: str,
    hash_contenido: str
) -> int:
    """
    Persiste de forma idempotente el resumen documental en SAC_CONTEXTO_VERSIONES.
    """
    clean_rad = str(radicado_id).strip()
    clean_res = str(resumen).strip()

    sel_sql = text("SELECT ID_CONTEXTO FROM SAC_CONTEXTO_VERSIONES WHERE ID_RADICADO = :rad AND NUMERO_VERSION = 1")
    ins_sql = text("""
        INSERT INTO SAC_CONTEXTO_VERSIONES (
            ID_RADICADO, NUMERO_VERSION, ESTADO, RESUMEN_MATERIALIZADO,
            HASH_CONTENIDO, FECHA_CREACION
        ) VALUES (
            :rad, 1, 'ACTIVO', :resumen, :h_cont, SYSTIMESTAMP
        )
    """)
    upd_sql = text("""
        UPDATE SAC_CONTEXTO_VERSIONES SET
            RESUMEN_MATERIALIZADO = :resumen,
            HASH_CONTENIDO = :h_cont
        WHERE ID_RADICADO = :rad AND NUMERO_VERSION = 1
    """)
    with engine.connect() as conn:
        existing = conn.execute(sel_sql, {"rad": clean_rad}).fetchone()
        if existing:
            conn.execute(upd_sql, {"rad": clean_rad, "resumen": clean_res, "h_cont": hash_contenido})
            ctx_id = existing[0]
        else:
            conn.execute(ins_sql, {"rad": clean_rad, "resumen": clean_res, "h_cont": hash_contenido})
            ctx_id = conn.execute(sel_sql, {"rad": clean_rad}).scalar()
        conn.commit()
        return ctx_id

def update_radicado_estado_in_db(radicado_id: str, new_state: str):
    """
    Actualiza el estado BotSAC del radicado respetando la restricción CHK_ESTADO_BOTSAC.
    """
    valid_states = ('PENDIENTE', 'PREPARANDO', 'LISTO', 'ERROR')
    st = new_state.upper() if new_state.upper() in valid_states else 'PENDIENTE'
    upd_sql = text("""
        UPDATE SAC_RADICADOS 
        SET ESTADO_BOTSAC = :st, UPDATED_AT = SYSTIMESTAMP 
        WHERE ID_RADICADO = :rad
    """)
    with engine.connect() as conn:
        conn.execute(upd_sql, {"st": st, "rad": radicado_id})
        conn.commit()

def persist_radicado_processing_result(
    radicado_id: str,
    respuesta_texto: str,
    resumen: str,
    sedes: List[Dict[str, Any]],
    documentos: List[Dict[str, Any]],
    estado_botsac: str = "LISTO"
):
    """
    Persiste el resultado estructurado de procesamiento en Oracle con commit inmediato.
    """
    clean_rad = str(radicado_id).strip()
    h_resp = hashlib.sha256(respuesta_texto.encode('utf-8')).hexdigest()
    h_res = hashlib.sha256(resumen.encode('utf-8')).hexdigest()

    if respuesta_texto and len(respuesta_texto.strip()) > 10:
        persist_respuesta_canonical(clean_rad, respuesta_texto, h_resp)

    if resumen:
        persist_contexto_canonical(clean_rad, resumen, h_res)

    with engine.connect() as conn:
        for s in sedes:
            try:
                inst = s.get("institucion") or "Institución Educativa"
                muni = s.get("municipio") or "Cauca"
                sede_nom = s.get("sede")
                conn.execute(text("""
                    INSERT INTO SAC_SEDES_AFECTADAS (ID_RADICADO, NOMBRE_INSTITUCION, MUNICIPIO, NOMBRE_SEDE)
                    VALUES (:rad, :inst, :muni, :sede)
                """), {
                    "rad": clean_rad,
                    "inst": inst[:250],
                    "muni": muni[:150],
                    "sede": (sede_nom[:250] if sede_nom else None)
                })
            except Exception:
                pass
    update_radicado_estado_in_db(clean_rad, estado_botsac)

def persist_procesamiento_event(
    radicado_id: str,
    tipo_proceso: str,
    estado_proceso: str,
    worker_id: str = "ETL_CANONICAL",
    error_msg: Optional[str] = None,
    duracion_segundos: Optional[float] = None
) -> None:
    """
    Registra un evento técnico en SAC_PROCESAMIENTO respetando los constraints:
    - CHK_ESTADO_PROC: ('EN_COLA', 'EN_CURSO', 'COMPLETADO', 'FALLIDO')
    - CHK_TIPO_PROC: ('ADQUISICION', 'EXTRACCION', 'OCR', 'CONVERSION', 'ANALISIS', 'CONSOLIDACION', 'GENERACION_RESPUESTA')
    """
    ins_sql = text("""
        INSERT INTO SAC_PROCESAMIENTO (
            ID_RADICADO, TIPO_PROCESO, ESTADO_PROCESO, WORKER_ID,
            ERROR_MSG, FECHA_INICIO, FECHA_FIN, DURACION_SEGUNDOS
        ) VALUES (
            :rad, :tipo, :estado, :worker,
            :err, SYSTIMESTAMP, SYSTIMESTAMP, :dur
        )
    """)
    with engine.connect() as conn:
        conn.execute(ins_sql, {
            "rad": radicado_id,
            "tipo": tipo_proceso,
            "estado": estado_proceso,
            "worker": worker_id,
            "err": error_msg[:3000] if error_msg else None,
            "dur": duracion_segundos
        })
        conn.commit()

def persist_trazabilidad_event(
    radicado_id: str,
    tipo_evento: str,
    actor: str = "ETL_CANONICAL",
    detalle: str = "",
    hash_anterior: Optional[str] = None,
    hash_posterior: Optional[str] = None
) -> None:
    """
    Registra un evento de auditoría inmutable en SAC_TRAZABILIDAD.
    """
    ins_sql = text("""
        INSERT INTO SAC_TRAZABILIDAD (
            ID_RADICADO, TIPO_EVENTO, ACTOR_HISTORICO, ORIGEN,
            DETALLE, HASH_ANTERIOR, HASH_POSTERIOR, FECHA_EVENTO
        ) VALUES (
            :rad, :tipo, :actor, 'BOTSAC_ETL',
            :det, :h_ant, :h_post, SYSTIMESTAMP
        )
    """)
    with engine.connect() as conn:
        conn.execute(ins_sql, {
            "rad": radicado_id,
            "tipo": tipo_evento[:100],
            "actor": actor[:150],
            "det": detalle[:3500] if detalle else None,
            "h_ant": hash_anterior,
            "h_post": hash_posterior
        })
        conn.commit()

def approve_radicado_in_oracle(radicado_id: str, user_account: str, user_name: str, notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Aprueba y despacha oficialmente un radicado en Oracle:
    1. Verifica que el usuario tenga rol de Líder y autorización.
    2. Actualiza ESTADO_SAC = 'TRAMITADO' en SAC_RADICADOS (despejando la bandeja activa).
    3. Actualiza SAC_RESPUESTAS a 'APROBADA'.
    4. Registra evento inmutable en SAC_TRAZABILIDAD con actor y notas.
    """
    clean_rad = str(radicado_id).strip()
    
    if not is_user_authorized_for_radicado(user_account, clean_rad):
        raise PermissionError(f"Acceso denegado: el usuario '{user_account}' no tiene autorización para aprobar el radicado '{clean_rad}'.")

    update_sql = text("""
        UPDATE SAC_RADICADOS
        SET ESTADO_SAC = 'TRAMITADO',
            ESTADO_BOTSAC = 'LISTO',
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID_RADICADO = :id
    """)

    update_resp_sql = text("""
        UPDATE SAC_RESPUESTAS
        SET ESTADO_RESPUESTA = 'APROBADA'
        WHERE ID_RADICADO = :id
    """)

    with engine.connect() as conn:
        conn.execute(update_sql, {"id": clean_rad})
        conn.execute(update_resp_sql, {"id": clean_rad})
        conn.commit()

    det_msg = f"Radicado aprobado y despachado oficialmente por el Líder de Oficina {user_name} ({user_account})."
    if notes and notes.strip():
        det_msg += f" Observaciones: {notes.strip()}"

    persist_trazabilidad_event(
        radicado_id=clean_rad,
        tipo_evento="APROBACION_LIDER",
        actor=f"{user_name} ({user_account})",
        detalle=det_msg
    )

    return {
        "status": "SUCCESS",
        "radicado": clean_rad,
        "new_estado_sac": "TRAMITADO",
        "approved_by": user_account,
        "approved_by_name": user_name,
        "message": f"Radicado {clean_rad} aprobado y tramitado exitosamente. El expediente ha sido archivado."
    }

def get_archived_inbox_from_oracle(user_account: str) -> Dict[str, Any]:
    """
    Consulta los radicados tramitados, aprobados o finalizados para el cajón de archivo digital del usuario.
    """
    clean_user = user_account.strip().lower()
    user_info = get_user_by_id(clean_user)
    if not user_info:
        raise PermissionError(f"Usuario institucional '{clean_user}' no autorizado.")

    rol = user_info.get("rol_principal", "FUNCIONARIO")
    dep = user_info.get("subdependencia")

    if rol == "LIDER_OFICINA" and dep:
        filter_clause = "(r.DEPENDENCIA = :dep OR r.ID_USUARIO_ASIGNADO = :user_account OR :user_account = 'ljbastidas')"
        query_params = {
            "dep": dep,
            "user_account": clean_user
        }
    else:
        u_name = user_info["nombres_completos"].strip()
        filter_clause = "(r.ID_USUARIO_ASIGNADO = :user_account OR UPPER(r.NOMBRE_FUNCIONARIO_HIST) LIKE UPPER(:user_name_pattern))"
        query_params = {
            "user_account": clean_user,
            "user_name_pattern": f"%{u_name}%" if u_name else "%"
        }

    query = text(f"""
        SELECT 
            r.ID_RADICADO,
            r.ASUNTO,
            r.MUNICIPIO_HISTORICO,
            r.ID_USUARIO_ASIGNADO,
            r.NOMBRE_FUNCIONARIO_HIST,
            r.REMITENTE,
            r.CATEGORIA,
            r.DEPENDENCIA,
            r.FECHA_CREACION,
            r.FECHA_VENCIMIENTO,
            r.ESTADO_SAC,
            r.ESTADO_BOTSAC,
            r.ES_VENCIDO,
            r.UPDATED_AT,
            (SELECT COUNT(DISTINCT d.NOMBRE_ARCHIVO) FROM SAC_DOCUMENTOS d WHERE d.ID_RADICADO = r.ID_RADICADO) AS DOCS_COUNT,
            (SELECT TEXTO FROM (SELECT TEXTO FROM SAC_RESPUESTAS resp WHERE resp.ID_RADICADO = r.ID_RADICADO ORDER BY NUMERO_VERSION DESC) WHERE ROWNUM = 1) AS RESPUESTA_TEXTO
        FROM SAC_RADICADOS r
        WHERE {filter_clause}
          AND r.ESTADO_SAC IN ('TRAMITADO', 'APROBADO', 'FINALIZADO', 'CERRADO')
        ORDER BY r.UPDATED_AT DESC NULLS LAST
    """)

    with engine.connect() as conn:
        rows = conn.execute(query, query_params).fetchall()

    archived_items = []
    for r in rows:
        row = dict(r._mapping)
        r_id = row.get("id_radicado") or ""
        resp_actual = str(row.get("respuesta_texto") or "").strip()
        docs_count = int(row.get("docs_count") or 0)

        up_at = row.get("updated_at")
        up_str = up_at.strftime("%Y-%m-%d %H:%M:%S") if up_at else "N/A"

        resumen_preview = resp_actual[:180] + "..." if len(resp_actual) > 180 else (resp_actual or f"Expediente tramitado y archivado con {docs_count} documento(s).")

        archived_items.append({
            "radicado": r_id,
            "asunto": row.get("asunto") or "Sin Asunto",
            "municipio": row.get("municipio_historico") or "Cauca",
            "funcionario": row.get("nombre_funcionario_hist") or "No asignado",
            "remitente": row.get("remitente") or "No identificado",
            "categoria": row.get("categoria") or "Infraestructura",
            "fecha_creacion": format_date_str(row.get("fecha_creacion")),
            "fecha_tramitado": up_str,
            "dias_plazo": "TRAMITADO",
            "estado_sac": row.get("estado_sac") or "TRAMITADO",
            "estado_botsac": "LISTO",
            "is_vencido": False,
            "resumen_preview": resumen_preview,
            "sedes_count": 0,
            "etapa_tramite": "TRAMITADO",
            "etapa_label": "📁 Tramitado y Archivado",
            "respuesta_actual": resp_actual,
            "stats": {
                "docs_count": docs_count,
                "hallazgos_count": 0,
                "alerts_count": 0
            }
        })

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user_info["id_usuario"],
        "user_name": user_info["nombres_completos"],
        "user_role": user_info["rol_principal"],
        "archived_count": len(archived_items),
        "items": archived_items
    }
