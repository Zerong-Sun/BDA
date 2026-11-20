// An exception accepts one advisory exactly as it is published today. When the
// advisory's range or severity changes, or a release fixes it, the entry stops
// matching and the gate fails until someone re-reviews it.
export const MAX_EXCEPTION_DAYS = 30

const DAY_MS = 24 * 60 * 60 * 1000
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/
const REQUIRED_FIELDS = ['advisory', 'package', 'vulnerable_range', 'severity', 'reason', 'reviewed', 'expires']

function parseDate(value) {
  if (typeof value !== 'string' || !ISO_DATE.test(value)) return null
  const time = Date.parse(`${value}T00:00:00Z`)
  return Number.isNaN(time) ? null : time
}

function advisoryId(url) {
  const match = /\/(GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4})$/.exec(url ?? '')
  return match ? match[1] : String(url ?? 'unknown advisory')
}

export function collectAdvisories(report) {
  if (!report || typeof report !== 'object' || !report.vulnerabilities || typeof report.vulnerabilities !== 'object') {
    throw new Error('npm audit did not return a vulnerability report')
  }
  const advisories = new Map()
  for (const entry of Object.values(report.vulnerabilities)) {
    for (const via of entry.via ?? []) {
      if (typeof via !== 'object' || via === null) continue
      const id = advisoryId(via.url)
      const key = `${id}|${via.name}`
      if (!advisories.has(key)) {
        advisories.set(key, { id, package: via.name, severity: via.severity, range: via.range, title: via.title })
      }
    }
  }
  return [...advisories.values()]
}

export function evaluateAudit(report, exceptions, today) {
  const failures = []
  const accepted = []
  const todayTime = parseDate(today)
  if (todayTime === null) throw new Error(`Invalid evaluation date: ${today}`)
  if (!Array.isArray(exceptions)) throw new Error('Audit exceptions must be a JSON array')

  const usable = []
  for (const [index, exception] of exceptions.entries()) {
    const label = `exception #${index + 1} (${exception?.advisory ?? 'no advisory'})`
    const missing = REQUIRED_FIELDS.filter((field) => typeof exception?.[field] !== 'string' || !exception[field].trim())
    if (missing.length) {
      failures.push(`${label} is missing ${missing.join(', ')}`)
      continue
    }
    const reviewed = parseDate(exception.reviewed)
    const expires = parseDate(exception.expires)
    if (reviewed === null || expires === null) {
      failures.push(`${label} must use YYYY-MM-DD for reviewed and expires`)
      continue
    }
    if (reviewed > todayTime) failures.push(`${label} has a review date in the future`)
    if (expires < reviewed) failures.push(`${label} expires before it was reviewed`)
    if (expires - reviewed > MAX_EXCEPTION_DAYS * DAY_MS) {
      failures.push(`${label} spans more than ${MAX_EXCEPTION_DAYS} days`)
    }
    if (todayTime > expires) failures.push(`${label} expired on ${exception.expires}; re-review it or remove it`)
    if (exception.severity === 'critical') failures.push(`${label} is critical, which cannot be excepted`)
    usable.push(exception)
  }

  const matched = new Set()
  for (const advisory of collectAdvisories(report)) {
    const exception = usable.find(
      (item) =>
        item.advisory === advisory.id
        && item.package === advisory.package
        && item.vulnerable_range === advisory.range
        && item.severity === advisory.severity,
    )
    if (exception && advisory.severity !== 'critical') {
      matched.add(exception)
      accepted.push(`${advisory.id} ${advisory.package} ${advisory.range} (${advisory.severity}) until ${exception.expires}`)
    } else {
      failures.push(`${advisory.id} ${advisory.package} ${advisory.range} (${advisory.severity}): ${advisory.title}`)
    }
  }

  for (const exception of usable) {
    if (!matched.has(exception)) {
      failures.push(
        `exception ${exception.advisory} ${exception.package} ${exception.vulnerable_range} no longer matches the audit; remove or re-review it`,
      )
    }
  }

  return { failures, accepted }
}
