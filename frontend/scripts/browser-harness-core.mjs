const PROJECT_ID = 'proj_browser'
const NOW = '2026-07-29T08:00:00Z'

export const ADD_CANDIDATE_FILTER_PATTERN = /add (?:candidate )?filter/i
export const CANDIDATE_SEARCH_FILTER_PATTERN = /candidate or family/i
export const COPILOT_LAYER_SELECTOR = '[role="dialog"][data-tour-id="copilot-drawer"]'
export const COPILOT_TRIGGER_PATTERN = /^Open Copilot$/
export const LOGIN_INVALID_CREDENTIALS_PATTERN =
  /invalid (?:browser acceptance credentials|credentials|username or password)/i

export const FOCUS_AUDIT_CONTRACTS = Object.freeze({
  login: { root: 'form', maxSteps: 24 },
  guide: { root: '.guide-page main', maxSteps: 96 },
  experiments: { root: 'section', maxSteps: 128 },
  workflow: { root: '[data-tour-id="workflow-page"]', maxSteps: 160 },
  candidates: { root: 'section', maxSteps: 128 },
  results: { root: 'section', maxSteps: 128 },
  research: { root: '[data-tour-id="research-tabs"]', maxSteps: 160 },
  faq: { root: '[data-tour-id="faq-content"]', maxSteps: 96 },
})

const exactText = (selector, text) => ({ selector, text })
const disabledControl = (selector, name, reason) => ({
  selector,
  name,
  disabled: true,
  reason,
})

export const SCENARIO_CONTRACTS = Object.freeze({
  'experiments:empty': {
    root: '[data-tour-id="project-library"]',
    evidence: [exactText('h3', 'No projects yet')],
    controls: [{
      selector: 'button',
      name: 'Create your first project',
      disabled: false,
      reason: 'The empty project library keeps its recovery action enabled.',
    }],
  },
  'experiments:loading': {
    root: 'section',
    loadingSelector: '[data-slot="skeleton"]',
    evidence: [],
  },
  'experiments:recoverable-error': {
    root: 'section',
    retry: { selector: '[data-slot="alert"] button', name: 'Retry' },
    evidence: [exactText('[data-slot="alert"]', 'Retry the deterministic browser fixture.')],
  },
  'experiments:blocked': {
    root: 'section',
    evidence: [exactText('[data-slot="alert"]', 'Target is not ready for workflow execution')],
    controls: [{
      selector: 'a[href="#/research?tab=structures&project=proj_browser"]',
      name: 'Resolve target readiness',
      disabled: false,
      reason: 'Blocked projects route to the exact target-readiness repair surface.',
    }],
  },
  'experiments:read-only': {
    root: 'section',
    evidence: [exactText('[data-slot="alert-title"]', 'Demo mode')],
    controls: [
      disabledControl('#target-chain-selection', null, 'Demo mode locks target preparation inputs.'),
      disabledControl('button', 'Prepare structure', 'Demo mode blocks target preparation mutations.'),
    ],
  },
  'workflow:loading': {
    root: '[data-tour-id="workflow-page"]',
    loadingSelector: '[data-tour-id="workflow-canvas"] [data-slot="skeleton"]',
    evidence: [],
  },
  'workflow:recoverable-error': {
    root: '[data-tour-id="workflow-page"]',
    retry: { selector: '[data-slot="alert"] button', name: 'Retry' },
    evidence: [exactText('[data-slot="alert"]', 'Retry the deterministic browser fixture.')],
  },
  'workflow:blocked': {
    root: '[data-tour-id="workflow-page"]',
    evidence: [exactText('[data-slot="alert"]', 'Target preparation is incomplete')],
    controls: [
      disabledControl('button', 'Add workflow node', 'Target readiness blocks graph mutations.'),
      disabledControl('button', 'Submit workflow', 'Target readiness blocks workflow submission.'),
    ],
  },
  'workflow:pending': {
    root: '[data-tour-id="workflow-page"]',
    evidence: [exactText('p', 'Browser acceptance workflow · running')],
    controls: [],
  },
  'workflow:read-only': {
    root: '[data-tour-id="workflow-page"]',
    evidence: [exactText('p', 'Demo mode: displaying read-only reference project data.')],
    absentControls: [{
      selector: 'button',
      name: 'Add workflow node',
      reason: 'Demo mode replaces the workflow mutation toolbar with a read-only notice.',
    }],
  },
  'candidates:empty': {
    root: 'section',
    evidence: [exactText('td', 'No candidates match the current filters.')],
    controls: [
      disabledControl('button', 'Download selected', 'No candidate selection exists in the empty grid.'),
    ],
  },
  'candidates:loading': {
    root: 'section',
    loadingSelector: '[aria-label="Loading candidates"] [data-slot="skeleton"]',
    evidence: [],
  },
  'candidates:recoverable-error': {
    root: 'section',
    retry: { selector: '[data-slot="alert"] button', name: 'Retry' },
    evidence: [exactText('[data-slot="alert"]', 'Retry the deterministic browser fixture.')],
  },
  'candidates:pending': {
    root: 'section',
    evidence: [exactText('[data-tour-id="candidate-table"]', 'Browser candidate 1')],
    controls: [{
      selector: 'button',
      name: 'Download selected (1)',
      disabled: true,
      reason: 'The selected-candidate download stays disabled while its fixture mutation is pending.',
      exercisePending: true,
    }],
  },
  'results:empty': {
    root: 'section',
    evidence: [
      exactText('[data-tour-id="results-validation"]', 'No experiment results uploaded yet.'),
      exactText('[data-tour-id="results-delivery"]', 'No delivery package has been generated from verified project artifacts yet.'),
    ],
    controls: [
      disabledControl('button', 'Prepare delivery package', 'No delivery package exists in the empty result state.'),
    ],
  },
  'results:loading': {
    root: '[data-tour-id="results-validation"]',
    loadingSelector: '[data-slot="skeleton"]',
    evidence: [],
  },
  'results:recoverable-error': {
    root: '[data-tour-id="results-validation"]',
    retry: { selector: '[data-slot="alert"] button', name: 'Retry' },
    evidence: [exactText('[data-slot="alert"]', 'Retry the deterministic browser fixture.')],
  },
  'results:pending': {
    root: 'section',
    evidence: [exactText('[data-tour-id="results-delivery"]', 'building')],
    controls: [
      disabledControl('button', 'Prepare delivery package', 'A building delivery package is not downloadable yet.'),
    ],
  },
  'research:empty': {
    root: '[data-tour-id="research-workspace"]',
    evidence: [exactText('[data-slot="alert"]', 'No review document or project notes are available yet.')],
    controls: [],
  },
  'research:loading': {
    root: '[data-tour-id="research-workspace"]',
    loadingSelector: '[data-slot="skeleton"]',
    evidence: [],
  },
  'research:recoverable-error': {
    root: '[data-tour-id="research-tabs"]',
    retry: { selector: '[data-slot="alert"] button', name: 'Retry' },
    evidence: [exactText('[data-slot="alert"]', 'The research workspace could not be loaded from the backend.')],
  },
  'research:pending': {
    root: '[data-tour-id="research-workspace"]',
    evidence: [exactText('[data-slot="badge"]', 'Pending review')],
    controls: [],
  },
  'research:read-only': {
    root: '[data-tour-id="research-workspace"]',
    evidence: [exactText('[data-slot="badge"]', 'Accepted')],
    controls: [
      disabledControl('button', 'Add finding/source', 'Viewer demo mode blocks research-note mutations.'),
    ],
  },
})

