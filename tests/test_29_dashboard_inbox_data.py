import os
import time
import json
import pytest
from datetime import datetime
from playwright.sync_api import Page
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

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

def test_29_dashboard_inbox_data(page: Page):
    assert SAC_USER and SAC_PASS and SAC_URL, "Faltan credenciales"
    print(f"\n[{datetime.now().isoformat()}] Iniciando TEST 29: ADQUISICIÓN METADATA BANDEJA...")
    
    try:
        # LOGIN
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
            
        page.wait_for_load_state("load")
        page.wait_for_timeout(5000)
        
        # PASO 2: Mis Sub-Dependencias
        print("Buscando 'Mis Sub-Dependencias'...")
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
            
        assert menu_clicked, "No se encontró 'Mis Sub-Dependencias'"
        page.wait_for_timeout(3000)
        
        # PASO 3: Por Dependencias (Clic en REQUERIMIENTOS)
        print("Esperando REQUERIMIENTOS...")
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
        
        # PASO 4: ASIGNADOS POR DEPENDENCIAS -> Infraestructura Educativa
        print("Esperando ASIGNADOS POR DEPENDENCIAS...")
        asignados_frame = None
        target_dep = "Infraestructura Educativa"
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if f.locator("text=/ASIGNADOS POR DEPENDENCIAS/i").count() > 0:
                        asignados_frame = f
                        break
                except: pass
            if asignados_frame: break
            page.wait_for_timeout(1000)
                
        assert asignados_frame is not None, "No se encontró ASIGNADOS POR DEPENDENCIAS"
        
        loc_dep = asignados_frame.locator(f"text=/{target_dep}/i")
        assert loc_dep.count() > 0, f"No se encontró {target_dep}"
        
        try:
            loc_dep.first.click(timeout=5000)
        except:
            loc_dep.first.evaluate("el => el.click()")
            
        # PASO 5: Extraer info de todos los funcionarios con radicados
        print("Esperando ASIGNADOS POR FUNCIONARIOS...")
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
        
        inbox_data = []
        officials = []

        rows = funcionarios_frame.locator("tr").all()
        for idx, row in enumerate(rows):
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
                    if ct and not ct.isdigit() and len(ct) > 3: # Nombre
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
                                    "count": vencidos_val
                                })
                                break
            except: pass

        print(f"Funcionarios encontrados con casos: {len(officials)}")
        
        # Iterar sobre funcionarios hasta llegar a 20 radicados
        for official in officials:
            if len(inbox_data) >= 20: break
            
            # Tenemos que volver a localizar el frame en caso de que se haya recargado
            f_frame = None
            for f in page.frames:
                try:
                    if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0:
                        f_frame = f
                        break
                except: pass
            
            if not f_frame: continue
            
            target_link = None
            rows = f_frame.locator("tr").all()
            for r in rows:
                if official["name"] in r.inner_text():
                    links = r.locator("a").all()
                    for l in links:
                        h = l.evaluate("el => el.getAttribute('href')") or l.evaluate("el => el.getAttribute('onclick')") or ""
                        if official["href"] == h:
                            target_link = l
                            break
                    if target_link: break
            
            if not target_link: continue
            
            print(f"Clicando funcionario: {official['name']}")
            try:
                target_link.click(timeout=5000)
            except:
                target_link.evaluate("el => el.click()")
                
            print("Esperando lista de radicados...")
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
                
            if not vencidos_frame: continue
            
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
                    
            for idx, row in enumerate(v_rows):
                if len(inbox_data) >= 20: break
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
                            inbox_data.append(item)
                except: pass
                
            # Regresar al listado de funcionarios haciendo clic en Infraestructura Educativa de nuevo
            try:
                asignados_frame.locator(f"text=/Infraestructura Educativa/i").first.click(timeout=5000)
            except:
                try:
                    asignados_frame.locator(f"text=/Infraestructura Educativa/i").first.evaluate("el => el.click()")
                except: pass
            page.wait_for_timeout(2000)

        print(f"Se extrajeron {len(inbox_data)} radicados en total.")
        
        os.makedirs("data", exist_ok=True)
        out_path = "data/dashboard_inbox.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(inbox_data, f, indent=4, ensure_ascii=False)
            
        print(f"Datos guardados en {out_path}")
        assert len(inbox_data) > 0, "No se extrajo ningún radicado de la lista"
        print("\n[REPORT] TEST 29: PASS")
        
    except Exception as e:
        page.screenshot(path="data/test_29_error.png")
        print(f"\n[ERROR] TEST 29: FAIL -> {e}")
        raise

if __name__ == "__main__":
    pytest.main(["-v", "tests/test_29_dashboard_inbox_data.py"])
