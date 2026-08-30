import { spawn } from 'node:child_process'
import { constants as fsConstants } from 'node:fs'
import { access, appendFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  ADD_CANDIDATE_FILTER_PATTERN,
  buildBrowserMatrix,
  CANDIDATE_SEARCH_FILTER_PATTERN,
  canonicalHashRoute,
  canonicalRequestSignature,
  COPILOT_LAYER_SELECTOR,
  COPILOT_TRIGGER_PATTERN,
  createFixtureRouter,
  createProcessCloseMonitor,
  createSerialTaskQueue,
  createStorageSeed,
  didSortTransition,
  FOCUS_AUDIT_CONTRACTS,
  LOGIN_INVALID_CREDENTIALS_PATTERN,
  parseResourceConsoleFailure,
  POLLING_CONTRACTS,
  reconcileResourceConsoleFailures,
  SCENARIO_CONTRACTS,
  selectCasesFromEnv,
  validatePort,
} from './browser-harness-core.mjs'

const SCRIPT_DIRECTORY = path.dirname(fileURLToPath(import.meta.url))
const FRONTEND_DIRECTORY = path.resolve(SCRIPT_DIRECTORY, '..')
const REPOSITORY_DIRECTORY = path.resolve(FRONTEND_DIRECTORY, '..')
const ARTIFACT_DIRECTORY = path.join(
  REPOSITORY_DIRECTORY,
  '.superpowers',
  'sdd',
  '2026-07-26-frontend-reui-migration',
  'browser-artifacts',
)
const HOST = '127.0.0.1'
const PORT = validatePort(process.env.BDA_BROWSER_SMOKE_PORT ?? '4173')
const BASE_URL = `http://${HOST}:${PORT}`
const RUN_ID = `${new Date().toISOString().replaceAll(/[:.]/g, '-')}-${process.pid}`
const RUN_DIRECTORY = path.join(ARTIFACT_DIRECTORY, RUN_ID)
const CASE_TIMEOUT_MS = Number(process.env.BDA_BROWSER_CASE_TIMEOUT_MS ?? 45_000)

const ROUTE_SURFACES = Object.freeze({
  login: 'form',
  guide: '.guide-page main',
  experiments: '[data-slot="app-shell"]',
  workflow: '[data-tour-id="workflow-page"]',
  candidates: '[data-tour-id="candidate-filters"]',
  results: '[data-tour-id="results-validation"]',
  research: '[data-tour-id="research-tabs"]',
  faq: '[data-tour-id="faq-content"]',
})

const matrix = buildBrowserMatrix()
const selectedCases = selectCasesFromEnv(matrix)

let previewProcess = null
let activeBrowser = null
let stopping = false

function asError(error) {
  return error instanceof Error ? error : new Error(String(error))
}

function serializeError(error) {
  const normalized = asError(error)
  return {
    name: normalized.name,
    message: normalized.message,
    stack: normalized.stack,
  }
}

function safeFilePart(value) {
  return value.replaceAll(/[^a-zA-Z0-9._-]/g, '_')
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

async function appendJsonLine(filePath, value) {
  await appendFile(filePath, `${JSON.stringify(value)}\n`, 'utf8')
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

function previewTail(output) {
  return output.join('').split(/\r?\n/).filter(Boolean).slice(-80).join('\n')
}

async function stopPreview() {
  if (!previewProcess || previewProcess.browserHarnessClosed === true) return
  const child = previewProcess
  const closeMonitor = createProcessCloseMonitor(child)
  if (child.exitCode === null && child.signalCode === null) child.kill('SIGTERM')
  if (await closeMonitor.wait(2_000)) return
  if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
  if (!(await closeMonitor.wait(2_000))) {
    throw new Error('Vite preview did not close its process streams after SIGKILL.')
  }
}

async function cleanup() {
  if (stopping) return
  stopping = true
  try {
    await activeBrowser?.close()
  } catch {
    // The primary failure is already recorded by the case runner.
  }
  activeBrowser = null
  await stopPreview()
}

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => {
    void cleanup().finally(() => {
      process.exitCode = 130
    })
  })
}

async function waitForPreviewReady(output, earlyExit) {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    if (earlyExit.value) {
      throw new Error(
        `Vite preview exited before becoming ready (code ${earlyExit.value.code}, signal ${earlyExit.value.signal}).\n`
        + previewTail(output),
      )
    }
    try {
      const response = await fetch(BASE_URL, { redirect: 'manual' })
      if (response.status >= 200 && response.status < 400) return
    } catch {
      // The strict-port preview process is still starting.
    }
    await delay(200)
  }
  throw new Error(`Vite preview did not become ready at ${BASE_URL}.\n${previewTail(output)}`)
}

