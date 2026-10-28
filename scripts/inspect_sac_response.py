import os
import sys
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

def inspect_sac_response():
    print("[1] Conectando a SAC...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        # Login
        page.goto(SAC_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector('select#id_sc_field_entidad', timeout=15000)
        page.select_option('select#id_sc_field_entidad', label="SE CAUCA")
        if page.locator('a#sub_form_b').is_visible():
            page.locator('a#sub_form_b').click()
        page.locator('input#id_sc_field_login').fill(SAC_USER)
        page.locator('input#id_sc_field_pswd').fill(SAC_PASS)
        page.locator('input.btn-login[value="Ingresar"]').click()
        page.wait_for_timeout(5000)

        # Modal
        for f in page.frames:
            try:
                for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                    loc = f.locator(loc_str)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click()
                        break
            except: pass

        page.wait_for_load_state("load")
        page.wait_for_timeout(3000)
        print("[2] Login exitoso. Buscando 'POR APROBAR'...")

        target_link = None
        for f in page.frames:
            try:
                locs = f.locator("text=/POR APROBAR/i").all()
                for loc in locs:
                    if loc.is_visible():
                        target_link = loc
                        break
            except: pass
            if target_link: break

        if not target_link:
            print("[ERROR] No se encontro enlace POR APROBAR")
            browser.close()
            return

        target_link.click()
        page.wait_for_timeout(4000)

        # Encontrar frame de cuadrícula
        aprob_frame = None
        for f in page.frames:
            try:
                if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                    aprob_frame = f
                    break
            except: pass

        if not aprob_frame:
            print("[ERROR] No se encontro frame de cuadrícula")
            browser.close()
            return

        # Seleccionar ver 50 registros por página si existe la opción
        try:
            ver_50 = aprob_frame.locator("a:has-text('50')").first
            if ver_50.count() > 0 and ver_50.is_visible():
                print("[INFO] Cambiando a 50 registros por página...")
                ver_50.click()
                page.wait_for_timeout(4000)
                # Reubicar frame
                for f in page.frames:
                    try:
                        if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                            aprob_frame = f
                            break
                    except: pass
        except Exception as e:
            print(f"[WARN] No se pudo cambiar a 50: {e}")

        target_rad = "CAU2026ER032828"
        print(f"[3] Buscando {target_rad}...")
        row = aprob_frame.locator(f"tr:has(td:has-text('{target_rad}'))").first
        
        # Si no está en la página actual, navegar a siguiente
        if row.count() == 0:
            print(f"[INFO] No está en esta página. Buscando en la siguiente...")
            next_link = aprob_frame.locator("a:has-text('2'), a#sc_b_avc_bot").first
            if next_link.count() > 0:
                next_link.click()
                page.wait_for_timeout(4000)
                for f in page.frames:
                    try:
                        if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                            aprob_frame = f
                            break
                    except: pass
                row = aprob_frame.locator(f"tr:has(td:has-text('{target_rad}'))").first

        if row.count() == 0:
            print(f"[ERROR] No se encontró {target_rad} tras paginar.")
            browser.close()
            return

        print(f"[4] Fila encontrada para {target_rad}!")
        cells = row.locator("td").all()
        for idx, c in enumerate(cells):
            links = c.locator("a, img, button, input").all()
            link_info = []
            for l in links:
                tag = l.evaluate("el => el.tagName")
                href = l.get_attribute("href") or ""
                onclick = l.get_attribute("onclick") or ""
                src = l.get_attribute("src") or ""
                title = l.get_attribute("title") or ""
                link_info.append(f"{tag}(href={href}, onclick={onclick}, title={title})")
            print(f"  Celda {idx}: text='{c.inner_text().strip()[:40]}' | Elements: {link_info}")

        # En la primera celda (columna RESPUESTA), clicar el botón
        btn_resp = cells[0].locator("a, img").first
        if btn_resp.count() == 0:
            print("[WARN] Celda 0 no tiene enlace/img, buscando en toda la fila...")
            btn_resp = row.locator("a, img").first

        print(f"[5] Clicando en el botón de respuesta de {target_rad}...")
        btn_resp.click()
        page.wait_for_timeout(6000)

        print("[6] Inspeccionando todos los frames después del clic...")
        for i, f in enumerate(page.frames):
            url_str = f.url
            try:
                body_snippet = f.locator("body").inner_text()[:400].replace("\n", " ")
            except:
                body_snippet = "<error leyendo>"
            print(f"FRAME {i}: name='{f.name}' | url='{url_str[:80]}' | text='{body_snippet[:150]}'")

            if "RESPUESTA" in body_snippet.upper() or target_rad in body_snippet:
                print(f"  >>> FRAME MATCH IDENTIFICADO ({i}) <<<")
                # Guardar HTML completo para inspección
                html = f.content()
                with open("scratch/sac_respuesta_form.html", "w", encoding="utf-8") as hf:
                    hf.write(html)
                print(f"  [SUCCESS] HTML guardado en scratch/sac_respuesta_form.html ({len(html)} bytes)")

                # Buscar campos clave
                print("  --- CAMPOS EN EL FRAME ---")
                for selector in [
                    "input#id_sc_field_no_radicado_respuesta",
                    "input[name*='radicado_respuesta']",
                    "textarea",
                    "div.scFormDataHelp",
                    "a:has-text('Ver PDF')",
                    "a:has-text('Aprobar')",
                    "a:has-text('Devolver')",
                    "span[id^='id_read_on_']"
                ]:
                    matches = f.locator(selector).all()
                    for m in matches:
                        try:
                            txt = m.inner_text().strip() if m.evaluate("el => el.tagName") != "INPUT" else m.input_value()
                            print(f"    Selector '{selector}': tag={m.evaluate('el => el.tagName')} id={m.get_attribute('id')} text={txt[:80]}")
                        except Exception as ex:
                            print(f"    Selector '{selector}' error: {ex}")

        browser.close()

if __name__ == "__main__":
    inspect_sac_response()
