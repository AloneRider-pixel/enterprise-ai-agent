import os
from pathlib import Path
SMOKE_DIR = Path(os.environ.get("PDF_SMOKE_DIR", "/tmp/enterprise-pdf-smoke"))
SMOKE_DIR.mkdir(parents=True, exist_ok=True)
"""Drive the real UI in Chrome: register, upload PDF, ask, open citation."""
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 900})
        page.on('pageerror', lambda e: print('PAGEERROR:', str(e)))
        page.on('console', lambda m: print('CONSOLE:', m.text) if m.type == 'error' else None)

        await page.goto('http://127.0.0.1:3000', wait_until='networkidle')
        # Register
        reg_toggle = page.locator('button', has_text='Register')
        if await reg_toggle.count():
            await reg_toggle.first.click()
        await page.wait_for_timeout(500)
        if await page.get_by_placeholder('John Doe').count():
            await page.get_by_placeholder('John Doe').fill('E2E Tester')
        await page.get_by_placeholder('you@company.com').fill('e2e@example.com')
        await page.get_by_placeholder('••••••••').fill('e2e-password-123')
        await page.locator('button[type=submit]').click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SMOKE_DIR / '01-after-login.png'))

        # Upload + ingest
        await page.get_by_role('button', name='Documents', exact=True).click()
        await page.wait_for_timeout(800)
        await page.locator('#file-upload').set_input_files(str(SMOKE_DIR / 'handbook.pdf'))
        await page.wait_for_timeout(6000)
        await page.screenshot(path=str(SMOKE_DIR / '02-after-upload.png'))

        # Ask question
        await page.get_by_role('button', name='Chat', exact=True).click()
        await page.wait_for_timeout(800)
        box = page.locator('input[type=text], textarea').last
        await box.fill('What does the Pro plan cost per month and what support does Basic include?')
        await box.press('Enter')
        await page.wait_for_timeout(8000)
        await page.evaluate("document.querySelector('main').insertAdjacentHTML('afterbegin', '<div style=\"position:fixed;bottom:4px;left:12px;font:12px sans-serif;z-index:100;color:#555;background:white\">Offline test fixture: mocked chat + hashing vectors, not model-quality proof</div>')")
        await page.screenshot(path=str(SMOKE_DIR / '03-answer.png'), full_page=True)

        assert await page.get_by_text('The Pro plan costs $25 per month. Basic includes email support', exact=False).count() == 1
        # Citation chips
        chips = page.locator('button', has_text='Source')
        n = await chips.count()
        print('citation chips:', n)
        for i in range(n):
            print(' chip', i, ':', (await chips.nth(i).inner_text()).replace('\n', ' '))
        if n:
            async with page.expect_popup() as popup_info:
                await chips.first.click()
            popup = await popup_info.value
            await popup.wait_for_timeout(1500)
            print('popup url scheme:', popup.url[:20])
            await popup.screenshot(path=str(SMOKE_DIR / '04-citation-page.png'))
        # A screenshot-only fact absent from prose/table. Still a transport fixture:
        # this proves OCR evidence reaches the prompt and its chip opens, not LLM quality.
        await box.fill('What escalation action is visible in the dashboard screenshot?')
        await box.press('Enter')
        await page.wait_for_timeout(5000)
        assert await page.get_by_text('The dashboard screenshot says to press the red button', exact=False).count() == 1
        await page.screenshot(path=str(SMOKE_DIR / '05-ocr-answer.png'), full_page=True)
        await browser.close()
        print('E2E_DONE')

asyncio.run(main())