export const POLLING_CONTRACTS = Object.freeze({
  'workflow:pending': {
    signature: 'GET /api/v2/workflow-runs/run_browser/graph',
    minimumCount: 2,
  },
})

export const ROUTES = Object.freeze([
  { id: 'login', path: '/login', authenticated: false },
  { id: 'guide', path: '/guide', authenticated: false },
  // The project library moved to /projects; /experiments still redirects there,
  // but the harness asserts on the resulting URL so it navigates to the
  // canonical route rather than through the alias.
  { id: 'experiments', path: `/projects?project=${PROJECT_ID}`, authenticated: true },
  { id: 'workflow', path: `/workflow?project=${PROJECT_ID}`, authenticated: true },
  { id: 'candidates', path: `/candidates?project=${PROJECT_ID}`, authenticated: true },
  { id: 'results', path: `/results?project=${PROJECT_ID}`, authenticated: true },
  { id: 'research', path: `/research?tab=evidence&project=${PROJECT_ID}`, authenticated: true },
  { id: 'faq', path: `/faq?project=${PROJECT_ID}`, authenticated: true },
])

export const VIEWPORTS = Object.freeze([
  { id: 'desktop', width: 1440, height: 900 },
  { id: 'mobile', width: 390, height: 844 },
])

export const APPEARANCES = Object.freeze([
  {
    id: 'en-light',
    language: 'en',
    locale: 'en-US',
    themePreference: 'light',
    colorScheme: 'light',
  },
  {
    id: 'zh-dark',
    language: 'zh',
    locale: 'zh-CN',
    themePreference: 'dark',
    colorScheme: 'dark',
  },
  {
    id: 'system-dark',
    language: 'en',
    locale: 'en-US',
    themePreference: 'system',
    colorScheme: 'dark',
  },
  {
    id: 'system-light',
    language: 'en',
    locale: 'en-US',
    themePreference: 'system',
    colorScheme: 'light',
  },
])

const ROUTE_STATE_SCENARIOS = Object.freeze({
  login: ['auth-retry'],
  guide: [],
  experiments: ['empty', 'loading', 'recoverable-error', 'blocked', 'read-only'],
  workflow: ['loading', 'recoverable-error', 'blocked', 'pending', 'read-only'],
  candidates: ['empty', 'loading', 'recoverable-error', 'pending'],
  results: ['empty', 'loading', 'recoverable-error', 'pending'],
  research: ['empty', 'loading', 'recoverable-error', 'pending', 'read-only'],
  faq: [],
})

export function buildBrowserMatrix() {
  const matrix = []
  for (const appearance of APPEARANCES) {
    for (const viewport of VIEWPORTS) {
      for (const route of ROUTES) {
        matrix.push(createCase(route, viewport, appearance, 'populated'))
      }
    }
  }

  const stateAppearance = APPEARANCES.find((appearance) => appearance.id === 'en-light')
  for (const scenario of [
    'auth-retry',
    'empty',
    'loading',
    'recoverable-error',
    'blocked',
    'pending',
    'read-only',
  ]) {
    for (const viewport of VIEWPORTS) {
      for (const route of ROUTES) {
        if (!ROUTE_STATE_SCENARIOS[route.id].includes(scenario)) continue
        matrix.push(createCase(route, viewport, stateAppearance, scenario))
      }
    }
  }
  return matrix
}

function createCase(route, viewport, appearance, scenario) {
  return {
    id: [route.id, viewport.id, appearance.id, scenario].join('__'),
    routeId: route.id,
    routePath: route.path,
    authenticated: route.authenticated,
    viewportId: viewport.id,
    viewport: { width: viewport.width, height: viewport.height },
    appearanceId: appearance.id,
    language: appearance.language,
    locale: appearance.locale,
    themePreference: appearance.themePreference,
    colorScheme: appearance.colorScheme,
    reducedMotion: 'reduce',
    scenario,
    timezoneId: 'UTC',
  }
}

function splitFilter(value) {
  return value
    .split(',')
    .map((entry) => entry.trim())
    .filter(Boolean)
}

