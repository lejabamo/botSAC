import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        
        print("LOGIN...")
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

        if modal_handled:
            page.wait_for_timeout(5000)
            page.wait_for_load_state("load")
        else:
            page.wait_for_load_state("load")

        print("ESPERANDO MENU...")
        page.wait_for_timeout(5000)
        
        selector_subdep = "text='Mis Sub-Dependencias'"
        page.wait_for_selector(selector_subdep, timeout=10000)
        
        loc_subdep = page.locator(selector_subdep)
        for i in range(loc_subdep.count()):
            if loc_subdep.nth(i).is_visible():
                loc_subdep.nth(i).evaluate("el => el.click()")
                print(f"[CLICK] Mis Sub-Dependencias (index {i})")
                break
                
        print("ESPERANDO 10 SEGUNDOS DESPUÉS DEL CLICK...")
        page.wait_for_timeout(10000)
        
        with open("scratch/test_06_after_click.html", "w", encoding="utf-8") as f:
            for i, fr in enumerate(page.frames):
                f.write(f"\n\n<!-- FRAME {i}: {fr.name} | {fr.url} -->\n")
                try:
                    f.write(fr.content())
                except Exception as e:
                    f.write(str(e))
                    
        print("DUMP COMPLETO EN scratch/test_06_after_click.html")
        browser.close()

if __name__ == "__main__":
    run()
