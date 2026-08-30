import { describe, expect, it } from 'vitest'
import { en } from './en'
import { zh } from './zh'

function keys(value: unknown, prefix = ''): string[] {
  if (typeof value !== 'object' || value === null) return [prefix]
  return Object.entries(value).flatMap(([key, nested]) => keys(nested, prefix ? `${prefix}.${key}` : key))
}

describe('i18n', () => {
  it('keeps en and zh key parity', () => {
    const enKeys = keys(en).sort()
    const zhKeys = keys(zh).sort()
    expect(zhKeys).toEqual(enKeys)
  })

  it('translates core navigation labels in zh', () => {
    expect(zh.nav.projects).not.toBe(en.nav.projects)
    expect(zh.login.signIn).not.toBe(en.login.signIn)
    expect(zh.shared.userMenu.logout).not.toBe(en.shared.userMenu.logout)
  })

  it('localizes project-library loading and clear-selection labels', () => {
    expect(zh.projectLibrary.loading).not.toBe(en.projectLibrary.loading)
    expect(zh.projectLibrary.selectNone).not.toBe(en.projectLibrary.selectNone)
  })

  it('translates every research tab, phase and hint in zh', () => {
    for (const group of ['tabs', 'phases', 'tabHint'] as const) {
      for (const key of Object.keys(en.research[group])) {
        const enValue = en.research[group][key as keyof (typeof en.research)[typeof group]]
        const zhValue = zh.research[group][key as keyof (typeof zh.research)[typeof group]]
        expect(zhValue, `research.${group}.${key} is untranslated`).not.toBe(enValue)
      }
    }
  })

  it('keeps the review section prompt bilingual and interpolatable', () => {
    const prompts = [en.research.projectReview.sectionPrompt, zh.research.projectReview.sectionPrompt]
    expect(prompts[0]).not.toBe(prompts[1])
    for (const prompt of prompts) {
      expect(prompt).toContain('{project}')
      expect(prompt).toContain('{section}')
    }
  })
})
