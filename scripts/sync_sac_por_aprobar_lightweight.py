import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Asegurar path para imports
sys.path.append(os.path.abspath("."))
from backend.oracle_service import persist_radicados_lightweight

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")
LOG_PATH = "data/oracle_lightweight_sync.log"

def log_event(msg: str):
    os.makedirs("data", exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
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

def parse_grid_rows(frame) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    v_rows = frame.locator("tr").all()
    col_indices: Dict[str, int] = {}
    headers_texts: List[str] = []

    # Localizar encabezados
    for r in v_rows:
        try:
            if r.locator("table").count() > 0:
                continue
            cells = r.locator("xpath=./td | ./th").all()
            if len(cells) > 3:
                texts = [th.inner_text().strip().upper() for th in cells]
                if any("RADICADO" in t for t in texts):
                    headers_texts = texts
                    for i, h in enumerate(headers_texts):
                        if "RADICADO" in h: col_indices["radicado"] = i
                        elif "ASUNTO" in h: col_indices["asunto"] = i
                        elif "FECHA CREACI" in h: col_indices["fecha_creacion"] = i
                        elif "CIUDADANO" in h: col_indices["ciudadano"] = i
                        elif "TIPO DE REQUERIMIENTO" in h or "CATEGORIA" in h: col_indices["categoria"] = i
                        elif "FECHA VENC" in h: col_indices["fecha_vencimiento"] = i
                        elif "FUNCIONARIO" in h: col_indices["funcionario"] = i
                        elif "PLAZO" in h or "DÍAS" in h or "DIAS" in h: col_indices["dias_plazo"] = i
                    break
        except Exception:
            pass

    if "radicado" not in col_indices:
        return [], col_indices

    extracted: List[Dict[str, Any]] = []
    rad_idx = col_indices["radicado"]

    for r in v_rows:
        try:
            if r.locator("table").count() > 0:
                continue
            cells = r.locator("xpath=./td").all()
            if len(cells) > rad_idx:
                raw_rad = cells[rad_idx].inner_text().strip()
                if not raw_rad or raw_rad.upper() == "RADICADO" or len(raw_rad) < 5 or "[" in raw_rad or " de " in raw_rad.lower():
                    continue

                cell_texts = [c.inner_text().strip() for c in cells]
                asunto_i = col_indices.get("asunto", -1)
                fc_i = col_indices.get("fecha_creacion", -1)
                fv_i = col_indices.get("fecha_vencimiento", -1)
                rem_i = col_indices.get("ciudadano", -1)
                cat_i = col_indices.get("categoria", -1)
                func_i = col_indices.get("funcionario", -1)
                plazo_i = col_indices.get("dias_plazo", -1)

                rad_val = fix_encoding(raw_rad)
                asunto_val = fix_encoding(cell_texts[asunto_i]) if asunto_i != -1 and asunto_i < len(cell_texts) else "Sin asunto"
                fc_val = fix_encoding(cell_texts[fc_i]) if fc_i != -1 and fc_i < len(cell_texts) else ""
                fv_val = fix_encoding(cell_texts[fv_i]) if fv_i != -1 and fv_i < len(cell_texts) else ""
                rem_val = fix_encoding(cell_texts[rem_i]) if rem_i != -1 and rem_i < len(cell_texts) else "Ciudadano"
                cat_val = fix_encoding(cell_texts[cat_i]) if cat_i != -1 and cat_i < len(cell_texts) else "Infraestructura"
                func_val = fix_encoding(cell_texts[func_i]) if func_i != -1 and func_i < len(cell_texts) else ""
                plazo_val = fix_encoding(cell_texts[plazo_i]) if plazo_i != -1 and plazo_i < len(cell_texts) else "N/A"

                is_venc = "VENC" in plazo_val.upper()

                extracted.append({
                    "radicado": rad_val,
                    "asunto": asunto_val,
                    "fecha_creacion": fc_val,
                    "fecha_vencimiento": fv_val,
                    "remitente": rem_val,
                    "categoria": cat_val,
                    "funcionario": func_val,
                    "dias_plazo": plazo_val,
                    "is_vencido": is_venc,
                    "estado_sac": "POR APROBAR"
                })
        except Exception:
            pass

    return extracted, col_indices

def sync_sac_por_aprobar_lightweight(max_pages: int = 5, headless: bool = True) -> Dict[str, Any]:
    """
    Sincronización liviana institucional de la bandeja 'POR APROBAR'.
    1. Inicia sesión en SAC institucional.
    2. Navega directamente al enlace 'POR APROBAR'.
    3. Lee la cuadrícula página por página sin abrir expedientes individuales.
    4. Normaliza los metadatos.
    5. Persiste en Oracle de forma idempotente.
    6. Mide tiempos por etapa.
    """
    t_total_start = time.time()
    timings = {
        "login": 0.0,
        "navigation": 0.0,
        "grid_extraction": 0.0,
        "normalization": 0.0,
        "oracle_persistence": 0.0,
        "total": 0.0
    }

    log_event("INICIANDO INGESTA LIVIANA SAC - BANDEJA POR APROBAR")

    if not SAC_URL or not SAC_USER or not SAC_PASS:
        raise ValueError("Variables de entorno SAC_URL, SAC_USER o SAC_PASS no configuradas.")

    all_items: List[Dict[str, Any]] = []
    seen_radicados = set()
    pages_processed = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="es-CO",
            timezone_id="America/Bogota"
        )
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 1. LOGIN
        t_login_start = time.time()
        log_event(f"Navegando a portal SAC: {SAC_URL}")
        page.goto(SAC_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
        page.locator('input#id_sc_field_login').fill(SAC_USER)
        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
        page.locator('input.btn-login[value="Ingresar"]').click()

        page.wait_for_timeout(5000)

        # Manejo de modal institucional
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
        timings["login"] = round(time.time() - t_login_start, 2)
        log_event(f"Login institucional completado en {timings['login']}s")

        # 2. NAVEGACIÓN A POR APROBAR
        t_nav_start = time.time()
        log_event("Localizando sección 'POR APROBAR' en dashboard...")
        target_link = None
        timeout_end = time.time() + 30

        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    locs = f.locator("text=/POR APROBAR/i").all()
                    for loc in locs:
                        if loc.is_visible():
                            tag = loc.evaluate("el => el.tagName").upper()
                            if tag == "A" or loc.evaluate("el => el.getAttribute('onclick')"):
                                target_link = loc
                            elif loc.locator("xpath=ancestor::a").count() > 0:
                                target_link = loc.locator("xpath=ancestor::a").first
                            elif loc.locator("xpath=ancestor::tr").count() > 0:
                                target_link = loc.locator("xpath=ancestor::tr").first
                            else:
                                target_link = loc
                            if target_link:
                                break
                except Exception:
                    pass
                if target_link:
                    break
            if target_link:
                break
            page.wait_for_timeout(1000)

        if not target_link:
            browser.close()
            raise RuntimeError("No se encontró el enlace o sección 'POR APROBAR' en el dashboard.")

        try:
            target_link.click(timeout=5000)
        except Exception:
            target_link.evaluate("el => el.click()")

        # Esperar iframe con la cuadrícula
        aprobaciones_frame = None
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO'), td:has-text('Radicado')").count() > 0:
                        aprobaciones_frame = f
                        break
                except Exception:
                    pass
            if aprobaciones_frame:
                break
            page.wait_for_timeout(1000)

        if not aprobaciones_frame:
            browser.close()
            raise RuntimeError("No cargó el frame de la cuadrícula de 'POR APROBAR'.")

        timings["navigation"] = round(time.time() - t_nav_start, 2)
        log_event(f"Navegación a 'POR APROBAR' completada en {timings['navigation']}s")

        # 3. LECTURA DE PÁGINAS (SIN ABRIR EXPEDIENTES)
        t_grid_start = time.time()
        for page_idx in range(max_pages):
            pages_processed += 1
            log_event(f"Extrayendo cuadrícula de página {pages_processed}...")
            page.wait_for_timeout(1500)

            # Reubicar frame
            for f in page.frames:
                try:
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                        aprobaciones_frame = f
                        break
                except Exception:
                    pass

            page_items, cols = parse_grid_rows(aprobaciones_frame)
            log_event(f"Página {pages_processed}: {len(page_items)} radicados identificados (columnas: {list(cols.keys())})")

            for item in page_items:
                r_num = item["radicado"]
                if r_num not in seen_radicados:
                    seen_radicados.add(r_num)
                    all_items.append(item)

            # Verificar si hay botón siguiente y no está deshabilitado
            next_btn = aprobaciones_frame.locator("a#forward_bot, a#forward_top, a#sc_b_avc_bot, a#sc_b_avc_top, img[title*='Siguiente']").first
            has_next = False
            try:
                if next_btn.count() > 0 and next_btn.is_visible():
                    cls = next_btn.get_attribute("class") or ""
                    if "disabled" not in cls.lower():
                        has_next = True
            except Exception:
                has_next = False

            if has_next and pages_processed < max_pages:
                log_event("Avanzando a siguiente página...")
                try:
                    next_btn.click(timeout=5000)
                except Exception:
                    next_btn.evaluate("el => el.click()")
                page.wait_for_timeout(3000)
            else:
                break

        timings["grid_extraction"] = round(time.time() - t_grid_start, 2)
        log_event(f"Extracción de cuadrícula terminada: {len(all_items)} radicados en {pages_processed} página(s) en {timings['grid_extraction']}s")

        browser.close()

    # 4. NORMALIZACIÓN
    t_norm_start = time.time()
    # (Ya vienen estructurados, aseguramos limpieza)
    for it in all_items:
        it["asunto"] = it["asunto"].strip()
        it["remitente"] = it["remitente"].strip()
        it["funcionario"] = it["funcionario"].strip()
    timings["normalization"] = round(time.time() - t_norm_start, 2)

    # 5. PERSISTENCIA EN ORACLE
    t_ora_start = time.time()
    log_event(f"Persistiendo {len(all_items)} radicados en Oracle (esquema BOTSAC)...")
    ora_stats = persist_radicados_lightweight(all_items)
    timings["oracle_persistence"] = round(time.time() - t_ora_start, 2)

    timings["total"] = round(time.time() - t_total_start, 2)

    log_event(f"Sincronización completada en {timings['total']}s. "
              f"Leídos: {ora_stats['read']} | Insertados: {ora_stats['inserted']} | "
              f"Actualizados: {ora_stats['updated']} | Omitidos: {ora_stats['skipped']} | "
              f"Fallidos: {ora_stats['failed']}")

    return {
        "status": "OK",
        "radicados_read": ora_stats["read"],
        "inserted": ora_stats["inserted"],
        "updated": ora_stats["updated"],
        "skipped": ora_stats["skipped"],
        "failed": ora_stats["failed"],
        "pages_processed": pages_processed,
        "items": all_items,
        "timings": timings
    }

if __name__ == "__main__":
    result = sync_sac_por_aprobar_lightweight(max_pages=2, headless=True)
    print("\n--- RESUMEN FINAL ---")
    print(f"Radicados leídos de SAC: {result['radicados_read']}")
    print(f"Insertados en Oracle:    {result['inserted']}")
    print(f"Actualizados en Oracle:  {result['updated']}")
    print(f"Omitidos:                {result['skipped']}")
    print(f"Fallidos:                {result['failed']}")
    print(f"Tiempos (s):             {result['timings']}")
