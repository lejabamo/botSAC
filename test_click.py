import asyncio
from playwright.async_api import async_playwright
import json, os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(ignore_https_errors=True)
        page = await context.new_page()
        
        from dotenv import load_dotenv
        load_dotenv()
        
        await page.goto('https://sac2.gestionsecretariasdeeducacion.gov.co/app_Login/')
        
        if await page.locator('a#sub_form_b').is_visible():
            await page.locator('a#sub_form_b').click()
            
        await page.wait_for_selector('input#id_sc_field_login', timeout=15000)
        await page.locator('input#id_sc_field_login').fill(os.getenv('SAC_USER'))
        await page.locator('input#id_sc_field_pswd').fill(os.getenv('SAC_PASS'))
        await page.locator('input.btn-login[value="Ingresar"]').click()
        
        await asyncio.sleep(5)
        
        modal_handled = False
        for f in page.frames:
            try:
                for loc_str in ["button:has-text('Aceptar')", "a:has-text('Aceptar')", "input[type='button'][value='Aceptar']"]:
                    loc = f.locator(loc_str)
                    if await loc.count() > 0 and await loc.first.is_visible():
                        await loc.first.click()
                        modal_handled = True
                        break
            except: pass
            if modal_handled: break
            
        await asyncio.sleep(5)
        
        els = page.locator("a[tab-title='Mis Sub-Dependencias']")
        count = await els.count()
        print(f"ENCONTRADOS {count} ELEMENTOS Mis Sub-Dependencias")
        for i in range(count):
            el = els.nth(i)
            print(f"[{i}] id=" + await el.evaluate("el => el.parentElement.id") + " text=" + await el.inner_text() + " onclick=" + await el.evaluate("el => el.getAttribute('onclick')"))
            
        await browser.close()

asyncio.run(main())
