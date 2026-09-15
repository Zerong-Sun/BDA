import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { StatusPills } from './StatusPill'
import { useAppStore } from '../../lib/store/appStore'
import { statusTone } from './statusTone'

afterEach(cleanup)
describe('Readable statuses', () => {
  it('translates status text without losing its original color', () => {
    useAppStore.setState({ language: 'zh' })
    render(<StatusPills status="active · archived · failed" />)
    expect(screen.getByText('进行中')).toHaveClass('bg-success/10')
    expect(screen.getByText('已归档')).toHaveClass('bg-transparent')
    expect(screen.getByText('失败')).toHaveClass('bg-destructive/10')
  })
  it.each([['unavailable', 'neutral'], ['disconnected', 'red'], ['connected', 'green'], ['active', 'green'], ['succeeded', 'green'], ['paused', 'amber']])('assigns %s its correct tone', (value, tone) => {
    expect(statusTone(value)).toBe(tone)
  })
})