async function startPreview() {
  const viteCli = fileURLToPath(new URL('../node_modules/vite/bin/vite.js', import.meta.url))
  const output = []
  const earlyExit = { value: null }
  const child = spawn(
    process.execPath,
    [viteCli, 'preview', '--host', HOST, '--port', String(PORT), '--strictPort'],
    {
      cwd: FRONTEND_DIRECTORY,
      env: { ...process.env, TMPDIR: '/tmp' },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )
  previewProcess = child
  child.browserHarnessClosed = false
  child.once('close', () => {
    child.browserHarnessClosed = true
  })
  child.stdout.on('data', (chunk) => output.push(chunk.toString()))
  child.stderr.on('data', (chunk) => output.push(chunk.toString()))
  child.once('exit', (code, signal) => {
    earlyExit.value = { code, signal }
  })
  child.once('error', (error) => {
    output.push(`${error.stack ?? error.message}\n`)
    earlyExit.value = { code: 'spawn-error', signal: null }
  })
  await waitForPreviewReady(output, earlyExit)
  return { output, earlyExit }
}

function describeFilters() {
  return {
    routes: process.env.BDA_BROWSER_ROUTES ?? null,
    viewports: process.env.BDA_BROWSER_VIEWPORTS ?? null,
    appearances: process.env.BDA_BROWSER_APPEARANCES ?? null,
    states: process.env.BDA_BROWSER_STATES ?? null,
    cases: process.env.BDA_BROWSER_CASES ?? null,
  }
}

async function runDryValidation() {
  for (const testCase of selectedCases) {
    const router = createFixtureRouter({
      scenario: testCase.scenario,
      routeId: testCase.routeId,
    })
    await router.resolve('GET', `${BASE_URL}/api/v2/health/ready`)
    if (testCase.authenticated) {
      await router.resolve('GET', `${BASE_URL}/api/v2/projects?limit=200`)
    }
  }
  console.log(JSON.stringify({
    mode: 'dry-run',
    frontendDirectory: FRONTEND_DIRECTORY,
    repositoryDirectory: REPOSITORY_DIRECTORY,
    baseUrl: BASE_URL,
    filters: describeFilters(),
    selectedCaseCount: selectedCases.length,
    selectedCaseIds: selectedCases.map((entry) => entry.id),
  }, null, 2))
}

function storageInitScript(seed) {
  sessionStorage.clear()
  localStorage.clear()
  for (const [key, value] of Object.entries(seed.session)) {
    if (value !== undefined) sessionStorage.setItem(key, value)
  }
  for (const [key, value] of Object.entries(seed.local)) {
    if (value !== undefined) localStorage.setItem(key, value)
  }
}

async function installDiagnostics(page, testCase, router, diagnostics) {
  const consoleLogPath = path.join(RUN_DIRECTORY, 'console.jsonl')
  const networkLogPath = path.join(RUN_DIRECTORY, 'network.jsonl')
  const logQueue = createSerialTaskQueue()
  const expectedHttpFailures = new Map()
  const expectedResourceFailures = []
  const pendingResourceConsole = []
  let activeApiRoutes = 0
  let lastActivityAt = Date.now()
  let resourceConsoleReconciled = false

  const markActivity = () => {
    lastActivityAt = Date.now()
  }
  const queueLog = (filePath, entry) => {
    markActivity()
    return logQueue.enqueue(() => appendJsonLine(filePath, entry))
  }
  const addExpectedHttpFailure = (key) => {
    expectedHttpFailures.set(key, (expectedHttpFailures.get(key) ?? 0) + 1)
  }
  const consumeExpectedHttpFailure = (key) => {
    const remaining = expectedHttpFailures.get(key) ?? 0
    if (remaining <= 0) return false
    expectedHttpFailures.set(key, remaining - 1)
    return true
  }

  page.on('console', (message) => {
    markActivity()
    const parsedResourceFailure = message.type() === 'error'
      ? parseResourceConsoleFailure({ text: message.text(), location: message.location() })
      : null
    const entry = {
      at: new Date().toISOString(),
      caseId: testCase.id,
      type: message.type(),
      text: message.text(),
      location: message.location(),
      expected: null,
    }
    diagnostics.console.push(entry)
    if (parsedResourceFailure) {
      pendingResourceConsole.push({ ...parsedResourceFailure, entry })
      return
    }
    void queueLog(consoleLogPath, entry)
    if (message.type() === 'error') {
      diagnostics.failures.push(`Console error: ${message.text()}`)
    }
  })
  page.on('pageerror', (error) => {
    markActivity()
    const entry = {
      at: new Date().toISOString(),
      caseId: testCase.id,
      type: 'pageerror',
      error: serializeError(error),
    }
    diagnostics.console.push(entry)
    diagnostics.failures.push(`Page error: ${error.message}`)
    void queueLog(consoleLogPath, entry)
  })
  page.on('requestfailed', (request) => {
    markActivity()
    const signature = canonicalRequestSignature(request.method(), request.url())
    const entry = {
      at: new Date().toISOString(),
      caseId: testCase.id,
      phase: 'requestfailed',
      signature,
      failure: request.failure(),
    }
    diagnostics.network.push(entry)
    diagnostics.failures.push(`Network request failed: ${signature} (${request.failure()?.errorText ?? 'unknown'})`)
    void queueLog(networkLogPath, entry)
  })
  page.on('response', (response) => {
    markActivity()
    if (response.status() < 400) return
    const request = response.request()
    const signature = canonicalRequestSignature(request.method(), request.url())
    const expectedKey = `${signature} ${response.status()}`
    const entry = {
      at: new Date().toISOString(),
      caseId: testCase.id,
      phase: 'http-error',
      signature,
      status: response.status(),
      expected: consumeExpectedHttpFailure(expectedKey),
    }
    diagnostics.network.push(entry)
    void queueLog(networkLogPath, entry)
    if (!entry.expected) {
      diagnostics.failures.push(`Unexpected HTTP ${response.status()}: ${signature}`)
    }
  })

  await page.route('**/api/v2/**', async (route) => {
    activeApiRoutes += 1
    markActivity()
    const request = route.request()
    const signature = canonicalRequestSignature(request.method(), request.url())
    let postData = request.postData()
    try {
      postData = request.postDataJSON()
    } catch {
      // Keep the exact raw body when the request is not JSON.
    }
    const requestEntry = {
      at: new Date().toISOString(),
      caseId: testCase.id,
      phase: 'request',
      signature,
      resourceType: request.resourceType(),
      postData,
    }
    diagnostics.network.push(requestEntry)
    await queueLog(networkLogPath, requestEntry)

    try {
      const fixture = await router.resolve(request.method(), request.url(), {
        headers: request.headers(),
        postData: request.postData(),
      })
      if (fixture.expectedHttpFailure) {
        addExpectedHttpFailure(`${signature} ${fixture.status}`)
        expectedResourceFailures.push({ url: request.url(), status: fixture.status, signature })
      }
      if (fixture.delayMs > 0) await delay(fixture.delayMs)
      const responseEntry = {
        at: new Date().toISOString(),
        caseId: testCase.id,
        phase: 'fixture-response',
        signature,
        status: fixture.status,
        expectedHttpFailure: fixture.expectedHttpFailure,
        delayMs: fixture.delayMs,
      }
      diagnostics.network.push(responseEntry)
      await queueLog(networkLogPath, responseEntry)
      await route.fulfill({
        status: fixture.status,
        contentType: 'application/json',
        headers: fixture.headers,
        body: JSON.stringify(fixture.body),
      })
    } catch (error) {
      const normalized = asError(error)
      diagnostics.failures.push(normalized.message)
      await queueLog(networkLogPath, {
        at: new Date().toISOString(),
        caseId: testCase.id,
        phase: 'unhandled',
        signature,
        error: serializeError(normalized),
      })
      await route.fulfill({
        status: 599,
        contentType: 'application/problem+json',
        body: JSON.stringify({
          title: 'Unhandled deterministic browser fixture',
          status: 599,
          detail: normalized.message,
        }),
      })
    } finally {
      activeApiRoutes -= 1
      markActivity()
    }
  })

  return {
    async quiesce() {
      const polling = POLLING_CONTRACTS[`${testCase.routeId}:${testCase.scenario}`]
      const deadline = Date.now() + (polling ? 8_000 : 4_000)
      if (polling) {
        while ((router.requestCounts()[polling.signature] ?? 0) < polling.minimumCount) {
          if (Date.now() >= deadline) {
            throw new Error(
              `Polling contract did not observe ${polling.minimumCount} requests for ${polling.signature}.`,
            )
          }
          await delay(50)
        }
      }
      while (true) {
        const activitySnapshot = lastActivityAt
        if (activeApiRoutes === 0 && Date.now() - activitySnapshot >= 250) break
        if (Date.now() >= deadline) {
          throw new Error(`Diagnostics did not quiesce; ${activeApiRoutes} API fixture routes remain active.`)
        }
        await delay(25)
      }
      await logQueue.flush()
      if (resourceConsoleReconciled) return
      resourceConsoleReconciled = true

      const reconciliation = reconcileResourceConsoleFailures(
        expectedResourceFailures,
        pendingResourceConsole,
      )
      for (const correlated of reconciliation.expected) {
        correlated.entry.expected = true
        await queueLog(consoleLogPath, correlated.entry)
      }
      for (const unexpected of reconciliation.unexpected) {
        unexpected.entry.expected = false
        diagnostics.failures.push(
          `Unexpected resource console error: ${unexpected.status} ${unexpected.url}`,
        )
        await queueLog(consoleLogPath, unexpected.entry)
      }
      diagnostics.resourceConsoleReconciliation = {
        expected: reconciliation.expected.map(({ url, status }) => ({ url, status })),
        unexpected: reconciliation.unexpected.map(({ url, status }) => ({ url, status })),
        expectedWithoutConsoleEntry: reconciliation.unconsumed.map(({ url, status }) => ({ url, status })),
      }
      await logQueue.flush()
    },
  }
}

async function expectVisible(locator, label, timeout = 10_000) {
  try {
    await locator.waitFor({ state: 'visible', timeout })
  } catch (error) {
    throw new Error(`Expected visible ${label}: ${asError(error).message}`)
  }
}

async function expectHidden(locator, label, timeout = 5_000) {
  try {
    await locator.waitFor({ state: 'hidden', timeout })
  } catch (error) {
    throw new Error(`Expected hidden ${label}: ${asError(error).message}`)
  }
}

async function assertDocumentContract(page, testCase) {
  const expectedTheme = testCase.themePreference === 'system'
    ? testCase.colorScheme
    : testCase.themePreference
  const actual = await page.evaluate(() => ({
    lang: document.documentElement.lang,
    theme: document.documentElement.getAttribute('data-theme'),
    dark: document.documentElement.classList.contains('dark'),
    hash: window.location.hash,
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  }))
  if (actual.lang !== testCase.language) {
    throw new Error(`Expected document language ${testCase.language}; received ${actual.lang}.`)
  }
  if (actual.theme !== expectedTheme || actual.dark !== (expectedTheme === 'dark')) {
    throw new Error(
      `Expected ${expectedTheme} theme with dark=${expectedTheme === 'dark'}; `
      + `received theme=${actual.theme}, dark=${actual.dark}.`,
    )
  }
  const expectedRoute = canonicalHashRoute(testCase.routePath)
  const actualRoute = canonicalHashRoute(actual.hash)
  const emptyProjectLibraryCanonicalRoute =
    testCase.routeId === 'experiments' && testCase.scenario === 'empty' && actualRoute === '/projects'
  if (actualRoute !== expectedRoute && !emptyProjectLibraryCanonicalRoute) {
    throw new Error(`Unexpected route hash ${actualRoute}; expected ${expectedRoute}.`)
  }
  if (!actual.reducedMotion) {
    throw new Error('Reduced motion was not active before application mount.')
  }
}

async function assertSystemThemeResponse(page, testCase) {
  if (testCase.themePreference !== 'system') return null
  const opposite = testCase.colorScheme === 'dark' ? 'light' : 'dark'
  await page.emulateMedia({ colorScheme: opposite, reducedMotion: 'reduce' })
  await page.waitForFunction(
    (theme) => document.documentElement.getAttribute('data-theme') === theme,
    opposite,
  )
  const toggled = await page.evaluate(() => ({
    theme: document.documentElement.getAttribute('data-theme'),
    dark: document.documentElement.classList.contains('dark'),
  }))
  await page.emulateMedia({ colorScheme: testCase.colorScheme, reducedMotion: 'reduce' })
  await page.waitForFunction(
    (theme) => document.documentElement.getAttribute('data-theme') === theme,
    testCase.colorScheme,
  )
  return { opposite, toggled }
}

async function assertNoPageOverflow(page) {
  const result = await page.evaluate(() => {
    const root = document.documentElement
    const localOverflow = [...document.querySelectorAll('*')].flatMap((element) => {
      if (!(element instanceof HTMLElement) || element.offsetParent === null) return []
      const style = getComputedStyle(element)
      if (!['auto', 'scroll'].includes(style.overflowX)) return []
      if (element.scrollWidth <= element.clientWidth + 1) return []
      return [{
        tag: element.tagName.toLowerCase(),
        slot: element.getAttribute('data-slot'),
        role: element.getAttribute('role'),
        label: element.getAttribute('aria-label'),
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
      }]
    })
    return {
      clientWidth: root.clientWidth,
      scrollWidth: root.scrollWidth,
      localOverflow,
    }
  })
  if (result.scrollWidth > result.clientWidth + 1) {
    throw new Error(
      `Page has horizontal overflow: scrollWidth=${result.scrollWidth}, clientWidth=${result.clientWidth}.`,
    )
  }
  return result
}

async function assertReducedMotion(page, { requiredLayer = null, label = 'document' } = {}) {
  const layerHandle = requiredLayer ? await requiredLayer.elementHandle() : null
  const result = await page.evaluate((layer) => {
    const parseTimeList = (value) => value.split(',').map((entry) => {
      const trimmed = entry.trim()
      if (trimmed.endsWith('ms')) return Number.parseFloat(trimmed)
      if (trimmed.endsWith('s')) return Number.parseFloat(trimmed) * 1000
      return 0
    })
    const isRendered = (element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return (
        style.display !== 'none'
        && style.visibility !== 'hidden'
        && rect.width > 0
        && rect.height > 0
      )
    }
    const offenders = []
    let auditedStyleCount = 0
    for (const element of document.querySelectorAll('*')) {
      if (!isRendered(element)) continue
      for (const pseudo of [null, '::before', '::after']) {
        const style = getComputedStyle(element, pseudo)
        auditedStyleCount += 1
        const animationDuration = Math.max(0, ...parseTimeList(style.animationDuration))
        const animationDelay = Math.max(0, ...parseTimeList(style.animationDelay))
        const transitionDuration = Math.max(0, ...parseTimeList(style.transitionDuration))
        const transitionDelay = Math.max(0, ...parseTimeList(style.transitionDelay))
        const iterationCount = style.animationIterationCount
          .split(',')
          .reduce((maximum, entry) => {
            const trimmed = entry.trim()
            return Math.max(maximum, trimmed === 'infinite' ? Number.POSITIVE_INFINITY : Number(trimmed) || 0)
          }, 0)
        const animated = (
          style.animationName !== 'none'
          && (animationDuration > 1 || animationDelay > 1 || iterationCount > 1)
        )
        const transitioning = (
          style.transitionProperty !== 'none'
          && (transitionDuration > 1 || transitionDelay > 1)
        )
        const smoothScrolling = style.scrollBehavior === 'smooth'
        const snapping = style.scrollSnapType !== 'none'
        if (!animated && !transitioning && !smoothScrolling && !snapping) continue
        offenders.push({
          tag: element.tagName.toLowerCase(),
          pseudo,
          slot: element.getAttribute('data-slot'),
          role: element.getAttribute('role'),
          className: element.getAttribute('class'),
          position: style.position,
          animationName: style.animationName,
          animationDuration,
          animationDelay,
          iterationCount,
          transitionProperty: style.transitionProperty,
          transitionDuration,
          transitionDelay,
          scrollBehavior: style.scrollBehavior,
          scrollSnapType: style.scrollSnapType,
        })
      }
    }
    const layerStyle = layer instanceof Element ? getComputedStyle(layer) : null
    const layerRect = layer instanceof Element ? layer.getBoundingClientRect() : null
    return {
      offenders: offenders.slice(0, 40),
      auditedStyleCount,
      layer: layer instanceof Element
        ? {
            tag: layer.tagName.toLowerCase(),
            role: layer.getAttribute('role'),
            slot: layer.getAttribute('data-slot'),
            position: layerStyle?.position,
            width: layerRect?.width,
            height: layerRect?.height,
            rendered: isRendered(layer),
          }
        : null,
    }
  }, layerHandle)
  await layerHandle?.dispose()
  if (requiredLayer && !result.layer?.rendered) {
    throw new Error(`${label} reduced-motion audit did not inspect the rendered layer.`)
  }
  if (result.offenders.length > 0) {
    throw new Error(`Visible non-essential motion remains under reduced motion:\n${JSON.stringify(result.offenders, null, 2)}`)
  }
  return {
    label,
    offenderCount: 0,
    auditedStyleCount: result.auditedStyleCount,
    layer: result.layer,
  }
}

async function assertMobileTouchTargets(page, testCase) {
  if (testCase.viewportId !== 'mobile') return { audited: false, exceptions: [], violations: [] }
  const result = await page.evaluate(() => {
    const selector = [
      'button',
      'a[href]',
      'input:not([type="hidden"])',
      'select',
      'textarea',
      '[role="button"]',
      '[role="checkbox"]',
      '[role="radio"]',
      '[role="tab"]',
      '[role="menuitem"]',
    ].join(',')
    const exceptions = []
    const violations = []
    for (const element of document.querySelectorAll(selector)) {
      if (!(element instanceof HTMLElement) || element.offsetParent === null) continue
      if (
        element.matches(':disabled,[aria-disabled="true"]')
        || element.closest('[aria-hidden="true"],[inert]')
      ) continue
      const rect = element.getBoundingClientRect()
      if (rect.width >= 44 && rect.height >= 44) continue
      const style = getComputedStyle(element)
      const inlineTextLink = (
        element instanceof HTMLAnchorElement
        && style.display === 'inline'
        && Boolean(element.closest('p,li,dd,td,[data-slot="data-grid-cell"]'))
      )
      const labeledNativeChoice = (
        element instanceof HTMLInputElement
        && ['checkbox', 'radio'].includes(element.type)
        && element.closest('label')?.getBoundingClientRect().width >= 44
        && element.closest('label')?.getBoundingClientRect().height >= 44
      )
      const entry = {
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role'),
        name: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 100) || '',
        width: Math.round(rect.width * 10) / 10,
        height: Math.round(rect.height * 10) / 10,
      }
      if (inlineTextLink) {
        exceptions.push({ ...entry, reason: 'Inline prose/table link; surrounding line box is the documented target.' })
      } else if (labeledNativeChoice) {
        exceptions.push({ ...entry, reason: 'Native choice delegates its effective target to a 44px label.' })
      } else {
        violations.push(entry)
      }
    }
    return { exceptions, violations }
  })
  if (result.violations.length > 0) {
    throw new Error(`Mobile controls below 44×44:\n${JSON.stringify(result.violations, null, 2)}`)
  }
  return { audited: true, ...result }
}

