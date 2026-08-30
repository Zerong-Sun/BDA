import { describe, expect, it } from 'vitest'
import { getGuideFaqSections } from './guideFAQData'
import { getGuideWorkflowStations } from './guideWorkflowData'

describe('Guide bilingual content', () => {
  it('keeps workflow station ids and list shapes aligned', () => {
    const en = getGuideWorkflowStations('en')
    const zh = getGuideWorkflowStations('zh')
    expect(zh.map((item) => item.id)).toEqual(en.map((item) => item.id))
    expect(zh.map((item) => item.inputs.length)).toEqual(en.map((item) => item.inputs.length))
    expect(zh[0].title).not.toBe(en[0].title)
    expect(zh.every((item) => item.title && item.technicalDetail)).toBe(true)
  })

  it('keeps FAQ section and item ids aligned', () => {
    const en = getGuideFaqSections('en')
    const zh = getGuideFaqSections('zh')
    expect(zh.map((item) => item.id)).toEqual(en.map((item) => item.id))
    expect(zh.flatMap((section) => section.items.map((item) => item.id)))
      .toEqual(en.flatMap((section) => section.items.map((item) => item.id)))
  })
})
