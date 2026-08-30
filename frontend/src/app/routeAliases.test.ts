import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { en } from '../lib/i18n/en'
import { zh } from '../lib/i18n/zh'

/**
 * The project library was reachable at `/experiments` while its own navigation
 * label said "Projects" — the URL and the UI disagreed about what the page was.
 * The route is now `/projects`, and `/experiments` redirects rather than 404s,
 * because links and bookmarks to it exist.
 */
const appSource = readFileSync(resolve(import.meta.dirname, '../App.tsx'), 'utf8')

describe('project library route', () => {
  it('is served at /projects', () => {
    expect(appSource).toMatch(/<Route path="\/projects" element=\{<ExperimentsPage \/>\}/)
  })

  it('keeps /experiments working as a redirect', () => {
    // Dropping this turns every existing bookmark into a 404, which is a worse
    // outcome than the naming mismatch it replaced.
    expect(appSource).toMatch(
      /<Route path="\/experiments" element=\{<Navigate to="\/projects" replace \/>\}/,
    )
  })

  it('lands on /projects rather than the old path', () => {
    expect(appSource).toMatch(/<Route index element=\{<Navigate to="\/projects" replace \/>\}/)
  })
})

describe('navigation copy', () => {
  it('names the page the same way the route does', () => {
    expect(en.nav.projects).toBe('Projects')
    expect(zh.nav.projects).toBe('项目')
  })

  it('no longer carries a key whose name contradicts what it renders', () => {
    expect('experiments' in en.nav).toBe(false)
    expect('experiments' in zh.nav).toBe(false)
  })
})