async function auditKeyboardFocus(page, testCase) {
  const contract = FOCUS_AUDIT_CONTRACTS[testCase.routeId]
    const expected = await page.evaluate(({ rootSelector, maxSteps }) => {
    const root = document.querySelector(rootSelector)
    if (!(root instanceof HTMLElement)) {
      throw new Error(`Missing route focus root ${rootSelector}.`)
    }
    const isRendered = (element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return (
        style.display !== 'none'
        && style.visibility !== 'hidden'
        && rect.width > 0
        && rect.height > 0
      )
    }
    const selector = [
      'a[href]',
      'button',
      'input:not([type="hidden"])',
      'select',
      'textarea',
      '[tabindex]',
    ].join(',')
    const candidates = [...document.querySelectorAll(selector)]
      .filter((element) => (
        element instanceof HTMLElement
        && isRendered(element)
        && element.tabIndex >= 0
        && !element.matches(':disabled,[aria-disabled="true"]')
        && !element.closest('[aria-hidden="true"],[inert]')
      ))
      .sort((left, right) => {
        const leftPositive = left.tabIndex > 0
        const rightPositive = right.tabIndex > 0
        if (leftPositive !== rightPositive) return leftPositive ? -1 : 1
        if (leftPositive && left.tabIndex !== right.tabIndex) return left.tabIndex - right.tabIndex
        return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1
      })
    if (candidates.length > maxSteps) {
      throw new Error(
        `Route focus contract found ${candidates.length} controls, exceeding its explicit ${maxSteps}-step bound.`,
      )
    }
    const entries = candidates.map((element, index) => {
      const auditId = `${rootSelector}:${index}`
      element.setAttribute('data-browser-focus-audit-id', auditId)
      return {
        auditId,
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role'),
        name: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 100) || '',
        tabIndex: element.tabIndex,
        insideRouteRoot: root.contains(element),
      }
    })
    if (!entries.some((entry) => entry.insideRouteRoot)) {
      throw new Error(`Route focus root ${rootSelector} contains no logical focus stops.`)
    }
    document.body.setAttribute('data-browser-focus-body-tabindex', document.body.getAttribute('tabindex') ?? '')
    document.body.tabIndex = -1
    document.body.focus()
    return entries
  }, { rootSelector: contract.root, maxSteps: contract.maxSteps })

  const sequence = []
  for (let index = 0; index < expected.length; index += 1) {
    await page.keyboard.press('Tab')
    const focused = await page.evaluate(() => {
      const element = document.activeElement
      if (!(element instanceof Element)) return null
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return {
        auditId: element.getAttribute('data-browser-focus-audit-id'),
        tag: element.tagName.toLowerCase(),
        role: element.getAttribute('role'),
        name: element.getAttribute('aria-label') || element.textContent?.trim().slice(0, 100) || '',
        focusVisible: element.matches(':focus-visible'),
        visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden',
        outlineStyle: style.outlineStyle,
        outlineWidth: style.outlineWidth,
        boxShadow: style.boxShadow,
      }
    })
    if (!focused || focused.auditId !== expected[index].auditId || !focused.visible || !focused.focusVisible) {
      throw new Error(
        `Unexpected logical focus at tab ${index + 1}; `
        + `expected ${JSON.stringify(expected[index])}, received ${JSON.stringify(focused)}; `
        + `nearby=${JSON.stringify(expected.slice(Math.max(0, index - 2), index + 3))}.`,
      )
    }
    const focusStyled = (
      (focused.outlineStyle !== 'none' && focused.outlineWidth !== '0px')
      || (focused.boxShadow !== 'none' && focused.boxShadow !== '')
    )
    if (!focusStyled) {
      throw new Error(`No visible focus treatment at tab ${index + 1}: ${JSON.stringify(focused)}`)
    }
    sequence.push(focused)
  }
  const tailAuditIds = expected.slice(-2).map((entry) => entry.auditId)
  const wrapTrail = []
  let wrapped = null
  for (let attempt = 0; attempt < 4; attempt += 1) {
    await page.keyboard.press('Tab')
    wrapped = await page.evaluate((firstAuditId) => {
      const element = document.activeElement
      if (!(element instanceof HTMLElement)) return null
      return element === document.body
        ? 'body'
        : element.getAttribute('data-browser-focus-audit-id') === firstAuditId
          ? 'first'
          : element.getAttribute('data-browser-focus-audit-id')
    }, expected[0]?.auditId)
    wrapTrail.push(wrapped)
    if (['body', 'first'].includes(wrapped)) break
    if (!tailAuditIds.includes(wrapped)) break
  }
  await page.evaluate(() => {
    for (const element of document.querySelectorAll('[data-browser-focus-audit-id]')) {
      element.removeAttribute('data-browser-focus-audit-id')
    }
    const previousBodyTabIndex = document.body.getAttribute('data-browser-focus-body-tabindex')
    document.body.removeAttribute('data-browser-focus-body-tabindex')
    if (previousBodyTabIndex) document.body.setAttribute('tabindex', previousBodyTabIndex)
    else document.body.removeAttribute('tabindex')
  })
  if (!['body', 'first'].includes(wrapped)) {
    throw new Error(
      `Focus order did not wrap after ${expected.length} route-specific steps; `
      + `tail=${JSON.stringify(expected.slice(-2))}; received ${JSON.stringify(wrapTrail)}.`,
    )
  }
  return {
    contract,
    expectedCount: expected.length,
    routeFocusCount: expected.filter((entry) => entry.insideRouteRoot).length,
    wrap: wrapped,
    wrapTrail,
    sequence,
  }
}

