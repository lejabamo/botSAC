import os
import time
import json
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

SAC_URL = os.getenv("SAC_URL")
SAC_USER = os.getenv("SAC_USER")
SAC_PASS = os.getenv("SAC_PASS")

def dump_menu():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Login...")
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

        print("Esperando menú...")
        page.wait_for_timeout(3000)

        # Dump all links in the main frame
        links = page.locator("a").all()
        print(f"Encontrados {len(links)} links. Extrayendo visibles...")
        
        menu_items = []
        for i, link in enumerate(links):
            if link.is_visible():
                text = link.inner_text().strip()
                href = link.get_attribute("href") or ""
                onclick = link.get_attribute("onclick") or ""
                title = link.get_attribute("title") or ""
                tab_title = link.get_attribute("tab-title") or ""
                id_val = link.get_attribute("id") or ""
                
                if text or "menu_sac" in href or "item" in id_val:
                    menu_items.append({
                        "index": i,
                        "text": text,
                        "id": id_val,
                        "href": href,
                        "onclick": onclick,
                        "tab_title": tab_title,
                        "title": title
                    })
                    print(f"[{i}] {text} | ID: {id_val} | HREF: {href}")

        with open("scratch/menu_dump.json", "w", encoding="utf-8") as f:
            json.dump(menu_items, f, indent=4, ensure_ascii=False)
            
        print("Menu dumpeado en scratch/menu_dump.json")
        browser.close()

if __name__ == "__main__":
    dump_menu()
