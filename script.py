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
            
        await page.wait_for_selector('input#id_sc_field_login')
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
        
        menu_loc = page.locator("a[tab-title='Mis Sub-Dependencias']").last
        await menu_loc.evaluate("el => el.click()")
        
        await asyncio.sleep(15)
        
        print("====== FRAME TEXT DUMP ======")
        for idx, f in enumerate(page.frames):
            try:
                text = await f.locator('body').inner_text()
                if len(text.strip()) > 10:
                    print(f"\n--- FRAME {idx} ({f.name}) ---")
                    print(text.strip())
            except: pass
            
        await browser.close()

asyncio.run(main())