async function assertEscapeFocusReturn(page, trigger, layer, label, diagnostics) {
  await expectVisible(trigger, `${label} trigger`)
  await trigger.focus()
  await trigger.click()
  await expectVisible(layer, `${label} layer`)
  const motion = await assertReducedMotion(page, { requiredLayer: layer, label })
  diagnostics.overlayMotion ??= {}
  diagnostics.overlayMotion[label] = motion
  await page.keyboard.press('Escape')
  await expectHidden(layer, `${label} layer`)
  const returned = await trigger.evaluate((element) => (
    document.activeElement === element || element.contains(document.activeElement)
  ))
  if (!returned) throw new Error(`${label} did not return focus to its trigger after Escape.`)
}

async function firstVisible(locator) {
  const count = await locator.count()
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index)
    if (await candidate.isVisible()) return candidate
  }
  return null
}

async function exerciseGlobalLayers(page, testCase, diagnostics) {
  if (
    !testCase.authenticated
    || testCase.appearanceId !== 'en-light'
    || testCase.scenario !== 'populated'
    || testCase.routeId !== 'experiments'
  ) return

  await assertEscapeFocusReturn(
    page,
    page.getByRole('button', { name: 'Application settings' }),
    page.getByRole('dialog').filter({ has: page.locator('[data-tour-id="settings-drawer"]') }),
    'Settings',
    diagnostics,
  )
  await assertEscapeFocusReturn(
    page,
    page.getByRole('button', { name: COPILOT_TRIGGER_PATTERN }),
    page.locator(COPILOT_LAYER_SELECTOR),
    'Copilot',
    diagnostics,
  )

  const helpTrigger = await firstVisible(page.getByRole('button', { name: 'Help' }))
  if (helpTrigger) {
    await assertEscapeFocusReturn(page, helpTrigger, page.getByRole('menu'), 'Help menu', diagnostics)
  } else {
    diagnostics.gating.push({ control: 'Help menu', reason: 'Desktop-only control hidden at the mobile breakpoint.' })
  }

  const userTrigger = await firstVisible(page.getByRole('button', { name: /Browser QA/ }))
  if (userTrigger) {
    await assertEscapeFocusReturn(page, userTrigger, page.getByRole('menu'), 'User menu', diagnostics)
  }

  await assertEscapeFocusReturn(
    page,
    page.locator('[data-tour-id="tour-help"]'),
    page.getByRole('dialog'),
    'Tour menu',
    diagnostics,
  )

  const projectTrigger = page.locator('[data-tour-id="project-selector"] button').first()
  await assertEscapeFocusReturn(
    page,
    projectTrigger,
    page.getByRole('listbox'),
    'Project selector',
    diagnostics,
  )
}

