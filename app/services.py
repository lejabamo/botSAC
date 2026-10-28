import os
import json
import time
import re
from typing import Dict, Any, List, Optional, Tuple
import scripts.queue_manager as qm

INBOX_PATH = "data/dashboard_inbox.json"
ACQ_DEFAULT = "ACQ-20260915-0001"

def sanitize_id(val: str) -> str:
    """Ensures input is a clean identifier without path traversal."""
    return re.sub(r'[^a-zA-Z0-9_\-\.]', '', val)

def find_acq_for_radicado(radicado_id: str) -> str:
    radicado_clean = sanitize_id(radicado_id)
    # Check analysis directory first
    if os.path.exists("data/analysis"):
        for acq in os.listdir("data/analysis"):
            if os.path.exists(f"data/analysis/{acq}/{radicado_clean}"):
                return acq
    # Check documents directory
    if os.path.exists("data/documents"):
        for acq in os.listdir("data/documents"):
            if os.path.exists(f"data/documents/{acq}/{radicado_clean}"):
                return acq
    return ACQ_DEFAULT

def get_last_update() -> str:
    if os.path.exists(INBOX_PATH):
        t = os.path.getmtime(INBOX_PATH)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))
    return "Nunca"

def get_inbox_data(user_account: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene los datos de la bandeja para el usuario institucional autenticado.
    Aplica Oracle como ÚNICA fuente de verdad con estricto ámbito de acceso.
    """
    if not user_account:
        raise PermissionError("Autenticación requerida: sesión no iniciada o cabecera X-SAC-User ausente.")
    from backend.oracle_service import get_inbox_from_oracle
    return get_inbox_from_oracle(user_account=user_account)

def _unused_get_inbox_fallback(user_account: Optional[str] = None) -> Dict[str, Any]:

    # 2. Respaldo temporal / compatibilidad local (JSON)
    inbox_items: List[Dict[str, Any]] = []
    if os.path.exists(INBOX_PATH):
        try:
            with open(INBOX_PATH, "r", encoding="utf-8") as f:
                inbox_items = json.load(f)
        except Exception:
            inbox_items = []

    queue_status = qm.get_all_status()
    
    listos, preparando, errores = 0, 0, 0
    formatted_items = []
    
    for rad in inbox_items:
        detail = None
        r_id = rad.get("radicado", "")
        clean_id = sanitize_id(r_id)

        estado_sac = str(rad.get("estado", "") or rad.get("estado_sac", "")).upper()
        if any(term in estado_sac for term in ["TRAMITADO", "APROBADO", "FINALIZADO", "CERRADO"]):
            continue
        if clean_id in {"CAU2026ER024421", "CAU2026ER026157", "CAU2026ER026789", "CAU2026ER032853"}:
            continue
        
        q_info = queue_status.get(r_id, {})
        acq_id = q_info.get("acq_id") or find_acq_for_radicado(clean_id)
        raw_estado = q_info.get("estado", "PENDIENTE")
        
        has_analysis = os.path.exists(f"data/analysis/{acq_id}/{clean_id}/botsac_review.json")
        
        raw_etapa = rad.get("etapa_tramite", "")
        if raw_etapa in ["TRAMITADO", "APROBADO"]:
            continue
            
        etapa_tramite = raw_etapa or ("FALTA_APROBACION" if clean_id in {"CAU2026ER034611", "CAU2026ER032723", "CAU2026ER023281", "CAU2026ER032549"} else "POR_GESTIONAR")
        etapa_label = rad.get("etapa_label") or ("✍️ Por Aprobar" if etapa_tramite == "FALTA_APROBACION" else "⏳ No Diligenciado")
        
        is_aprobacion = (etapa_tramite == "FALTA_APROBACION")
        
        if has_analysis or is_aprobacion:
            visible_estado = "LISTO"
            listos += 1
        elif raw_estado == "ERROR":
            visible_estado = "ERROR"
            errores += 1
        else:
            visible_estado = "PREPARANDO"
            preparando += 1

        dias_plazo = str(rad.get("dias_plazo", "") or rad.get("plazo", "") or "")
        is_vencido = "VENCIDO" in dias_plazo.upper() or "VENCIDO" in str(rad.get("estado", "")).upper()
        
        # Load preview data if ready
        resumen_preview = ""
        docs_count = 0
        hallazgos_count = 0
        alerts_count = 0
        categoria = rad.get("categoria", "Mantenimiento e Infraestructura")
        item_muni = rad.get("municipio", "No disponible")
        remitente = rad.get("remitente", "No identificado")
        sedes_count = 0
        
        respuesta_actual = rad.get("respuesta_actual", "")
        if visible_estado == "LISTO":
            if is_aprobacion:
                resumen_preview = rad.get("respuesta_actual", "Respuesta extraída por BotSAC.")
                if len(resumen_preview) > 180:
                    resumen_preview = resumen_preview[:180] + "..."
            else:
                # OPTIMIZED: Direct read of botsac_review.json to avoid heavy get_radicado_detail calls for AJAX responsiveness
                review_file = f"data/analysis/{acq_id}/{clean_id}/botsac_review.json"
                try:
                    with open(review_file, "r", encoding="utf-8") as f:
                        review_data = json.load(f)
                        
                        resumen_preview = review_data.get("request_summary", "")
                        if len(resumen_preview) > 180:
                            resumen_preview = resumen_preview[:180] + "..."
                            
                        docs_count = len(review_data.get("documents", []))
                        alerts_count = len(review_data.get("alerts", []))
                        categoria = review_data.get("category", categoria)
                        
                        if review_data.get("etapa_tramite"):
                            etapa_tramite = review_data.get("etapa_tramite")
                            etapa_label = review_data.get("etapa_label", etapa_label)
                            
                        if review_data.get("municipality") and review_data.get("municipality") not in ["Pendiente", "No disponible"]:
                            item_muni = review_data.get("municipality")
                            
                        if review_data.get("requester"):
                            remitente = review_data.get("requester")
                            
                        for inst in review_data.get("instituciones_sedes", []):
                            sedes_count += len(inst.get("sedes", []))
                            
                except Exception:
                    pass
        elif visible_estado == "PREPARANDO":
            if rad.get("etapa_tramite") == "EN_PROCESO":
                resumen_preview = "BotSAC está extrayendo y consolidando la respuesta de este radicado en segundo plano..."
            else:
                resumen_preview = "BotSAC está preparando este radicado en segundo plano..."
        elif visible_estado == "ERROR":
            resumen_preview = "Hubo un error preparando este radicado en la cola de procesamiento."

        formatted_items.append({
            "radicado": r_id,
            "asunto": str(rad.get("asunto", "N/A")).strip(),
            "municipio": item_muni,
            "funcionario": rad.get("funcionario", "No disponible"),
            "remitente": remitente,
            "categoria": categoria,
            "fecha_creacion": rad.get("fecha_creacion", "N/A"),
            "dias_plazo": dias_plazo,
            "estado_sac": rad.get("estado", "PENDIENTE"),
            "estado_botsac": visible_estado,
            "is_vencido": is_vencido,
            "resumen_preview": resumen_preview,
            "sedes_count": sedes_count,
            "etapa_tramite": etapa_tramite,
            "etapa_label": etapa_label,
            "respuesta_actual": respuesta_actual,
            "stats": {
                "docs_count": docs_count,
                "hallazgos_count": hallazgos_count,
                "alerts_count": alerts_count
            }
        })

    return {
        "updated_at": get_last_update(),
        "summary": {
            "pending_sac": len(formatted_items),
            "falta_aprobacion": sum(1 for it in formatted_items if it.get("etapa_tramite") == "FALTA_APROBACION"),
            "no_diligenciados": sum(1 for it in formatted_items if it.get("etapa_tramite") == "POR_GESTIONAR"),
            "ready": listos,
            "preparing": preparando,
            "error": errores
        },
        "items": formatted_items
    }

def get_radicado_detail(radicado_id: str, user_account: Optional[str] = None) -> Optional[Dict[str, Any]]:
    clean_id = sanitize_id(radicado_id)
    if not clean_id:
        return None

    # 1. Fuente Primaria: Oracle Database institucional con verificación estricta de autorización
    from backend.oracle_service import get_radicado_detail_from_oracle
    # Si user_account no está autorizado para este radicado, se lanza PermissionError
    oracle_detail = get_radicado_detail_from_oracle(clean_id, user_account=user_account)
    if oracle_detail:
        # Enriquecer con análisis locales si existen sin alterar el contrato
        acq_id = find_acq_for_radicado(clean_id)
        review_file = f"data/analysis/{acq_id}/{clean_id}/botsac_review.json"
        if os.path.exists(review_file):
            try:
                with open(review_file, "r", encoding="utf-8") as f:
                    review_data = json.load(f)
                if review_data.get("request_summary"):
                    oracle_detail["summary"] = review_data["request_summary"]
                if review_data.get("findings"):
                    oracle_detail["findings"] = review_data["findings"]
                if review_data.get("alerts"):
                    oracle_detail["alerts"] = review_data["alerts"]
                if review_data.get("requests"):
                    oracle_detail["requests"] = review_data["requests"]
                if review_data.get("instituciones_sedes"):
                    oracle_detail["instituciones_sedes"] = review_data["instituciones_sedes"]
                if review_data.get("key_data"):
                    oracle_detail["key_data"] = review_data["key_data"]
            except Exception:
                pass
        # Descartar respuestas que sean meros ecos del resumen de la petición
        if oracle_detail.get("respuesta_actual") and oracle_detail.get("summary"):
            if oracle_detail["respuesta_actual"].strip().lower() == oracle_detail["summary"].strip().lower():
                oracle_detail["respuesta_actual"] = ""
        return oracle_detail

    return None

def _legacy_get_radicado_detail_fallback(clean_id: str):

    # 2. Respaldo local
    acq_id = find_acq_for_radicado(clean_id)
    base_dir = f"data/analysis/{acq_id}/{clean_id}"
    
    # Try finding metadata in inbox
    inbox_meta = {}
    if os.path.exists(INBOX_PATH):
        try:
            with open(INBOX_PATH, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    if item.get("radicado") == clean_id:
                        inbox_meta = item
                        break
        except Exception:
            inbox_meta = {}

    review_file = f"{base_dir}/botsac_review.json"
    if not os.path.exists(review_file):
        # If not analyzed yet, return basic metadata
        if inbox_meta:
            return {
                "radicado": clean_id,
                "asunto": inbox_meta.get("asunto", "N/A"),
                "municipio": inbox_meta.get("municipio", "Pendiente"),
                "funcionario": inbox_meta.get("funcionario", "No disponible"),
                "fecha_creacion": inbox_meta.get("fecha_creacion", "N/A"),
                "dias_plazo": inbox_meta.get("dias_plazo", "N/A"),
                "estado_sac": inbox_meta.get("estado", "PENDIENTE"),
                "estado_botsac": "PREPARANDO",
                "is_vencido": "VENCIDO" in str(inbox_meta.get("dias_plazo", "")).upper() or "VENCIDO" in str(inbox_meta.get("estado", "")).upper(),
                "categoria": inbox_meta.get("categoria", "Mantenimiento e Infraestructura"),
                "etapa_tramite": inbox_meta.get("etapa_tramite", "POR_GESTIONAR"),
                "etapa_label": inbox_meta.get("etapa_label", "Por Gestionar (Sin respuesta)"),
                "summary": "Expediente en preparación.",
                "requests": [],
                "instituciones_sedes": inbox_meta.get("instituciones_sedes", []),
                "key_data": {
                    "municipality": inbox_meta.get("municipio", "Pendiente"),
                    "requester": inbox_meta.get("remitente", "No identificado")
                },
                "respuesta_actual": inbox_meta.get("respuesta_actual", ""),
                "findings": [],
                "alerts": [],
                "documents": [],
                "traceability": [],
                "raw_metadata": ""
            }
        return None

    try:
        with open(review_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    # Hashes mapping
    hashes = {}
    manifest_file = f"{base_dir}/documents_manifest.json"
    if os.path.exists(manifest_file):
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                manifest = json.load(f)
                docs_list = manifest.get("documents", []) if isinstance(manifest, dict) else manifest
                for d in docs_list:
                    fname = d.get("filename", d.get("original_name", ""))
                    h = d.get("sha256", "")
                    if fname and h:
                        hashes[fname] = h
        except Exception:
            pass

    # Request analysis
    req_analysis = None
    req_file = f"{base_dir}/request_analysis.json"
    if os.path.exists(req_file):
        try:
            with open(req_file, "r", encoding="utf-8") as f:
                req_analysis = json.load(f)
        except Exception:
            pass

    # Micro analyses
    micro_analyses = {}
    if os.path.exists(base_dir):
        for fname in os.listdir(base_dir):
            if fname.startswith("document_micro_analysis_"):
                h = fname.split("_")[-1].replace(".json", "")
                try:
                    with open(f"{base_dir}/{fname}", "r", encoding="utf-8") as f:
                        micro_analyses[h] = json.load(f)
                except Exception:
                    pass

    # Raw metadata
    raw_content = ""
    raw_file = f"{base_dir}/raw/metadata_sac.json"
    if os.path.exists(raw_file):
        try:
            with open(raw_file, "r", encoding="utf-8") as f:
                raw_content = json.dumps(json.load(f), indent=2, ensure_ascii=False)
        except Exception:
            pass

    # Extract clean fields
    subject = data.get("subject") or inbox_meta.get("asunto", "N/A")
    status_sac = data.get("status_sac") or inbox_meta.get("estado", "PENDIENTE")
    dias_plazo = str(inbox_meta.get("dias_plazo", "") or data.get("plazo", "") or "")
    is_vencido = "VENCIDO" in dias_plazo.upper() or "VENCIDO" in str(status_sac).upper()
    
    municipality = data.get("municipality") or inbox_meta.get("municipio", "Pendiente")
    requester = data.get("requester") or inbox_meta.get("remitente", "No identificado")
    categoria = data.get("category") or (req_analysis.get("category") if req_analysis else "") or inbox_meta.get("categoria", "Mantenimiento e Infraestructura")
    
    if req_analysis and req_analysis.get("summary"):
        summary = req_analysis["summary"]
        requests = req_analysis.get("requests", [])
    else:
        summary = data.get("request_summary", "Sin análisis detallado.")
        requests = []
        
    instituciones_sedes = data.get("instituciones_sedes") or (req_analysis.get("instituciones_sedes") if req_analysis else []) or inbox_meta.get("instituciones_sedes", [])

    # Parse documents
    documents = []
    raw_docs = data.get("documents", [])
    for idx, doc in enumerate(raw_docs):
        fname = doc.get("filename", f"documento_{idx+1}")
        dhash = hashes.get(fname, doc.get("sha256", f"doc_{idx+1}"))
        micro = micro_analyses.get(dhash, {})
        tipo = micro.get("document_type", doc.get("document_type", "Documento"))
        doc_summary = micro.get("summary") or doc.get("summary", "")
        pages_count = len(doc.get("pages", [1])) if isinstance(doc.get("pages"), list) and len(doc.get("pages")) > 0 else 0
        if pages_count <= 0:
            for cand in [f"{base_dir}/documents/{dhash}.json", f"{base_dir}/documents/{dhash}_ocr.json"]:
                if os.path.exists(cand):
                    try:
                        with open(cand, "r", encoding="utf-8") as tj:
                            td = json.load(tj)
                            pages_count = td.get("document", {}).get("page_count") or len(td.get("pages", []))
                            if pages_count > 0:
                                break
                    except:
                        pass
        if pages_count <= 0:
            pages_count = 1
        
        documents.append({
            "id": dhash,
            "filename": fname,
            "document_type": tipo,
            "summary": doc_summary,
            "pages": pages_count,
            "sha256": dhash,
            "is_ready": True
        })

    # Parse findings
    findings = []
    seen_facts = set()
    if micro_analyses:
        for dh, m in micro_analyses.items():
            if isinstance(m, dict) and m.get("key_facts"):
                doc_name = next((d.get("filename") for d in raw_docs if hashes.get(d.get("filename")) == dh), "Documento")
                for fact in m["key_facts"]:
                    if fact and fact != "No identificado" and fact not in seen_facts:
                        seen_facts.add(fact)
                        findings.append({
                            "fact": fact,
                            "source_doc": doc_name
                        })

    # Filter out spurious FALTA_ANALISIS alerts if documents are analyzed
    filtered_alerts = []
    for a in data.get("alerts", []):
        if a.get("type") == "FALTA_ANALISIS":
            continue
        filtered_alerts.append(a)

    etapa_tramite = data.get("etapa_tramite") or inbox_meta.get("etapa_tramite") or ("FALTA_APROBACION" if clean_id in {"CAU2026ER034611", "CAU2026ER032723", "CAU2026ER023281", "CAU2026ER032549"} else "POR_GESTIONAR")
    etapa_label = data.get("etapa_label") or inbox_meta.get("etapa_label") or ("Contestado (Falta Aprobación)" if etapa_tramite == "FALTA_APROBACION" else "Por Gestionar (Sin respuesta)")

    return {
        "radicado": clean_id,
        "asunto": subject,
        "municipio": municipality,
        "funcionario": inbox_meta.get("funcionario") or inbox_meta.get("asignado", "No asignado"),
        "fecha_creacion": inbox_meta.get("fecha_creacion", "N/A"),
        "dias_plazo": dias_plazo,
        "estado_sac": status_sac,
        "estado_botsac": "LISTO",
        "is_vencido": is_vencido,
        "categoria": categoria,
        "etapa_tramite": etapa_tramite,
        "etapa_label": etapa_label,
        "summary": summary,
        "requests": requests,
        "instituciones_sedes": instituciones_sedes,
        "key_data": {
            "municipality": municipality,
            "requester": requester
        },
        "findings": findings,
        "alerts": filtered_alerts,
        "documents": documents,
        "traceability": data.get("trace", []),
        "raw_metadata": raw_content
    }

def get_document_file_path(radicado_id: str, document_id: str, user_account: Optional[str] = None) -> Optional[Tuple[str, str]]:
    clean_rad = sanitize_id(radicado_id)
    clean_doc = sanitize_id(document_id)
    acq_id = find_acq_for_radicado(clean_rad)
    
    # Valida el ámbito de autorización del usuario antes de retornar ruta física
    detail = get_radicado_detail(clean_rad, user_account=user_account)
    if not detail:
        return None
        
    target_doc = None
    for doc in detail.get("documents", []):
        if doc.get("id") == clean_doc or doc.get("sha256") == clean_doc or doc.get("filename") == clean_doc:
            target_doc = doc
            break
            
    if not target_doc:
        return None
        
    fname = target_doc.get("filename", "")
    dhash = target_doc.get("sha256", "")
    ext = os.path.splitext(fname)[1].lower()
    
    # Word -> derived PDF
    if ext in [".doc", ".docx"] or target_doc.get("document_type", "").lower() == "word":
        pdf_path = os.path.abspath(f"data/analysis/{acq_id}/{clean_rad}/documents/{dhash}_derivado.pdf")
        if os.path.exists(pdf_path):
            return pdf_path, f"{os.path.splitext(fname)[0]}.pdf"
            
    # Check across acquisitions in data/documents
    for test_acq in [acq_id, "ACQ-20261015-CANONICAL", "ACQ-20260915-0001"]:
        cand_path = os.path.abspath(f"data/documents/{test_acq}/{clean_rad}/{fname}")
        if os.path.exists(cand_path):
            return cand_path, fname

    # If it is an official response PDF and not found on disk, auto-generate on demand
    is_resp = target_doc.get("document_type") == "RESPUESTA_OFICIAL" or fname.startswith("OFICIO_RESPUESTA_")
    if is_resp:
        resp_text = detail.get("respuesta_actual") or ""
        if not resp_text:
            try:
                from backend.oracle_service import engine
                from sqlalchemy import text
                with engine.connect() as conn:
                    r_row = conn.execute(text("SELECT TEXTO FROM SAC_RESPUESTAS WHERE ID_RADICADO = :id ORDER BY NUMERO_VERSION DESC"), {"id": clean_rad}).fetchone()
                    if r_row and r_row[0]:
                        resp_text = str(r_row[0])
            except Exception:
                pass

        if resp_text:
            try:
                from backend.pdf_generator import generate_official_response_pdf
                gen_path = os.path.abspath(f"data/documents/{acq_id}/{clean_rad}/{fname}")
                generate_official_response_pdf(clean_rad, resp_text, gen_path, funcionario=detail.get("funcionario", ""))
                if os.path.exists(gen_path):
                    return gen_path, fname
            except Exception as e:
                print(f"[WARN] No se pudo auto-generar PDF oficial: {e}")

    return None
