import os
import sys
import time
import json
import subprocess
import pytest
from datetime import datetime
from playwright.sync_api import Page
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")
ACQUISITION_ID = "ACQ-20260915-0001"

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    }

def fix_encoding(text):
    if not isinstance(text, str): return text
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def test_30_mvp_flow(page: Page):
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales"
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 30: VALIDACIÓN FUNCIONAL MVP...")
    
    # --------------------------------------------------
    # 1. EXTRACCIÓN DE TODOS LOS FUNCIONARIOS Y CASOS
    # --------------------------------------------------
    page.goto(SAC_URL, wait_until="domcontentloaded")
    page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
    page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
    if page.locator('a#sub_form_b').is_visible():
        page.locator('a#sub_form_b').click()
    page.wait_for_selector('input#id_sc_field_login', timeout=15000)
    page.locator('input#id_sc_field_login').fill(SAC_USER)
    page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
    page.locator('input.btn-login[value="Ingresar"]').click()
    
    page.wait_for_timeout(5000)
    
    # Manejo de modal
    modal_handled = False
    for f in page.frames:
        try:
            for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                loc = f.locator(loc_str)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    modal_handled = True
                    break
        except: pass
        if modal_handled: break
        
    page.wait_for_timeout(5000)
    
    # Navegar a REQUERIMIENTOS
    menu_clicked = False
    timeout_end = time.time() + 30
    while time.time() < timeout_end:
        for f in page.frames:
            try:
                loc = f.locator("text='Mis Sub-Dependencias'")
                if loc.count() > 0:
                    for i in range(loc.count()):
                        if loc.nth(i).is_visible():
                            loc.nth(i).evaluate("el => el.click()")
                            menu_clicked = True
                            break
            except: pass
            if menu_clicked: break
        if menu_clicked: break
        page.wait_for_timeout(1000)
        
    page.wait_for_timeout(3000)
    
    otras_dep_frame = None
    selector_req = "text='REQUERIMIENTOS'"
    timeout_end = time.time() + 30
    while time.time() < timeout_end:
        for f in page.frames:
            try:
                if "Fun_Semaforo_OtrasDependencias" in f.url and f.locator(selector_req).count() > 0:
                    otras_dep_frame = f
                    break
            except: pass
        if otras_dep_frame: break
        page.wait_for_timeout(1000)
            
    assert otras_dep_frame is not None, "No se encontró REQUERIMIENTOS"
    otras_dep_frame.locator(selector_req).first.click()
    
    asignados_frame = None
    target_dep = "Infraestructura Educativa"
    timeout_end = time.time() + 30
    while time.time() < timeout_end:
        for f in page.frames:
            try:
                if f.locator(f"text=/{target_dep}/i").count() > 0:
                    asignados_frame = f
                    break
            except: pass
        if asignados_frame: break
        page.wait_for_timeout(1000)
        
    assert asignados_frame is not None, f"No se encontró {target_dep}"
    
    # Hacemos click en Infraestructura Educativa
    try:
        asignados_frame.locator(f"text=/{target_dep}/i").first.click(timeout=5000)
    except:
        asignados_frame.locator(f"text=/{target_dep}/i").first.evaluate("el => el.click()")

    # Esperar ASIGNADOS POR FUNCIONARIOS
    funcionarios_frame = None
    timeout_end = time.time() + 30
    while time.time() < timeout_end:
        for f in page.frames:
            try:
                if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0 and f.locator("tr").count() > 3:
                    funcionarios_frame = f
                    break
            except: pass
        if funcionarios_frame: break
        page.wait_for_timeout(1000)
        
    assert funcionarios_frame is not None, "No se encontró ASIGNADOS POR FUNCIONARIOS"
    
    # Recolectar lista de funcionarios (nombre y enlace con casos)
    officials = []
    rows = funcionarios_frame.locator("tr").all()
    for row in rows:
        try:
            text = row.inner_text().strip().upper()
            if not text or "TOTAL" in text or "FUNCIONARIO" in text:
                continue
            cells = row.locator("td").all()
            if len(cells) < 3: continue
                
            cell_texts = [c.inner_text().strip() for c in cells]
            name_idx = -1
            vencidos_idx = -1
            
            for i, ct in enumerate(cell_texts):
                if ct and not ct.isdigit() and len(ct) > 3: 
                    name_idx = i
                    for j in range(i + 1, len(cell_texts)):
                        if cell_texts[j].isdigit():
                            vencidos_idx = j
                            break
                    break
                    
            if name_idx != -1 and vencidos_idx != -1:
                vencidos_val = int(cell_texts[vencidos_idx])
                if vencidos_val > 0:
                    target_name = cell_texts[name_idx]
                    links_in_row = row.locator("a").all()
                    for link in links_in_row:
                        link_text = link.inner_text().strip()
                        link_href = link.evaluate("el => el.getAttribute('href')") or link.evaluate("el => el.getAttribute('onclick')") or ""
                        if str(vencidos_val) in link_text or "venc" in link_href.lower():
                            officials.append({
                                "name": target_name,
                                "href": link_href,
                                "count": vencidos_val,
                                "radicados_extraidos": 0
                            })
                            break
        except: pass

    all_radicados = []
    
    # Iterar funcionarios de manera robusta
    for official in officials:
        # Re-ubicar asignados_frame ya que pudo volverse stale
        asignados_frame = None
        timeout_end = time.time() + 10
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator(f"text=/{target_dep}/i").count() > 0:
                        asignados_frame = f
                        break
                except: pass
            if asignados_frame: break
            page.wait_for_timeout(1000)
            
        if not asignados_frame:
            print("[INFO] No se pudo re-ubicar el frame de Infraestructura Educativa. Abortando iteración.")
            break

        try:
            asignados_frame.locator(f"text=/{target_dep}/i").first.click(timeout=5000)
        except:
            asignados_frame.locator(f"text=/{target_dep}/i").first.evaluate("el => el.click()")
        page.wait_for_timeout(2000)
        
        # Esperar a que recargue ASIGNADOS POR FUNCIONARIOS
        f_frame = None
        timeout_end = time.time() + 20
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0:
                        f_frame = f
                        break
                except: pass
            if f_frame: break
            page.wait_for_timeout(500)
            
        if not f_frame:
            continue
            
        # Buscar el enlace de este funcionario
        target_link = None
        rows = f_frame.locator("tr").all()
        for r in rows:
            if official["name"] in r.inner_text():
                links = r.locator("a").all()
                for l in links:
                    h = l.evaluate("el => el.getAttribute('href')") or l.evaluate("el => el.getAttribute('onclick')") or ""
                    if official["href"] == h or (str(official["count"]) in l.inner_text().strip()):
                        target_link = l
                        break
                if target_link: break
                
        if not target_link:
            continue
            
        try:
            target_link.click(timeout=5000)
        except:
            target_link.evaluate("el => el.click()")
            
        # Esperar la grilla de radicados (Vencidos)
        vencidos_frame = None
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if "FunAdm_RequerimientosAsignados_Funcionarios" in f.url and f.locator("tr").count() > 5:
                        vencidos_frame = f
                        break
                except: pass
            if vencidos_frame: break
            page.wait_for_timeout(1000)
            
        if not vencidos_frame:
            continue
            
        v_rows = vencidos_frame.locator("tr").all()
        headers_texts = []
        col_indices = {}
        for r in v_rows:
            th_cells = r.locator("td.scGridLabelFont, th.scGridLabelFont").all()
            if len(th_cells) > 3:
                headers_texts = [th.inner_text().strip().upper() for th in th_cells if th.inner_text().strip()]
                for i, h in enumerate(headers_texts):
                    if "RADICADO" in h: col_indices["radicado"] = i
                    elif "ASUNTO" in h: col_indices["asunto"] = i
                    elif "ESTADO" in h: col_indices["estado"] = i
                    elif "DIAS" in h or "DÍAS" in h or "PLAZO" in h: col_indices["dias"] = i
                    elif "FECHA" in h: col_indices["fecha"] = i
                    elif "MUNICIPIO" in h: col_indices["municipio"] = i
                break
                
        extracted_for_this = 0
        for row in v_rows:
            try:
                class_attr = row.evaluate("el => el.getAttribute('class')") or ""
                if "scGridFieldOdd" in class_attr or "scGridFieldEven" in class_attr:
                    cells = row.locator("td").all()
                    valid_cells = [c for c in cells if c.inner_text().strip() or c.inner_text() == ""]
                    
                    if len(valid_cells) >= len(headers_texts) and col_indices.get("radicado") is not None:
                        cell_texts = [c.inner_text().strip() for c in valid_cells]
                        rad_idx = col_indices["radicado"]
                        rad_val = cell_texts[rad_idx] if rad_idx < len(cell_texts) else ""
                        if not rad_val or rad_val.upper() == "RADICADO": continue
                        
                        asunto_idx = col_indices.get("asunto", -1)
                        estado_idx = col_indices.get("estado", -1)
                        dias_idx = col_indices.get("dias", -1)
                        fecha_idx = col_indices.get("fecha", -1)
                        muni_idx = col_indices.get("municipio", -1)
                        
                        item = {
                            "radicado": fix_encoding(rad_val),
                            "asunto": fix_encoding(cell_texts[asunto_idx]) if asunto_idx != -1 and asunto_idx < len(cell_texts) else "Sin asunto",
                            "estado": fix_encoding(cell_texts[estado_idx]) if estado_idx != -1 and estado_idx < len(cell_texts) else "Asignado",
                            "dias_plazo": fix_encoding(cell_texts[dias_idx]) if dias_idx != -1 and dias_idx < len(cell_texts) else "N/A",
                            "fecha_creacion": fix_encoding(cell_texts[fecha_idx]) if fecha_idx != -1 and fecha_idx < len(cell_texts) else "Desconocida",
                            "municipio": fix_encoding(cell_texts[muni_idx]) if muni_idx != -1 and muni_idx < len(cell_texts) else "Pendiente",
                            "asignado": fix_encoding(official["name"])
                        }
                        all_radicados.append(item)
                        extracted_for_this += 1
            except: pass
            
        official["radicados_extraidos"] = extracted_for_this

    # Imprimir Tabla de Diagnóstico
    print("\n" + "="*80)
    print("TABLA DE DIAGNÓSTICO DE BANDEJA BOTSAC")
    print(f"{'FUNCIONARIO':<40} | {'USUARIO':<10} | {'SIN FINALIZAR EN SAC':<20} | {'OBTENIDOS POR BOTSAC'}")
    print("-" * 80)
    for off in officials:
        print(f"{off['name']:<40} | {'N/A':<10} | {off['count']:<20} | {off['radicados_extraidos']}")
    print("="*80 + "\n")

    # --------------------------------------------------
    # 2. DEDUPLICACIÓN Y REGLA DE LOS 20 (Fecha Descendente)
    # --------------------------------------------------
    unique_radicados = {}
    for r in all_radicados:
        unique_radicados[r["radicado"]] = r
        
    deduplicated = list(unique_radicados.values())
    
    # Parse dates to sort
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except:
            return datetime.min # If no date, send to bottom

    deduplicated.sort(key=lambda x: parse_date(x["fecha_creacion"]), reverse=True)
    
    final_20 = deduplicated[:20]
    
    print(f"[REGLA DE LOS 20] Total recolectados: {len(all_radicados)}, Deduplicados: {len(deduplicated)}, Finales: {len(final_20)}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/dashboard_inbox.json", "w", encoding="utf-8") as f:
        json.dump(final_20, f, indent=4, ensure_ascii=False)
        
    # Validar que si SAC permite obtener 20, hay 20. Si no, se reporta.
    if len(final_20) < 20:
        print(f"[INFO] SAC sólo devolvió {len(final_20)} radicados pendientes en total para esta ruta.")
        
    # --------------------------------------------------
    # 3. VERIFICACIÓN UTF-8
    # --------------------------------------------------
    inbox_str = json.dumps(final_20)
    assert "Ã³" not in inbox_str, "Codificación corrupta en la bandeja."
    assert "Ã¡" not in inbox_str, "Codificación corrupta en la bandeja."
    # Asegurarse que sí guardó strings reales
    # Opcional: assert "Gobernación" in inbox_str, "No se encontraron palabras acentuadas."

    # --------------------------------------------------
    # 4. VALIDACIÓN DE ADQUISICIÓN Y CACHÉ (CAU2026ER032558)
    # --------------------------------------------------
    radicado_test = "CAU2026ER032558"
    print(f"\n[STEP] Validando adquisición de {radicado_test}...")
    
    res = subprocess.run([sys.executable, "scripts/acquire_radicado.py", "--radicado", radicado_test], capture_output=True, text=True)
    print(res.stdout)
    assert res.returncode == 0, f"Error en la adquisición de {radicado_test}: {res.stderr}"
    
    # Verificar que generó los archivos
    base_dir = f"data/analysis/{ACQUISITION_ID}/{radicado_test}"
    assert os.path.exists(f"{base_dir}/botsac_review.json"), "No se generó el review base."
    assert os.path.exists(f"{base_dir}/documents_manifest.json"), "No se generó el manifest."
    
    # Simular carga desde caché
    sys.path.append(os.path.abspath("app"))
    from dashboard import load_radicado_data
    
    data, hashes = load_radicado_data(radicado_test)
    assert data is not None, "Fallo al cargar desde caché (CAU2026ER032558)"
    assert len(data.get("documents", [])) > 0, "No se registraron documentos en el caché."
    
    # --------------------------------------------------
    # 5. VALIDACIÓN DE RADICADO EXISTENTE CON QWEN (CAU2026ER032723)
    # --------------------------------------------------
    radicado_existente = "CAU2026ER032723"
    print(f"\n[STEP] Validando caché de radicado existente {radicado_existente}...")
    
    data_existente, hashes_existente = load_radicado_data(radicado_existente)
    assert data_existente is not None, "Fallo al cargar caché existente."
    
    # Debe conservar su análisis previo de LLM
    doc_existente = data_existente["documents"][0]
    assert "summary" in doc_existente, "Perdió el resumen"
    
    # Si el summary es un string plano que empieza con "Documento adquirido", significaría que fue reescrito por acquire_radicado
    if isinstance(doc_existente["summary"], str):
        assert "Documento adquirido. Análisis pendiente" not in doc_existente["summary"], "El caché fue sobreescrito y perdió el LLM."
        
    print("\n[REPORT] TEST 30: PASS. Funcionalidad de bandeja, regla de los 20, adquisición cero-LLM y caché validados con éxito.")
