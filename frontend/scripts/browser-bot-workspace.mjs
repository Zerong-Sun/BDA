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
const catalog = process.env.BDA_BOT_TEST_CATALOG ? JSON.parse(await readFile(process.env.BDA_BOT_TEST_CATALOG, 'utf8')) : null
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
let failTask = false
const task = {
  id: 'task-browser', project_id: 'proj_browser', goal: 'Review the synthetic QA sources', status: 'succeeded',
  parent_run_id: null, allowed_tools: [], version: 1, turn_count: 2, max_turns: 24, cost_usd_cents: 0,
  task_contract: { version: 1, service_kind: 'literature' },
  outcome: { status: 'needs_input', summary: 'Synthetic QA delivery: source review needs your input.', missing: ['Confirm the source selection.'], next_action: 'Review the project materials.', steps: [] },
}
const writes = []
const failures = []
const browser = await chromium.launch({ headless: true })
const checks = []
let server

async function newPage(language = 'en', themePreference = 'light', scenario = 'populated', chatFixture = null) {
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
    if (chatFixture && method === 'POST' && path === '/api/v2/copilot/chat') {
      chatFixture.requests.push(request.postDataJSON())
      await route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ conversation_id: 'qa-stream', message: { id: 'qa-request' } }) })
      return
    }
    if (chatFixture && path === '/api/v2/copilot/conversations/qa-stream/stream') {
      await new Promise((resolve) => { chatFixture.release = resolve; chatFixture.ready() })
      const message = { id: 'qa-reply', role: 'assistant', content: 'Synthetic streaming reply after navigation.', citations: [], tool_calls: [] }
      await route.fulfill({ status: 200, contentType: 'text/event-stream', body: `event: message\ndata: ${JSON.stringify(message)}\n\nevent: done\ndata: {}\n\n` })
      return
    }
    if (method !== 'GET') writes.push({ method, path })
    let reply
    if (path === '/api/v2/projects') reply = { status: 200, body: { items: emptyProjects ? [] : [project], next_cursor: null } }
    else if (path === '/api/v2/projects/library') reply = { status: 200, body: { items: [{ ...project, reference_count: 12, structure_count: 4, finding_count: 4 }], next_cursor: null } }
    else if (path.endsWith('/research-workspace')) reply = { status: 200, body: workspace }
    else if (path.endsWith('/research-goals')) reply = { status: 200, body: { items: [], next_cursor: null } }
    else if (path === '/api/v2/copilot/projects/proj_browser/agent-runs') reply = { status: 200, body: { items: [task], next_cursor: null } }
    else if (path === '/api/v2/copilot/agent-runs/task-browser') reply = failTask ? { status: 422, body: { detail: 'Task unavailable for this test' } } : { status: 200, body: task }
    else if (path === '/api/v2/copilot/agent-runs/task-browser/turns') reply = { status: 200, body: { items: [], next_cursor: null } }
    else if (path === '/api/v2/copilot/bots' && failRoster) reply = { status: 422, body: { status: 422, title: 'Roster unavailable', detail: 'Roster unavailable for this test' } }
    else if (path === '/api/v2/copilot/bots' && catalog) reply = { status: 200, body: catalog.bots }
    else if (path === '/api/v2/copilot/task-services' && catalog) reply = { status: 200, body: catalog.services }
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
  const currentStage = page.locator('[data-slot="stepper-trigger"][aria-current="page"]')
  assert.ok((await currentStage.textContent()).includes('Research'))
  assert.ok((await currentStage.textContent()).includes('You are here'))
  checks.push('Open reaches the project brief in one click; no decorative project images; source-derived questions are visible without saved goals')
  await screenshot(page, 'brief-en-light')
  await page.getByRole('button', { name: 'Discuss with a Bot: Which structures and sources support ligand recognition and antibody binding?', exact: true }).click()
  await page.getByRole('tab', { name: 'Conversation', selected: true }).waitFor()
  await page.waitForFunction(() => document.querySelector('input[aria-label="Ask the Copilot a question"]')?.value.includes('Which structures and sources'))
  assert.equal(writes.length, 0)
  await page.goBack()
  await page.getByRole('region', { name: 'Project brief' }).waitFor()
  checks.push('A brief question opens an editable, unsent Bot draft with citation requirements')
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
  await page.waitForFunction(() => document.querySelector('input[aria-label="Ask the Copilot a question"]')?.value.includes('DEMO-2'))
  const drafted = await page.getByLabel('Ask the Copilot a question', { exact: true }).inputValue()
  assert.ok(drafted.includes('DEMO-1') && drafted.includes('DEMO-2'))
  assert.equal(writes.length, 0, 'Selecting a structure or Bot must not send or execute anything')
  checks.push('Both synthetic structures render; comparison transfers both source IDs to an unsent Bot draft')
  await page.goBack()
  await page.getByRole('button', { name: 'Single structure', exact: true }).waitFor()
  assert.equal(await page.locator('.structure-comparison-pane').count(), 2)
  await page.reload()
  await page.getByRole('button', { name: 'Single structure', exact: true }).waitFor()
  assert.equal(await page.locator('.structure-comparison-pane').count(), 2)
  await page.getByRole('button', { name: 'Discuss with a Bot', exact: true }).click()
  await page.getByRole('tab', { name: 'Conversation', selected: true }).waitFor()
  checks.push('Structure A/B selection survives Bot round trips and full page reloads')
  await page.getByRole('button', { name: 'Structuralist structuralist', exact: true }).click()
  assert.equal(await page.getByRole('button', { name: 'Structuralist structuralist', exact: true }).getAttribute('aria-pressed'), 'true')
  await page.getByRole('tab', { name: 'Bot handoffs', exact: true }).click()
  await screenshot(page, 'bots-handoffs-en-light')
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).click()
  await page.getByRole('heading', { name: 'What would you like to accomplish?' }).waitFor()
  if (catalog) {
    assert.equal(await page.locator('.bot-roster-item').count(), catalog.bots.length + 1)
    assert.equal(await page.getByLabel('Service type', { exact: true }).getByRole('button').count(), catalog.services.length)
    checks.push(`Actual FastAPI catalog renders all ${catalog.bots.length} Bots and ${catalog.services.length} services`)
  }
  await screenshot(page, 'bots-en-light')
  await page.getByLabel('Task goal', { exact: true }).fill('Research the existing project sources')
  await page.getByRole('button', { name: 'Research the evidence', exact: true }).click()
  await page.getByRole('checkbox', { name: 'Allow saving research notes for review' }).check()
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).focus()
  await page.keyboard.press('ArrowRight')
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), 'Conversation')
  await page.keyboard.press('Enter')
  await page.getByRole('tab', { name: 'Conversation', selected: true }).waitFor()
  assert.equal(await page.getByLabel('Ask the Copilot a question', { exact: true }).inputValue(), drafted)
  await page.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).click()
  assert.equal(await page.getByLabel('Task goal', { exact: true }).inputValue(), 'Research the existing project sources')
  assert.ok(await page.getByRole('checkbox', { name: 'Allow saving research notes for review' }).isChecked())
  await page.getByRole('link', { name: 'Read project brief', exact: true }).click()
  await page.getByRole('region', { name: 'Project brief' }).waitFor()
  await page.goBack()
  await page.getByLabel('Task goal', { exact: true }).waitFor()
  assert.equal(await page.getByLabel('Task goal', { exact: true }).inputValue(), 'Research the existing project sources')
  checks.push('Unsent conversation and reviewed task drafts survive view changes and a trip to project materials')
  await page.getByRole('button', { name: /Review the synthetic QA sources/ }).click()
  await page.getByText(task.outcome.summary, { exact: true }).waitFor()
  assert.ok(page.url().includes('run=task-browser'))
  await page.reload()
  await page.getByText(task.outcome.summary, { exact: true }).waitFor()
  await screenshot(page, 'task-delivery-en-light')
  await page.getByRole('link', { name: 'Read project brief', exact: true }).click()
  await page.getByRole('region', { name: 'Project brief' }).waitFor()
  await page.goBack()
  await page.getByText(task.outcome.summary, { exact: true }).waitFor()
  await page.getByRole('button', { name: 'Back to runs', exact: true }).click()
  assert.ok(!page.url().includes('run='))
  await page.getByLabel('Task goal', { exact: true }).waitFor()
  checks.push('Task delivery has a durable URL; reload and material round trips return to the same task')
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
  await zh.goto(`${origin}/#/bots?project=proj_browser&view=tasks&run=task-browser`)
  await zh.getByText(task.outcome.summary, { exact: true }).waitFor()
  assert.ok(await zh.getByRole('button', { name: '继续此任务', exact: true }).isDisabled())
  assert.ok(await zh.getByRole('button', { name: '保存为待审核计划记录', exact: true }).isDisabled())
  await zh.getByRole('tab', { name: '对话', exact: true }).click()
  assert.ok(await zh.locator('.bot-chat-surface input[placeholder]').isDisabled())
  checks.push('Viewer can inspect task deliveries and chat history without command controls')

  let streamReady
  const waitingForStream = new Promise((resolve) => { streamReady = resolve })
  const chatFixture = { requests: [], ready: streamReady, release: null }
  const streaming = await newPage('en', 'light', 'populated', chatFixture)
  await streaming.goto(`${origin}/#/bots?project=proj_browser&view=chat`)
  await streaming.getByLabel('Ask the Copilot a question', { exact: true }).fill('Check the synthetic source summary?')
  await streaming.getByRole('button', { name: 'Send message', exact: true }).click()
  await waitingForStream
  await streaming.getByRole('tab', { name: 'Tasks & deliverables', exact: true }).click()
  await streaming.getByRole('tab', { name: 'Conversation', exact: true }).click()
  assert.ok(await streaming.getByLabel('Ask the Copilot a question', { exact: true }).isDisabled())
  assert.ok(await streaming.getByRole('button', { name: 'Send message', exact: true }).isDisabled())
  assert.equal(chatFixture.requests.length, 1)
  chatFixture.release()
  await streaming.getByText('Synthetic streaming reply after navigation.', { exact: true }).waitFor()
  assert.ok(await streaming.getByLabel('Ask the Copilot a question', { exact: true }).isEnabled())
  assert.equal(chatFixture.requests[0].project_id, 'proj_browser')
  checks.push('Delayed synthetic SSE reply stays locked across tabs and completes in its original project')

  failRoster = true
  const errorPage = await newPage()
  await errorPage.goto(`${origin}/#/bots?project=proj_browser`)
  await errorPage.getByText('Roster unavailable for this test').waitFor()
  failRoster = false
  await errorPage.getByRole('button', { name: 'Retry', exact: true }).click()
  await errorPage.getByRole('button', { name: 'Conductor conductor', exact: true }).waitFor()
  checks.push('Roster failure is recoverable through Retry')
  failTask = true
  const taskError = await newPage()
  await taskError.goto(`${origin}/#/bots?project=proj_browser&view=tasks&run=task-browser`)
  await taskError.getByRole('button', { name: 'Reload task records', exact: true }).waitFor()
  failTask = false
  await taskError.getByRole('button', { name: 'Reload task records', exact: true }).click()
  await taskError.getByText(task.outcome.summary, { exact: true }).waitFor()
  checks.push('Failed task deep links can be retried without leaving the workspace')
  emptyProjects = true
  const empty = await newPage()
  await empty.goto(`${origin}/#/bots`)
  await empty.getByRole('heading', { name: 'Start with a research project' }).waitFor()
  checks.push('Empty workspace offers project selection without broken task controls')
  assert.deepEqual(failures, [], 'No uncaught browser errors')
  assert.equal(writes.length, 0, 'Read-only navigation never mutates backend state')
  await writeFile(`${output}/report.json`, JSON.stringify({ checks, failures, writes, syntheticChatPosts: chatFixture.requests.length, catalog: catalog ? { bots: catalog.bots.length, services: catalog.services.length } : 'lightweight fixtures' }, null, 2))
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
