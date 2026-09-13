import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

// A real browser against the running Vite app, with deterministic API responses.
// No model invocation, live database mutation or external compute is performed.
const origin = process.env.BDA_BOT_TEST_ORIGIN ?? 'http://127.0.0.1:4188'
const output = process.env.BDA_BOT_TEST_OUTPUT ?? '/tmp/bda-bot-workspace'
await mkdir(output, { recursive: true })
const bundle = JSON.parse(await readFile(new URL('../public/research-packages/pd1-demo-v1.json', import.meta.url), 'utf8'))
const pdb = await readFile(new URL('../../examples/migration-fixtures/pd1/complexes/PD1Binder_a0172_complex.pdb', import.meta.url), 'utf8')
const base = createFixtureRouter({ routeId: 'research' })
const project = structuredClone((await base.resolve('GET', '/api/v2/projects?limit=200')).body.items[0])
Object.assign(project, { name: bundle.projects[0].name.en, summary: bundle.projects[0].summary.en, source_package_id: bundle.package_id, source_project_key: 'PD1', localized_content: { name: bundle.projects[0].name, summary: bundle.projects[0].summary } })
const workspace = structuredClone((await base.resolve('GET', '/api/v2/projects/proj_browser/research-workspace')).body)
Object.assign(workspace.project, { name: bundle.projects[0].name, summary: bundle.projects[0].summary, source_package_id: bundle.package_id })
workspace.review_document.content = bundle.projects[0].project_review
workspace.structures = [0, 1].map((index) => ({
  artifact_id: `synthetic-qa-${index}`, pdb_id: `DEMO-${index + 1}`, name: { en: `Synthetic QA structure ${index + 1}`, zh: `合成验收结构 ${index + 1}` },
  role: { en: 'Synthetic fixture for UI verification', zh: '用于界面验收的合成夹具' }, method: { en: 'Synthetic', zh: '合成' },
  resolution: null, status: 'available', download_url: `${origin}/qa-structure-${index}.pdb`, lineage: { chains: ['A', 'B'] }, reference_id: 'SYNTHETIC-QA',
}))
let failRoster = false
let emptyProjects = false
const writes = []
const failures = []
const browser = await chromium.launch({ headless: true })
const checks = []
let server

async function newPage(language = 'en', themePreference = 'light', scenario = 'populated') {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
  const storage = createStorageSeed({ authenticated: true, language, themePreference, scenario })
  storage.session.bda_user = JSON.stringify({ ...JSON.parse(storage.session.bda_user), role: scenario === 'read-only' ? 'viewer' : 'researcher' })
  await page.addInitScript(({ session, local }) => {
    Object.entries(session).forEach(([key, value]) => sessionStorage.setItem(key, value))
    Object.entries(local).forEach(([key, value]) => localStorage.setItem(key, value))
  }, storage)
  page.on('pageerror', (error) => failures.push(error.message))
  await page.route('**/qa-structure-*.pdb', (route) => route.fulfill({ contentType: 'text/plain', body: pdb }))
  await page.route('**/api/v2/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()
    if (method !== 'GET') writes.push({ method, path })
    let reply
    if (path === '/api/v2/projects') reply = { status: 200, body: { items: emptyProjects ? [] : [project], next_cursor: null } }
    else if (path === '/api/v2/projects/library') reply = { status: 200, body: { items: [{ ...project, reference_count: 12, structure_count: 4, finding_count: 4 }], next_cursor: null } }
    else if (path.endsWith('/research-workspace')) reply = { status: 200, body: workspace }
    else if (path.endsWith('/research-goals')) reply = { status: 200, body: { items: [], next_cursor: null } }
    else if (path === '/api/v2/copilot/bots' && failRoster) reply = { status: 422, body: { status: 422, title: 'Roster unavailable', detail: 'Roster unavailable for this test' } }
    else if (path.includes('/handoffs')) reply = { status: 200, body: { items: [], next_cursor: null } }
    else reply = await base.resolve(method, url.href, { body: request.postDataJSON() })
    await route.fulfill({ status: reply.status, contentType: 'application/json', body: JSON.stringify(reply.body) })
  })
  return page
}

async function screenshot(page, name) { await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))); await page.screenshot({ path: `${output}/${name}.png`, fullPage: true }) }
async function noOverflow(page, label) {
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))))
  const dimensions = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }))
  if (dimensions.scroll > dimensions.width + 1) console.log(await page.evaluate(() => Array.from(document.querySelectorAll('body *')).filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.right > innerWidth + 1 }).map((el) => ({ tag: el.tagName, cls: el.className, text: el.textContent?.slice(0,80), rect: el.getBoundingClientRect().toJSON() })).slice(0,25)))
  assert.ok(dimensions.scroll <= dimensions.width + 1, `${label}: horizontal overflow ${JSON.stringify(dimensions)}`)
}

