import { execFile } from 'node:child_process'
import { readFile } from 'node:fs/promises'
import { promisify } from 'node:util'

import { evaluateAudit } from './npm-audit-policy.mjs'

const run = promisify(execFile)

async function auditReport() {
  try {
    const { stdout } = await run('npm', ['audit', '--json'], { maxBuffer: 64 * 1024 * 1024 })
    return JSON.parse(stdout)
  } catch (error) {
    // npm audit exits non-zero whenever it reports anything; the JSON is still on stdout.
    if (typeof error?.stdout === 'string' && error.stdout.trim()) return JSON.parse(error.stdout)
    throw error
  }
}

const exceptions = JSON.parse(await readFile('audit-exceptions.json', 'utf8'))
const today = new Date().toISOString().slice(0, 10)
const { failures, accepted } = evaluateAudit(await auditReport(), exceptions, today)

for (const line of accepted) console.log(`accepted by reviewed exception: ${line}`)
if (failures.length) {
  console.error(`npm audit gate failed:\n${failures.map((line) => `  - ${line}`).join('\n')}`)
  process.exit(1)
}
console.log(`npm audit gate passed (${accepted.length} reviewed exception(s))`)
