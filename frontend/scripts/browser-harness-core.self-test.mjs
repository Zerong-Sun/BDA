import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import test from 'node:test'

import {
  ADD_CANDIDATE_FILTER_PATTERN,
  APPEARANCES,
  canonicalHashRoute,
  createProcessCloseMonitor,
  createSerialTaskQueue,
  FOCUS_AUDIT_CONTRACTS,
  parseResourceConsoleFailure,
  POLLING_CONTRACTS,
  reconcileResourceConsoleFailures,
  ROUTES,
  SCENARIO_CONTRACTS,
  VIEWPORTS,
  buildBrowserMatrix,
  CANDIDATE_SEARCH_FILTER_PATTERN,
  COPILOT_TRIGGER_PATTERN,
  COPILOT_LAYER_SELECTOR,
  canonicalRequestSignature,
  createFixtureRouter,
  createStorageSeed,
  didSortTransition,
  isHiddenControlProxy,
  LOGIN_INVALID_CREDENTIALS_PATTERN,
  selectCasesFromEnv,
  validatePort,
} from './browser-harness-core.mjs'

test('builds the complete route, viewport, appearance, and state matrix', () => {
  const matrix = buildBrowserMatrix()

  assert.equal(ROUTES.length, 8)
  assert.equal(VIEWPORTS.length, 2)
  assert.equal(APPEARANCES.length, 4)
  assert.equal(matrix.filter((entry) => entry.scenario === 'populated').length, 64)
  assert.equal(matrix.length, 112)
  assert.equal(new Set(matrix.map((entry) => entry.id)).size, matrix.length)
  assert.ok(matrix.every((entry) => entry.reducedMotion === 'reduce'))
  assert.ok(matrix.some((entry) => entry.routeId === 'workflow' && entry.scenario === 'read-only'))
  assert.ok(matrix.some((entry) => entry.routeId === 'research' && entry.scenario === 'recoverable-error'))
  assert.ok(matrix.some((entry) => entry.routeId === 'results' && entry.scenario === 'loading'))
})

test('rejects mistyped rerun filters instead of silently weakening coverage', () => {
  const matrix = buildBrowserMatrix()
  const selected = selectCasesFromEnv(matrix, {
    BDA_BROWSER_ROUTES: 'candidates,research',
    BDA_BROWSER_VIEWPORTS: 'mobile',
    BDA_BROWSER_APPEARANCES: 'en-light',
    BDA_BROWSER_STATES: 'populated,recoverable-error',
  })

  assert.deepEqual(
    selected.map((entry) => [entry.routeId, entry.viewportId, entry.appearanceId, entry.scenario]),
    [
      ['candidates', 'mobile', 'en-light', 'populated'],
      ['research', 'mobile', 'en-light', 'populated'],
      ['candidates', 'mobile', 'en-light', 'recoverable-error'],
      ['research', 'mobile', 'en-light', 'recoverable-error'],
    ],
  )
  assert.throws(
    () => selectCasesFromEnv(matrix, { BDA_BROWSER_ROUTES: 'canddiates' }),
    /Unknown BDA_BROWSER_ROUTES value/,
  )
  assert.throws(() => selectCasesFromEnv(matrix, { BDA_BROWSER_CASES: 'missing-case' }), /Unknown BDA_BROWSER_CASES value/)
})

test('seeds complete deterministic guest and authenticated browser storage', () => {
  const authenticated = createStorageSeed({
    authenticated: true,
    language: 'zh',
    themePreference: 'dark',
  })
  assert.equal(authenticated.session.bda_token, 'browser-acceptance-token')
  assert.equal(JSON.parse(authenticated.session.bda_user).username, 'browser.qa')
  assert.equal(authenticated.session['bda-research-package-sync-attempted'], 'true')
  const persisted = JSON.parse(authenticated.local['bda-app-store'])
  assert.equal(persisted.state.activeProjectId, 'proj_browser')
  assert.equal(persisted.state.language, 'zh')
  assert.equal(persisted.state.uiDensity, 'guided')
  assert.equal(persisted.state.themePreference, 'dark')
  assert.equal(persisted.state.copilotOpen, false)
  assert.equal(persisted.state.settingsOpen, false)
  assert.equal(persisted.state.tourMenuOpen, false)

  const guest = createStorageSeed({
    authenticated: false,
    language: 'en',
    themePreference: 'light',
  })
  assert.equal(guest.session.bda_token, undefined)
  assert.equal(JSON.parse(guest.local['bda-app-store']).state.language, 'en')
})

test('canonicalizes query order while preserving strict method, path, and query matching', async () => {
  assert.equal(
    canonicalRequestSignature('get', 'https://example.test/api/v2/projects?limit=200&cursor=next'),
    'GET /api/v2/projects?cursor=next&limit=200',
  )

  const router = createFixtureRouter({ scenario: 'populated' })
  const projects = await router.resolve('GET', 'http://app.test/api/v2/projects?limit=200')
  assert.equal(projects.status, 200)
  assert.equal(projects.body.items[0].id, 'proj_browser')
  await assert.rejects(
    () => router.resolve('GET', 'http://app.test/api/v2/projects?limit=201'),
    /Unhandled browser API request: GET .*limit=201/,
  )
  await assert.rejects(
    () => router.resolve('POST', 'http://app.test/api/v2/projects?limit=200'),
    /Unhandled browser API request: POST/,
  )
})

