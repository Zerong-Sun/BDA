import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

const port = 4188
const origin = `http://127.0.0.1:${port}`
const output = process.env.BDA_TOUR_UX_OUTPUT ?? '/tmp/bda-tour-ux'
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
let browser
try {
  for (let attempt = 0; attempt < 50 && !ready; attempt++) await new Promise((resolve) => setTimeout(resolve, 100))
  assert.ok(ready, 'Dedicated preview server started')
  browser = await chromium.launch({ headless: true })
  for (const [name, viewport, language] of [
    ['desktop', { width: 1440, height: 1000 }, 'zh'],
    ['mobile', { width: 390, height: 844 }, 'zh'],
    ['english', { width: 1280, height: 800 }, 'en'],
  ]) {
    const context = await browser.newContext({ viewport, reducedMotion: name === 'desktop' ? 'no-preference' : 'reduce' })
    const seed = createStorageSeed({ authenticated: true, language, themePreference: 'light' })
    const persisted = JSON.parse(seed.local['bda-app-store'])
    persisted.state.tourMenuOpen = true
    seed.local['bda-app-store'] = JSON.stringify(persisted)
    await context.addInitScript((data) => {
      for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
      for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
    }, seed)
    const fixture = createFixtureRouter({ routeId: 'experiments' })
    const errors = []
    await context.route('**/api/v2/**', async (route) => {
      try {
        const request = route.request()
        assert.equal(request.method(), 'GET', 'Tour must not write or submit work')
        const response = await fixture.resolve(request.method(), request.url())
        const body = structuredClone(response.body)
        if (new URL(request.url()).pathname.startsWith('/api/v2/projects')) {
          if (body?.id === 'proj_browser') body.source_project_key = 'PD1'
          for (const item of body?.items ?? []) if (item.id === 'proj_browser') item.source_project_key = 'PD1'
        }
        await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(body) })
      } catch (error) {
        errors.push(String(error))
        await route.fulfill({ status: 500, body: '{}' })
      }
    })
    const page = await context.newPage()
    page.on('pageerror', (error) => errors.push(error.message))
    await page.goto(`${origin}/#/projects?project=proj_browser`)
    await page.getByRole('button', { name: language === 'zh' ? '项目与全局导航' : 'Projects & navigation', exact: true }).click()
    const next = () => page.getByTestId('tour-card').getByRole('button', { name: language === 'zh' ? '下一步' : 'Next', exact: true })
    await next().click()
    const card = page.locator('[data-tour-anchor="project-selector"]')
    await card.waitFor()
    const target = page.locator('[data-tour-id="project-selector"] [role="combobox"]')
    const frame = page.getByTestId('tour-spotlight')
    await frame.waitFor()
    await page.getByRole('button', { name: language === 'zh' ? '定位到高亮位置' : 'Locate highlighted area' }).click()
    assert.ok(await target.evaluate((el) => el === document.activeElement))
    const bounds = await target.boundingBox()
    const highlight = await frame.boundingBox()
    assert.ok(Math.abs(bounds.x - highlight.x - 5) <= 1)
    assert.ok(Math.abs(bounds.width + 10 - highlight.width) <= 1)
    assert.ok(await card.locator('[data-slot="popover-description"]').evaluate((el) => parseFloat(getComputedStyle(el).fontSize) >= 16))
    assert.ok(await next().evaluate((el) => parseFloat(getComputedStyle(el).fontSize) >= 16), 'Next label is readable')
    const cardBounds = await card.boundingBox()
    assert.ok(cardBounds.x >= 0 && cardBounds.x + cardBounds.width <= viewport.width + 1, 'Card fits viewport')
    assert.ok(cardBounds.y >= 0 && cardBounds.y + cardBounds.height <= viewport.height + 1, 'Card height fits viewport')
    // The callout must leave the dropdown reachable with a real pointer click.
    await page.screenshot({ path: `${output}/${name}-step-two.png`, fullPage: false })
    await target.click()
    await page.getByRole('status').filter({ hasText: language === 'zh' ? '请选择项目' : 'Choose a project' }).waitFor()
    const option = page.getByRole('option').first()
    await option.click()
    await page.locator('[data-tour-anchor="project-library"]').waitFor()
    await next().click()
    await page.locator('[data-tour-anchor="main-navigation"]').waitFor()
    await next().click()
    await page.getByTestId('tour-menu').waitFor()
    await page.getByRole('button', { name: language === 'zh' ? '项目与全局导航, 已完成' : 'Projects & navigation, Completed', exact: true }).click()
    await next().click()
    await card.waitFor()
    await next().click()
    await page.locator('[data-tour-anchor="project-library"]').waitFor()
    assert.deepEqual(errors, [])
    console.log(`${name}: chapter entry, readable text, exact spotlight, locate, actual dropdown and chapter completion passed`)
    await context.close()
  }
} finally {
  await browser?.close()
  server.kill('SIGTERM')
}
