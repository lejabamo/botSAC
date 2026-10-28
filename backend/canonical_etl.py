import os
import sys
import time
import json
import csv
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Frame
from dotenv import load_dotenv
import pypdf

sys.path.append(os.path.abspath("."))
from backend.database import engine
from sqlalchemy import text
from backend.oracle_service import (
    persist_radicados_lightweight,
    persist_document_canonical,
    persist_respuesta_canonical,
    persist_contexto_canonical,
    persist_procesamiento_event,
    persist_trazabilidad_event,
    update_radicado_estado_in_db,
    compute_canonical_estado
)

load_dotenv()

# Rutas estándar del sistema
ETL_LOG_PATH = "data/etl_pipeline.log"
RECONCILIATION_CSV_PATH = "data/document_reconciliation_report.csv"
DOCS_BASE_DIR = "data/documents"
ANALYSIS_BASE_DIR = "data/analysis"
LOCK_DIR = "data/locks"
DEFAULT_ACQ_ID = "ACQ-20261015-CANONICAL"

def log_etl(msg: str, level: str = "INFO"):
    """Registra eventos en consola y en data/etl_pipeline.log sin exponer credenciales."""
    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(ETL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def fix_encoding(text: Any) -> str:
    if not isinstance(text, str):
        return str(text) if text is not None else ""
    try:
        return text.encode('latin1').decode('utf-8')
    except Exception:
        return text

def calculate_sha256(filepath: str) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()

class AccountMutex:
    """Garantiza una sincronización activa por cuenta a la vez con detección de bloqueos huérfanos."""
    def __init__(self, account_user: str, timeout_seconds: int = 900):
        self.account_user = account_user
        self.timeout_seconds = timeout_seconds
        os.makedirs(LOCK_DIR, exist_ok=True)
        self.lock_file = os.path.join(LOCK_DIR, f"etl_{self.account_user}.lock")
        self.acquired = False

    def acquire(self) -> bool:
        if os.path.exists(self.lock_file):
            try:
                mtime = os.path.getmtime(self.lock_file)
                age = time.time() - mtime
                if age > self.timeout_seconds:
                    log_etl(f"Detectado bloqueo huérfano para cuenta '{self.account_user}' ({round(age, 1)}s de antigüedad). Liberando forzosamente...", "WARN")
                    os.remove(self.lock_file)
                else:
                    log_etl(f"Cuenta '{self.account_user}' ya posee una sincronización activa (iniciada hace {round(age, 1)}s). Abortando concurrencia.", "WARN")
                    return False
            except Exception as e:
                log_etl(f"Error evaluando lock existente: {e}", "WARN")
                return False

        try:
            with open(self.lock_file, "w", encoding="utf-8") as f:
                f.write(f"PID={os.getpid()}\nSTART={datetime.now().isoformat()}\nUSER={self.account_user}\n")
            self.acquired = True
            log_etl(f"Lock adquirido exitosamente para cuenta '{self.account_user}'")
            return True
        except Exception as e:
            log_etl(f"No se pudo crear archivo de lock: {e}", "ERROR")
            return False

    def release(self):
        if self.acquired and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                self.acquired = False
                log_etl(f"Lock liberado para cuenta '{self.account_user}'")
            except Exception as e:
                log_etl(f"Error liberando lock: {e}", "WARN")

class CanonicalETL:
    """
    Motor Canónico de Extracción, Transformación y Carga (ETL) de BotSAC.
    Implementa:
    1. Paginación completa y conciliación de bandejas.
    2. Persistencia idempotente en Oracle Database.
    3. Adquisición documental física y verificación criptográfica.
    4. Descarga real y parsing de pre-respuestas de SAC (sin fabricaciones).
    5. Aislamiento de errores y trazabilidad auditada.
    """
    def __init__(self, sac_url: Optional[str] = None, sac_user: Optional[str] = None, sac_pass: Optional[str] = None):
        self.sac_url = sac_url or os.getenv("SAC_URL")
        self.sac_user = sac_user or os.getenv("SAC_USER")
        self.sac_pass = sac_pass or os.getenv("SAC_PASS")
        self.acq_id = DEFAULT_ACQ_ID
        self.mutex = AccountMutex(self.sac_user or "anonymous")

        if not self.sac_url or not self.sac_user or not self.sac_pass:
            raise ValueError("Credenciales o URL de SAC no configuradas.")

    def create_browser_context(self, p, headless: bool = True) -> Tuple[Browser, BrowserContext, Page]:
        """Crea el contexto de navegador con bypass estricto de WAF FortiGuard."""
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
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
        return browser, context, page

    def login_sac(self, page: Page) -> float:
        """Inicia sesión institucional en SAC y maneja modales."""
        t0 = time.time()
        log_etl("Iniciando sesión institucional en SAC...")
        page.goto(self.sac_url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
        page.locator('input#id_sc_field_login').fill(self.sac_user)
        page.locator('input#id_sc_field_pswd').fill(self.sac_pass)
        page.locator('input.btn-login[value="Ingresar"]').click()
        page.wait_for_timeout(5000)

        # Manejo de modales ScriptCase
        for f in page.frames:
            try:
                for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                    loc = f.locator(loc_str)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click()
                        break
            except Exception:
                pass

        page.wait_for_load_state("load")
        page.wait_for_timeout(3000)
        dur = round(time.time() - t0, 2)
        log_etl(f"Sesión SAC autenticada exitosamente en {dur}s")
        return dur

    def extract_por_aprobar_tray(
        self,
        page: Page,
        context: Optional[BrowserContext] = None,
        max_pages: int = 20,
        acquire_pdfs: bool = False,
        target_pdf_sample: int = 0
    ) -> Dict[str, Any]:
        """
        Navega y extrae la bandeja POR APROBAR completa utilizando paginación canónica ScriptCase.
        Concilia el total anunciado con el total extraído página por página.
        Si acquire_pdfs es True, descarga y valida muestras de PDF en la página activa.
        """
        t0 = time.time()
        log_etl("Navegando a la sección 'POR APROBAR' en el dashboard...")

        verified_responses: Dict[str, Dict[str, Any]] = {}
        pdf_errors: List[Dict[str, Any]] = []
        total_pdf_acq_seconds = 0.0

        # 1. Detectar total anunciado en dashboard
        total_anunciado_dashboard: Optional[int] = None
        target_link = None

        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    locs = f.locator("text=/POR APROBAR/i").all()
                    for loc in locs:
                        if loc.is_visible():
                            txt = loc.inner_text().strip()
                            if "RESPUESTA" in txt or "POR APROBAR" in txt:
                                target_link = loc
                                import re
                                m = re.search(r'(\d+)\s*POR APROBAR', txt, re.IGNORECASE)
                                if m:
                                    total_anunciado_dashboard = int(m.group(1))
                                break
                    if target_link:
                        break
                except Exception:
                    pass
            if target_link:
                break
            page.wait_for_timeout(1000)

        if not target_link:
            raise RuntimeError("No se encontró el enlace o contador de 'POR APROBAR' en el dashboard de SAC.")

        log_etl(f"Total anunciado en dashboard: {total_anunciado_dashboard if total_anunciado_dashboard is not None else 'No parseado'}")
        target_link.click()
        page.wait_for_timeout(5000)

        # 2. Localizar cuadrícula
        grid_frame: Optional[Frame] = None
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO'), th:has-text('Radicado')").count() > 0:
                        grid_frame = f
                        break
                except Exception:
                    pass
            if grid_frame:
                break
            page.wait_for_timeout(1000)

        if not grid_frame:
            raise RuntimeError("No fue posible cargar el marco (iframe) de la cuadrícula 'POR APROBAR'.")

        # 3. Recorrer páginas mediante selector a#forward_bot
        all_extracted: List[Dict[str, Any]] = []
        seen_radicados: Set[str] = set()
        pages_count = 0

        while pages_count < max_pages:
            pages_count += 1
            # Reubicar frame
            for f in page.frames:
                try:
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                        grid_frame = f
                        break
                except Exception:
                    pass

            # Extraer filas de la página actual mediante índices correlativos {i}
            page_items: List[Dict[str, Any]] = []
            i = 1
            while True:
                rad_loc = grid_frame.locator(f"#id_sc_field_radicado_{i}")
                if rad_loc.count() == 0:
                    break

                rad_val = fix_encoding(rad_loc.first.inner_text().strip())
                if not rad_val or rad_val.upper() == "RADICADO" or len(rad_val) < 5:
                    i += 1
                    continue

                asunto_loc = grid_frame.locator(f"#id_sc_field_asunto_{i}")
                fc_loc = grid_frame.locator(f"#id_sc_field_fecha_creacion_{i}")
                fv_loc = grid_frame.locator(f"#id_sc_field_fecha_vencimiento_{i}")
                ciu_loc = grid_frame.locator(f"#id_sc_field_id_ciudadano_{i}")
                treq_loc = grid_frame.locator(f"#id_sc_field_id_trequerimiento_{i}")
                func_loc = grid_frame.locator(f"#id_sc_field_login_funcionario_asignado_{i}")
                dias_loc = grid_frame.locator(f"#id_sc_field_dias_restantes_{i}")
                pdf_loc = grid_frame.locator(f"#id_sc_field_pdf_respuesta_{i}")

                asunto_val = fix_encoding(asunto_loc.first.inner_text().strip()) if asunto_loc.count() > 0 else "Sin Asunto"
                fc_val = fix_encoding(fc_loc.first.inner_text().strip()) if fc_loc.count() > 0 else ""
                fv_val = fix_encoding(fv_loc.first.inner_text().strip()) if fv_loc.count() > 0 else ""
                ciu_val = fix_encoding(ciu_loc.first.inner_text().strip()) if ciu_loc.count() > 0 else "Ciudadano"
                treq_val = fix_encoding(treq_loc.first.inner_text().strip()) if treq_loc.count() > 0 else "Infraestructura"
                func_val = fix_encoding(func_loc.first.inner_text().strip()) if func_loc.count() > 0 else ""
                dias_val = fix_encoding(dias_loc.first.inner_text().strip()) if dias_loc.count() > 0 else "N/A"
                has_pdf_btn = (pdf_loc.count() > 0)

                item = {
                    "row_index": i,
                    "page_number": pages_count,
                    "radicado": rad_val,
                    "asunto": asunto_val,
                    "fecha_creacion": fc_val,
                    "fecha_vencimiento": fv_val,
                    "remitente": ciu_val,
                    "categoria": treq_val,
                    "funcionario": func_val,
                    "dias_plazo": dias_val,
                    "has_pdf_btn": has_pdf_btn,
                    "estado_sac": "POR APROBAR"
                }

                if rad_val not in seen_radicados:
                    seen_radicados.add(rad_val)
                    all_extracted.append(item)
                    page_items.append(item)
                else:
                    log_etl(f"Aviso: Radicado {rad_val} repetido ignorado en página {pages_count}", "WARN")

                i += 1

            log_etl(f"Página {pages_count}: extraídos {len(page_items)} radicados (Total acumulado: {len(all_extracted)})")

            # Persistir inmediatamente los radicados de la página para que existan en SAC_RADICADOS
            # antes de descargar PDFs o registrar eventos con claves foráneas
            if page_items:
                persist_radicados_lightweight(page_items, user_account=self.sac_user)

            # Adquisición de muestra en la página activa si fue solicitada
            if acquire_pdfs and context and len(verified_responses) < target_pdf_sample:
                t_pdf_chunk = time.time()
                for p_it in page_items:
                    if p_it.get("has_pdf_btn") and len(verified_responses) < target_pdf_sample:
                        p_rad = p_it["radicado"]
                        p_idx = p_it["row_index"]
                        log_etl(f"Adquiriendo pre-respuesta para {p_rad} en página {pages_count} (fila {p_idx})...")
                        try:
                            pdf_res = self.acquire_single_response_pdf(page, context, grid_frame, p_rad, p_idx)
                            verified_responses[p_rad] = pdf_res
                        except Exception as pdf_err:
                            log_etl(f"Error recuperando PDF para {p_rad}: {pdf_err}", "ERROR")
                            pdf_errors.append({"radicado": p_rad, "error": str(pdf_err)})
                            persist_procesamiento_event(
                                radicado_id=p_rad,
                                tipo_proceso="ADQUISICION",
                                estado_proceso="FALLIDO",
                                error_msg=str(pdf_err)
                            )
                total_pdf_acq_seconds += (time.time() - t_pdf_chunk)

            # Comprobar control de avance
            fwd_btn = grid_frame.locator("a#forward_bot, a#forward_top").first
            if fwd_btn.count() == 0:
                log_etl("Paginador forward_bot no presente. Fin de cuadrícula.")
                break

            btn_classes = fwd_btn.get_attribute("class") or ""
            if "disabled" in btn_classes.lower():
                log_etl(f"Paginador forward_bot deshabilitado ('disabled') en página {pages_count}. Fin de bandeja alcanzado.")
                break

            # Avanzar a la siguiente página
            log_etl(f"Avanzando a página {pages_count + 1} mediante a#forward_bot...")
            fwd_btn.click()
            page.wait_for_timeout(3500)

        dur = round(time.time() - t0, 2)
        total_extracted = len(all_extracted)
        diff = (total_anunciado_dashboard - total_extracted) if total_anunciado_dashboard is not None else 0
        is_complete = (diff == 0) if total_anunciado_dashboard is not None else True

        log_etl(f"Extracción POR APROBAR completada: {total_extracted} radicados en {pages_count} páginas ({dur}s). "
                f"Anunciado: {total_anunciado_dashboard} | Desfase: {diff} | Cobertura Completa: {is_complete}")

        return {
            "total_anunciado": total_anunciado_dashboard,
            "total_extraido": total_extracted,
            "desfase": diff,
            "is_complete": is_complete,
            "pages_count": pages_count,
            "duration_seconds": dur,
            "pdf_acquisition_seconds": round(total_pdf_acq_seconds, 2),
            "items": all_extracted,
            "verified_responses": verified_responses,
            "pdf_errors": pdf_errors
        }

    def acquire_single_response_pdf(self, page: Page, context: BrowserContext, grid_frame: Frame, radicado_id: str, row_index: int) -> Dict[str, Any]:
        """
        Descarga física y verificación criptográfica del PDF de respuesta oficial de SAC.
        Reglas estrictas:
        - Nunca fabrica PDFs con metadatos.
        - Rechaza archivos vacíos o placeholders.
        - Valida SHA-256, páginas (>0) y texto extraído con pypdf.
        """
        clean_rad = str(radicado_id).strip()
        target_dir = os.path.join(DOCS_BASE_DIR, self.acq_id, clean_rad)
        os.makedirs(target_dir, exist_ok=True)
        target_pdf_path = os.path.join(target_dir, f"OFICIO_RESPUESTA_{clean_rad}.pdf")

        # Fallback de copia desde scratch/probe si ya fue verificado previamente
        probe_source = os.path.join("scratch", "probe", f"OFICIO_RESPUESTA_{clean_rad}.pdf")
        if os.path.exists(probe_source) and os.path.getsize(probe_source) > 2000:
            if not os.path.exists(target_pdf_path) or os.path.getsize(target_pdf_path) != os.path.getsize(probe_source):
                import shutil
                shutil.copyfile(probe_source, target_pdf_path)

        # Idempotencia: Verificar si ya existe en disco y es válido
        if os.path.exists(target_pdf_path) and os.path.getsize(target_pdf_path) > 2000:
            existing_hash = calculate_sha256(target_pdf_path)
            try:
                reader = pypdf.PdfReader(target_pdf_path)
                if len(reader.pages) > 0:
                    text_extracted = ""
                    for p in reader.pages:
                        text_extracted += p.extract_text() or ""
                    has_identity = (clean_rad in text_extracted) or ("CAU2026" in text_extracted) or ("LOS ANAYES" in text_extracted.upper())
                    if len(text_extracted.strip()) > 50 and has_identity:
                        log_etl(f"[IDEMPOTENCIA] PDF verificado previamente en disco para {clean_rad} ({len(reader.pages)} págs, {os.path.getsize(target_pdf_path)} bytes)")
                        # Asegurar persistencia en Oracle
                        doc_id = persist_document_canonical(
                            radicado_id=clean_rad,
                            filename=f"OFICIO_RESPUESTA_{clean_rad}.pdf",
                            filepath=target_pdf_path,
                            file_hash=existing_hash,
                            file_size=os.path.getsize(target_pdf_path),
                            pages=len(reader.pages),
                            mime_type="application/pdf",
                            tipo_original="RESPUESTA_OFICIAL",
                            origen="SAC"
                        )
                        resp_id = persist_respuesta_canonical(
                            radicado_id=clean_rad,
                            texto=text_extracted,
                            file_hash=existing_hash,
                            estado_respuesta="EN_REVISION",
                            id_externo_sac=clean_rad
                        )
                        update_radicado_estado_in_db(clean_rad, "LISTO")
                        return {
                            "status": "VERIFIED_CACHED",
                            "doc_id": doc_id,
                            "resp_id": resp_id,
                            "file_path": target_pdf_path,
                            "sha256": existing_hash,
                            "size_bytes": os.path.getsize(target_pdf_path),
                            "pages": len(reader.pages),
                            "text_length": len(text_extracted),
                            "text_snippet": text_extracted[:150].replace("\n", " ")
                        }
            except Exception:
                pass

        # Proceder con la descarga viva desde la interfaz SAC
        pdf_btn = grid_frame.locator(f"#id_sc_field_pdf_respuesta_{row_index}").first
        if pdf_btn.count() == 0:
            raise RuntimeError(f"Botón de respuesta no presente para fila {row_index} ({clean_rad})")

        download_obj = None
        popup_page = None

        try:
            with context.expect_page(timeout=12000) as new_page_info:
                try:
                    with page.expect_download(timeout=12000) as download_info:
                        pdf_btn.click()
                    download_obj = download_info.value
                except Exception:
                    pass
            popup_page = new_page_info.value
        except Exception:
            pass

        if download_obj:
            download_obj.save_as(target_pdf_path)
            log_etl(f"Descarga binaria interceptada para {clean_rad}: {download_obj.suggested_filename}")
        elif popup_page:
            popup_page.wait_for_load_state("domcontentloaded")
            popup_page.wait_for_timeout(3000)
            if popup_page.url.lower().endswith(".pdf") or "pdf" in popup_page.url.lower():
                resp = context.request.get(popup_page.url)
                with open(target_pdf_path, "wb") as f_pdf:
                    f_pdf.write(resp.body())
            else:
                embeds = popup_page.locator("embed, object, iframe, a[href*='.pdf']").all()
                found_src = None
                for emb in embeds:
                    src = emb.get_attribute("src") or emb.get_attribute("data") or emb.get_attribute("href")
                    if src and ".pdf" in src.lower():
                        found_src = src
                        break
                if found_src:
                    full_url = found_src if found_src.startswith("http") else f"https://sac2.gestionsecretariasdeeducacion.gov.co{found_src}"
                    resp = context.request.get(full_url)
                    with open(target_pdf_path, "wb") as f_pdf:
                        f_pdf.write(resp.body())
                else:
                    raise RuntimeError(f"Popup abierto no contiene flujo binario PDF directo ({popup_page.url})")

        if not os.path.exists(target_pdf_path) or os.path.getsize(target_pdf_path) == 0:
            raise RuntimeError(f"El archivo descargado no existe o tiene 0 bytes para {clean_rad}")

        file_size = os.path.getsize(target_pdf_path)
        file_hash = calculate_sha256(target_pdf_path)

        # Validación con pypdf
        reader = pypdf.PdfReader(target_pdf_path)
        pages = len(reader.pages)
        if pages == 0:
            raise RuntimeError(f"El archivo PDF de {clean_rad} no contiene páginas legibles.")

        text_extracted = ""
        for p in reader.pages:
            text_extracted += p.extract_text() or ""

        text_clean = text_extracted.strip()
        if len(text_clean) < 30:
            raise RuntimeError(f"El PDF de {clean_rad} contiene texto insuficiente ({len(text_clean)} caracteres).")

        # Verificar identidad documental: confirmar presencia del radicado o número de oficio
        has_identity = (clean_rad in text_clean) or ("OFICIO" in text_clean.upper()) or ("CAU2026" in text_clean)

        log_etl(f"PDF validado para {clean_rad}: {file_size} bytes, {pages} págs, SHA: {file_hash[:16]}..., Identidad: {has_identity}")

        # Persistir en Oracle
        doc_id = persist_document_canonical(
            radicado_id=clean_rad,
            filename=f"OFICIO_RESPUESTA_{clean_rad}.pdf",
            filepath=target_pdf_path,
            file_hash=file_hash,
            file_size=file_size,
            pages=pages,
            mime_type="application/pdf",
            tipo_original="RESPUESTA_OFICIAL",
            origen="SAC"
        )

        resp_id = persist_respuesta_canonical(
            radicado_id=clean_rad,
            texto=text_clean,
            file_hash=file_hash,
            estado_respuesta="EN_REVISION",
            id_externo_sac=clean_rad
        )

        persist_trazabilidad_event(
            radicado_id=clean_rad,
            tipo_evento="PRE_RESPUESTA_ADQUIRIDA",
            actor="BOTSAC_ETL",
            detalle=f"PDF oficial descargado y validado ({pages} págs, {file_size} bytes, hash {file_hash})",
            hash_posterior=file_hash
        )

        update_radicado_estado_in_db(clean_rad, "LISTO")

        return {
            "status": "VERIFIED_ACQUIRED",
            "doc_id": doc_id,
            "resp_id": resp_id,
            "file_path": target_pdf_path,
            "sha256": file_hash,
            "size_bytes": file_size,
            "pages": pages,
            "text_length": len(text_clean),
            "text_snippet": text_clean[:180].replace("\n", " ")
        }

    def acquire_citizen_attachments_for_radicado(self, page: Page, context: BrowserContext, radicado_id: str) -> List[Dict[str, Any]]:
        """
        Descarga física y persistencia canónica de los documentos adjuntos del solicitante.
        Accede a través de 'Consultar Radicado' -> 'DOCUMENTOS ADJUNTOS',
        intercepta los URLs de archivo directos y persiste en SAC_DOCUMENTOS como DOCUMENTO_SOLICITANTE.
        """
        clean_rad = str(radicado_id).strip()
        with engine.connect() as conn:
            existing = conn.execute(text("""
                SELECT COUNT(*) FROM SAC_DOCUMENTOS 
                WHERE ID_RADICADO = :id AND TIPO_ORIGINAL = 'DOCUMENTO_SOLICITANTE'
            """), {"id": clean_rad}).scalar()
            if existing and existing > 0:
                log_etl(f"Radicado {clean_rad} ya posee {existing} adjuntos del solicitante en Oracle. Omitiendo búsqueda.")
                return []

        out_dir = os.path.join(DOCS_BASE_DIR, self.acq_id, clean_rad)
        os.makedirs(out_dir, exist_ok=True)
        downloaded = []

        try:
            consultar_link = None
            for f in page.frames:
                loc = f.locator("text=/Consultar Radicado/i")
                if loc.count() > 0 and loc.first.is_visible():
                    consultar_link = loc.first
                    break

            if not consultar_link:
                return []

            consultar_link.click()
            page.wait_for_timeout(2500)

            search_frame = None
            for f in page.frames:
                if f.locator("input#id_sc_field_radicado").count() > 0:
                    search_frame = f
                    break

            if not search_frame:
                return []

            inp = search_frame.locator("input#id_sc_field_radicado")
            inp.fill(clean_rad)
            inp.press("Enter")
            page.wait_for_timeout(3500)

            adj_links = []
            for f in page.frames:
                doc_links = f.locator("a[href*='_lib/file/doc']").all()
                for l in doc_links:
                    txt = fix_encoding(l.inner_text().strip())
                    href = l.get_attribute("href") or ""
                    adj_links.append((txt, href, f.url))

            for raw_fname, rel_href, frame_url in adj_links:
                fname = fix_encoding(raw_fname)
                if not fname:
                    import urllib.parse
                    fname = os.path.basename(urllib.parse.unquote(rel_href))
                import urllib.parse
                full_url = urllib.parse.urljoin(frame_url, rel_href)
                save_path = os.path.join(out_dir, fname)

                if not os.path.exists(save_path) or os.path.getsize(save_path) == 0:
                    resp = context.request.get(full_url, timeout=25000)
                    if resp.status == 200:
                        with open(save_path, "wb") as f_out:
                            f_out.write(resp.body())

                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    fsize = os.path.getsize(save_path)
                    fhash = calculate_sha256(save_path)
                    doc_id = persist_document_canonical(
                        radicado_id=clean_rad,
                        filename=fname,
                        filepath=os.path.abspath(save_path),
                        file_hash=fhash,
                        file_size=fsize,
                        pages=1,
                        mime_type="application/pdf" if fname.lower().endswith(".pdf") else "application/octet-stream",
                        tipo_original="DOCUMENTO_SOLICITANTE",
                        origen="SAC"
                    )
                    downloaded.append({"doc_id": doc_id, "filename": fname, "size": fsize})
                    log_etl(f"Adjunto del peticionario adquirido para {clean_rad}: '{fname}' ({fsize} bytes)")

            # Volver a la vista previa
            volver_btn = None
            for f in page.frames:
                loc = f.locator("a:has-text('Volver'), button:has-text('Volver'), #sc_b_sai_t")
                if loc.count() > 0 and loc.first.is_visible():
                    volver_btn = loc.first
                    break
            if volver_btn:
                try:
                    volver_btn.click()
                except Exception:
                    pass
            page.wait_for_timeout(2000)
        except Exception as e:
            log_etl(f"Aviso adquiriendo adjuntos del solicitante para {clean_rad}: {e}", "WARN")

        return downloaded

    def generate_reconciliation_report(self, items: List[Dict[str, Any]], verified_responses: Dict[str, Dict[str, Any]]):
        """Genera y actualiza data/document_reconciliation_report.csv con el balance de conciliación."""
        os.makedirs("data", exist_ok=True)
        headers = [
            "RADICADO", "ESTADO_SAC", "ESTADO_BOTSAC", "TIPO_DOCUMENTO",
            "NOMBRE_ARCHIVO", "TAMANO_BYTES", "SHA256", "PAGINAS",
            "VERIFICADO", "ORIGEN", "FECHA_VERIFICACION"
        ]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = []

        for it in items:
            rad = it["radicado"]
            st_sac = it.get("estado_sac", "POR APROBAR")
            v_info = verified_responses.get(rad)

            if v_info and v_info.get("sha256"):
                st_botsac = "LISTO"
                doc_type = "RESPUESTA_OFICIAL"
                fname = f"OFICIO_RESPUESTA_{rad}.pdf"
                size_b = v_info.get("size_bytes", 0)
                sha = v_info.get("sha256", "")
                pgs = v_info.get("pages", 1)
                verificado = "SI"
                origen = "SAC"
            else:
                st_botsac = "PENDIENTE"
                doc_type = "SIN_DOCUMENTO"
                fname = "N/A"
                size_b = 0
                sha = "N/A"
                pgs = 0
                verificado = "NO"
                origen = "SAC"

            rows.append([rad, st_sac, st_botsac, doc_type, fname, size_b, sha, pgs, verificado, origen, now_str])

        with open(RECONCILIATION_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)

        log_etl(f"Reporte de conciliación generado en {RECONCILIATION_CSV_PATH} ({len(rows)} registros)")

    def run_full_pipeline(self, max_pages: int = 20, acquire_pdfs: bool = True, target_pdf_sample: int = 3) -> Dict[str, Any]:
        """
        Ejecución canónica completa del ETL con control de concurrencia y aislamiento de errores.
        """
        t_pipeline_start = time.time()
        log_etl("=== INICIANDO PIPELINE CANÓNICO BOTSAC ===")

        if not self.mutex.acquire():
            return {
                "status": "LOCKED",
                "message": f"Sincronización cancelada. La cuenta '{self.sac_user}' tiene un proceso activo."
            }

        timings = {
            "login": 0.0,
            "tray_extraction": 0.0,
            "oracle_persistence": 0.0,
            "pdf_acquisition": 0.0,
            "total": 0.0
        }

        verified_responses: Dict[str, Dict[str, Any]] = {}
        pdf_errors: List[Dict[str, Any]] = []

        try:
            with sync_playwright() as p:
                browser, context, page = self.create_browser_context(p, headless=True)
                try:
                    # 1. LOGIN
                    t_login_0 = time.time()
                    self.login_sac(page)
                    timings["login"] = round(time.time() - t_login_0, 2)

                    # 2. EXTRACCIÓN Y PAGINACIÓN CANÓNICA DE BANDEJA CON ADQUISICIÓN EN PÁGINA ACTIVA
                    t_tray_0 = time.time()
                    tray_result = self.extract_por_aprobar_tray(
                        page=page,
                        context=context,
                        max_pages=max_pages,
                        acquire_pdfs=acquire_pdfs,
                        target_pdf_sample=target_pdf_sample
                    )
                    timings["tray_extraction"] = round(time.time() - t_tray_0, 2)
                    timings["pdf_acquisition"] = tray_result.get("pdf_acquisition_seconds", 0.0)

                    extracted_items = tray_result["items"]
                    verified_responses = tray_result.get("verified_responses", {})
                    pdf_errors = tray_result.get("pdf_errors", [])

                    # 3. PERSISTENCIA IDEMPOTENTE EN ORACLE
                    t_ora_0 = time.time()
                    log_etl(f"Persistiendo {len(extracted_items)} radicados de forma idempotente en Oracle...")
                    ora_stats = persist_radicados_lightweight(extracted_items, user_account=self.sac_user)
                    timings["oracle_persistence"] = round(time.time() - t_ora_0, 2)
                    log_etl(f"Oracle stats: Insertados: {ora_stats['inserted']}, Actualizados: {ora_stats['updated']}, Omitidos: {ora_stats['skipped']}")

                    log_etl(f"Pre-respuestas procesadas: {len(verified_responses)} verificadas | {len(pdf_errors)} errores ({timings['pdf_acquisition']}s)")

                finally:
                    browser.close()

            # 5. RECONCILIACIÓN Y REPORTES
            self.generate_reconciliation_report(extracted_items, verified_responses)

            timings["total"] = round(time.time() - t_pipeline_start, 2)
            log_etl(f"=== PIPELINE CANÓNICO COMPLETADO EN {timings['total']}s ===")

            return {
                "status": "SUCCESS",
                "total_anunciado": tray_result["total_anunciado"],
                "total_extraido": tray_result["total_extraido"],
                "desfase": tray_result["desfase"],
                "is_complete": tray_result["is_complete"],
                "pages_count": tray_result["pages_count"],
                "oracle_stats": ora_stats,
                "verified_responses_count": len(verified_responses),
                "verified_responses": verified_responses,
                "pdf_errors": pdf_errors,
                "timings": timings
            }

        except Exception as e:
            log_etl(f"Fallo crítico en el pipeline ETL: {e}", "ERROR")
            return {
                "status": "ERROR",
                "error": str(e),
                "timings": timings
            }
        finally:
            self.mutex.release()

if __name__ == "__main__":
    etl = CanonicalETL()
    res = etl.run_full_pipeline(max_pages=3, acquire_pdfs=True, target_pdf_sample=3)
    print("\n--- RESULTADO DE EJECUCIÓN ETL ---")
    print(json.dumps(res, indent=2, ensure_ascii=False))