async function clickAndAssertSort(table, label) {
  // A grid can retain sorting for an expert-only hidden column, leaving no
  // visible header with aria-sort until the user chooses a visible column.
  const sortableHeaders = table.locator('thead th:has(button)')
  await expectVisible(sortableHeaders.first(), `${label} sortable header`)
  const beforeRows = await table.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => row.getAttribute('data-row-id') || row.textContent?.trim()))
  const headerCount = await sortableHeaders.count()
  for (let headerIndex = 0; headerIndex < headerCount; headerIndex += 1) {
    const sortableHeader = sortableHeaders.nth(headerIndex)
    const beforeSort = await sortableHeader.getAttribute('aria-sort')
    const sortButton = sortableHeader.getByRole('button').first()
    for (let clickCount = 1; clickCount <= 2; clickCount += 1) {
      await sortButton.click()
      const afterSort = await sortableHeader.getAttribute('aria-sort')
      const afterRows = await table.locator('tbody tr').evaluateAll((rows) =>
        rows.map((row) => row.getAttribute('data-row-id') || row.textContent?.trim()))
      if (didSortTransition({ beforeSort, afterSort, beforeRows, afterRows })) {
        return {
          header: (await sortableHeader.textContent())?.trim(),
          beforeSort,
          afterSort,
          beforeRows,
          afterRows,
          clickCount,
        }
      }
    }
  }
  throw new Error(`${label} sort did not change both aria-sort and row order on any sortable column.`)
}

async function exerciseCandidateGrid(page, diagnostics) {
  const candidateRequests = diagnostics.network
    .filter((entry) => entry.phase === 'request' && entry.signature.includes('/candidates?'))
    .map((entry) => entry.signature)
  const requiredCandidateRequests = [
    'GET /api/v2/projects/proj_browser/candidates?limit=100',
    'GET /api/v2/projects/proj_browser/candidates?cursor=candidate-page-2&limit=100',
  ]
  for (const signature of requiredCandidateRequests) {
    if (!candidateRequests.includes(signature)) {
      throw new Error(`Candidate client/server contract did not exhaust cursor request: ${signature}`)
    }
  }
  const table = page.locator('[data-slot="data-grid-table"]').first()
  await expectVisible(table, 'candidate Data Grid')
  diagnostics.interactions.candidateSort = await clickAndAssertSort(table, 'Candidate Data Grid')

  const checkboxes = table.getByRole('checkbox')
  if ((await checkboxes.count()) < 2) {
    throw new Error('Candidate Data Grid did not expose row selection checkboxes.')
  }
  const selectionLabel = page.getByText(/^\d+ selected$/).first()
  const beforeSelection = await selectionLabel.textContent()
  await checkboxes.nth(1).click()
  const afterSelection = await selectionLabel.textContent()
  if (beforeSelection === afterSelection) {
    throw new Error('Candidate row selection did not change the selected count.')
  }

  const next = page.locator('[data-testid="candidate-pagination"]').getByRole('button', { name: /next page/i })
  const previous = page.locator('[data-testid="candidate-pagination"]').getByRole('button', { name: /previous page/i })
  const pageOneRows = await table.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => row.getAttribute('data-row-id')))
  await next.click()
  const pageTwoRows = await table.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => row.getAttribute('data-row-id')))
  if (JSON.stringify(pageOneRows) === JSON.stringify(pageTwoRows)) {
    throw new Error('Candidate ReUI pagination did not change the visible cursor-exhausted page.')
  }
  await previous.click()
  const restoredRows = await table.locator('tbody tr').evaluateAll((rows) =>
    rows.map((row) => row.getAttribute('data-row-id')))
  if (JSON.stringify(pageOneRows) !== JSON.stringify(restoredRows)) {
    throw new Error('Candidate ReUI pagination did not restore the first page.')
  }

  const filters = page.locator('[data-slot="filters"]')
  const addFilter = filters.getByRole('button', { name: ADD_CANDIDATE_FILTER_PATTERN })
  await assertEscapeFocusReturn(
    page,
    addFilter,
    page.getByRole('listbox'),
    'Candidate Filters',
    diagnostics,
  )
  await addFilter.click()
  const searchField = page.getByRole('option', { name: CANDIDATE_SEARCH_FILTER_PATTERN }).first()
  await expectVisible(searchField, 'candidate Search filter choice')
  await searchField.click()
  const filterInput = filters.getByPlaceholder(CANDIDATE_SEARCH_FILTER_PATTERN).first()
  await filterInput.fill('later-page-family')
  await page.keyboard.press('Enter')
  await expectVisible(page.getByText('Browser candidate 12').first(), 'filtered later-page candidate')
  if (await page.getByText('Browser candidate 1', { exact: true }).count()) {
    throw new Error('Candidate filter left a non-matching row visible.')
  }
  const candidateRequestsAfterFiltering = diagnostics.network
    .filter((entry) => entry.phase === 'request' && entry.signature.includes('/candidates?'))
    .map((entry) => entry.signature)
  if (JSON.stringify(candidateRequestsAfterFiltering) !== JSON.stringify(candidateRequests)) {
    throw new Error('Candidate local filtering issued an unsupported or redundant server query.')
  }
  diagnostics.interactions.candidateSelection = { beforeSelection, afterSelection }
  diagnostics.interactions.candidatePagination = { pageOneRows, pageTwoRows, restoredRows }
  diagnostics.interactions.candidateRequestContract = {
    cursorRequests: candidateRequests,
    filtering: 'complete cursor collection first; filter/sort/paginate locally without fabricated API parameters',
  }
}