function assertKnownFilter(label, requested, known) {
  for (const value of requested) {
    if (!known.has(value)) {
      throw new Error(`Unknown ${label} value "${value}". Expected one of: ${[...known].join(', ')}`)
    }
  }
}

export function selectCasesFromEnv(matrix, env = process.env) {
  const filters = [
    ['BDA_BROWSER_ROUTES', 'routeId'],
    ['BDA_BROWSER_VIEWPORTS', 'viewportId'],
    ['BDA_BROWSER_APPEARANCES', 'appearanceId'],
    ['BDA_BROWSER_STATES', 'scenario'],
    ['BDA_BROWSER_CASES', 'id'],
  ]

  let selected = matrix
  for (const [environmentKey, property] of filters) {
    const raw = env[environmentKey]
    if (!raw) continue
    const requested = splitFilter(raw)
    const known = new Set(matrix.map((entry) => entry[property]))
    assertKnownFilter(environmentKey, requested, known)
    const requestedSet = new Set(requested)
    selected = selected.filter((entry) => requestedSet.has(entry[property]))
  }

  if (selected.length === 0) {
    throw new Error('Browser rerun filters selected zero cases.')
  }
  return selected
}

export function validatePort(rawPort) {
  if (!/^\d+$/.test(String(rawPort))) {
    throw new Error(`BDA_BROWSER_SMOKE_PORT must be an integer; received "${rawPort}".`)
  }
  const port = Number(rawPort)
  if (!Number.isSafeInteger(port) || port < 1024 || port > 65535) {
    throw new Error(`BDA_BROWSER_SMOKE_PORT must be between 1024 and 65535; received "${rawPort}".`)
  }
  return port
}

export function isHiddenControlProxy({ tag, ariaHidden, tabIndex }) {
  return tag === 'input' && ariaHidden === 'true' && tabIndex === -1
}

export function didSortTransition({ beforeSort, afterSort, beforeRows, afterRows }) {
  return (
    beforeSort !== afterSort
    && JSON.stringify(beforeRows) !== JSON.stringify(afterRows)
  )
}

export function canonicalHashRoute(rawHash) {
  const route = String(rawHash).startsWith('#') ? String(rawHash).slice(1) : String(rawHash)
  return canonicalRequestSignature('GET', route).slice(4)
}

export function parseResourceConsoleFailure({ text, location }) {
  if (!String(text).startsWith('Failed to load resource:')) return null
  const match = String(text).match(/\bstatus of (\d{3})\b/i)
  const url = location?.url
  if (!match || !url) return null
  return { url: String(url), status: Number(match[1]) }
}

export function reconcileResourceConsoleFailures(expectedTokens, resourceErrors) {
  const remaining = new Map()
  for (const token of expectedTokens) {
    const key = `${token.url} ${token.status}`
    const entries = remaining.get(key) ?? []
    entries.push(token)
    remaining.set(key, entries)
  }
  const expected = []
  const unexpected = []
  for (const entry of resourceErrors) {
    const key = `${entry.url} ${entry.status}`
    const tokens = remaining.get(key)
    if (tokens?.length) {
      tokens.shift()
      expected.push(entry)
    } else {
      unexpected.push(entry)
    }
  }
  return {
    expected,
    unexpected,
    unconsumed: [...remaining.values()].flat(),
  }
}

export function createSerialTaskQueue() {
  let tail = Promise.resolve()
  const errors = []
  return {
    enqueue(task) {
      const result = tail.then(task)
      tail = result.catch((error) => {
        errors.push(error)
      })
      return tail
    },
    async flush() {
      await tail
      if (errors.length) {
        throw new AggregateError(errors.splice(0), 'Queued diagnostic write failed.')
      }
    },
  }
}

export function createProcessCloseMonitor(child) {
  let closed = child.browserHarnessClosed === true
  const closePromise = closed
    ? Promise.resolve()
    : new Promise((resolve) => {
        child.once('close', () => {
          closed = true
          resolve()
        })
      })
  return {
    async wait(timeoutMs) {
      if (closed) return true
      return Promise.race([
        closePromise.then(() => true),
        new Promise((resolve) => setTimeout(() => resolve(false), timeoutMs)),
      ])
    },
  }
}

export function createStorageSeed({ authenticated, language, themePreference, scenario = 'populated' }) {
  const session = {
    'bda-research-package-sync-attempted': 'true',
  }
  if (authenticated) {
    session.bda_token = 'browser-acceptance-token'
    session.bda_user = JSON.stringify({
      id: 'user_browser',
      username: 'browser.qa',
      display_name: 'Browser QA',
      organization_id: 'org_browser',
    })
  }

  const state = {
    activeProjectId: authenticated ? PROJECT_ID : '',
    appMode: scenario === 'read-only' ? 'demo' : 'application',
    language,
    uiDensity: 'guided',
    themePreference,
    copilotMessages: [],
    copilotSessions: {},
    copilotOpen: false,
    settingsOpen: false,
    copilotWidth: 380,
    targetIntakeOpen: false,
    tourState: {
      status: 'idle',
      sectionId: 'projects',
      stepId: 'projects-welcome',
      completedSections: [],
      updatedAt: null,
    },
    tourMenuOpen: false,
  }

  return {
    session,
    local: {
      'bda-app-store': JSON.stringify({ state, version: 0 }),
      bda_intro_dismissed: 'true',
    },
  }
}

export function canonicalRequestSignature(method, rawUrl) {
  const url = new URL(rawUrl, 'http://browser.invalid')
  const sorted = [...url.searchParams.entries()].sort(([leftKey, leftValue], [rightKey, rightValue]) => {
    const keyOrder = leftKey.localeCompare(rightKey)
    return keyOrder || leftValue.localeCompare(rightValue)
  })
  const query = new URLSearchParams()
  for (const [key, value] of sorted) query.append(key, value)
  const serialized = query.toString()
  return `${String(method).toUpperCase()} ${url.pathname}${serialized ? `?${serialized}` : ''}`
}

