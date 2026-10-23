import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve, sep } from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

const port = 4196
const origin = `http://127.0.0.1:${port}`
const output = pathToFileURL(resolve(process.env.BDA_WORKSPACE_UX_OUTPUT ?? '/tmp/bda-workspace-ux') + sep)
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
let serverError = ''
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
server.stderr.on('data', (chunk) => { serverError += String(chunk) })
const results = []
let browser
try {
  for (let attempt = 0; attempt < 100 && !ready; attempt++) {
    assert.equal(server.exitCode, null, `Preview failed: ${serverError}`)
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  assert.ok(ready, `Preview did not become ready: ${serverError}`)
  browser = await chromium.launch({ headless: true })
  const cases = [320, 390, 768, 1024, 1099, 1100, 1280, 1440].flatMap((width) => ['en', 'zh'].map((language) => ({ width, height: width <= 390 ? 568 : 768, language, scenario: 'populated' })))
  cases.push({ width: 1440, height: 500, language: 'en', scenario: 'populated' })
  for (const scenario of ['empty', 'project-error']) cases.push({ width: 390, height: 844, language: 'en', scenario })
  for (const test of cases) {
    const id = `${test.width}x${test.height}-${test.language}-${test.scenario}`
    if (process.env.BDA_WORKSPACE_UX_CASES && !process.env.BDA_WORKSPACE_UX_CASES.split(',').includes(id)) continue
    const context = await browser.newContext({ viewport: { width: test.width, height: test.height }, reducedMotion: 'reduce' })
    const seed = createStorageSeed({ authenticated: true, language: test.language, themePreference: test.language === 'zh' ? 'dark' : 'light' })
    await context.addInitScript((data) => {
      for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
      for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
    }, seed)
    const fixture = createFixtureRouter({ routeId: 'tools', scenario: test.scenario === 'empty' ? 'empty' : 'populated' })
    const errors = []
    const writes = []
    await context.route('**/api/v2/**', async (route) => {
      const request = route.request()
      if (request.method() !== 'GET') writes.push(request.url())
      try {
        if (test.scenario === 'project-error' && new URL(request.url()).pathname === '/api/v2/projects') {
          await route.fulfill({ status: 503, contentType: 'application/problem+json', body: JSON.stringify({ title: 'Projects unavailable', status: 503 }) })
          return
        }
        const response = await fixture.resolve(request.method(), request.url(), { headers: request.headers(), postData: request.postData() })
        await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(response.body) })
      } catch (error) {
        errors.push(String(error))
        await route.fulfill({ status: 599, body: '{}' })
      }
    })
    const page = await context.newPage()
    page.setDefaultTimeout(10_000)
    page.setDefaultNavigationTimeout(15_000)
    page.on('pageerror', (error) => errors.push(error.message))
    try {
      await page.goto(`${origin}/#/tools?project=proj_browser&tool=protein-properties`)
      const tools = page.getByTestId('lab-tools-page')
      await tools.getByRole('form').waitFor()
      if (test.scenario === 'populated') await page.waitForFunction(() => document.querySelector('[data-nav-route="/tools"]')?.getAttribute('href')?.includes('project=proj_browser'))
      const shell = page.locator('[data-slot="app-shell"]')
      const bounds = await shell.boundingBox()
      assert.ok(Math.abs(bounds.height - test.height) < 1, 'Shell must fit the viewport')
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Document must not overflow horizontally')
      const brand = await page.locator('.science-brand').boundingBox()
      const actions = await page.locator('.topbar-actions').boundingBox()
      assert.ok(brand.x + brand.width <= actions.x + 1 || brand.y + brand.height <= actions.y + 1, 'Brand and global controls must not overlap')
      if (test.width <= 390) assert.ok((await page.locator('.science-topbar').boundingBox()).height <= 140, 'Compact header must leave room for tools')
      const compact = test.width < 1100
      const pageMenu = page.getByRole('button', { name: test.language === 'zh' ? '切换页面' : 'Switch page' })
      assert.equal(await pageMenu.isVisible(), compact, 'Navigation must match the breakpoint')
      const nav = page.locator('[data-tour-id="main-navigation"]')
      const navTop = (await nav.boundingBox()).y
      await page.locator('#workspace-main').evaluate((element) => { element.scrollTop = element.scrollHeight })
      assert.equal((await nav.boundingBox()).y, navTop, 'Navigation must remain reachable after page scrolling')
      const catalog = tools.locator('#lab-tool-catalog')
      if (!await catalog.isVisible()) await tools.locator('[aria-controls="lab-tool-catalog"]').click()
      await catalog.getByRole('button', { name: /^(Centrifuge|离心) RPM/ }).click()
      await page.waitForFunction(() => location.hash.includes('tool=centrifuge'))
      await page.waitForFunction(() => document.querySelector('#workspace-main').scrollTop <= 24)
      const heading = tools.getByRole('heading', { name: /^(Centrifuge|离心) RPM/ })
      assert.ok(await heading.evaluate((element) => document.activeElement === element), 'Category selection must focus the new tool')
      const picker = tools.getByRole('combobox', { name: test.language === 'zh' ? '选择实验工具' : 'Choose lab tool' })
      await picker.click()
      await page.getByRole('option', { name: test.language === 'zh' ? '蛋白分子量与消光系数' : 'Protein mass & extinction', exact: true }).click()
      await page.locator('[role="listbox"]').waitFor({ state: 'hidden' })
      await page.locator('[data-slot="select-content"]').evaluateAll((elements) => Promise.all(elements.flatMap((element) => element.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined)))))
      await tools.getByRole('textbox', { name: test.language === 'zh' ? '序列' : 'Sequence', exact: true }).waitFor()
      const routeBeforeSkip = await page.evaluate(() => location.hash)
      await page.locator('.workspace-skip-link').focus()
      await page.keyboard.press('Enter')
      assert.equal(await page.evaluate(() => document.activeElement.id), 'workspace-main', 'Skip link must focus main')
      assert.equal(await page.evaluate(() => location.hash), routeBeforeSkip, 'Skip link must not change the hash route')
      if (test.scenario === 'populated') {
        if (compact) {
          await pageMenu.focus()
          await page.keyboard.press('ArrowDown')
          await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitem')
          await page.keyboard.press('Escape')
          await page.locator('[role="menu"]').waitFor({ state: 'hidden' })
          await page.waitForFunction(() => document.activeElement === document.querySelector('.workspace-navigation-mobile button'), undefined, { timeout: 5000 })
          await page.keyboard.press('ArrowDown')
          await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'menuitem')
          await page.keyboard.press('Home')
          for (let step = 0; step < 3; step++) await page.keyboard.press('ArrowDown')
          assert.ok(await page.evaluate(() => document.activeElement?.getAttribute('href')?.startsWith('#/workflow?')), 'Keyboard navigation must reach Workflow')
          await page.keyboard.press('Enter')
        } else {
          await nav.locator('[data-nav-route="/workflow"]').click()
        }
        await page.locator('[data-tour-id="workflow-page"]').waitFor()
        assert.ok((await page.evaluate(() => location.hash)).includes('project=proj_browser'), 'Navigation must preserve the project')
        assert.equal(await page.locator('#workspace-main').evaluate((element) => element.scrollTop), 0, 'A new page must start at the top')
        await page.goBack()
        await tools.getByRole('form').waitFor()
        assert.ok((await page.evaluate(() => location.hash)).includes('tool=protein-properties'), 'Back must restore the selected tool')
      }
      assert.deepEqual(errors, [], 'No rendering errors or unhandled API fixtures')
      assert.deepEqual(writes, [], 'Page and tool navigation must not submit work')
      await page.screenshot({ path: new URL(`${id}.png`, output).pathname })
      results.push({ ...test, id, status: 'passed' })
      console.log(`PASS ${id}`)
    } catch (error) {
      await page.screenshot({ path: new URL(`${id}-failure.png`, output).pathname })
      results.push({ ...test, id, status: 'failed', error: String(error), stack: error.stack, errors, focus: await page.evaluate(() => document.activeElement?.outerHTML.slice(0, 600)), popups: await page.locator('[data-slot="select-content"], [data-slot="dropdown-menu-content"]').evaluateAll((elements) => elements.map((element) => ({ open: element.hasAttribute("data-open"), hidden: element.getAttribute("aria-hidden"), display: getComputedStyle(element).display }))) })
      console.error(`FAIL ${id}: ${error}`)
    } finally {
      await context.close()
    }
  }
  await writeFile(new URL('results.json', output), JSON.stringify(results, null, 2) + '\n')
  assert.ok(results.length > 0, 'No workspace browser cases matched')
  assert.equal(results.filter((result) => result.status === 'failed').length, 0, 'Workspace browser regressions failed')
  console.log(`Workspace browser checks passed (${results.length}/${results.length}).`)
} finally {
  if (browser) await browser.close()
  server.kill('SIGTERM')
}
