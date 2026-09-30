import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'
import { TOUR_SECTIONS } from '../src/features/tour/tourData.ts'

const port = Number(process.env.BDA_TOUR_UX_PORT ?? 4192)
const origin = `http://127.0.0.1:${port}`
const output = process.env.BDA_TOUR_UX_OUTPUT ?? '/tmp/bda-tour-ux'
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
let serverError = ''
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
server.stderr.on('data', (chunk) => { serverError += String(chunk) })
let browser
try {
  for (let attempt = 0; attempt < 50 && !ready; attempt++) {
    if (server.exitCode !== null) throw new Error(serverError || 'Preview server exited')
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  assert.ok(ready, `Dedicated preview server started: ${serverError}`)
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
    const next = () => page.getByTestId('tour-card').getByRole('button', { name: language === 'zh' ? /^(下一步|完成本章)$/ : /^(Next|Finish chapter)$/ })
    await next().click()
    const card = page.locator('[data-tour-anchor="project-selector"]')
    await card.waitFor()
    const target = page.locator('[data-tour-id="project-selector"] [role="combobox"]')
    assert.ok(!(await target.innerText()).includes('proj_browser'), 'Project name is shown before opening the list')
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
    const completedSteps = ['projects-welcome', 'project-selector', 'project-library', 'main-navigation']
    for (const section of TOUR_SECTIONS.filter((item) => item.id !== 'projects')) {
      await page.getByTestId('tour-menu').getByRole('button', { name: section.title[language], exact: true }).click()
      for (const step of section.steps) {
        const stepCard = page.locator(`[data-tour-step="${step.id}"]`)
        await stepCard.waitFor()
        if (step.anchor) {
          // A fallback modal must not count as a visited control.
          await page.locator(`[data-tour-anchor="${step.anchor.id}"]`).waitFor({ timeout: 8000 })
          assert.equal(await stepCard.getByRole('alert').count(), 0, `${step.id}: anchor must exist`)
        }
        const rect = await stepCard.boundingBox()
        assert.ok(rect && rect.x >= -1 && rect.x + rect.width <= viewport.width + 1, `${step.id}: fits viewport`)
        if (step === section.steps[0]) {
          await stepCard.evaluate((element) => Promise.all(element.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined))))
          await page.screenshot({ path: `${output}/${name}-${section.id}.png` })
        }
        if (step.id === 'research-tabs') {
          await page.locator('[data-tour-id="research-tabs"] [role="tab"]').last().click()
        } else if (step.id === 'research-operations') {
          await page.locator('[data-tour-id="research-operations"] button[aria-expanded]').first().click()
        } else if (step.id === 'workflow-canvas') {
          await page.locator('[data-tour-id="workflow-canvas"] .react-flow__node').first().click()
        } else if (step.id === 'candidate-filters') {
          await page.locator('[data-tour-id="candidate-filters"] button[aria-haspopup]').first().click()
          await page.getByRole('status').filter({ hasText: language === 'zh' ? '完成选择后关闭列表' : 'Make a selection' }).waitFor()
          await page.keyboard.press('Escape')
        } else if (step.id === 'faq-content') {
          await page.locator('[data-tour-id="faq-content"] button[aria-expanded]').first().click()
        } else {
          await next().click()
        }
        completedSteps.push(step.id)
      }
    }
    await page.getByTestId('tour-card').waitFor({ state: 'hidden' })
    const state = await page.evaluate(() => JSON.parse(localStorage.getItem('bda-app-store')).state)
    assert.equal(state.tourState.status, 'completed')
    assert.deepEqual(new Set(state.tourState.completedSections), new Set(TOUR_SECTIONS.map((section) => section.id)))
    await page.locator('[data-tour-id="copilot-drawer"]').waitFor({ state: 'hidden' })
    await page.locator('[data-tour-id="settings-drawer"]').waitFor({ state: 'hidden' })
    await page.goto(`${origin}/#/guide?project=proj_browser`)
    await page.locator('.guide-station').first().waitFor()
    assert.equal(await page.locator('.guide-flow').count(), 11, 'Each guide step has a real explanation diagram')
    assert.equal(await page.locator('.guide-station a').count(), 11, 'Each guide step reaches a real workbench')
    assert.ok(await page.locator('.guide-station a').evaluateAll((links) => links.every((link) => link.getAttribute('href').includes('project=proj_browser'))))
    assert.equal(await page.getByText(/animationComponent|原理动画占位|Principle animation placeholder/).count(), 0)
    const firstDetails = page.locator('.guide-station [data-slot="accordion-trigger"]').first()
    assert.equal(await firstDetails.getAttribute('aria-expanded'), 'false')
    await firstDetails.click()
    assert.equal(await firstDetails.getAttribute('aria-expanded'), 'true')
    await page.locator('.guide-station').first().evaluate((element) => Promise.all(element.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined))))
    if (name !== 'desktop') {
      assert.ok(await page.locator('.guide-flow-node').evaluateAll((nodes) => nodes.every((node) => getComputedStyle(node).animationName === 'none')), 'Reduced motion disables flow animation')
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Guide fits viewport')
    await page.screenshot({ path: `${output}/${name}-guide.png` })
    assert.deepEqual(errors, [])
    await writeFile(`${output}/${name}-report.json`, JSON.stringify({ language, viewport, completedSteps, errors }, null, 2))
    console.log(`${name}: all ${TOUR_SECTIONS.length} chapters / ${completedSteps.length} steps passed; no missing anchors or writes`)
    await context.close()
  }
} catch (error) {
  for (const context of browser?.contexts() ?? []) for (const page of context.pages()) {
    await page.screenshot({ path: `${output}/failure.png` })
    await writeFile(`${output}/failure.txt`, `${String(error)}\n${await page.locator('body').innerText()}`)
  }
  throw error
} finally {
  await browser?.close()
  server.kill('SIGTERM')
}
