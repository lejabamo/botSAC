import os
import sys
import time
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

def fix_encoding(text):
    if not isinstance(text, str): return text
    try:
        return text.encode('latin1').decode('utf-8')
    except:
        return text

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except:
        return datetime.min

def run_sync():
    print(f"\n[{datetime.now().isoformat()}] INICIANDO SINCRONIZACIÓN DE BANDEJA...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()
        
        # LOGIN
        page.goto(SAC_URL, wait_until="domcontentloaded")
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
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
            
        page.wait_for_timeout(3000)
        
        # PASO 3: Por Dependencias (Clic en REQUERIMIENTOS)
        print("Esperando REQUERIMIENTOS...")
        otras_dep_frame = None
        selector_req = "text='REQUERIMIENTOS'"
        timeout_end = time.time() + 30
        while time.time() < timeout_end:
            for f in page.frames:
                try:
                    if "Semaforo" in f.url and f.locator(selector_req).count() > 0:
                        otras_dep_frame = f
                        break
                except: pass
            if otras_dep_frame: break
            page.wait_for_timeout(1000)
                
        try:
            otras_dep_frame.locator(selector_req).first.click(timeout=3000, force=True)
        except:
            otras_dep_frame.locator(selector_req).first.evaluate("el => el.click()")
        
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
            
        loc_dep = asignados_frame.locator(f"text=/{target_dep}/i")
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
                    if f.locator("text=/ASIGNADOS POR FUNCIONARIOS/i").count() > 0:
                        funcionarios_frame = f
                        break
                except: pass
            if funcionarios_frame: break
            page.wait_for_timeout(1000)
            
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
        
        all_radicados = []
        
        # Iterar sobre funcionarios
        for official in officials:
            print(f"Procesando funcionario: {official['name']}")
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
            
            try:
                target_link.click(timeout=5000)
            except:
                target_link.evaluate("el => el.click()")
                
            vencidos_frame = None
            timeout_end = time.time() + 30
            while time.time() < timeout_end:
                for f in page.frames:
                    try:
                        if "RequerimientosAsignados" in f.url and f.locator("tr").count() > 5:
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
                        elif "DIAS" in h or "DÍAS" in h or "PLAZO" in h or "VENC" in h: col_indices["dias"] = i
                        elif "FECHA" in h: col_indices["fecha"] = i
                        elif "MUNICIPIO" in h: col_indices["municipio"] = i
                    break
                    
            for idx, row in enumerate(v_rows):
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
                            
                            user_funcionario = ""
                            if "DIAZ" in official["name"]: user_funcionario = "adiaz"
                            
                            item = {
                                "radicado": fix_encoding(rad_val),
                                "asunto": fix_encoding(cell_texts[asunto_idx]) if asunto_idx != -1 and asunto_idx < len(cell_texts) else "Sin asunto",
                                "estado": fix_encoding(cell_texts[estado_idx]) if estado_idx != -1 and estado_idx < len(cell_texts) else "Asignado",
                                "plazo": fix_encoding(cell_texts[dias_idx]) if dias_idx != -1 and dias_idx < len(cell_texts) else "N/A",
                                "fecha_creacion": fix_encoding(cell_texts[fecha_idx]) if fecha_idx != -1 and fecha_idx < len(cell_texts) else "Desconocida",
                                "municipio": fix_encoding(cell_texts[muni_idx]) if muni_idx != -1 and muni_idx < len(cell_texts) else "Pendiente",
                                "funcionario": fix_encoding(official["name"]),
                                "usuario_funcionario": user_funcionario,
                                "fecha_vencimiento": ""
                            }
                            if "SIN FINALIZAR" in item["estado"].upper() or "ASIGNADO" in item["estado"].upper() or True:
                                all_radicados.append(item)
                except: pass
                
            # Regresar al listado haciendo clic en Infraestructura Educativa
            try:
                asignados_frame.locator(f"text=/{target_dep}/i").first.click(timeout=5000)
            except:
                try:
                    asignados_frame.locator(f"text=/{target_dep}/i").first.evaluate("el => el.click()")
                except: pass
            page.wait_for_timeout(2000)

        browser.close()

    unique_radicados = {}
    for r in all_radicados:
        unique_radicados[r["radicado"]] = r
        
    deduplicated = list(unique_radicados.values())
    deduplicated.sort(key=lambda x: parse_date(x["fecha_creacion"]), reverse=True)
    final_20 = deduplicated[:20]
    
    print(f"[INFO] Consolidación: Total {len(all_radicados)} | Deduplicados: {len(deduplicated)} | Finales (Top 20): {len(final_20)}")
    
    # ---------------------------------------------------------
    # AGREGAR A LA COLA
    # ---------------------------------------------------------
    try:
        sys.path.append(os.path.abspath("."))
        import scripts.queue_manager as qm
        items_to_add = []
        for r in final_20:
            func = r.get("asignado") or r.get("funcionario", "")
            u_func = r.get("usuario_funcionario", "")
            items_to_add.append({
                "radicado": r["radicado"],
                "funcionario": func,
                "usuario_funcionario": u_func
            })
        
        if hasattr(qm, 'add_batch_to_queue'):
            qm.add_batch_to_queue(items_to_add)
        else:
            for item in items_to_add:
                qm.add_to_queue(item["radicado"], item["funcionario"], item["usuario_funcionario"])
                
        print("[INFO] Todos los radicados en la bandeja han sido sincronizados con la cola de preprocesamiento.")
    except Exception as e:
        print(f"[WARNING] No se pudo agregar a la cola: {e}")
    
    os.makedirs("data", exist_ok=True)
    with open("data/dashboard_inbox.json", "w", encoding="utf-8") as f:
        json.dump(final_20, f, indent=4, ensure_ascii=False)
        
    with open("data/dashboard_meta.json", "w", encoding="utf-8") as f:
        json.dump({"last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, f)
        
    print("[SUCCESS] Sincronización finalizada correctamente.")

if __name__ == "__main__":
    run_sync()
