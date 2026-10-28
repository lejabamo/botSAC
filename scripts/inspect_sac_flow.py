import os
import sys
import time
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SAC_URL")
user = os.getenv("SAC_USER")
pwd = os.getenv("SAC_PASS")

def inspect_sac():
    print(f"Iniciando inspección en {url} con usuario {user}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        page = context.new_page()

        print("[1] Cargando login...")
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_selector("select#id_sc_field_entidad", timeout=30000)
        page.select_option("select#id_sc_field_entidad", label="SE CAUCA")
        if page.locator("a#sub_form_b").is_visible():
            page.locator("a#sub_form_b").click()
        page.locator("input#id_sc_field_login").fill(user)
        page.locator("input#id_sc_field_pswd").fill(pwd)
        page.locator('input.btn-login[value="Ingresar"]').click()
        print("[2] Login enviado. Esperando respuesta...")
        page.wait_for_timeout(6000)

        # Modal
        for f in page.frames:
            for btn in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                try:
                    loc = f.locator(btn)
                    if loc.count() > 0 and loc.first.is_visible():
                        loc.first.click()
                        print("[3] Modal de alerta aceptado.")
                        break
                except:
                    pass

        page.wait_for_timeout(4000)

        # Buscar POR APROBAR
        print("[4] Buscando sección 'POR APROBAR'...")
        target_link = None
        for f in page.frames:
            locs = f.locator("text=/POR APROBAR/i").all()
            for loc in locs:
                if loc.is_visible():
                    tag = loc.evaluate("el => el.tagName").upper()
                    if tag == "A" or loc.evaluate("el => el.getAttribute('onclick')"):
                        target_link = loc
                        break
                    elif loc.locator("xpath=ancestor::a").count() > 0:
                        target_link = loc.locator("xpath=ancestor::a").first
                        break
            if target_link:
                break

        if not target_link:
            print("[ERROR] Enlace POR APROBAR no encontrado.")
            browser.close()
            return

        print("[5] Clic en POR APROBAR...")
        target_link.click()
        page.wait_for_timeout(5000)

        # Frame de la tabla
        grid_frame = None
        for _ in range(15):
            for f in page.frames:
                try:
                    if f.locator("th:has-text('RADICADO'), td:has-text('RADICADO')").count() > 0:
                        grid_frame = f
                        break
                except:
                    pass
            if grid_frame:
                break
            page.wait_for_timeout(1000)

        if not grid_frame:
            print("[ERROR] Frame de cuadrícula no encontrado.")
            browser.close()
            return

        print("[6] Vista POR APROBAR cargada con éxito.")

        # Inspeccionar elementos de paginación
        toolbar_links = grid_frame.locator("a, select, img, span").all()
        pagination_info = []
        for el in toolbar_links:
            try:
                txt = el.inner_text().strip()
                title = el.get_attribute("title") or ""
                onclick = el.get_attribute("onclick") or ""
                href = el.get_attribute("href") or ""
                if any(k in (txt + title + onclick + href).lower() for k in ["pag", "sig", "avc", "10", "20", "50", "de 3", "de 4", "ir a"]):
                    pagination_info.append(f"TAG={el.evaluate('el => el.tagName')}, TXT='{txt}', TITLE='{title}', ONCLICK='{onclick[:60]}', HREF='{href[:60]}'")
            except:
                pass
        print(f"\n[INFO] Elementos de paginación detectados ({len(pagination_info)}):")
        for p in pagination_info[:15]:
            print("  ", p)

        # Inspeccionar columnas y primer radicado
        rows = grid_frame.locator("tr.scGridFieldOdd, tr.scGridFieldEven").all()
        print(f"\n[INFO] Total filas de datos en página: {len(rows)}")

        if rows:
            first_row = rows[0]
            tds = first_row.locator("td").all()
            td_texts = [td.inner_text().strip() for td in tds]
            rad_target = td_texts[2] if len(td_texts) > 2 else "DESCONOCIDO"
            print(f"\n[TEST PDF] Probando descarga de PDF de respuesta para radicado: {rad_target}")

            pdf_btn = first_row.locator("td").nth(1).locator("a").first
            print("  Href del enlace PDF:", pdf_btn.get_attribute("href"))

            download_info_holder = []
            popup_info_holder = []

            page.on("download", lambda d: download_info_holder.append(d))
            context.on("page", lambda p: popup_info_holder.append(p))

            print("  Haciendo clic en el botón de PDF...")
            try:
                with page.expect_download(timeout=10000) as download_info:
                    pdf_btn.click()
                dl = download_info.value
                out_path = f"data/test_response_{rad_target}.pdf"
                dl.save_as(out_path)
                print(f"[SUCCESS] ¡PDF descargado exitosamente como archivo físico!: {out_path} ({os.path.getsize(out_path)} bytes)")
            except Exception as e_dl:
                print(f"  No fue expect_download directo: {e_dl}. Verificando popups o frames...")
                page.wait_for_timeout(5000)
                if popup_info_holder:
                    pop = popup_info_holder[0]
                    print(f"  Popup detectado con URL: {pop.url}")
                    pop.wait_for_load_state("networkidle")
                    pop.screenshot(path=f"data/popup_{rad_target}.png")
                for f in page.frames:
                    if "Respuesta" in f.url or "pdf" in f.url.lower():
                        print(f"  Frame de PDF detectado: {f.url}")

        browser.close()
        print("\n[OK] Inspección finalizada.")

if __name__ == "__main__":
    inspect_sac()