async function exerciseResearchGrids(page, diagnostics) {
  const dataTab = page.getByRole('tab', { name: /Data/i })
  await dataTab.evaluate((element) => element.scrollIntoView({ block: 'center', inline: 'nearest' }))
  await dataTab.click()
  const tables = page.locator('[data-slot="data-grid-table"]')
  await expectVisible(tables.first(), 'research Data Grids')
  if ((await tables.count()) < 2) {
    throw new Error('Research data view did not render both target and dataset Data Grids.')
  }
  diagnostics.interactions.researchSort = await clickAndAssertSort(tables.first(), 'Research target Data Grid')
  const search = page.getByRole('textbox', { name: /search dataset/i })
  await search.fill('no-browser-dataset-match')
  const datasetTable = tables.nth(1)
  await page.waitForFunction(
    (table) => table instanceof HTMLTableElement && table.querySelectorAll('tbody tr[data-row-id]').length === 0,
    await datasetTable.elementHandle(),
  )
  if ((await datasetTable.locator('tbody tr[data-row-id]').count()) !== 0) {
    throw new Error('Dataset search did not produce the expected empty grid state.')
  }
  await search.fill('Secondary target')
  await page.waitForFunction(
    (table) => table instanceof HTMLTableElement && table.querySelectorAll('tbody tr[data-row-id]').length === 1,
    await datasetTable.elementHandle(),
  )
  if ((await datasetTable.locator('tbody tr[data-row-id]').count()) !== 1) {
    throw new Error('Dataset search did not restore the matching bilingual fixture row.')
  }
}

async function exerciseDisclosure(page, containerSelector, label) {
  const selected = page.locator(containerSelector).locator('button[aria-expanded]').first()
  await expectVisible(selected, `${label} disclosure`)
  const before = await selected.getAttribute('aria-expanded')
  await selected.click()
  const after = await selected.getAttribute('aria-expanded')
  if (before === after) throw new Error(`${label} disclosure did not change expanded state.`)
  await selected.click()
  return { label, before, after, restored: await selected.getAttribute('aria-expanded') }
}

async function exerciseRouteInteractions(page, testCase, diagnostics) {
  if (testCase.appearanceId !== 'en-light') return

  if (testCase.routeId === 'login' && testCase.scenario === 'auth-retry') {
    await page.getByLabel(/username/i).fill('browser.qa')
    await page.getByLabel(/password/i).fill('wrong-then-correct')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expectVisible(page.getByText(LOGIN_INVALID_CREDENTIALS_PATTERN), 'login 401 alert')
    await page.getByRole('button', { name: /sign in/i }).click()
    await page.waitForURL('**/#/projects')
    diagnostics.interactions.login = '401 alert then authenticated navigation'
    return
  }

  if (testCase.scenario === 'recoverable-error') {
    const contract = SCENARIO_CONTRACTS[`${testCase.routeId}:${testCase.scenario}`]
    const stateRoot = page.locator(contract.root).first()
    const retry = stateRoot.getByRole('button', { name: contract.retry.name, exact: true })
    await expectVisible(retry, `${testCase.routeId} recoverable Retry`, 15_000)
    await retry.click()
    await expectHidden(retry, `${testCase.routeId} recoverable Retry`, 10_000)
    diagnostics.interactions.retry = 'error visible after automatic retries; manual Retry recovered'
    return
  }

  if (testCase.scenario !== 'populated') return

  if (testCase.routeId === 'workflow') {
    await assertEscapeFocusReturn(
      page,
      page.getByRole('button', { name: /add (?:workflow )?node/i }),
      page.getByRole('dialog'),
      'Workflow node builder',
      diagnostics,
    )
    const jobTrigger = page.getByRole('button').filter({ hasText: 'job_browser' }).first()
    await assertEscapeFocusReturn(
      page,
      jobTrigger,
      page.getByRole('dialog'),
      'Workflow job detail',
      diagnostics,
    )
  } else if (testCase.routeId === 'candidates') {
    await exerciseCandidateGrid(page, diagnostics)
  } else if (testCase.routeId === 'results') {
    diagnostics.interactions.resultsSort = await clickAndAssertSort(
      page.locator('[data-slot="data-grid-table"]').first(),
      'Results validation Data Grid',
    )
  } else if (testCase.routeId === 'research') {
    await exerciseResearchGrids(page, diagnostics)
  } else if (testCase.routeId === 'guide') {
    diagnostics.interactions.guideDisclosure =
      await exerciseDisclosure(page, '.guide-page', 'Guide FAQ')
    const guideDialogs = page.getByRole('dialog')
    if ((await guideDialogs.count()) !== 0) {
      throw new Error('Guide unexpectedly exposes a dialog; its stations and FAQ are inline/disclosure-only.')
    }
    diagnostics.gating.push({
      control: 'Guide dialogs',
      selector: '[role="dialog"] (including document portals)',
      reason: 'The Guide has inline workflow stations and accordion disclosures; it defines no dialog trigger.',
    })
  } else if (testCase.routeId === 'faq') {
    diagnostics.interactions.faqDisclosure =
      await exerciseDisclosure(page, '[data-tour-id="faq-content"]', 'FAQ')
  }
}

function assertControlAcceptance(testCase, diagnostics) {
  if (testCase.appearanceId !== 'en-light') {
    return {
      status: 'documented-gating',
      reason: 'Mutation and layer activation use the EN-light fixture case; this localized case receives full focus and state-contract audits without duplicate mutations.',
    }
  }
  if (!['populated', 'auth-retry'].includes(testCase.scenario)) {
    return {
      status: 'route-state-contract',
      contract: `${testCase.routeId}:${testCase.scenario}`,
      reason: 'Non-populated controls are accepted only through their exact route-scoped state contract.',
    }
  }
  const requirements = {
    login: testCase.scenario === 'auth-retry' ? ['login'] : [],
    guide: ['guideDisclosure'],
    experiments: [],
    workflow: [],
    candidates: ['candidateSort', 'candidateSelection', 'candidatePagination'],
    results: ['resultsSort'],
    research: ['researchSort'],
    faq: ['faqDisclosure'],
  }[testCase.routeId]
  if (testCase.routeId === 'experiments') {
    for (const layer of ['Settings', 'Copilot', 'Tour menu', 'Project selector']) {
      if (!diagnostics.overlayMotion?.[layer]) {
        throw new Error(`Experiments did not exercise its required ${layer} control and layer.`)
      }
    }
  } else if (testCase.routeId === 'workflow') {
    for (const layer of ['Workflow node builder', 'Workflow job detail']) {
      if (!diagnostics.overlayMotion?.[layer]) {
        throw new Error(`Workflow did not exercise its required ${layer} control and layer.`)
      }
    }
  } else if (testCase.routeId === 'candidates' && !diagnostics.overlayMotion?.['Candidate Filters']) {
    throw new Error('Candidates did not exercise Filters Escape dismissal and focus return.')
  }
  for (const key of requirements) {
    if (!diagnostics.interactions[key]) {
      if (testCase.routeId === 'login' && testCase.scenario === 'populated') continue
      throw new Error(`${testCase.routeId} did not exercise required enabled control contract ${key}.`)
    }
  }
  return requirements.length === 0 && testCase.routeId === 'login'
    ? {
        status: 'documented-gating',
        reason: 'The populated guest login case audits the complete focus order; credential submission is exercised by the exact auth-retry case.',
      }
    : { status: 'exercised', interactions: requirements, overlays: Object.keys(diagnostics.overlayMotion ?? {}) }
}