test('fixtures provide two candidate cursor pages and explicit expected 404 responses', async () => {
  const router = createFixtureRouter({ scenario: 'populated' })
  const first = await router.resolve(
    'GET',
    'http://app.test/api/v2/projects/proj_browser/candidates?limit=100',
  )
  const second = await router.resolve(
    'GET',
    'http://app.test/api/v2/projects/proj_browser/candidates?cursor=candidate-page-2&limit=100',
  )
  assert.equal(first.body.next_cursor, 'candidate-page-2')
  assert.equal(second.body.next_cursor, null)
  assert.notEqual(first.body.items[0].id, second.body.items[0].id)

  const blockedRouter = createFixtureRouter({ scenario: 'blocked', routeId: 'experiments' })
  const missingTarget = await blockedRouter.resolve(
    'GET',
    'http://app.test/api/v2/projects/proj_browser/primary-target',
  )
  assert.equal(missingTarget.status, 404)
  assert.equal(missingTarget.expectedHttpFailure, true)
})

test('login and recoverable-error scenarios advance only through intended retries', async () => {
  const loginRouter = createFixtureRouter({ scenario: 'auth-retry' })
  const rejected = await loginRouter.resolve('POST', 'http://app.test/api/v2/auth/token')
  const rejectedRefresh = await loginRouter.resolve('POST', 'http://app.test/api/v2/auth/refresh')
  const accepted = await loginRouter.resolve('POST', 'http://app.test/api/v2/auth/token')
  assert.equal(rejected.status, 401)
  assert.equal(rejected.expectedHttpFailure, true)
  assert.equal(rejectedRefresh.status, 401)
  assert.equal(rejectedRefresh.expectedHttpFailure, true)
  assert.equal(accepted.status, 200)
  assert.equal(accepted.body.access_token, 'browser-login-token')

  const errorRouter = createFixtureRouter({
    scenario: 'recoverable-error',
    routeId: 'research',
  })
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const response = await errorRouter.resolve(
      'GET',
      'http://app.test/api/v2/projects/proj_browser/research-workspace',
    )
    assert.equal(response.status, 503)
    assert.equal(response.expectedHttpFailure, true)
  }
  const recovered = await errorRouter.resolve(
    'GET',
    'http://app.test/api/v2/projects/proj_browser/research-workspace',
  )
  assert.equal(recovered.status, 200)
  assert.equal(recovered.body.project.id, 'proj_browser')
})

test('strict preview port validation rejects non-numeric and reserved values', () => {
  assert.equal(validatePort('4173'), 4173)
  assert.throws(() => validatePort('0'), /between 1024 and 65535/)
  assert.throws(() => validatePort('abc'), /integer/)
})

test('excludes Base UI hidden form proxies without excluding real controls', () => {
  assert.equal(isHiddenControlProxy({ tag: 'input', ariaHidden: 'true', tabIndex: -1 }), true)
  assert.equal(isHiddenControlProxy({ tag: 'button', ariaHidden: null, tabIndex: -1 }), false)
  assert.equal(isHiddenControlProxy({ tag: 'input', ariaHidden: null, tabIndex: -1 }), false)
  assert.equal(isHiddenControlProxy({ tag: 'input', ariaHidden: 'true', tabIndex: 0 }), false)
})

test('recognizes the product login copy and a first visible-column sort transition', () => {
  assert.match('Invalid username or password.', LOGIN_INVALID_CREDENTIALS_PATTERN)
  assert.equal(didSortTransition({
    beforeSort: null,
    afterSort: 'ascending',
    beforeRows: ['candidate-2', 'candidate-1'],
    afterRows: ['candidate-1', 'candidate-2'],
  }), true)
  assert.equal(didSortTransition({
    beforeSort: null,
    afterSort: null,
    beforeRows: ['candidate-2', 'candidate-1'],
    afterRows: ['candidate-2', 'candidate-1'],
  }), false)
})

test('matches the product-specific candidate filter trigger', () => {
  assert.match('Add candidate filter', ADD_CANDIDATE_FILTER_PATTERN)
  assert.match('Add filter', ADD_CANDIDATE_FILTER_PATTERN)
  assert.match('Candidate or family', CANDIDATE_SEARCH_FILTER_PATTERN)
  assert.match('Search candidate or family', CANDIDATE_SEARCH_FILTER_PATTERN)
})

test('keeps the global Copilot trigger distinct from the page chat action', () => {
  assert.match('Open Copilot', COPILOT_TRIGGER_PATTERN)
  assert.doesNotMatch('Open Copilot chat', COPILOT_TRIGGER_PATTERN)
  assert.equal(COPILOT_LAYER_SELECTOR, '[role="dialog"][data-tour-id="copilot-drawer"]')
})

