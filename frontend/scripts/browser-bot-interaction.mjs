import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

const origin = 'http://127.0.0.1:4197'
const output = resolve(process.env.BDA_BOT_UX_OUTPUT ?? '/tmp/bda-bot-interaction')
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4197', '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
let serverError = ''
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) ready = true })
server.stderr.on('data', (chunk) => { serverError += String(chunk) })
const run = {
  id: 'review-run', project_id: 'proj_browser', conversation_id: null, created_by: 'user_browser',
  goal: 'Review saved project notes', bot: 'researcher', status: 'succeeded', parent_run_id: null,
  allowed_tools: ['list_projects'], max_turns: 24, turn_count: 2, cost_usd_cents: 0,
  subtree_cost_usd_cents: 0, max_cost_usd_cents: 0, error: null, version: 3,
  created_at: '2026-10-20T00:00:00Z', updated_at: '2026-10-20T00:00:00Z',
  task_contract: { version: 1, service_kind: 'brief', authorized_writes: [] },
  outcome: {
    summary: 'Check the existing notes before continuing.',
    sections: { objective: 'Review existing records. Source: synthetic_source_reference_identifier_that_must_remain_readable_in_the_expanded_deliverable_0123456789.' },
    evidence: [{ tool: 'list_projects', call_id: 'synthetic_tool_call_reference_that_must_wrap_without_clipping_0123456789', successful: true }],
    next_action: 'Open the saved record.', decision_record_id: 'decision_browser_1',
  },
}
const results = []
let browser
try {
  for (let attempt = 0; attempt < 100 && !ready; attempt++) {
    assert.equal(server.exitCode, null, serverError)
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  assert.ok(ready, serverError)
  browser = await chromium.launch({ headless: true })
  const cases = [320, 390, 1440].flatMap((width) => ['en', 'zh'].map((language) => ({ width, language, scenario: 'populated' })))
  cases.push({ width: 390, language: 'en', scenario: 'empty' }, { width: 1440, language: 'en', scenario: 'error' })
  for (const test of cases) {
    const id = `${test.width}-${test.language}-${test.scenario}`
    if (process.env.BDA_BOT_UX_CASES && !process.env.BDA_BOT_UX_CASES.split(',').includes(id)) continue
    const zh = test.language === 'zh'
    const context = await browser.newContext({ viewport: { width: test.width, height: test.width === 320 ? 568 : 900 }, reducedMotion: 'reduce' })
    const seed = createStorageSeed({ authenticated: true, language: test.language, themePreference: zh ? 'dark' : 'light' })
    await context.addInitScript((data) => {
      for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
      for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
    }, seed)
    const fixture = createFixtureRouter({ routeId: 'tools', scenario: test.scenario === 'empty' ? 'empty' : 'populated' })
    const errors = []
    const writes = []
    let failRecords = test.scenario === 'error'
    await context.route('**/api/v2/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      if (request.method() !== 'GET') writes.push(request.url())
      const respond = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
      try {
        if (test.scenario === 'empty' && url.pathname === '/api/v2/projects') return await respond({ items: [], next_cursor: null })
        if (url.pathname === '/api/v2/copilot/projects/proj_browser/agent-runs') {
          if (failRecords) return await respond({ title: 'Temporarily unavailable', detail: 'Try again', status: 422 }, 422)
          return await respond({ items: url.searchParams.has('cursor') ? [{ ...run, id: 'child-run', parent_run_id: run.id, goal: 'Review delegated notes' }] : [run], next_cursor: url.searchParams.has('cursor') ? null : 'older' })
        }
        if (url.pathname === '/api/v2/copilot/agent-runs/review-run') return await respond(run)
        if (url.pathname === '/api/v2/copilot/agent-runs/review-run/turns') return await respond({
          items: url.searchParams.has('cursor') ? [{ id: 't2', role: 'assistant', content: 'Later recorded explanation.', sequence: 201 }] : [{
            id: 't1', role: 'assistant', content: 'Check existing records.', sequence: 1,
            tool_calls: [{ id: 'call-1', function: { name: 'list_projects', arguments: '{"limit":10}' } }],
          }], next_cursor: url.searchParams.has('cursor') ? null : 'later',
        })
        const response = await fixture.resolve(request.method(), request.url(), { headers: request.headers(), postData: request.postData() })
        if (url.pathname === '/api/v2/projects/proj_browser/timeline') {
          response.body.items = response.body.items.map((entry) => entry.id === 'decision_browser_1'
            ? { ...entry, body: 'Recorded reasoning: synthetic_reference_identifier_that_must_wrap_without_clipping_0123456789.\n'.repeat(100) }
            : entry)
        }
        await respond(response.body, response.status)
      } catch (error) {
        errors.push(String(error))
        await respond({}, 599)
      }
    })
    const page = await context.newPage()
    page.setDefaultTimeout(10_000)
    page.on('pageerror', (error) => errors.push(error.message))
    try {
      await page.goto(`${origin}/#/tools?project=proj_browser`)
      await page.getByTestId('lab-tools-page').waitFor()
      const trigger = page.locator('[data-tour-id="copilot-launcher"]')
      await trigger.waitFor()
      assert.ok(await trigger.isVisible(), 'Bot must be directly visible at every width')
      const brand = await page.locator('.science-brand').boundingBox()
      const actions = await page.locator('.topbar-actions').boundingBox()
      assert.ok(brand.x + brand.width <= actions.x + 1, 'Brand and controls overlap')
      await trigger.focus()
      await page.keyboard.press('Enter')
      const drawer = page.locator('[data-tour-id="copilot-drawer"]')
      await drawer.waitFor()
      const taskTab = drawer.getByRole('tab', { name: zh ? '发起任务' : 'Start a task' })
      const reviewTab = drawer.getByRole('tab', { name: zh ? '决策与参数' : 'Decisions & parameters' })
      for (const tab of await drawer.getByRole('tab').all()) {
        assert.ok(await tab.evaluate((node) => node.scrollWidth <= node.clientWidth + 1), 'Tab labels must fit without overlapping adjacent actions')
        assert.ok((await tab.boundingBox()).height >= 44, 'Primary tabs must remain usable touch targets')
      }
      if (test.scenario !== 'empty') {
        const goal = drawer.getByRole('textbox', { name: zh ? '希望完成的工作' : 'Task goal' })
        await goal.fill('Keep this unsent draft')
        await reviewTab.click()
        if (failRecords) {
          await drawer.getByRole('alert').waitFor()
          failRecords = false
          await drawer.getByRole('button', { name: 'Retry', exact: true }).click()
        }
        await drawer.getByRole('button', { name: /Review saved project notes/ }).waitFor()
        await taskTab.click()
        assert.equal(await goal.inputValue(), 'Keep this unsent draft', 'Inspecting work must preserve the task draft')
        await reviewTab.click()
        await drawer.getByRole('button', { name: zh ? '加载更多执行记录' : 'Load more executions' }).click()
        await drawer.getByRole('button', { name: /Review delegated notes/ }).waitFor()
        await drawer.getByRole('button', { name: /Review saved project notes/ }).click()
        const details = drawer.getByRole('button', { name: zh ? '技术详情' : 'Technical details', exact: true })
        await details.waitFor()
        assert.equal(await details.getAttribute('aria-expanded'), 'false', 'Technical metadata must be hidden by default')
        await details.click()
        const params = drawer.getByRole('region', { name: zh ? '技术详情' : 'Technical details' })
        await params.waitFor()
        assert.ok(await params.getByText(zh ? '0 美分' : '0 US cents', { exact: true }).isVisible(), 'Zero budget is not an unset budget')
        await drawer.screenshot({ path: `${output}/${id}-parameters.png` })
        await drawer.getByRole('button', { name: zh ? '查看完整交付内容' : 'Full deliverable', exact: true }).click()
        await drawer.getByRole('button', { name: zh ? '查看来源与操作记录' : 'Sources and actions', exact: true }).click()
        const delivery = drawer.getByRole('region', { name: zh ? '任务交付' : 'Task delivery', exact: true })
        assert.ok(await delivery.evaluate((node) => [...node.querySelectorAll('dd, li')].every((item) => item.scrollWidth <= item.clientWidth + 1)), 'Expanded deliverables and source identifiers must fit their content panels')
        await drawer.getByRole('button', { name: zh ? '过程记录' : 'Transcript', exact: true }).click()
        await drawer.getByRole('button', { name: zh ? '查看调用参数' : 'Inspect call parameters' }).click()
        assert.ok(await drawer.locator('pre').filter({ hasText: '"arguments"' }).isVisible())
        await drawer.getByRole('button', { name: zh ? '加载后续记录' : 'Load later records' }).click()
        await drawer.getByText('Later recorded explanation.').waitFor()
        await drawer.getByRole('link', { name: zh ? '在工作区展开' : 'Open workspace' }).click()
        await drawer.waitFor({ state: 'hidden' })
        await page.waitForFunction(() => location.hash.includes('/bots?') && location.hash.includes('run=review-run') && location.hash.includes('project=proj_browser'))
        await page.getByRole('button', { name: zh ? '技术详情' : 'Technical details', exact: true }).waitFor()
        await page.getByRole('link', { name: zh ? '查看已保存的计划记录' : 'Open saved plan record', exact: true }).click()
        await page.waitForFunction(() => location.hash.includes('tab=timeline') && location.hash.includes('project=proj_browser'))
        const selectedRecord = page.locator('li[aria-current="true"]')
        await selectedRecord.waitFor()
        await page.waitForFunction(() => document.activeElement?.getAttribute('aria-current') === 'true')
        const recordBounds = await selectedRecord.boundingBox()
        const mainBounds = await page.locator('main').boundingBox()
        assert.ok(recordBounds.y >= mainBounds.y && recordBounds.y < mainBounds.y + 80, 'A long saved record must open at its heading')
        assert.ok(await selectedRecord.evaluate((node) => node.scrollWidth <= node.clientWidth + 1), 'Record text and evidence identifiers must not be clipped')
        assert.ok(await page.locator('main').evaluate((node) => node.scrollWidth <= node.clientWidth + 1), 'The work surface must not overflow horizontally')
        await page.goBack()
        await page.getByRole('button', { name: zh ? '技术详情' : 'Technical details', exact: true }).waitFor()
        assert.ok((await page.evaluate(() => location.hash)).includes('run=review-run'), 'Back must restore the same execution')
        await trigger.click()
        await taskTab.click()
        assert.equal(await goal.inputValue(), 'Keep this unsent draft', 'Closing and reopening must preserve the unsent draft')
      } else {
        await reviewTab.click()
        await drawer.getByRole('tabpanel', { name: 'Decisions & parameters', exact: true }).getByRole('link', { name: 'Choose a project', exact: true }).waitFor()
      }
      await page.keyboard.press('Escape')
      await drawer.waitFor({ state: 'hidden' })
      await page.waitForFunction(() => document.activeElement?.getAttribute('data-tour-id') === 'copilot-launcher')
      if (test.width < 1100) {
        await page.getByRole('button', { name: zh ? '更多工作区操作' : 'More workspace actions' }).click()
        await page.getByRole('menuitem', { name: zh ? '应用设置' : 'Application settings', exact: true }).click()
      } else {
        await page.getByRole('button', { name: zh ? '应用设置' : 'Application settings', exact: true }).click()
      }
      const settings = page.getByRole('dialog').filter({ has: page.locator('[data-tour-id="settings-drawer"]') })
      await settings.waitFor({ state: 'visible' })
      await settings.evaluate((element) => Promise.all(element.getAnimations({ subtree: true }).map((animation) => animation.finished.catch(() => undefined))))
      if (test.scenario !== 'empty') {
        await settings.getByRole('tab', { name: zh ? '模型配置' : 'Model', exact: true }).click()
        await settings.getByRole('button', { name: zh ? '保存模型配置' : 'Save model configuration' }).waitFor()
        await settings.getByRole('button', { name: zh ? '高级模型设置' : 'Advanced model settings' }).click()
        const prompt = settings.locator('#copilot-project-prompt')
        await prompt.fill('Unsaved browser regression preferences')
        const testApi = settings.getByRole('button', { name: zh ? '测试 API' : 'Test API', exact: true })
        assert.ok(await testApi.isDisabled(), 'An unsaved draft must not test the previous configuration')
        await settings.getByText(zh ? '配置有未保存的修改。请先保存，再测试实际生效的模型。' : 'Save your changes before testing the active model configuration.').waitFor()
      } else assert.equal(await settings.getByRole('tab', { name: 'Model', exact: true }).count(), 0, 'A projectless user cannot configure a project model')
      for (const button of await settings.locator('[data-slot="sheet-footer"] button').all()) {
        const bounds = await button.boundingBox()
        assert.ok(bounds && bounds.x >= 0 && bounds.x + bounds.width <= test.width + 1, 'Settings actions must not be clipped')
      }
      await settings.screenshot({ path: `${output}/${id}-settings.png` })
      await settings.getByRole('tab', { name: zh ? '偏好与帮助' : 'Preferences' }).click()
      assert.equal(await settings.getByRole('button', { name: zh ? '保存模型配置' : 'Save model configuration' }).count(), 0)
      await page.keyboard.press('Escape')
      if (test.scenario !== 'empty') {
        await page.goto(`${origin}/#/bots?project=proj_browser&view=tasks&run=review-run`)
        await page.getByRole('textbox', { name: zh ? '补充信息或修改要求' : 'Add information or revise the request' }).fill('Include a reviewer for each UI check.')
        await page.getByRole('button', { name: zh ? '准备重新尝试' : 'Prepare a new attempt', exact: true }).click()
        const replace = page.getByRole('button', { name: zh ? '替换草稿并检查' : 'Replace draft and review' })
        if (await replace.count()) {
          await page.getByRole('button', { name: zh ? '保留现有草稿' : 'Keep existing draft' }).click()
          assert.equal(await replace.count(), 0, 'Keeping a draft must dismiss replacement')
          await page.getByRole('button', { name: zh ? '准备重新尝试' : 'Prepare a new attempt', exact: true }).click()
          await replace.click()
        }
        const retryGoal = page.getByRole('textbox', { name: zh ? '希望完成的工作' : 'Task goal' })
        await retryGoal.waitFor()
        assert.ok((await retryGoal.inputValue()).includes('Include a reviewer for each UI check.'))
        const source = page.getByRole('link', { name: zh ? '查看原任务' : 'View original task', exact: true })
        assert.ok((await source.getAttribute('href')).includes('run=review-run'))
        assert.ok(await page.locator('main').evaluate((node) => node.scrollWidth <= node.clientWidth + 1), 'Retry draft must fit the work surface')
        await source.click()
        await page.getByRole('button', { name: zh ? '技术详情' : 'Technical details', exact: true }).waitFor()
      }
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Horizontal overflow')
      assert.deepEqual(errors, [], 'No render errors or missing fixtures')
      assert.deepEqual(writes, [], 'Inspection and navigation must never execute work')
      results.push({ ...test, id, status: 'passed' })
      console.log(`PASS ${id}`)
    } catch (error) {
      await page.screenshot({ path: `${output}/${id}-failure.png` })
      results.push({ ...test, id, status: 'failed', error: String(error), errors })
      console.error(`FAIL ${id}: ${error}`)
    } finally {
      await context.close()
    }
  }
  await writeFile(`${output}/results.json`, JSON.stringify(results, null, 2) + '\n')
  assert.ok(results.length)
  assert.equal(results.filter((result) => result.status === 'failed').length, 0)
} finally {
  if (browser) await browser.close()
  server.kill('SIGTERM')
}
