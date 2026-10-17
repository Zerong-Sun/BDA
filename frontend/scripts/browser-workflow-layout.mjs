import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

const origin = 'http://127.0.0.1:4188'
const output = process.env.BDA_WORKFLOW_LAYOUT_OUTPUT ?? '../output/playwright/workflow-layout'
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', '4188', '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let ready = false
server.stdout.on('data', chunk => { if (String(chunk).includes(origin)) ready = true })
const fixture = createFixtureRouter({ routeId: 'workflow' })
const graph = (await fixture.resolve('GET', '/api/v2/workflow-runs/run_browser/graph')).body
const first = structuredClone(graph.nodes[0])
graph.nodes = Array.from({ length: 8 }, (_, i) => ({ ...structuredClone(first), id: i ? `node_layout_${i}` : first.id, node_key: `Manual stage ${i + 1}`, execution_mode: 'manual', position: { x: (i % 4) * 280, y: Math.floor(i / 4) * 200 } }))
const saves = []
const errors = []
let browser
try {
  for (let i = 0; i < 50 && !ready; i++) await new Promise(resolve => setTimeout(resolve, 100))
  assert.ok(ready, 'Preview server started')
  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1512, height: 950 } })
  const seed = createStorageSeed({ authenticated: true, language: 'en', themePreference: 'light' })
  await context.addInitScript(data => {
    for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
    for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
  }, seed)
  await context.route('**/api/v2/**', async route => {
    const request = route.request(), url = new URL(request.url())
    let response
    if (url.pathname.endsWith('/graph')) response = { status: 200, body: graph }
    else if (url.pathname === '/api/v2/workflow-runs/run_browser') response = { status: 200, body: graph.workflow }
    else if (url.pathname.endsWith('/layout') && request.method() === 'PATCH') {
      const body = request.postDataJSON()
      saves.push(body)
      for (const item of body.nodes) Object.assign(graph.nodes.find(node => node.id === item.id), { position: item.position })
      graph.layout = { nodes: body.nodes.map(item => ({ ...item, id: graph.nodes.find(node => node.id === item.id).node_key })) }
      graph.workflow.version++
      response = { status: 200, body: graph }
    } else if (url.pathname.endsWith('/preflight')) response = { status: 200, body: { workflow_run_id: graph.workflow.id, allowed: false, blockers: [{ code: 'no_dispatch_nodes', message: 'Every node is a manual stage; there is nothing to submit' }], warnings: [], checks: {} } }
    else response = await fixture.resolve(request.method(), url.href, { body: request.postDataJSON() })
    await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(response.body) })
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${origin}/#/workflow`)
  const canvas = page.locator('[data-tour-id="workflow-canvas"]'), inspector = page.locator('[data-tour-id="workflow-inspector"]')
  const node = page.locator(`.react-flow__node[data-id="${first.id}"]`)
  await node.waitFor()
  await page.screenshot({ path: `${output}/desktop.png`, fullPage: true })
  const canvasBox = await canvas.boundingBox(), inspectorBox = await inspector.boundingBox()
  assert.ok(canvasBox.width > 500, `Canvas must occupy the flexible middle column, got ${canvasBox.width}px`)
  assert.ok(inspectorBox.x > canvasBox.x + canvasBox.width, 'Inspector sits to the right of the canvas')
  const resources = page.locator('[data-workflow-panel="resources"]')
  assert.ok((await resources.boundingBox()).x < canvasBox.x, 'Resources sit to the left of the canvas')
  const dragBy = async (target, dx, dy = 0) => {
    const box = await target.boundingBox(), x = box.x + box.width / 2, y = box.y + Math.min(12, box.height / 2)
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x + dx, y + dy, { steps: 12 })
    await page.mouse.up()
  }
  const positionBefore = structuredClone(graph.nodes[0].position)
  const saved = page.waitForResponse(response => response.url().endsWith('/layout') && response.request().method() === 'PATCH')
  await dragBy(node, 65, 45)
  await saved
  assert.ok(graph.nodes[0].position.x > positionBefore.x + 20, 'Dragging manual stage changes saved X')
  assert.ok(graph.nodes[0].position.y > positionBefore.y + 20, 'Dragging manual stage changes saved Y')
  const savedPosition = structuredClone(graph.nodes[0].position)
  await page.reload()
  await node.waitFor()
  const restoredPosition = await node.evaluate(el => ({ x: new DOMMatrix(el.style.transform).m41, y: new DOMMatrix(el.style.transform).m42 }))
  assert.ok(Math.abs(restoredPosition.x - savedPosition.x) < 0.01 && Math.abs(restoredPosition.y - savedPosition.y) < 0.01, 'Saved position survives reload (CSS transforms round coordinates)')
  await node.click()
  const cardResizer = node.getByRole('button', { name: 'Resize node card width' })
  const cardWidth = () => node.evaluate(el => parseFloat(getComputedStyle(el).width))
  const initialCardWidth = await cardWidth()
  const resized = page.waitForResponse(response => response.url().endsWith('/layout') && response.request().method() === 'PATCH')
  await dragBy(cardResizer, 75)
  await resized
  const savedCardWidth = graph.layout.nodes.find(item => item.id === graph.nodes[0].node_key).width
  await page.screenshot({ path: `${output}/card-resized.png`, fullPage: true })
  assert.ok(savedCardWidth > initialCardWidth + 50, `Card can be widened independently of sidebars: ${JSON.stringify({ initialCardWidth, savedCardWidth, saves: saves.length, renderedWidth: await cardWidth() })}`)
  assert.deepEqual(graph.nodes[0].position, savedPosition, 'Right resize handle does not move the card')
  await page.reload()
  await node.waitFor()
  assert.ok(Math.abs(await cardWidth() - savedCardWidth) < 1, 'Card width survives reload from server layout')
  await cardResizer.focus()
  const keyboardResized = page.waitForResponse(response => response.url().endsWith('/layout') && response.request().method() === 'PATCH')
  await page.keyboard.press('ArrowRight')
  await keyboardResized
  const keyboardWidth = await cardWidth()
  assert.ok(Math.abs(keyboardWidth - savedCardWidth - 20) < 1, 'Card width supports keyboard resizing')
  const resourceDivider = page.getByRole('separator', { name: 'Resize resource sidebar' }), inspectorDivider = page.getByRole('separator', { name: 'Resize inspector', exact: true })
  const initialResources = (await resources.boundingBox()).width
  await dragBy(resourceDivider, 60)
  assert.ok((await resources.boundingBox()).width > initialResources + 45, 'Resource width responds to dragging')
  const initialInspector = (await inspector.boundingBox()).width
  await dragBy(inspectorDivider, -60)
  assert.ok((await inspector.boundingBox()).width > initialInspector + 45, 'Inspector width responds to dragging')
  await inspectorDivider.focus()
  await page.keyboard.press('ArrowRight')
  const adjustedWidth = (await inspector.boundingBox()).width
  assert.ok(adjustedWidth < initialInspector + 60, 'Inspector supports keyboard resizing')
  await page.reload()
  await node.waitFor()
  assert.equal((await inspector.boundingBox()).width, adjustedWidth, 'Panel widths survive reload')
  await page.getByRole('button', { name: 'Workflow overview', exact: true }).click()
  assert.equal(await cardResizer.count(), 0, 'Overview cards have no resize control')
  assert.equal(await cardWidth(), 300, 'Overview uses uniform card widths')
  assert.equal(await resourceDivider.isVisible(), false)
  assert.ok((await canvas.boundingBox()).width > 1200, 'Overview fills the workspace')
  await page.getByRole('button', { name: 'Open workflow workbench', exact: true }).click()
  assert.equal(await cardWidth(), keyboardWidth, 'Returning from overview restores card width')
  for (const width of [1280, 1024, 390]) {
    await page.setViewportSize({ width, height: 950 })
    await page.screenshot({ path: `${output}/width-${width}.png`, fullPage: true })
    const bounds = await canvas.boundingBox()
    if (width < 1280) {
      assert.equal(await resourceDivider.isVisible(), false)
      assert.ok(bounds.width > width - 100, 'Narrow layout gives canvas the available width')
      assert.ok((await inspector.boundingBox()).y >= bounds.y + bounds.height, 'Narrow layout stacks inspector below canvas')
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `No horizontal overflow at ${width}px`)
  }
  assert.deepEqual(errors, [])
  await writeFile(`${output}/result.json`, JSON.stringify({ passed: true, canvasWidth: canvasBox.width, layoutSaves: saves.length, savedPosition, adjustedWidth }, null, 2))
  graph.workflow.status = 'running'
  await page.reload()
  await node.waitFor()
  assert.equal(await cardResizer.count(), 0, 'Read-only workflows have no resize control')
  console.log('PASS: desktop/mobile layout, manual-node drag, node/panel pointer and keyboard resize, reload persistence, overview and read-only controls')
} finally {
  await browser?.close()
  server.kill()
}
