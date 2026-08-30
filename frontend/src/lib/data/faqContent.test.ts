import { describe, expect, it } from 'vitest'
import { bundleEn } from '../i18n/locales/en.bundle'
import { bundleZh } from '../i18n/locales/zh.bundle'
import { faqSectionRefs, resolveFaqSections } from './faqContent'

describe('resolveFaqSections', () => {
  it('returns empty array when sections are undefined', () => {
    expect(resolveFaqSections(undefined)).toEqual([])
  })

  it('resolves sections in configured order and skips incomplete entries', () => {
    const resolved = resolveFaqSections({
      gettingStarted: {
        label: 'Getting started',
        title: 'Platform overview',
        items: {
          whatIsPlatform: {
            question: 'What is this platform for?',
            answer: 'Protein design automation.',
          },
          whoIsItFor: {
            question: 'Who is it designed for?',
            answer: 'Researchers.',
          },
        },
      },
      research: {
        label: 'Research',
        title: 'Literature review',
        items: {
          whyResearchRequired: {
            question: 'Why is research required?',
            answer: '',
          },
        },
      },
    })

    expect(resolved).toHaveLength(1)
    expect(resolved[0]?.id).toBe('gettingStarted')
    expect(resolved[0]?.items).toHaveLength(2)
  })

  it('keeps faqSectionRefs aligned with all eight FAQ modules', () => {
    expect(faqSectionRefs).toHaveLength(8)
    expect(faqSectionRefs.map((section) => section.id)).toEqual([
      'gettingStarted',
      'research',
      'targetProtein',
      'structurePrep',
      'aiDesign',
      'results',
      'projectsApi',
      'troubleshooting',
    ])
  })

  it('resolves complete English and Chinese FAQ bundles without gaps', () => {
    const enSections = resolveFaqSections(bundleEn.faq.sections)
    const zhSections = resolveFaqSections(bundleZh.faq.sections)

    expect(enSections).toHaveLength(faqSectionRefs.length)
    expect(zhSections).toHaveLength(faqSectionRefs.length)

    for (const sectionRef of faqSectionRefs) {
      const enSection = enSections.find((section) => section.id === sectionRef.id)
      const zhSection = zhSections.find((section) => section.id === sectionRef.id)

      expect(enSection?.items).toHaveLength(sectionRef.items.length)
      expect(zhSection?.items).toHaveLength(sectionRef.items.length)
    }
  })
})