try {
  if (!process.env.BDA_BOT_TEST_ORIGIN) {
    let ready = false
    let serverError = ''
    server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4188', '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
    server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
    server.stderr.on('data', (chunk) => { serverError += chunk })
    for (let attempt = 0; !ready && attempt < 50; attempt++) {
      if (server.exitCode !== null) throw new Error(serverError || 'Preview server exited')
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
    assert.ok(ready, 'Run npm run build before testing the production preview')
  }
  const page = await newPage()
  await page.goto(`${origin}/#/projects?project=proj_browser`)
  await page.getByRole('link', { name: bundle.projects[0].name.en, exact: true }).waitFor()
  assert.equal(await page.locator('.project-row canvas, .project-row img').count(), 0)
  await screenshot(page, 'projects-en-light')
  for (const width of [320, 390, 768]) { await page.setViewportSize({ width, height: 1000 }); await noOverflow(page, `Projects ${width}`) }
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('link', { name: 'Open', exact: true }).click()
  await page.getByRole('region', { name: 'Project brief' }).waitFor()
  assert.ok(page.url().includes('/research?project=proj_browser&tab=goals'))
  assert.ok(await page.getByText('Which structures and sources support ligand recognition and antibody binding?').isVisible())
  checks.push('Open reaches the project brief in one click; no decorative project images; source-derived questions are visible without saved goals')
  await screenshot(page, 'brief-en-light')
  await page.goBack()
  await page.locator('.project-row').waitFor()
  assert.ok(page.url().includes('/projects'))
  checks.push('Browser back returns to project library')

  await page.goto(`${origin}/#/research?project=proj_browser&tab=evidence`)
  await page.getByText('Curated binding evidence', { exact: true }).waitFor()
  const review = page.getByRole('button', { name: 'Project Review', exact: true })
  if (await review.count()) {
    assert.equal(await review.getAttribute('aria-expanded'), 'false')
    await review.click()
    assert.equal(await review.getAttribute('aria-expanded'), 'true')
  }
  await screenshot(page, 'evidence-en-light')

  await page.goto(`${origin}/#/research?project=proj_browser&tab=structures`)
  await page.getByRole('button', { name: 'Compare side by side', exact: true }).click()
  await page.getByRole('combobox', { name: 'Structure B', exact: true }).waitFor()
  await page.locator('.structure-comparison-pane canvas').first().waitFor({ timeout: 45000 })
  assert.equal(await page.locator('.structure-comparison-pane').count(), 2)
  await screenshot(page, 'structures-en-light')
  await page.setViewportSize({ width: 390, height: 1000 })
  await noOverflow(page, 'Structure comparison 390')
  await screenshot(page, 'structures-mobile')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.getByRole('button', { name: 'Discuss with a Bot', exact: true }).click()
  await page.getByRole('tab', { name: 'Conversation', exact: true }).waitFor()
  assert.ok(page.url().includes('/bots?project=proj_browser&view=chat'))
  const drafted = await page.locator('input').evaluateAll((inputs) => inputs.map((input) => input.value).join(' '))
  assert.ok(drafted.includes('DEMO-1') && drafted.includes('DEMO-2'))
  assert.equal(writes.length, 0, 'Selecting a structure or Bot must not send or execute anything')
  checks.push('Both synthetic structures render; comparison transfers both source IDs to an unsent Bot draft')
  await page.getByRole('button', { name: 'Structuralist structuralist', exact: true }).click()
  assert.equal(await page.getByRole('button', { name: 'Structuralist structuralist', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.getByRole('tab', { name: 'Bot handoffs', exact: true }).click()
  await screenshot(page, 'bots-handoffs-en-light')
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).click()
  await page.getByRole('heading', { name: 'What would you like to accomplish?' }).waitFor()
  await screenshot(page, 'bots-en-light')
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).focus()
  await page.keyboard.press('ArrowRight')
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), 'Conversation')
  await page.keyboard.press('Enter')
  await page.getByRole('tab', { name: 'Conversation', selected: true }).waitFor()
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).click()
  checks.push('Roster selection updates the project-scoped Bot and handoffs are directly reachable')

  for (const width of [320, 390, 768, 1024, 1440, 1920, 2560]) {
    await page.setViewportSize({ width, height: 1000 })
    await noOverflow(page, `Bots ${width}`)
  }
  const zh = await newPage('zh', 'dark', 'read-only')
  await zh.goto(`${origin}/#/projects?project=proj_browser`)
  await zh.locator('.project-row').waitFor()
  await screenshot(zh, 'projects-zh-dark')
  await zh.getByRole('link', { name: 'Open', exact: true }).count().then(async (count) => {
    if (count) await zh.getByRole('link', { name: 'Open', exact: true }).click()
    else await zh.locator('.project-row-actions a').first().click()
  })
  await zh.getByRole('region', { name: '项目简报' }).waitFor()
  assert.ok(await zh.locator('[data-tour-id="research-goals"] input').isDisabled())
  await screenshot(zh, 'brief-zh-dark')
  for (const width of [320, 390, 768, 1024, 1440]) {
    await zh.setViewportSize({ width, height: 1000 })
    await noOverflow(zh, `Chinese brief ${width}`)
  }
  checks.push('Responsive Bot and Chinese brief layouts; demo/viewer goal edits disabled')

  failRoster = true
  const errorPage = await newPage()
  await errorPage.goto(`${origin}/#/bots?project=proj_browser`)
  await errorPage.getByText('Roster unavailable for this test').waitFor()
  failRoster = false
  await errorPage.getByRole('button', { name: 'Retry', exact: true }).click()
  await errorPage.getByRole('button', { name: 'Conductor conductor', exact: true }).waitFor()
  checks.push('Roster failure is recoverable through Retry')
  emptyProjects = true
  const empty = await newPage()
  await empty.goto(`${origin}/#/bots`)
  await empty.getByRole('heading', { name: 'Start with a research project' }).waitFor()
  checks.push('Empty workspace offers project selection without broken task controls')
  assert.deepEqual(failures, [], 'No uncaught browser errors')
  assert.equal(writes.length, 0, 'Read-only navigation never mutates backend state')
  await writeFile(`${output}/report.json`, JSON.stringify({ checks, failures, writes }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, output, checks }, null, 2))
} catch (error) {
  for (const context of browser.contexts()) for (const page of context.pages()) {
    await screenshot(page, 'failure')
    await writeFile(`${output}/failure.txt`, await page.locator('body').innerText())
  }
  throw error
} finally {
  await browser.close()
  server?.kill('SIGTERM')
}