async function expectScenarioEvidence(root, evidence, label) {
  const exactTextLocator = root.getByText(evidence.text, { exact: true }).first()
  await expectVisible(exactTextLocator, `${label} exact text "${evidence.text}"`)
  const selectorMatched = await exactTextLocator.evaluate((element, selector) => (
    element.matches(selector) || Boolean(element.closest(selector))
  ), evidence.selector)
  if (!selectorMatched) {
    throw new Error(
      `${label} text "${evidence.text}" was not contained by exact selector ${evidence.selector}.`,
    )
  }
}

async function findContractControl(root, descriptor) {
  if (!descriptor.name) return root.locator(descriptor.selector).first()
  const role = descriptor.selector.startsWith('a') ? 'link' : 'button'
  const control = root.getByRole(role, { name: descriptor.name, exact: true }).first()
  if ((await control.count()) === 0) {
    throw new Error(`Missing exact ${role} contract control "${descriptor.name}".`)
  }
  const selectorMatched = await control.evaluate((element, selector) => (
    element.matches(selector) || Boolean(element.closest(selector))
  ), descriptor.selector)
  if (!selectorMatched) {
    throw new Error(
      `Control "${descriptor.name}" did not match its exact contract selector ${descriptor.selector}.`,
    )
  }
  return control
}

async function assertScenarioState(page, testCase, diagnostics) {
  if (['populated', 'auth-retry', 'loading'].includes(testCase.scenario)) return
  const contract = SCENARIO_CONTRACTS[`${testCase.routeId}:${testCase.scenario}`]
  if (!contract) {
    throw new Error(`${testCase.routeId}:${testCase.scenario} has no route-scoped state contract.`)
  }
  const root = page.locator(contract.root).first()
  await expectVisible(root, `${testCase.routeId} ${testCase.scenario} state root`)
  for (const evidence of contract.evidence ?? []) {
    await expectScenarioEvidence(root, evidence, `${testCase.routeId} ${testCase.scenario}`)
  }
  const controlEvidence = []
  for (const descriptor of contract.controls ?? []) {
    if (descriptor.exercisePending) continue
    const control = await findContractControl(root, descriptor)
    await expectVisible(control, `${testCase.routeId} ${testCase.scenario} control ${descriptor.name ?? descriptor.selector}`)
    const disabled = await control.isDisabled()
    if (disabled !== descriptor.disabled) {
      throw new Error(
        `${descriptor.name ?? descriptor.selector} disabled=${disabled}; `
        + `expected ${descriptor.disabled}: ${descriptor.reason}`,
      )
    }
    controlEvidence.push({ ...descriptor, observedDisabled: disabled })
  }
  for (const descriptor of contract.absentControls ?? []) {
    const role = descriptor.selector.startsWith('a') ? 'link' : 'button'
    const count = descriptor.name
      ? await root.getByRole(role, { name: descriptor.name, exact: true }).count()
      : await root.locator(descriptor.selector).count()
    if (count !== 0) {
      throw new Error(
        `${descriptor.name ?? descriptor.selector} must be absent: ${descriptor.reason}`,
      )
    }
    controlEvidence.push({ ...descriptor, observedAbsent: true })
  }
  diagnostics.state = {
    contract: `${testCase.routeId}:${testCase.scenario}`,
    root: contract.root,
    evidence: contract.evidence ?? [],
    controls: controlEvidence,
  }

  if (testCase.scenario === 'pending') {
    if (testCase.routeId === 'candidates') {
      const table = page.locator('[data-slot="data-grid-table"]').first()
      await table.getByRole('checkbox').nth(1).click()
      const download = page.getByRole('button', { name: /download selected \(1\)/i })
      await download.click()
      if (!(await download.isDisabled())) {
        throw new Error('Candidate download did not enter a disabled pending state.')
      }
      await download.waitFor({ state: 'visible' })
      await page.waitForFunction(
        (button) => button instanceof HTMLButtonElement && !button.disabled,
        await download.elementHandle(),
      )
      diagnostics.state.pendingMutation =
        'candidate mutation disabled while the delayed safe fixture was pending'
      const transientToast = page.locator('[data-sonner-toast]').first()
      if (await transientToast.count()) {
        await transientToast.waitFor({ state: 'hidden', timeout: 5_000 })
      }
      return
    }
  }
}

async function navigateCase(page, testCase, caseDirectory) {
  const url = `${BASE_URL}/#${testCase.routePath}`
  const navigation = page.goto(url, { waitUntil: 'domcontentloaded', timeout: CASE_TIMEOUT_MS })
  if (testCase.scenario === 'loading') {
    const contract = SCENARIO_CONTRACTS[`${testCase.routeId}:loading`]
    const loadingRoot = page.locator(contract.root).first()
    await expectVisible(loadingRoot, `${testCase.routeId} loading state root`, 5_000)
    const skeleton = loadingRoot.locator(contract.loadingSelector).first()
    await expectVisible(skeleton, `${testCase.routeId} layout Skeleton`, 5_000)
    await page.screenshot({
      path: path.join(caseDirectory, `${safeFilePart(testCase.id)}--loading.png`),
      fullPage: true,
    })
  }
  await navigation
  await expectVisible(page.locator(ROUTE_SURFACES[testCase.routeId]).first(), `${testCase.routeId} route surface`)
  if (testCase.scenario === 'loading') {
    const contract = SCENARIO_CONTRACTS[`${testCase.routeId}:loading`]
    const skeleton = page.locator(contract.root).first().locator(contract.loadingSelector).first()
    await expectHidden(skeleton, `${testCase.routeId} layout Skeleton`, 8_000)
  }
}

