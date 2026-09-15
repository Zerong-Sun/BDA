import type { ReactNode } from 'react'
import { act, renderHook } from '@testing-library/react'
import { HashRouter } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { useSearchParamPatch } from './useSearchParamPatch'

const wrapper = ({ children }: { children: ReactNode }) => <HashRouter>{children}</HashRouter>

function mount() {
  return renderHook(() => useSearchParamPatch(), { wrapper })
}

describe('useSearchParamPatch', () => {
  beforeEach(() => {
    window.location.hash = '#/workflow?project=p1'
  })

  it('composes two patches from one event instead of the second undoing the first', () => {
    const { result } = mount()

    act(() => {
      result.current[1]({ run: 'r1' })
      result.current[1]({ node: 'n1' })
    })

    expect(result.current[0].get('run')).toBe('r1')
    expect(result.current[0].get('node')).toBe('n1')
  })

  it('leaves keys it was not given alone', () => {
    const { result } = mount()

    act(() => result.current[1]({ run: 'r1' }))

    expect(result.current[0].get('project')).toBe('p1')
  })

  it('removes a key given null or an empty string', () => {
    window.location.hash = '#/workflow?project=p1&run=r1&node=n1'
    const { result } = mount()

    act(() => result.current[1]({ run: null, node: '' }))

    expect(result.current[0].has('run')).toBe(false)
    expect(result.current[0].has('node')).toBe(false)
    expect(result.current[0].get('project')).toBe('p1')
  })

  it('does not navigate when the patch changes nothing', () => {
    const { result } = mount()
    const before = window.history.length

    act(() => result.current[1]({ project: 'p1', node: null }))

    expect(window.history.length).toBe(before)
  })

  it('replaces the history entry when asked, so Back leaves the page', () => {
    const { result } = mount()
    const before = window.history.length

    act(() => result.current[1]({ node: 'n1' }, { replace: true }))
    act(() => result.current[1]({ node: 'n2' }, { replace: true }))

    expect(window.history.length).toBe(before)
    expect(result.current[0].get('node')).toBe('n2')
  })

  it('keeps one function identity while the URL changes', () => {
    const { result } = mount()
    const first = result.current[1]

    act(() => result.current[1]({ run: 'r1' }))

    expect(result.current[1]).toBe(first)
  })
})
