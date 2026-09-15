from playwright.sync_api import sync_playwright

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36')
        page.goto('https://sac2.gestionsecretariasdeeducacion.gov.co/app_Login/')
        page.wait_for_timeout(3000)
        
        # Primero seleccionar "21" para ver qué pasa
        select_locator = page.locator('select#id_sc_field_entidad')
        if select_locator.count() > 0:
            select_locator.select_option("21")
            page.wait_for_timeout(1000)
            
            # Hacer clic en Aceptar
            page.locator('a#sub_form_b').click()
            page.wait_for_timeout(4000)
        
        # Dump inputs, buttons, a
        els = page.locator('input, select, button, a').all()
        out = []
        for e in els:
            try:
                out.append(e.evaluate('el => el.outerHTML'))
            except:
                pass
        
        with open('elements.txt', 'w', encoding='utf-8') as f:
            f.write('\n---\n'.join(out))

if __name__ == "__main__":
    run()
