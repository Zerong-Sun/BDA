import { describe, expect, it } from 'vitest'
import { resolveStoredText } from './localizedText'

describe('resolveStoredText', () => {
  it('uses the selected stored language', () => {
    expect(resolveStoredText({ en: 'English', zh: '中文', default: 'Source' }, 'zh')).toBe('中文')
  })

  it('silently preserves the original when the selected language is absent', () => {
    expect(resolveStoredText({ en: 'English', default: 'Original text' }, 'zh')).toBe('Original text')
  })

  it('uses the base source before another locale', () => {
    expect(resolveStoredText({ en: 'English' }, 'zh', 'Database source')).toBe('Database source')
  })

  it('falls back to another stored locale only when no original is available', () => {
    expect(resolveStoredText({ en: 'English only' }, 'zh')).toBe('English only')
  })

  it('ignores blank localized values', () => {
    expect(resolveStoredText({ zh: '   ', default: ' Original ' }, 'zh')).toBe('Original')
  })
})