test('canonical hash routes require the full path and complete query', () => {
  assert.equal(
    canonicalHashRoute('#/research?project=proj_browser&tab=evidence'),
    '/research?project=proj_browser&tab=evidence',
  )
  assert.equal(
    canonicalHashRoute('#/research?tab=evidence&project=proj_browser'),
    '/research?project=proj_browser&tab=evidence',
  )
  assert.notEqual(
    canonicalHashRoute('#/research?project=proj_browser'),
    canonicalHashRoute('#/research?tab=evidence&project=proj_browser'),
  )
  assert.notEqual(
    canonicalHashRoute('#/research?project=proj_browser&tab=evidence&extra=1'),
    canonicalHashRoute('#/research?tab=evidence&project=proj_browser'),
  )
  assert.notEqual(canonicalHashRoute('#/research-extra'), canonicalHashRoute('#/research'))
})

test('defines route-scoped scenario and full-focus contracts for every matrix case', () => {
  const stateCases = buildBrowserMatrix().filter((entry) => !['populated', 'auth-retry'].includes(entry.scenario))
  for (const entry of stateCases) {
    const contract = SCENARIO_CONTRACTS[`${entry.routeId}:${entry.scenario}`]
    assert.ok(contract, `missing ${entry.routeId}:${entry.scenario}`)
    assert.match(contract.root, /^\S/)
    assert.ok(contract.evidence?.length || contract.loadingSelector || contract.retry)
  }
  for (const route of ROUTES) {
    const focus = FOCUS_AUDIT_CONTRACTS[route.id]
    assert.ok(focus, `missing focus contract for ${route.id}`)
    assert.ok(focus.maxSteps > 8)
    assert.match(focus.root, /^\S/)
  }
  assert.deepEqual(POLLING_CONTRACTS['workflow:pending'], {
    signature: 'GET /api/v2/workflow-runs/run_browser/graph',
    minimumCount: 2,
  })
})

test('correlates resource console errors one-to-one by exact URL and status regardless of event order', () => {
  const expected = [
    { url: 'http://app.test/api/v2/auth/token', status: 401 },
    { url: 'http://app.test/api/v2/auth/token', status: 401 },
  ]
  const resourceErrors = [
    { url: 'http://app.test/api/v2/auth/token', status: 401, id: 'first' },
    { url: 'http://app.test/api/v2/auth/token', status: 404, id: 'wrong-status' },
    { url: 'http://app.test/api/v2/other', status: 401, id: 'wrong-url' },
    { url: 'http://app.test/api/v2/auth/token', status: 401, id: 'second' },
    { url: 'http://app.test/api/v2/auth/token', status: 401, id: 'duplicate' },
  ]
  const result = reconcileResourceConsoleFailures(expected, resourceErrors)
  assert.deepEqual(result.expected.map((entry) => entry.id), ['first', 'second'])
  assert.deepEqual(result.unexpected.map((entry) => entry.id), ['wrong-status', 'wrong-url', 'duplicate'])
  assert.deepEqual(result.unconsumed, [])
  assert.deepEqual(parseResourceConsoleFailure({
    text: 'Failed to load resource: the server responded with a status of 503 (Service Unavailable)',
    location: { url: 'http://app.test/api/v2/projects/proj_browser/overview' },
  }), {
    url: 'http://app.test/api/v2/projects/proj_browser/overview',
    status: 503,
  })
})

test('serial task queue preserves append order and flush waits for deferred work', async () => {
  const values = []
  const queue = createSerialTaskQueue()
  queue.enqueue(async () => {
    await new Promise((resolve) => setTimeout(resolve, 10))
    values.push('first')
  })
  queue.enqueue(async () => {
    values.push('second')
  })
  await queue.flush()
  assert.deepEqual(values, ['first', 'second'])
})

test('process close monitor waits for close after SIGKILL and times out when streams never close', async () => {
  const child = new EventEmitter()
  child.exitCode = null
  child.signalCode = null
  child.killed = true
  const monitor = createProcessCloseMonitor(child)
  let resolved = false
  const waiting = monitor.wait(100).then((value) => {
    resolved = true
    return value
  })
  await new Promise((resolve) => setTimeout(resolve, 5))
  assert.equal(resolved, false)
  child.emit('close', null, 'SIGKILL')
  assert.equal(await waiting, true)

  const exitedBeforeStreamsClosed = new EventEmitter()
  exitedBeforeStreamsClosed.exitCode = 1
  exitedBeforeStreamsClosed.signalCode = null
  const exitedMonitor = createProcessCloseMonitor(exitedBeforeStreamsClosed)
  let exitOnlyResolved = false
  const exitOnlyWaiting = exitedMonitor.wait(100).then((value) => {
    exitOnlyResolved = true
    return value
  })
  await new Promise((resolve) => setTimeout(resolve, 5))
  assert.equal(exitOnlyResolved, false)
  exitedBeforeStreamsClosed.emit('close', 1, null)
  assert.equal(await exitOnlyWaiting, true)

  const neverCloses = new EventEmitter()
  neverCloses.exitCode = null
  neverCloses.signalCode = null
  const timedOut = createProcessCloseMonitor(neverCloses)
  assert.equal(await timedOut.wait(5), false)
})
