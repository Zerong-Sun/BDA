import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

const origin = 'http://127.0.0.1:4189'
const output = process.env.BDA_DISPLAY_OUTPUT ?? '/tmp/bda-display-ux'
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4189', '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
let browser
try {
  for (let attempt = 0; attempt < 50 && !ready; attempt++) await new Promise((resolve) => setTimeout(resolve, 100))
  assert.ok(ready, 'Preview server started')
  browser = await chromium.launch({ headless: true })
  for (const [name, width, language, theme] of [['desktop', 1440, 'zh', 'light'], ['mobile', 390, 'zh', 'light'], ['english-dark', 1280, 'en', 'dark']]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' })
    const fixture = createFixtureRouter({ routeId: 'experiments' })
    const seed = createStorageSeed({ authenticated: true, language, themePreference: theme })
    await context.addInitScript((data) => {
      for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
      for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
    }, seed)
    const problems = []
    const fullName = language === 'zh' ? '用于验证长项目名称完整显示的演示项目：第一阶段结果检查与团队审核（包含多组参考资料）' : 'Readable project name for a long-running review with several teams and multiple reference collections'
    const otherName = language === 'zh' ? '另一个演示项目' : 'Another example project'
    await context.route('**/api/v2/**', async (route) => {
      try {
        const request = route.request()
        assert.equal(request.method(), 'GET', 'Display checks must not write data')
        const url = new URL(request.url())
        if (url.pathname === '/api/v2/health/ready') {
          return await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ checks: { scheduler_dispatch: 'paused', postgresql: 'ok', redis: 'ok' } }) })
        }
        const response = await fixture.resolve('GET', request.url().replaceAll('proj_second', 'proj_browser'))
        const body = structuredClone(response.body)
        if (url.pathname === '/api/v2/projects' || url.pathname === '/api/v2/projects/library') {
          for (const item of body.items ?? []) {
            item.name = fullName
            item.localized_content = { ...item.localized_content, name: { en: fullName, zh: fullName } }
          }
          if (body.items?.length) body.items.push({ ...structuredClone(body.items[0]), id: 'proj_second', name: otherName, localized_content: { name: { en: otherName, zh: otherName } } })
        }
        await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(body) })
      } catch (error) { problems.push(String(error)); await route.fulfill({ status: 500, body: '{}' }) }
    })
    const page = await context.newPage()
    page.on('pageerror', (error) => problems.push(error.message))
    await page.goto(`${origin}/#/projects?project=proj_browser`)
    const selector = page.locator('[data-tour-id="project-selector"] [role="combobox"]')
    await selector.waitFor()
    assert.equal(await selector.innerText(), fullName)
    assert.equal(await selector.getAttribute('title'), fullName)
    assert.equal(await page.getByRole('combobox', { name: language === 'zh' ? '按状态筛选' : 'Filter by status', exact: true }).innerText(), language === 'zh' ? '全部状态' : 'All statuses')
    assert.equal(await page.getByRole('combobox', { name: language === 'zh' ? '排序方式' : 'Sort projects', exact: true }).innerText(), language === 'zh' ? '最近创建' : 'Recently created')
    await page.getByText(language === 'zh' ? '自动调度已暂停，仍可浏览已有项目和结果。' : 'Automatic scheduling is paused. You can continue browsing existing projects and results.').waitFor()
    assert.ok(!(await page.locator('body').innerText()).includes('8100'))
    await page.screenshot({ path: `${output}/${name}-page.png` })
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No horizontal page overflow')
    await selector.click()
    const option = page.getByRole('option', { name: fullName, exact: true })
    await option.waitFor()
    assert.ok(await option.evaluate((el) => el.scrollWidth <= el.clientWidth + 1), 'Long option fits its popup')
    await page.screenshot({ path: `${output}/${name}-project-list.png` })
    await page.getByRole('option', { name: otherName, exact: true }).click()
    await page.waitForURL(/project=proj_second/)
    assert.equal(await selector.innerText(), otherName)
    await page.reload()
    await selector.waitFor()
    assert.equal(await selector.innerText(), otherName, 'Name survives refresh')
    assert.deepEqual(problems, [])
    console.log(`${name}: names, long-name layout, selection, refresh, readable filters and accurate health banner passed`)
    await context.close()
  }
} finally { await browser?.close(); server.kill('SIGTERM') }
