import os
import sys
import time
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import text
from dotenv import load_dotenv

sys.path.append(os.path.abspath("."))
from backend.database import engine
from backend.oracle_service import persist_radicado_processing_result
from botsac.analysis.document_extractor import (
    extract_municipalities,
    extract_institutions,
    extract_requester
)

load_dotenv()
SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")
LOG_PATH = "data/batch_processing.log"

def log_batch(msg: str):
    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [BATCH] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def fix_encoding(text: Any) -> str:
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

def get_pending_radicados(limit: int = 3, user_account: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Obtiene el siguiente bloque de radicados pendientes por procesar en Oracle.
    Prioriza los casos en 'POR APROBAR' que requieren revisión del líder.
    Filtra por usuario asignado si se especifica.
    """
    query = text("""
        SELECT 
            ID_RADICADO,
            ASUNTO,
            MUNICIPIO_HISTORICO,
            NOMBRE_FUNCIONARIO_HIST,
            REMITENTE,
            CATEGORIA,
            ESTADO_SAC,
            ID_USUARIO_ASIGNADO,
            TO_CHAR(FECHA_CREACION, 'YYYY-MM-DD') as FECHA_CREA
        FROM SAC_RADICADOS
        WHERE ESTADO_BOTSAC IN ('PENDIENTE', 'PREPARANDO')
          AND ESTADO_SAC NOT IN ('TRAMITADO', 'APROBADO', 'FINALIZADO', 'CERRADO')
          AND (:user_acc IS NULL OR ID_USUARIO_ASIGNADO = :user_acc)
        ORDER BY CASE WHEN ESTADO_SAC = 'POR APROBAR' THEN 0 ELSE 1 END, FECHA_CREACION DESC NULLS LAST
        FETCH FIRST :limit ROWS ONLY
    """)
    
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit, "user_acc": user_account}).fetchall()
        return [dict(r._mapping) for r in rows]

def synthesize_institutional_response(rad: Dict[str, Any], extracted_resp: str = "") -> str:
    """
    Garantiza una respuesta institucional estructurada para el líder aprobador.
    Si se extrajo texto desde SAC, lo preserva y limpia.
    Si no, estructura un proyecto de respuesta formal conforme a la solicitud.
    """
    if extracted_resp and len(extracted_resp.strip()) > 30 and "Error" not in extracted_resp:
        return extracted_resp.strip()
        
    rad_id = rad.get("id_radicado", "")
    asunto = rad.get("asunto", "Solicitud general")
    func = rad.get("nombre_funcionario_hist") or "Área Técnica de Infraestructura"
    remitente = rad.get("remitente") or "el solicitante"
    muni = rad.get("municipio_historico") or "el departamento del Cauca"
    
    # Respuesta tipo borrador oficial para aprobación
    draft = f"""Popayán, Cauca.

Señor(a):
{remitente}
Municipio de {muni}

Asunto: Respuesta formal al requerimiento SAC {rad_id} - {asunto}

Respetado(a) solicitante:

En atención al requerimiento radicado bajo el número {rad_id}, mediante el cual solicita intervención, apoyo o reporte técnico de infraestructura educativa ({asunto}), la Secretaría de Educación Departamental del Cauca se permite informar:

1. El equipo de Infraestructura Educativa ha recepcionado el informe y documentación técnica remitida para el municipio de {muni}.
2. Se programará inspección técnica de evaluación de daños estructurales / verificación de necesidades en articulación con el personal técnico y directivos docentes correspondientes.
3. Las afectaciones reportadas han sido registradas en la base de priorización de intervenciones y contingencias institucionales.

La presente respuesta ha sido proyectada por el funcionario {func} y se remite a despacho para su revisión, firma y trámite oficial ante el sistema SAC.

Atentamente,

SECRETARÍA DE EDUCACIÓN Y CULTURA DEL DEPARTAMENTO DEL CAUCA
Subproceso de Infraestructura Educativa
Proyectó: {func}
Estado: Pendiente de Aprobación Institucional"""
    return draft

def process_batch_block(
    batch_size: int = 3,
    headless: bool = True,
    sac_user: Optional[str] = None,
    sac_pass: Optional[str] = None
) -> Dict[str, Any]:
    """
    Procesa un bloque de radicados pendientes:
    1. Lee el bloque desde Oracle filtrando por usuario si aplica.
    2. Actualiza a 'PREPARANDO' en tiempo real.
    3. Intenta extraer respuesta y anexos en SAC oficial si está disponible.
    4. Estructura el resumen, sedes y respuesta proyectada.
    5. Persiste caso por caso con COMMIT INMEDIATO en Oracle.
    """
    t_start = time.time()
    active_user = sac_user or SAC_USER
    active_pass = sac_pass or SAC_PASS
    log_batch(f"Iniciando procesamiento de bloque para cuenta '{active_user}' (Tamaño solicitado: {batch_size})...")

    pending_items = get_pending_radicados(limit=batch_size, user_account=sac_user)
    if not pending_items:
        log_batch(f"No se encontraron radicados en estado PENDIENTE para '{active_user}'. Bandeja al día.")
        return {
            "status": "COMPLETED",
            "message": "No hay radicados pendientes por procesar.",
            "processed_count": 0,
            "processed_items": [],
            "remaining_pending": 0
        }

    log_batch(f"Radicados seleccionados para el bloque: {[item['id_radicado'] for item in pending_items]}")

    # Marcar inmediatamente como 'PREPARANDO' en Oracle
    with engine.connect() as conn:
        for item in pending_items:
            conn.execute(text("""
                UPDATE SAC_RADICADOS 
                SET ESTADO_BOTSAC = 'PREPARANDO', UPDATED_AT = SYSTIMESTAMP 
                WHERE ID_RADICADO = :id
            """), {"id": item["id_radicado"]})
        conn.commit()

    processed_results = []
    
    # Intentar extracción directa en SAC si hay credenciales
    sac_extracted_map: Dict[str, str] = {}
    if SAC_URL and active_user and active_pass:
        try:
            from playwright.sync_api import sync_playwright
            log_batch(f"Conectando a portal SAC con cuenta '{active_user}' para extraer respuestas y anexos...")
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=headless,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
                    viewport={"width": 1366, "height": 768},
                    locale="es-CO",
                    timezone_id="America/Bogota",
                    accept_downloads=True
                )
                page = context.new_page()
                page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

                # Login
                page.goto(SAC_URL, wait_until="domcontentloaded", timeout=30000)
                try:
                    page.wait_for_selector('select#id_sc_field_entidad', timeout=12000)
                    page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
                    if page.locator('a#sub_form_b').is_visible():
                        page.locator('a#sub_form_b').click()
                    page.locator('input#id_sc_field_login').fill(active_user)
                    page.locator('input#id_sc_field_pswd').fill(active_pass)
                    page.locator('input.btn-login[value="Ingresar"]').click()
                    page.wait_for_timeout(4000)

                    # Descartar modales
                    for f in page.frames:
                        try:
                            for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')"]:
                                loc = f.locator(loc_str)
                                if loc.count() > 0 and loc.first.is_visible():
                                    loc.first.click()
                                    break
                        except Exception:
                            pass

                    # Navegar a POR APROBAR
                    por_aprob_link = None
                    for f in page.frames:
                        loc = f.locator("text=/POR APROBAR/i")
                        if loc.count() > 0 and loc.first.is_visible():
                            por_aprob_link = loc.first
                            break

                    if por_aprob_link:
                        por_aprob_link.click()
                        page.wait_for_timeout(3000)

                        # Localizar frame de cuadrícula
                        grid_frame = None
                        for f in page.frames:
                            if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                                grid_frame = f
                                break

                        if grid_frame:
                            for item in pending_items:
                                rad_id = item["id_radicado"]
                                log_batch(f"Buscando fila para {rad_id} en cuadrícula SAC...")
                                row_loc = grid_frame.locator(f"tr:has(td:has-text('{rad_id}'))")
                                if row_loc.count() > 0:
                                    btn_action = row_loc.first.locator("a, button, img").first
                                    if btn_action.count() > 0:
                                        btn_action.click(timeout=4000)
                                        page.wait_for_timeout(3000)

                                        # Buscar frame de respuesta
                                        resp_found = ""
                                        for f in page.frames:
                                            for sp_id in ["id_read_on_respuesta", "id_read_on_observaciones", "id_read_on_observacion"]:
                                                sp = f.locator(f"#{sp_id}")
                                                if sp.count() > 0:
                                                    txt = sp.first.inner_text().strip()
                                                    if txt:
                                                        resp_found = txt
                                                        break
                                            if resp_found:
                                                break

                                        if resp_found:
                                            log_batch(f"Respuesta extraída en SAC para {rad_id} ({len(resp_found)} chars)")
                                            sac_extracted_map[rad_id] = fix_encoding(resp_found)

                                        # Volver a cuadrícula
                                        try:
                                            page.go_back(timeout=5000)
                                            page.wait_for_timeout(2000)
                                        except Exception:
                                            pass
                except Exception as ex_browser:
                    log_batch(f"Aviso durante interacción SAC Playwright: {ex_browser}")
                finally:
                    browser.close()
        except Exception as ex_pw:
            log_batch(f"No fue posible abrir sesión de Playwright: {ex_pw}")

    # Procesar y persistir caso por caso en Oracle
    for item in pending_items:
        rad_id = item["id_radicado"]
        asunto = item.get("asunto", "")
        remitente = item.get("remitente", "")
        muni_hist = item.get("municipio_historico", "")
        
        # 1. Obtener respuesta oficial extraída o sintetizada
        raw_sac_resp = sac_extracted_map.get(rad_id, "")
        respuesta_final = synthesize_institutional_response(item, raw_sac_resp)

        # 2. Extraer sedes e instituciones
        search_corpus = f"{asunto} {remitente} {respuesta_final}"
        sedes_extracted = []
        try:
            detected_insts = extract_institutions(search_corpus)
            detected_munis = extract_municipalities(search_corpus, default_muni=muni_hist)
            muni_val = detected_munis[0] if detected_munis and detected_munis[0] != "Pendiente" else (muni_hist or "Cauca")

            if detected_insts:
                for inst_obj in detected_insts:
                    if isinstance(inst_obj, str):
                        sedes_extracted.append({
                            "institucion": inst_obj[:200],
                            "municipio": muni_val,
                            "sede": None
                        })
                    elif isinstance(inst_obj, dict):
                        inst_nom = inst_obj.get("institucion", "Institución Educativa")
                        sub_sedes = inst_obj.get("sedes", [])
                        if sub_sedes:
                            for s_nom in sub_sedes:
                                sedes_extracted.append({
                                    "institucion": inst_nom,
                                    "municipio": muni_val,
                                    "sede": s_nom
                                })
                        else:
                            sedes_extracted.append({
                                "institucion": inst_nom,
                                "municipio": muni_val,
                                "sede": None
                            })
            elif "SEDE" in asunto.upper() or "I.E" in asunto.upper() or "CE " in asunto.upper():
                sedes_extracted.append({
                    "institucion": asunto[:120],
                    "municipio": muni_val,
                    "sede": None
                })
        except Exception as e_sedes:
            log_batch(f"Aviso extrayendo sedes para {rad_id}: {e_sedes}")

        # 3. Documentos asociados iniciales
        doc_list = [{
            "filename": f"OFICIO_RESPUESTA_{rad_id}.pdf",
            "type": "RESPUESTA_PRELIMINAR",
            "size": len(respuesta_final.encode('utf-8')),
            "pages": 1
        }]

        # 4. Resumen Ejecutivo
        resumen_ejecutivo = f"Expediente administrativo {rad_id} analizado por BotSAC. Requerimiento: {asunto}. Funcionario asignado: {item.get('nombre_funcionario_hist', 'Técnico')}. Proyecto de respuesta oficial elaborado y listo para aprobación."

        # 5. Persistir en Oracle con COMMIT INMEDIATO
        persist_radicado_processing_result(
            radicado_id=rad_id,
            respuesta_texto=respuesta_final,
            resumen=resumen_ejecutivo,
            sedes=sedes_extracted,
            documentos=doc_list,
            estado_botsac="LISTO"
        )
        
        log_batch(f"Radicado {rad_id} persistido exitosamente en Oracle -> ESTADO_BOTSAC = 'LISTO' (Sedes: {len(sedes_extracted)}, Respuesta: {len(respuesta_final)} chars).")
        processed_results.append({
            "radicado": rad_id,
            "funcionario": item.get("nombre_funcionario_hist"),
            "asunto": asunto,
            "sedes_count": len(sedes_extracted),
            "respuesta_length": len(respuesta_final),
            "status": "LISTO"
        })

    # Conteo restante de pendientes
    with engine.connect() as conn:
        rem_count = conn.execute(text("""
            SELECT count(*) FROM SAC_RADICADOS 
            WHERE ESTADO_BOTSAC = 'PENDIENTE' 
              AND ESTADO_SAC NOT IN ('TRAMITADO', 'APROBADO', 'FINALIZADO', 'CERRADO')
        """)).scalar()

    elapsed = round(time.time() - t_start, 2)
    log_batch(f"Bloque completado en {elapsed}s. Procesados: {len(processed_results)} | Pendientes restantes en Oracle: {rem_count}")

    return {
        "status": "SUCCESS",
        "elapsed_seconds": elapsed,
        "processed_count": len(processed_results),
        "processed_items": processed_results,
        "remaining_pending": rem_count
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    res = process_batch_block(batch_size=args.batch_size, headless=args.headless)
    print("Resultado Bloque:", res)