async function runCase(browser, testCase) {
  const startedAt = new Date().toISOString()
  const caseDirectory = path.join(RUN_DIRECTORY, 'cases', safeFilePart(testCase.id))
  const screenshotDirectory = path.join(RUN_DIRECTORY, 'screenshots')
  const failureDirectory = path.join(RUN_DIRECTORY, 'failures')
  const traceDirectory = path.join(RUN_DIRECTORY, 'traces')
  await Promise.all([
    mkdir(caseDirectory, { recursive: true }),
    mkdir(screenshotDirectory, { recursive: true }),
    mkdir(failureDirectory, { recursive: true }),
    mkdir(traceDirectory, { recursive: true }),
  ])

  const context = await browser.newContext({
    viewport: testCase.viewport,
    locale: testCase.locale,
    timezoneId: testCase.timezoneId,
    colorScheme: testCase.colorScheme,
    reducedMotion: testCase.reducedMotion,
    serviceWorkers: 'block',
    acceptDownloads: true,
  })
  const diagnostics = {
    console: [],
    network: [],
    failures: [],
    gating: [],
    interactions: {},
  }
  let page = null
  let failure = null
  let diagnosticController = null
  const router = createFixtureRouter({
    scenario: testCase.scenario,
    routeId: testCase.routeId,
  })

  try {
    await context.addInitScript(
      storageInitScript,
      createStorageSeed({
        authenticated: testCase.authenticated,
        language: testCase.language,
        themePreference: testCase.themePreference,
        scenario: testCase.scenario,
      }),
    )
    await context.tracing.start({ screenshots: true, snapshots: true, sources: true })
    page = await context.newPage()
    page.setDefaultTimeout(10_000)
    diagnosticController = await installDiagnostics(page, testCase, router, diagnostics)
    await navigateCase(page, testCase, caseDirectory)
    await assertDocumentContract(page, testCase)
    await assertScenarioState(page, testCase, diagnostics)

    const screenshotPath = path.join(screenshotDirectory, `${safeFilePart(testCase.id)}.png`)
    await page.screenshot({ path: screenshotPath, fullPage: true })

    diagnostics.systemTheme = await assertSystemThemeResponse(page, testCase)
    await exerciseGlobalLayers(page, testCase, diagnostics)
    diagnostics.overflow = await assertNoPageOverflow(page)
    diagnostics.reducedMotion = await assertReducedMotion(page)
    diagnostics.touchTargets = await assertMobileTouchTargets(page, testCase)
    diagnostics.focusSequence = await auditKeyboardFocus(page, testCase)
    await exerciseRouteInteractions(page, testCase, diagnostics)
    diagnostics.controlAcceptance = assertControlAcceptance(testCase, diagnostics)
    await diagnosticController.quiesce()

    if (diagnostics.failures.length > 0) {
      throw new Error(diagnostics.failures.join('\n'))
    }
    await context.tracing.stop()
    await writeJson(path.join(caseDirectory, 'diagnostics.json'), {
      case: testCase,
      requestCounts: router.requestCounts(),
      ...diagnostics,
    })
    return {
      id: testCase.id,
      status: 'passed',
      startedAt,
      finishedAt: new Date().toISOString(),
      screenshot: path.relative(RUN_DIRECTORY, screenshotPath),
      requestCounts: router.requestCounts(),
    }
  } catch (error) {
    failure = asError(error)
    await diagnosticController?.quiesce().catch((quiesceError) => {
      diagnostics.failures.push(`Diagnostic quiescence failed: ${asError(quiesceError).message}`)
    })
    if (page) {
      await page.screenshot({
        path: path.join(failureDirectory, `${safeFilePart(testCase.id)}.png`),
        fullPage: true,
      }).catch(() => undefined)
    }
    await context.tracing.stop({
      path: path.join(traceDirectory, `${safeFilePart(testCase.id)}.zip`),
    }).catch(() => undefined)
    await writeJson(path.join(caseDirectory, 'failure.json'), {
      case: testCase,
      error: serializeError(failure),
      requestCounts: router.requestCounts(),
      ...diagnostics,
    })
    return {
      id: testCase.id,
      status: 'failed',
      startedAt,
      finishedAt: new Date().toISOString(),
      error: serializeError(failure),
      failureScreenshot: path.join('failures', `${safeFilePart(testCase.id)}.png`),
      trace: path.join('traces', `${safeFilePart(testCase.id)}.zip`),
      requestCounts: router.requestCounts(),
    }
  } finally {
    await context.close()
  }
}

async function readPackageVersion() {
  const packageJson = JSON.parse(await readFile(path.join(FRONTEND_DIRECTORY, 'package.json'), 'utf8'))
  return packageJson.devDependencies?.playwright ?? packageJson.dependencies?.playwright ?? 'unknown'
}

async function run() {
  if (process.env.BDA_BROWSER_LIST === '1' || process.env.BDA_BROWSER_DRY_RUN === '1') {
    await runDryValidation()
    return
  }

  const distIndex = path.join(FRONTEND_DIRECTORY, 'dist', 'index.html')
  await access(distIndex, fsConstants.R_OK).catch(() => {
    throw new Error(`Production build is missing at ${distIndex}. Run: TMPDIR=/tmp ./node_modules/.bin/vite build`)
  })

  const { chromium } = await import('playwright')
  const executablePath = chromium.executablePath()
  await access(executablePath, fsConstants.X_OK).catch(() => {
    throw new Error(
      `Playwright Chromium is missing or not executable at ${executablePath}.\n`
      + 'Install the exact Playwright 1.62.0 browser with: TMPDIR=/tmp npx playwright install chromium',
    )
  })

  await mkdir(RUN_DIRECTORY, { recursive: true })
  const metadata = {
    runId: RUN_ID,
    startedAt: new Date().toISOString(),
    frontendDirectory: FRONTEND_DIRECTORY,
    repositoryDirectory: REPOSITORY_DIRECTORY,
    baseUrl: BASE_URL,
    filters: describeFilters(),
    fullMatrixCaseCount: matrix.length,
    selectedCaseCount: selectedCases.length,
    playwrightVersion: await readPackageVersion(),
    chromiumExecutable: executablePath,
    cases: selectedCases.map((entry) => ({ ...entry, status: 'planned' })),
  }
  await writeJson(path.join(RUN_DIRECTORY, 'matrix.json'), metadata)

  const preview = await startPreview()
  activeBrowser = await chromium.launch({ headless: true })
  const results = []
  for (let index = 0; index < selectedCases.length; index += 1) {
    const testCase = selectedCases[index]
    console.log(`[${index + 1}/${selectedCases.length}] ${testCase.id}`)
    const result = await runCase(activeBrowser, testCase)
    results.push(result)
    await writeJson(path.join(RUN_DIRECTORY, 'matrix.json'), {
      ...metadata,
      updatedAt: new Date().toISOString(),
      cases: selectedCases.map((entry) => (
        results.find((resultEntry) => resultEntry.id === entry.id) ?? { ...entry, status: 'planned' }
      )),
    })
  }

  const failed = results.filter((entry) => entry.status === 'failed')
  await writeJson(path.join(RUN_DIRECTORY, 'matrix.json'), {
    ...metadata,
    finishedAt: new Date().toISOString(),
    previewOutput: previewTail(preview.output),
    summary: {
      passed: results.length - failed.length,
      failed: failed.length,
      total: results.length,
    },
    cases: results,
  })
  if (failed.length > 0) {
    throw new Error(
      `${failed.length}/${results.length} browser cases failed. `
      + `Targeted rerun: BDA_BROWSER_CASES=${failed.map((entry) => entry.id).join(',')} `
      + `TMPDIR=/tmp node scripts/browser-vertical-slice.mjs\n`
      + `Artifacts: ${RUN_DIRECTORY}`,
    )
  }
  console.log(`Browser matrix passed (${results.length}/${results.length}). Artifacts: ${RUN_DIRECTORY}`)
}

run()
  .catch((error) => {
    console.error(asError(error).stack ?? asError(error).message)
    process.exitCode = 1
  })
  .finally(async () => {
    await cleanup()
  })