function localized(en, zh) {
  return { default: en, en, zh }
}

function projectFixture(scenario) {
  return {
    id: PROJECT_ID,
    legacy_id: null,
    organization_id: 'org_browser',
    owner_id: 'user_browser',
    name: 'Sweet Protein Browser Acceptance',
    project_type: 'sweet_protein_design',
    status: scenario === 'read-only' ? 'archived' : 'active',
    source_package_id: 'package_browser',
    source_project_key: 'PD1',
    summary: 'Deterministic browser acceptance project for scientific UI verification.',
    localized_content: {
      name: localized('Sweet Protein Browser Acceptance', '甜味蛋白浏览器验收'),
      summary: localized(
        'Deterministic browser acceptance project for scientific UI verification.',
        '用于科研界面验证的确定性浏览器验收项目。',
      ),
    },
    primary_target_id: scenario === 'blocked' ? null : 'target_browser',
    version: 7,
    created_at: NOW,
    updated_at: NOW,
  }
}

function readinessFixture(scenario) {
  if (scenario === 'blocked') {
    return {
      stage: 'identity_confirmation',
      ready_for_workflow: false,
      blockers: ['target_identity_confirmation_required'],
      next_action: 'Confirm target identity',
      target_id: null,
      structure_artifact_id: null,
      identity_status: null,
      structure_status: null,
    }
  }
  return {
    stage: 'approved',
    ready_for_workflow: true,
    blockers: [],
    next_action: 'Plan the workflow',
    target_id: 'target_browser',
    structure_artifact_id: null,
    identity_status: 'confirmed',
    structure_status: 'approved',
  }
}

function workflowRunFixture(scenario) {
  return {
    id: 'run_browser',
    project_id: PROJECT_ID,
    name: 'Browser acceptance workflow',
    status: scenario === 'read-only' ? 'succeeded' : scenario === 'pending' ? 'running' : 'draft',
    graph: { nodes: [], edges: [], layout: {} },
    version: 3,
    created_by: 'user_browser',
    created_at: NOW,
    updated_at: NOW,
  }
}

