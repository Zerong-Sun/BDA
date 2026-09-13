import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import { chromium } from 'playwright'
import { createFixtureRouter, createStorageSeed } from './browser-harness-core.mjs'

// Stateful API fixtures exercise real browser controls and persistence across reloads.
// Backend execution and physical subset correctness have separate integration tests.
const port = 4187
const origin = `http://127.0.0.1:${port}`
const output = process.env.BDA_WORKFLOW_UX_OUTPUT ?? '/tmp/bda-workflow-ux'
await mkdir(output, { recursive: true })
const server = spawn(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], { cwd: new URL('..', import.meta.url), stdio: 'pipe' })
let serverError = ''
let serverReady = false
server.stdout.on('data', (chunk) => { if (String(chunk).includes(origin)) serverReady = true })
server.stderr.on('data', (chunk) => { serverError += chunk })
const fixture = createFixtureRouter({ routeId: 'workflow' })
const graph = (await fixture.resolve('GET', '/api/v2/workflow-runs/run_browser/graph')).body
const plugin = (await fixture.resolve('GET', '/api/v2/registry/model-plugins?limit=200')).body.items[0]
plugin.input_ports = [{ name: 'sequences', kind: 'sequence', accepts: ['sequence'], required: false }]
plugin.output_ports = [{ name: 'sequences', kind: 'sequence', artifact_type: 'sequence' }]
plugin.parameter_schema = { type: 'object', properties: { threshold: { type: 'number', default: 0.7 } } }
graph.nodes[0].parameters.threshold = 0.8
graph.nodes[0].configuration = {}
graph.nodes[0].input_bindings = []
let gates = []
let rejectSave = false
let resultDelay = 0
const mutations = []
const problems = []
const steps = []
let browser
let page
const ok = (body) => ({ status: 200, body })
const nodeBy = (key) => graph.nodes.find((node) => node.id === key || node.node_key === key)

async function routeApi(request) {
  const url = new URL(request.url())
  const path = url.pathname
  const method = request.method()
  const body = request.postDataJSON()
  if (method !== 'GET') mutations.push({ method, path, body })
  if (path.endsWith('/graph')) return ok(graph)
  if (path === '/api/v2/workflow-runs/run_browser') return ok(graph.workflow)
  if (path.endsWith('/registry/model-plugins')) return ok({ items: [plugin], next_cursor: null })
  if (path.endsWith('/nodes') && method === 'POST') {
    const node = { ...structuredClone(graph.nodes[0]), id: `node_${graph.nodes.length}`, node_key: body.key, parameters: body.parameters, position: body.position, configuration: {}, input_bindings: [] }
    graph.nodes.push(node)
    graph.workflow.version++
    return ok(node)
  }
  if (/\/nodes\/[^/]+$/.test(path) && method === 'PATCH') {
    const node = nodeBy(path.split('/').at(-1))
    Object.assign(node, body, { version: node.version + 1 })
    graph.workflow.version++
    return ok(node)
  }
  if (path.endsWith('/connections') && method === 'PUT') {
    if (rejectSave) { rejectSave = false; return { status: 409, body: { status: 409, title: 'Conflict', detail: 'Graph changed; retry your connection save.' } } }
    assert.equal(request.headers()['if-match'], `W/"${graph.workflow.version}"`)
    graph.edges = body.edges.map((edge) => ({ ...edge, source: nodeBy(edge.source).node_key, target: nodeBy(edge.target).node_key }))
    // Mirrors `replace_connections`: a dependency edge is ordering only and stages no
    // data, so it must not produce an input binding here either.
    for (const node of graph.nodes) node.input_bindings = graph.edges.filter((edge) => edge.target === node.node_key && edge.gate?.mode !== 'dependency').map((edge) => ({ source: 'upstream', port: edge.target_port, from_node: edge.source, from_port: edge.source_port }))
    graph.workflow.version++
    return ok(graph)
  }
  if (path.endsWith('/gates')) return ok({ items: gates })
  if (path.endsWith('/preview-sources')) return ok({ items: [{ id: 'source-job', node_key: graph.nodes[0].node_key, attempt: 1, count: 2, created_at: graph.workflow.created_at }] })
  if (path.endsWith('/parameter-suggestions')) return ok({ fingerprint: 'fixture', workflow_version: graph.workflow.version, objective: 'Synthetic workflow interaction check', suggestions: [{ parameter: 'threshold', current: 0.7, value: 0.8, source: 'explicit fixture mapping', reason: 'Use the connected upstream threshold' }] })
  if (path.endsWith('/script-imports')) return ok({ ...body, checksum_sha256: 'a'.repeat(64), parameters: { threshold: 0.8 }, commands: ['print'], inputs: [], outputs: [], warnings: ['Synthetic static import'] })
  if (path.endsWith('/script-previews')) return ok({ workflow_node_id: path.split('/').at(-2), plugin_id: plugin.id, script: body.configuration.script.source, input_manifest: {} })
  if (path.endsWith('/previews')) {
    const gate = { id: `gate-${gates.length}`, edge_id: graph.edges[0].id, status: 'previewed', version: 1, revision: gates.length + 1, preview: true, total: 2, passed: 1, selected: 0, selected_ids: [], created_at: graph.workflow.created_at, policy: body.policy }
    gates.unshift(gate)
    return ok(gate)
  }
  if (path.endsWith('/results')) {
    if (resultDelay) await new Promise((resolve) => setTimeout(resolve, resultDelay))
    const gate = gates.find((item) => item.id === path.split('/').at(-2))
    let items = [{ id: 'keep', key: 'Accepted record', passed: true, selected: false, reasons: [], sequence: 'AAAA', metrics: { score: 90 }, files: [] }, { id: 'drop', key: 'Rejected record', passed: false, selected: false, reasons: ['score too low'], metrics: { score: 10 }, files: [] }]
    if (url.searchParams.get('q')) items = items.filter((item) => item.key.toLowerCase().includes(url.searchParams.get('q').toLowerCase()))
    return ok({ gate, items, total: items.length })
  }
  if (path.endsWith('/release')) {
    const gate = gates.find((item) => item.id === path.split('/').at(-2))
    assert.equal(body.version, gate.version)
    assert.deepEqual(body.selected_ids, ['keep'])
    Object.assign(gate, { status: 'released', version: gate.version + 1, selected: 1, selected_ids: body.selected_ids })
    return ok(gate)
  }
  return fixture.resolve(method, url.href, { body })
}

