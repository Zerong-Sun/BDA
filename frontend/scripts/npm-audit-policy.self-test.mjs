import assert from 'node:assert/strict'
import test from 'node:test'

import { collectAdvisories, evaluateAudit } from './npm-audit-policy.mjs'

const picomatch = {
  source: 1247710,
  name: 'picomatch',
  title: 'picomatch vulnerable to ReDoS',
  url: 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf',
  severity: 'high',
  range: '<=4.0.7',
}

function report(...vias) {
  return {
    auditReportVersion: 2,
    vulnerabilities: {
      picomatch: { name: 'picomatch', via: vias },
      tinyglobby: { name: 'tinyglobby', via: ['picomatch'] },
    },
  }
}

const exception = {
  advisory: 'GHSA-fc5q-39xc-vjpf',
  package: 'picomatch',
  vulnerable_range: '<=4.0.7',
  severity: 'high',
  reason: 'build tooling only',
  reviewed: '2026-11-18',
  expires: '2026-12-18',
}

test('a clean report passes without exceptions', () => {
  assert.deepEqual(evaluateAudit({ vulnerabilities: {} }, [], '2026-11-18'), { failures: [], accepted: [] })
})

test('an unreviewed advisory fails', () => {
  const { failures } = evaluateAudit(report(picomatch), [], '2026-11-18')
  assert.equal(failures.length, 1)
  assert.match(failures[0], /GHSA-fc5q-39xc-vjpf picomatch/)
})

test('a matching, unexpired exception is accepted', () => {
  const result = evaluateAudit(report(picomatch), [exception], '2026-12-18')
  assert.deepEqual(result.failures, [])
  assert.equal(result.accepted.length, 1)
})

test('an expired exception fails', () => {
  const { failures } = evaluateAudit(report(picomatch), [exception], '2026-12-19')
  assert.ok(failures.some((line) => /expired on 2026-12-18/.test(line)))
})

test('an exception longer than the review window fails', () => {
  const { failures } = evaluateAudit(report(picomatch), [{ ...exception, expires: '2027-01-18' }], '2026-11-18')
  assert.ok(failures.some((line) => /spans more than 30 days/.test(line)))
})

test('a changed advisory range no longer matches', () => {
  const { failures } = evaluateAudit(report({ ...picomatch, range: '<=4.0.8' }), [exception], '2026-11-18')
  assert.ok(failures.some((line) => /<=4\.0\.8/.test(line)))
  assert.ok(failures.some((line) => /no longer matches/.test(line)))
})

test('a stale exception fails once the advisory is gone', () => {
  const { failures } = evaluateAudit({ vulnerabilities: {} }, [exception], '2026-11-18')
  assert.deepEqual(failures.length, 1)
  assert.match(failures[0], /no longer matches/)
})

test('critical advisories cannot be excepted', () => {
  const critical = { ...picomatch, severity: 'critical' }
  const { failures, accepted } = evaluateAudit(report(critical), [{ ...exception, severity: 'critical' }], '2026-11-18')
  assert.deepEqual(accepted, [])
  assert.ok(failures.some((line) => /cannot be excepted/.test(line)))
})

test('an incomplete exception is rejected', () => {
  const { failures } = evaluateAudit(report(picomatch), [{ ...exception, reason: ' ' }], '2026-11-18')
  assert.ok(failures.some((line) => /missing reason/.test(line)))
})

test('an npm error payload is not treated as a clean report', () => {
  assert.throws(() => collectAdvisories({ error: { code: 'ENOTFOUND' } }), /did not return a vulnerability report/)
})