function workflowNodeFixture(scenario) {
  return {
    id: 'node_browser',
    workflow_run_id: 'run_browser',
    node_key: 'score-candidates',
    node_type: 'scoring',
    model_plugin: 'browser-scoring-model',
    model_plugin_id: 'model_browser',
    container_image: 'browser.invalid/scoring:1',
    command: 'score --input candidates.json',
    queue: 'cpu',
    status: scenario === 'pending' ? 'running' : 'draft',
    parameters: { threshold: 0.7 },
    error_message: null,
    position: { x: 80, y: 120 },
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function candidateFixture(id, rank, overrides = {}) {
  return {
    id,
    project_id: PROJECT_ID,
    candidate_key: `BROWSER-${rank.toString().padStart(3, '0')}`,
    name: overrides.name ?? `Browser candidate ${rank}`,
    candidate_kind: 'design_candidate',
    status: overrides.status ?? 'generated',
    rank,
    score: overrides.score ?? 90 - rank,
    scores: {
      interface_score: overrides.score ?? 90 - rank,
      design_score: 84 - rank,
      plddt: 76 + rank,
      solubility_score: 0.72 + rank / 100,
    },
    properties: {
      family: overrides.family ?? 'sweet-protein',
      pred_kd: `${rank * 10} nM`,
      decision: overrides.decision ?? (rank === 2 ? 'Anchor' : 'Review'),
      next_action: 'Review evidence before ordering.',
    },
    structure_artifact_id: null,
    complex_artifact_id: null,
    source_job_id: null,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function experimentResultFixture(id, value, passStatus) {
  return {
    id,
    project_id: PROJECT_ID,
    candidate_id: id === 'result_browser_1' ? 'candidate_browser_1' : 'candidate_browser_2',
    candidate_ref: id === 'result_browser_1' ? 'BROWSER-001' : 'BROWSER-002',
    source_artifact_id: null,
    batch_key: 'batch-browser',
    experiment_type: 'binding_affinity',
    pass_status: passStatus,
    value,
    unit: 'nM',
    conclusion: passStatus === 'pass' ? 'Meets the acceptance threshold.' : 'Requires review.',
    failure_reason: null,
    result_metadata: { replicate_count: 3 },
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function researchWorkspaceFixture(scenario) {
  const empty = scenario === 'empty'
  return {
    project: {
      id: PROJECT_ID,
      name: localized('Sweet Protein Evidence Workspace', '甜味蛋白证据工作区'),
      summary: localized(
        'Bilingual evidence, target, and dataset acceptance fixtures.',
        '双语证据、靶点与数据集验收夹具。',
      ),
      project_type: 'sweet_protein_design',
      source_project_key: 'PD1',
      source_package_id: 'package_browser',
      package: { version: '2.0', as_of: '2026-07-29' },
    },
    review_document: empty
      ? null
      : {
          id: 'review_browser',
          title: localized('Evidence review', '证据审阅'),
          content: localized(
            'The candidate hypothesis is supported by curated evidence.',
            '候选假设得到已整理证据的支持。',
          ),
          status: scenario === 'read-only'
            ? 'accepted'
            : scenario === 'pending'
              ? 'pending_review'
              : 'active',
          version: 1,
          updated_at: NOW,
        },
    review_sections: [],
    graph_nodes: empty
      ? []
      : [{
          id: 'node_browser_1',
          kind: 'target',
          label: localized('Sweet receptor target', '甜味受体靶点'),
          description: localized('Primary evidence node', '主要证据节点'),
          reference_ids: ['REF-BROWSER-1'],
          review_status: scenario === 'pending' ? 'pending_review' : 'accepted',
        }],
    graph_edges: empty
      ? []
      : [{
          id: 'edge_browser_1',
          source: 'node_browser_1',
          target: 'node_browser_2',
          source_label: localized('Sweet receptor target', '甜味受体靶点'),
          target_label: localized('Binding response', '结合响应'),
          predicate: 'supports',
          summary: localized('Curated binding evidence', '已整理的结合证据'),
          context: localized('Acceptance fixture', '验收夹具'),
          assertion: 'established_fact',
          evidence_grade: 'A',
          reference_ids: ['REF-BROWSER-1'],
          source_urls: ['https://example.test/evidence'],
          review_status: scenario === 'pending' ? 'pending_review' : 'accepted',
        }],
    references: empty
      ? []
      : [{
          document_id: 'document_browser_1',
          ref_id: 'REF-BROWSER-1',
          title: localized('Browser evidence paper', '浏览器证据论文'),
          authors: 'Ada Browser; Lin Evidence',
          doi: '10.1000/browser',
          status: 'ready',
          verification_status: 'verified',
          url: 'https://example.test/evidence',
        }],
    structures: [],
    research_targets: empty
      ? []
      : [
          {
            id: 'research_target_browser_1',
            candidate_key: 'RT-01',
            name: localized('High-priority target', '高优先级靶点'),
            pain_group: localized('Metabolic', '代谢'),
            protein_type: localized('Receptor', '受体'),
            localization: localized('Membrane', '细胞膜'),
            axis: localized('Taste signaling', '味觉信号'),
            score: 93,
            rank: 1,
            scores: {
              evidence: 94,
              novelty: 84,
              tractability: 78,
              human: 88,
              specificity: 81,
              safety: 76,
            },
            properties: { bibliometrics: { historical_count: 34, recent_5y_count: 12 } },
            reference_ids: ['REF-BROWSER-1'],
          },
          {
            id: 'research_target_browser_2',
            candidate_key: 'RT-02',
            name: localized('Secondary target', '次要靶点'),
            pain_group: localized('Sensory', '感觉'),
            protein_type: localized('Channel', '通道'),
            localization: localized('Membrane', '细胞膜'),
            axis: localized('Signal modulation', '信号调节'),
            score: 72,
            rank: 2,
            scores: { evidence: 70, novelty: 77, tractability: 68, human: 73, specificity: 69, safety: 82 },
            properties: { bibliometrics: { historical_count: 18, recent_5y_count: 6 } },
            reference_ids: ['REF-BROWSER-1'],
          },
        ],
    datasets: empty
      ? []
      : [{
          id: 'dataset_browser',
          key: 'browser-targets',
          title: localized('Browser target dataset', '浏览器靶点数据集'),
          content: localized('Deterministic target measurements', '确定性靶点测量'),
          data: [
            { target: 'RT-01', score: 93, reviewed: true },
            { target: 'RT-02', score: 72, reviewed: false },
          ],
          display_data: [
            { target: localized('High-priority target', '高优先级靶点'), score: 93, reviewed: true },
            { target: localized('Secondary target', '次要靶点'), score: 72, reviewed: false },
          ],
          version: 1,
        }],
    methods: empty
      ? []
      : [{
          id: 'method_browser',
          key: 'curated-review',
          title: localized('Curated evidence review', '整理证据审阅'),
          content: localized('Manual review with provenance checks.', '带来源检查的人工审阅。'),
          data: null,
          version: 1,
        }],
    counts: empty ? {} : { references: 1, research_targets: 2, datasets: 1 },
  }
}

function computeNodeFixture() {
  return {
    id: 'compute_browser',
    server_id: null,
    name: 'Browser CPU worker',
    backend: 'local',
    queue: 'cpu',
    labels: { resource_type: 'cpu' },
    enabled: true,
    health_status: 'healthy',
    health_checked_at: NOW,
    health_error: null,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function modelPluginFixture() {
  return {
    id: 'model_browser',
    plugin_key: 'browser-scoring',
    plugin_version: '1.0.0',
    name: 'Browser scoring model',
    container_image: 'browser.invalid/scoring:1',
    command: 'score',
    parameter_schema: { type: 'object', properties: {} },
    output_schema: { type: 'object', properties: {} },
    enabled: true,
    validation_status: 'valid',
    validated_at: NOW,
    validation_errors: [],
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function methodPluginFixture() {
  return {
    id: 'method_browser',
    plugin_key: 'browser-method',
    name: 'Browser method',
    specification: { method_type: 'scoring' },
    enabled: true,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function jobFixture(scenario) {
  return {
    id: 'job_browser',
    submission_id: 'submission_browser',
    workflow_run_id: 'run_browser',
    workflow_node_id: 'node_browser',
    project_id: PROJECT_ID,
    status: scenario === 'pending' ? 'running' : 'succeeded',
    compute_backend: 'lsf',
    model_plugin: 'browser-scoring-model',
    attempt_number: 1,
    external_id: '12345',
    next_poll_at: scenario === 'pending' ? '2026-07-29T08:01:00Z' : null,
    timeout_at: null,
    error_code: null,
    error_message: null,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }
}

function routeResponse(status, body, options = {}) {
  return {
    status,
    body,
    headers: options.headers ?? {},
    delayMs: options.delayMs ?? 0,
    expectedHttpFailure: options.expectedHttpFailure ?? false,
  }
}

const LOADING_PATH_BY_ROUTE = Object.freeze({
  experiments: `/api/v2/projects/${PROJECT_ID}/overview`,
  workflow: `/api/v2/workflow-runs/run_browser/graph`,
  candidates: `/api/v2/projects/${PROJECT_ID}/candidates`,
  results: `/api/v2/projects/${PROJECT_ID}/experiment-results`,
  research: `/api/v2/projects/${PROJECT_ID}/research-workspace`,
})

function strictRoute(method, path, query, resolver) {
  const queryString = new URLSearchParams(
    Object.entries(query ?? {}).filter(([, value]) => value !== undefined),
  )
  const signature = canonicalRequestSignature(method, `${path}${queryString.size ? `?${queryString}` : ''}`)
  return { signature, resolver }
}

function createStrictRoutes({ scenario, routeId }) {
  const project = projectFixture(scenario)
  const readiness = readinessFixture(scenario)
  const workflowRun = workflowRunFixture(scenario)
  const workflowNode = workflowNodeFixture(scenario)
  const empty = scenario === 'empty'
  const routes = []
  const add = (method, path, query, resolver) => {
    routes.push(strictRoute(method, path, query, resolver))
  }
  const ok = (body, options) => routeResponse(200, body, options)

  add('GET', '/api/v2/health/ready', {}, () => ok({
    status: 'ok',
    service: 'bda-v2',
    checks: { postgresql: 'ok', redis: 'ok', object_storage: 'ok' },
  }))
  add('GET', '/api/v2/research-packages', {}, () => ok([{
    package_id: 'pd1-demo-v1',
    version: '1.0.0',
    display_name: localized('PD-1 synthetic demonstration', 'PD-1 合成演示'),
    license: 'CC BY 4.0',
    checksum: 'a'.repeat(64),
    size: 4096,
    installed: true,
  }]))
  add('GET', '/api/v2/projects', { limit: '200' }, () => ok({
    items: empty && routeId === 'experiments' ? [] : [project],
    next_cursor: null,
  }))
  add('GET', '/api/v2/projects/library', { limit: '200' }, () => ok({
    items: empty
      ? []
      : [{
          ...project,
          research_candidate_count: 2,
          finding_count: 1,
          reference_count: 1,
          knowledge_count: 1,
          structure_count: 0,
          primary_structure_ready: scenario !== 'blocked',
          package_version: '2.0',
          evidence_as_of: '2026-07-29',
        }],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/overview`, {}, () => ok({
    project,
    funnel: empty
      ? { generated: 0, designed: 0, folded: 0, scored: 0, ordered: 0 }
      : { generated: 4, designed: 3, folded: 2, scored: 2, ordered: 1 },
    candidate_count: empty ? 0 : 4,
    experiment_result_count: empty ? 0 : 2,
    available_artifact_count: empty ? 0 : 1,
    active_job_count: scenario === 'pending' ? 1 : 0,
    latest_workflow_id: empty ? null : workflowRun.id,
    target_readiness: readiness,
    next_action: readiness.next_action,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/target-readiness`, {}, () => ok(readiness))
  add('GET', `/api/v2/projects/${PROJECT_ID}/primary-target`, {}, () => {
    if (scenario === 'blocked') {
      return routeResponse(404, { detail: 'Project has no primary target' }, { expectedHttpFailure: true })
    }
    return ok({
      id: 'target_browser',
      project_id: PROJECT_ID,
      name: 'Sweet receptor target',
      sequence: null,
      uniprot_accession: 'P01234',
      organism: 'Homo sapiens',
      structure_artifact_id: null,
      structure_status: 'approved',
      identity_status: 'confirmed',
      version: 2,
      created_at: NOW,
      updated_at: NOW,
    })
  })
  add('GET', '/api/v2/targets/target_browser/structure', {}, () => ok({
    target_id: 'target_browser',
    structure_status: 'approved',
    current_artifact_id: null,
    approved_revision_id: null,
    latest_revision: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/research-summary`, {}, () => ok({
    brief: null,
    findings: [],
    literature_document_count: empty ? 0 : 1,
    intelligence_run_count: scenario === 'pending' ? 1 : 0,
    knowledge_entry_count: empty ? 0 : 1,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/research-workspace`, {}, () =>
    ok(researchWorkspaceFixture(scenario)))
  add('GET', `/api/v2/projects/${PROJECT_ID}/workflow-runs`, { limit: '200' }, () => ok({
    items: empty ? [] : [workflowRun],
    next_cursor: null,
  }))
  add('GET', `/api/v2/workflow-runs/${workflowRun.id}/graph`, {}, () => ok({
    workflow: workflowRun,
    nodes: empty ? [] : [workflowNode],
    edges: [],
    layout: {},
  }))
  add('GET', `/api/v2/workflow-runs/${workflowRun.id}/preflight`, {}, () => ok({
    workflow_run_id: workflowRun.id,
    allowed: scenario !== 'blocked' && scenario !== 'read-only',
    blockers: scenario === 'blocked'
      ? [{ code: 'target_not_ready', message: 'Target readiness is not approved.' }]
      : [],
    warnings: scenario === 'read-only'
      ? [{ code: 'read_only', message: 'Completed workflows are read-only.' }]
      : [],
    checks: { target_ready: scenario !== 'blocked' },
  }))
  add('GET', `/api/v2/workflow-runs/${workflowRun.id}/jobs`, {}, () => ok({
    items: empty ? [] : [jobFixture(scenario)],
    next_cursor: null,
  }))
  add('GET', `/api/v2/jobs/job_browser`, {}, () => ok(jobFixture(scenario)))
  add('GET', '/api/v2/jobs/job_browser/logs', { limit: '200' }, () => ok({
    items: [
      { id: 'log_1', job_id: 'job_browser', level: 'info', message: 'Browser job started.', created_at: NOW },
      { id: 'log_2', job_id: 'job_browser', level: 'info', message: 'Browser job completed.', created_at: NOW },
    ],
    next_cursor: null,
  }))
  // The top bar's activity indicator asks on every page, so this one is not optional:
  // without it every case fails on an unhandled request rather than on a defect.
  add('GET', '/api/v2/operations', { limit: '20', mine: 'true' }, () => ok({
    items: empty
      ? []
      : [
          {
            id: 'operation_browser_1',
            project_id: PROJECT_ID,
            organization_id: null,
            kind: 'literature.search',
            resource_type: 'project',
            resource_id: PROJECT_ID,
            status: 'succeeded',
            progress: {},
            result: {},
            error_code: null,
            error_message: null,
            version: 2,
            created_at: NOW,
            updated_at: NOW,
            started_at: NOW,
            finished_at: NOW,
          },
        ],
    next_cursor: null,
  }))
  // The goal tree is fetched only when an attach menu is opened, so most cases never
  // ask for it. Stubbed anyway: the harness is an allowlist, and a case that does open
  // one must not fail for want of a route.
  add('GET', `/api/v2/projects/${PROJECT_ID}/research-goals`, {}, () => ok({
    items: empty
      ? []
      : [
          {
            id: 'goal_browser_1',
            project_id: PROJECT_ID,
            parent_id: null,
            title: 'Does the designed binder hold at bench concentrations?',
            detail: '',
            status: 'open',
            sort_order: 0,
            tags: [],
            links: [],
            version: 1,
            created_at: NOW,
            updated_at: NOW,
          },
        ],
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/candidate-funnel`, {}, () => ok(
    empty
      ? { generated: 0, designed: 0, folded: 0, scored: 0, ordered: 0 }
      : { generated: 4, designed: 3, folded: 2, scored: 2, ordered: 1 },
  ))
  add('GET', `/api/v2/projects/${PROJECT_ID}/candidates`, { limit: '100' }, () => ok({
    items: empty
      ? []
      : Array.from({ length: 6 }, (_, index) => {
          const rank = index + 1
          return candidateFixture(`candidate_browser_${rank}`, rank, {
            score: 94 - rank,
            status: rank % 2 === 0 ? 'Validated' : 'Reserve',
          })
        }),
    next_cursor: empty ? null : 'candidate-page-2',
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/candidates`, {
    cursor: 'candidate-page-2',
    limit: '100',
  }, () => ok({
    items: Array.from({ length: 6 }, (_, index) => {
      const rank = index + 7
      return candidateFixture(`candidate_browser_${rank}`, rank, {
        score: 94 - rank,
        family: rank === 12 ? 'later-page-family' : 'sweet-protein',
        status: rank % 2 === 0 ? 'Validated' : 'Reserve',
      })
    }),
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/candidates`, { limit: '50' }, () => ok({
    items: empty
      ? []
      : Array.from({ length: 6 }, (_, index) => {
          const rank = index + 1
          return candidateFixture(`candidate_browser_${rank}`, rank, {
            score: 94 - rank,
            status: rank % 2 === 0 ? 'Validated' : 'Reserve',
          })
        }),
    next_cursor: empty ? null : 'candidate-page-2',
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/candidates`, {
    cursor: 'candidate-page-2',
    limit: '50',
  }, () => ok({
    items: Array.from({ length: 6 }, (_, index) => {
      const rank = index + 7
      return candidateFixture(`candidate_browser_${rank}`, rank, {
        score: 94 - rank,
        family: rank === 12 ? 'later-page-family' : 'sweet-protein',
        status: rank % 2 === 0 ? 'Validated' : 'Reserve',
      })
    }),
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/experiment-results`, { limit: '200' }, () => ok({
    items: empty
      ? []
      : [
          experimentResultFixture('result_browser_1', 18, 'pass'),
          experimentResultFixture('result_browser_2', 64, 'review'),
        ],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/result-summary`, {}, () => ok({
    project_id: PROJECT_ID,
    candidate_count: empty ? 0 : 4,
    experiment_result_count: empty ? 0 : 2,
    available_artifact_count: empty ? 0 : 1,
    tested_candidate_count: empty ? 0 : 2,
    passed_result_count: empty ? 0 : 1,
    failed_result_count: 0,
    unknown_result_count: empty ? 0 : 1,
    pass_rate: empty ? null : 0.5,
    top_candidate_ids: empty ? [] : ['candidate_browser_1', 'candidate_browser_2'],
    best_result_id: empty ? null : 'result_browser_1',
    best_result_value: empty ? null : 18,
    best_result_unit: empty ? null : 'nM',
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/delivery-packages`, { limit: '1' }, () => ok({
    items: empty
      ? []
      : [{
          id: 'delivery_browser',
          project_id: PROJECT_ID,
          name: 'Browser delivery package',
          status: scenario === 'pending' ? 'building' : 'ready',
          selection: { candidate_ids: ['candidate_browser_1'], include_experiment_results: true },
          artifact_id: null,
          error: null,
          version: 1,
          created_at: NOW,
          updated_at: NOW,
        }],
    next_cursor: null,
  }))
  add('GET', '/api/v2/artifacts', { limit: '200', project_id: PROJECT_ID }, () => ok({
    items: [],
    next_cursor: null,
  }))
  add('GET', '/api/v2/registry/model-plugins', { limit: '200' }, () => ok({
    items: empty ? [] : [modelPluginFixture()],
    next_cursor: null,
  }))
  add('GET', '/api/v2/registry/method-plugins', { limit: '200' }, () => ok({
    items: empty ? [] : [methodPluginFixture()],
    next_cursor: null,
  }))
  add('GET', '/api/v2/registry/compute-nodes', { limit: '200' }, () => ok({
    items: empty ? [] : [computeNodeFixture()],
    next_cursor: null,
  }))
  add('GET', '/api/v2/registry/script-assets', { limit: '200' }, () => ok({
    items: [],
    next_cursor: null,
  }))
  add('GET', `/api/v2/copilot/projects/${PROJECT_ID}/config`, {}, () => ok({
    project_id: PROJECT_ID,
    llm_provider_id: null,
    api_key_configured: false,
    version: 1,
    llm_api_base: '',
    llm_model: '',
    system_prompt: 'Browser acceptance fixture',
    settings: { llm_api_base: '', llm_model: '', system_prompt: 'Browser acceptance fixture' },
    enabled_skills: [],
  }))
  add('GET', '/api/v2/compute-drafts', { limit: '200', project_id: PROJECT_ID }, () => ok({
    items: scenario === 'pending'
      ? [{ id: 'draft_browser', status: 'pending', project_id: PROJECT_ID, created_at: NOW }]
      : [],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/knowledge`, { limit: '100' }, () => ok({
    items: empty
      ? []
      : [{
          id: 'knowledge_browser',
          project_id: PROJECT_ID,
          entry_type: 'evidence',
          title: 'Browser knowledge',
          content: 'Deterministic knowledge fixture.',
          status: scenario === 'read-only' ? 'accepted' : 'pending_review',
          version: 1,
          created_at: NOW,
          updated_at: NOW,
        }],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/literature/claims`, { limit: '100' }, () => ok({
    items: [],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/literature/relations`, { limit: '100' }, () => ok({
    items: [],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/campaigns`, { limit: '100' }, () => ok({
    items: [],
    next_cursor: null,
  }))
  add('GET', `/api/v2/projects/${PROJECT_ID}/intelligence-runs`, { limit: '100' }, () => ok({
    items: scenario === 'pending'
      ? [{ id: 'intelligence_browser', project_id: PROJECT_ID, status: 'running', created_at: NOW, updated_at: NOW }]
      : [],
    next_cursor: null,
  }))

  add('POST', '/api/v2/auth/token', {}, ({ count }) => {
    if (scenario === 'auth-retry' && count === 1) {
      return routeResponse(
        401,
        { detail: 'Invalid browser acceptance credentials' },
        { expectedHttpFailure: true },
      )
    }
    return ok({
      access_token: 'browser-login-token',
      token_type: 'bearer',
      expires_in: 3600,
      user: {
        id: 'user_browser',
        username: 'browser.qa',
        display_name: 'Browser QA',
        organization_id: 'org_browser',
      },
    })
  })
  add('POST', '/api/v2/auth/refresh', {}, () => routeResponse(
    401,
    { detail: 'No refresh cookie is available in the guest fixture.' },
    { expectedHttpFailure: true },
  ))
  add('POST', `/api/v2/projects/${PROJECT_ID}/delivery-packages`, {}, () => ok({
    id: 'delivery_browser_pending',
    project_id: PROJECT_ID,
    name: 'Browser candidate structures',
    status: 'building',
    artifact_id: null,
    candidate_ids: ['candidate_browser_1'],
    include_experiment_results: true,
    version: 1,
    created_at: NOW,
    updated_at: NOW,
  }, { delayMs: scenario === 'pending' ? 1_000 : 0 }))
  add('POST', `/api/v2/workflow-runs/${workflowRun.id}/submissions`, {}, () => ok({
    id: 'submission_browser',
    workflow_run_id: workflowRun.id,
    status: scenario === 'blocked' ? 'blocked' : 'accepted',
    jobs: scenario === 'blocked' ? [] : [jobFixture('pending')],
    preflight: {
      workflow_run_id: workflowRun.id,
      allowed: scenario !== 'blocked',
      blockers: scenario === 'blocked'
        ? [{ code: 'target_not_ready', message: 'Target readiness is not approved.' }]
        : [],
      warnings: [],
      checks: {},
    },
  }, { delayMs: scenario === 'pending' ? 1_000 : 0 }))
  add('POST', `/api/v2/jobs/job_browser/cancel`, {}, () => ok({
    id: 'job_browser',
    status: 'cancelled',
  }))

  return routes
}

const RECOVERABLE_PATH_BY_ROUTE = Object.freeze({
  experiments: `/api/v2/projects/${PROJECT_ID}/overview`,
  workflow: `/api/v2/workflow-runs/run_browser/graph`,
  candidates: `/api/v2/projects/${PROJECT_ID}/candidates`,
  results: `/api/v2/projects/${PROJECT_ID}/experiment-results`,
  research: `/api/v2/projects/${PROJECT_ID}/research-workspace`,
})

export function createFixtureRouter({ scenario = 'populated', routeId = '' } = {}) {
  const routes = createStrictRoutes({ scenario, routeId })
  const routesBySignature = new Map(routes.map((route) => [route.signature, route]))
  const counts = new Map()

  return {
    expected404Signatures: new Set(
      scenario === 'blocked'
        ? [`GET /api/v2/projects/${PROJECT_ID}/primary-target`]
        : [],
    ),
    async resolve(method, rawUrl, request = {}) {
      const signature = canonicalRequestSignature(method, rawUrl)
      const route = routesBySignature.get(signature)
      if (!route) {
        throw new Error(`Unhandled browser API request: ${signature}`)
      }
      const count = (counts.get(signature) ?? 0) + 1
      counts.set(signature, count)

      const url = new URL(rawUrl, 'http://browser.invalid')
      const recoverablePath = RECOVERABLE_PATH_BY_ROUTE[routeId]
      if (
        scenario === 'recoverable-error'
        && recoverablePath === url.pathname
        && count <= 4
      ) {
        return routeResponse(
          503,
          {
            type: 'about:blank',
            title: 'Temporary browser fixture failure',
            status: 503,
            detail: 'Retry the deterministic browser fixture.',
          },
          { expectedHttpFailure: true },
        )
      }

      const response = await route.resolver({
        count,
        method: String(method).toUpperCase(),
        url,
        request,
      })
      if (
        scenario === 'loading'
        && count === 1
        && LOADING_PATH_BY_ROUTE[routeId] === url.pathname
      ) {
        return { ...response, delayMs: Math.max(response.delayMs, 1_500) }
      }
      return response
    },
    requestCounts() {
      return Object.fromEntries([...counts.entries()].sort(([left], [right]) => left.localeCompare(right)))
    },
  }
}
