import { describe, expect, it } from 'vitest'
import { extensionMessage, extensionCheckStatus } from './extensionText'

describe('extension service copy', () => {
  it('translates known conditions and keeps unknown operator messages intact', () => {
    expect(extensionMessage('Select a registered model plugin.', true)).toBe('请选择已登记的模型插件。')
    expect(extensionMessage('Operator-specific review: custom scope', true)).toBe('Operator-specific review: custom scope')
    expect(extensionMessage('Select a registered model plugin.', false)).toBe('Select a registered model plugin.')
  })
  it('preserves dynamic counts and reviewed scientific scope', () => {
    expect(extensionMessage('3 matching registry declarations exist. Select exact resources for a scoped assessment; a record does not prove installation.', true)).toContain('3 条')
    expect(extensionMessage('Recorded use review is scoped to: custom assay A. It does not establish scientific validity or prove which files were loaded at runtime.', true)).toContain('custom assay A')
    expect(extensionCheckStatus('missing', true)).toBe('待补充')
    expect(extensionCheckStatus('future_status', true)).toBe('future_status')
  })
})