try {
  for (let attempt = 0; attempt < 50; attempt++) {
    if (server.exitCode !== null) throw new Error(serverError || 'Preview server exited')
    try { if (serverReady && (await fetch(origin)).ok) break } catch { /* Wait for our server. */ }
    await new Promise((resolve) => setTimeout(resolve, 100))
  }
  assert.equal(serverReady, true, 'The dedicated preview server must start before browser testing')
  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const seed = createStorageSeed({ authenticated: true, language: 'en', themePreference: 'light' })
  await context.addInitScript((data) => {
    for (const [key, value] of Object.entries(data.local)) localStorage.setItem(key, value)
    for (const [key, value] of Object.entries(data.session)) sessionStorage.setItem(key, value)
  }, seed)
  await context.route('**/api/v2/**', async (route) => {
    try {
      const response = await routeApi(route.request())
      await route.fulfill({ status: response.status, contentType: 'application/json', body: JSON.stringify(response.body) })
    } catch (error) {
      problems.push(error.message)
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: error.message }) })
    }
  })
  page = await context.newPage()
  page.on('pageerror', (error) => problems.push(error.message))
  page.setDefaultTimeout(10000)
  const button = (name) => page.getByRole('button', { name, exact: true })
  await page.goto(`${origin}/#/workflow`)
  await page.locator('.react-flow__node[data-id="node_browser"]').click()
  await button('Add next node').click()
  await page.getByLabel('Node name', { exact: true }).fill('downstream-check')
  await page.getByRole('dialog').getByRole('button', { name: /Add card to workflow/i }).click()
  const dialog = page.getByRole('dialog', { name: 'Connect nodes' })
  await dialog.waitFor()
  await dialog.getByRole('button', { name: 'Connect', exact: true }).click()
  await page.getByText('Connection gate', { exact: true }).waitFor()
  assert.equal(graph.nodes.length, 2)
  assert.equal(graph.edges.length, 1)
  assert.equal(graph.nodes[1].input_bindings[0].from_port, 'sequences')
  steps.push('Add plugin node and connect its compatible ports')
  const firstEdgeId = graph.edges[0].id
  await button('Edit connection ports').click()
  await page.getByRole('dialog').getByRole('button', { name: 'Connect', exact: true }).click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  assert.equal(graph.edges[0].id, firstEdgeId)
  await button('Delete connection').click()
  await page.getByText('Connection gate', { exact: true }).waitFor({ state: 'hidden' })
  assert.equal(graph.edges.length, 0)
  assert.deepEqual(graph.nodes[1].input_bindings, [])
  // Address the handles by port name: every card also carries the ordering handles, so
  // a bare `.source`/`.target` now matches more than one element.
  const handle = (node, kind, port) =>
    page.locator(`.react-flow__node[data-id="${node}"] [data-handleid="${port}"].${kind}`)
  await handle('node_browser', 'source', 'sequences').dragTo(handle('node_1', 'target', 'sequences'))
  await page.getByText('Connection gate', { exact: true }).waitFor()
  assert.equal(graph.edges.length, 1)
  steps.push('Edit ports without replacing edge identity, delete bindings, reconnect by dragging')

  // Ordering handle to ordering handle: states "run after" with no data, which is the
  // only way to relate two stages that share no compatible port.
  await button('Delete connection').click()
  await page.getByText('Connection gate', { exact: true }).waitFor({ state: 'hidden' })
  await handle('node_browser', 'source', '__order_out').dragTo(
    handle('node_1', 'target', '__order_in'),
  )
  // The badge on an ordering arrow says what it does rather than asking for a gate.
  await page.getByRole('button', { name: 'Wait for completion' }).waitFor()
  assert.equal(graph.edges.length, 1)
  assert.equal(graph.edges[0].gate.mode, 'dependency')
  assert.equal(graph.edges[0].source_port, null)
  assert.equal(graph.edges[0].target_port, null)
  // Ordering stages no data, so it must not create an input binding.
  assert.deepEqual(graph.nodes[1].input_bindings, [])
  steps.push('Create an ordering-only connection by dragging between the ordering handles')

  // Back to the data connection the rest of this run configures gates against.
  await page.getByRole('button', { name: 'Wait for completion' }).click()
  await button('Delete connection').click()
  await page.getByText('Connection gate', { exact: true }).waitFor({ state: 'hidden' })
  await handle('node_browser', 'source', 'sequences').dragTo(handle('node_1', 'target', 'sequences'))
  await page.getByText('Connection gate', { exact: true }).waitFor()
  assert.equal(graph.edges.length, 1)
  assert.equal(graph.edges[0].gate.mode, 'automatic')
  await button('Branch screening policy').click()
  for (const label of ['Manual selection', 'Automatic screening']) {
    await page.getByRole('combobox', { name: 'Release mode' }).click()
    await page.getByRole('option', { name: label, exact: true }).click()
    await button('Save rules').click()
    await page.waitForResponse((response) => response.url().endsWith('/preflight'))
  }
  steps.push('Switch and save automatic and manual release modes')
  await page.getByRole('combobox', { name: 'Release mode' }).click()
  await page.getByRole('option', { name: 'Screen then review', exact: true }).click()
  await button('Add metric condition').click()
  await page.getByLabel('Metric', { exact: true }).fill('score')
  await page.getByLabel('Threshold', { exact: true }).fill('50')
  rejectSave = true
  await button('Save rules').click()
  await page.getByText('Graph changed; retry your connection save.', { exact: false }).first().waitFor()
  assert.equal(graph.edges[0].gate.mode, 'automatic')
  await button('Save rules').click()
  await page.getByText('Gate rules saved', { exact: true }).first().waitFor()
  assert.equal(graph.edges[0].gate.mode, 'review')
  steps.push('Save failure feedback, retry, and rule persistence')
  await page.reload()
  await button('Waiting for upstream').click()
  await button('Branch screening policy').click()
  assert.equal(await page.getByLabel('Metric', { exact: true }).inputValue(), 'score')
  await page.getByRole('combobox', { name: 'Preview data (same project and plugin)' }).click()
  await page.getByRole('option', { name: /source|score-candidates/ }).click()
  await page.getByRole('combobox', { name: 'Preview data (same project and plugin)' }).click()
  await page.getByRole('option', { name: 'Current upstream results', exact: true }).click()
  assert.match(await page.getByRole('combobox', { name: 'Preview data (same project and plugin)' }).innerText(), /Current upstream results/)
  await page.getByRole('combobox', { name: 'Preview data (same project and plugin)' }).click()
  await page.getByRole('option', { name: /score-candidates/ }).click()
  await button('Preview').click()
  await page.getByText('score too low', { exact: true }).waitFor()
  await page.getByPlaceholder('Search sequence, name, rejection reason').fill('no-matching-record')
  await page.getByText('No matching results. Adjust your search.').waitFor()
  await page.getByPlaceholder('Search sequence, name, rejection reason').fill('')
  await page.getByText('score too low', { exact: true }).waitFor()
  steps.push('Reload persisted connection, change preview source, preview results and clear an empty search')
  await button('Upstream output standard (shared)').click()
  await button('Output standard (shared by all outgoing edges)').click()
  await page.getByRole('checkbox', { name: 'Structure quality standard (DSSP)' }).click()
  const chains = page.getByLabel('Design chains (required, comma separated)', { exact: true })
  await chains.pressSequentially('A,B')
  assert.equal(await chains.inputValue(), 'A,B')
  await button('Save parameters').click()
  await page.getByText(/Parameters saved/i).first().waitFor()
  assert.deepEqual(graph.nodes[0].configuration.output_policy.structure.chains, ['A', 'B'])
  await page.locator('.react-flow__node[data-id="node_1"]').click()
  await button('Explicit upstream parameter links').click()
  await page.getByRole('combobox', { name: 'Target parameter', exact: true }).click()
  await page.getByRole('option', { name: 'threshold', exact: true }).click()
  await page.getByRole('combobox', { name: 'Upstream node', exact: true }).click()
  await page.getByRole('option', { name: 'score-candidates', exact: true }).click()
  await page.getByRole('combobox', { name: 'Source parameter', exact: true }).click()
  await page.getByRole('option', { name: 'threshold', exact: true }).click()
  await button('Add link').click()
  await button('Save parameters').click()
  await page.waitForResponse((response) => response.url().endsWith('/preflight'))
  assert.equal(graph.nodes[1].configuration.parameter_links.threshold.from_node, 'score-candidates')
  steps.push('Edit shared output standard with multiple chains and explicitly map an upstream parameter')
  await button('Suggest from upstream').click()
  await button('Apply suggestion').click()
  await button('Node script: import and bind').click()
  await page.getByLabel('Import node script', { exact: true }).setInputFiles({ name: 'synthetic.py', mimeType: 'text/plain', buffer: Buffer.from('threshold = 0.8\nprint(threshold)\n') })
  await button('Use this script version').click()
  await page.getByRole('button', { name: /Save parameters/i }).click()
  await page.getByText(/Parameters saved/i).first().waitFor()
  assert.equal(graph.nodes[1].parameters.threshold, 0.8)
  assert.equal(graph.nodes[1].configuration.script.filename, 'synthetic.py')
  await button('Generate script').click()
  await page.locator('pre').filter({ hasText: 'print(threshold)' }).last().waitFor()
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTitle('Download script').click()])
  const stream = await download.createReadStream()
  const chunks = []
  for await (const chunk of stream) chunks.push(chunk)
  assert.equal(Buffer.concat(chunks).toString(), graph.nodes[1].configuration.script.source)
  steps.push('Apply upstream suggestion, import and bind script, save, preview and download identical script text')
  gates.unshift({ ...gates[0], id: 'formal', preview: false, status: 'awaiting_review', version: 4, revision: 2 })
  graph.workflow.status = 'running'
  graph.nodes[0].status = 'succeeded'
  graph.nodes[1].status = 'pending'
  resultDelay = 800
  await page.reload()
  await button('Awaiting selection').click()
  assert.equal(await button('Keep none and end branch').isDisabled(), true)
  await page.getByText('score too low', { exact: true }).waitFor()
  await button('Keep none and end branch').click()
  await page.getByRole('dialog', { name: 'End this branch?' }).waitFor()
  assert.equal(mutations.filter((item) => item.path.endsWith('/release')).length, 0)
  await button('Continue selecting').click()
  await page.getByRole('dialog').waitFor({ state: 'hidden' })
  await button('Select qualified on page').click()
  await button('Release selected (1)').click()
  await page.getByText('Released 1 / 2', { exact: true }).first().waitFor()
  assert.equal(mutations.filter((item) => item.path.endsWith('/release')).length, 1)
  steps.push('Locked running graph: wait for results and release only qualified IDs once')
  await page.getByText('score too low', { exact: true }).waitFor()
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: `${output}/desktop.png`, fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await button('Released 1 / 2').click()
  await page.getByText('score too low', { exact: true }).waitFor()
  await page.evaluate(() => scrollTo(0, 0))
  await page.screenshot({ path: `${output}/mobile.png`, fullPage: true })
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false)
  steps.push('Mobile layout has no page overflow')
  assert.deepEqual(problems, [])
  await writeFile(`${output}/report.json`, JSON.stringify({ steps, mutations, problems }, null, 2))
  console.log(JSON.stringify({ passed: steps.length, output, steps }, null, 2))
} catch (error) {
  if (page) {
    await page.screenshot({ path: `${output}/failure.png`, fullPage: true }).catch(() => {})
    await writeFile(`${output}/failure.txt`, await page.locator('body').innerText()).catch(() => {})
  }
  console.error(error, problems)
  process.exitCode = 1
} finally {
  await browser?.close()
  server.kill('SIGTERM')
}
