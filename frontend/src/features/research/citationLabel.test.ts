import { describe, expect, it } from 'vitest'
import { citationLabel } from './citationLabel'

describe('citationLabel', () => {
  it('reads structured, JSON and legacy Python language records without changing the source', () => {
    const title = { zh: 'PD-L1/高亲和力PD-1复合物', en: 'PD-L1/high-affinity PD-1 complex' }
    const labels = [title, JSON.stringify(title), "{'zh': 'PD-L1/高亲和力PD-1复合物', 'en': 'PD-L1/high-affinity PD-1 complex'}"]
    for (const label of labels) {
      const citation = { label }
      expect(citationLabel(citation, 'zh', 0)).toBe(title.zh)
      expect(citationLabel(citation, 'en', 0)).toBe(title.en)
      expect(citation.label).toBe(label)
    }
  })

  it('handles quoted apostrophes and empty locale values', () => {
    expect(citationLabel({ label: String.raw`{'en': 'Receptor\'s structure', 'zh': ''}` }, 'zh', 0)).toBe("Receptor's structure")
    expect(citationLabel({ label: { zh: ' ', en: 'English', default: 'Default' } }, 'zh', 0)).toBe('English')
    expect(citationLabel({ label: { default: 'Default' } }, 'en', 0)).toBe('Default')
  })

  it('uses a source fallback for non-label objects without interpreting code', () => {
    for (const label of [{ type: 'structure' }, "{'type': 'structure'}", "{'en': alert('no')}" ]) {
      expect(citationLabel({ label, entity_id: 'structure-one' }, 'en', 0)).toBe('structure-one')
    }
    expect(citationLabel({ label: { zh: '' } }, 'zh', 2)).toBe('来源 3')
    expect(citationLabel({ label: 'Unparsed source title' }, 'en', 0)).toBe('Unparsed source title')
  })
})
