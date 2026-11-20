import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, relative, resolve, sep } from 'node:path'

const src = resolve(import.meta.dirname, '..')
const specifier = /(?:from|import|vi\.mock)\s*\(?\s*['"]([^'"]+)['"]/g

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(dir, entry.name)
    if (entry.isDirectory()) return entry.name === 'generated' ? [] : sources(path)
    return /\.tsx?$/.test(entry.name) ? [path] : []
  })
}

function importedArea(file: string, spec: string): string | null {
  const target = spec.startsWith('@/') ? resolve(src, spec.slice(2)) : spec.startsWith('.') ? resolve(dirname(file), spec) : null
  if (!target || !target.startsWith(src + sep)) return null
  return relative(src, target).split(sep)[0]
}

function violations(area: 'components' | 'lib'): string[] {
  return sources(resolve(src, area)).flatMap((file) =>
    [...readFileSync(file, 'utf8').matchAll(specifier)]
      .filter((match) => ['features', 'app'].includes(importedArea(file, match[1]) ?? ''))
      .map((match) => `${relative(src, file)} -> ${match[1]}`),
  )
}

// Shared layers sit below the features that compose them; app/ is the only place features are assembled.
describe('frontend layering', () => {
  it.each(['components', 'lib'] as const)('%s imports neither features nor app', (area) => {
    expect(violations(area)).toEqual([])
  })
})
