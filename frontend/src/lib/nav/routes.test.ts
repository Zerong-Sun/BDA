import { describe, expect, it } from 'vitest'
import { APP_ROUTES, PRIMARY_ROUTES, routeLabel, workbenchRoutes, type NavTranslationKey } from './routes'

/**
 * The registry exists to stop two copies of the route list drifting. These
 * tests are the drift detector: they pin the relationships the top bar and the
 * command palette both rely on, so a route added to one place cannot quietly
 * disagree with the other.
 */

describe('route registry', () => {
  it('every primary route is a real route', () => {
    const known = new Set(APP_ROUTES.map((route) => route.to))

    for (const route of PRIMARY_ROUTES) {
      expect(known.has(route)).toBe(true)
    }
  })

  it('the workbench menu is everything that is neither primary nor help', () => {
    const behind = workbenchRoutes().map((route) => route.to)

    expect(behind).not.toContain('/faq')
    for (const route of PRIMARY_ROUTES) {
      expect(behind).not.toContain(route)
    }
    expect(behind).toContain('/workflow')
    expect(behind).toContain('/results')
  })

  it('lists each route once', () => {
    const paths = APP_ROUTES.map((route) => route.to)

    expect(new Set(paths).size).toBe(paths.length)
  })

  it('words the two routes whose navigation label differs from their page title', () => {
    // The translator is never consulted for these two: `t.nav` has no entry
    // for them, which is the reason the overrides exist.
    const translate = () => {
      throw new Error('t.nav was asked for a key it does not carry')
    }

    expect(routeLabel('inbox', false, translate)).toBe('Decisions')
    expect(routeLabel('bots', false, translate)).toBe('Research team')
    expect(routeLabel('inbox', true, translate)).toBe('待我决定')
    expect(routeLabel('bots', true, translate)).toBe('研究团队')
  })

  it('falls back to the translation for every other route', () => {
    const translate = (key: NavTranslationKey) => `translated:${key}`

    expect(routeLabel('workflow', false, translate)).toBe('translated:workflow')
    expect(routeLabel('results', true, translate)).toBe('translated:results')
  })
})
