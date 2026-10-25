import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { LineChart } from './LineChart'
import { useAppStore } from '../../lib/store/appStore'
afterEach(cleanup)
it('draws raw observations without smoothing and pairs fitted curves by color with different dashes', () => {
  useAppStore.setState({ language: 'en' })
  const { container } = render(<LineChart ariaLabel="Sensorgrams" xLabel="Time (s)" yLabel="Response (nm)" traces={[
    { label: '10 nM', points: [[0, 0], [1, 3], [2, 1]], colorIndex: 0, kind: 'measured' },
    { label: '10 nM fit', points: [[0, 0], [1, 2], [2, 1]], colorIndex: 0, kind: 'fitted' },
    { label: 'Simulation', points: [[0, 1], [2, 2]], colorIndex: 1, kind: 'simulated' },
  ]} />)
  const raw = container.querySelector('[data-trace-kind="measured"]')!
  const fitted = container.querySelector('[data-trace-kind="fitted"]')!
  expect(raw.tagName).toBe('polyline')
  expect(raw.getAttribute('points')?.split(' ')).toHaveLength(3)
  expect(raw).toHaveAttribute('stroke-dasharray', 'none')
  expect(fitted.getAttribute('stroke')).toBe(raw.getAttribute('stroke'))
  expect(fitted).toHaveAttribute('stroke-dasharray', '6 3')
  expect(screen.getByText('Simulation · simulated')).toBeInTheDocument()
  expect(screen.getByText('Time (s)')).toBeInTheDocument()
  expect(screen.getByText('Response (nm)')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Export SVG chart' })).toBeInTheDocument()
})
it('renders flat series with a real axis range and no duplicate tick keys', () => {
  render(<LineChart ariaLabel="Flat" xLabel="Time (s)" yLabel="Response (nm)" traces={[{ label: 'Flat', points: [[5, 0], [5, 0]] }]} />)
  expect(screen.getByRole('img', { name: 'Flat' }).innerHTML).not.toMatch(/NaN|Infinity/)
})

it('exports a self-contained SVG with explicit dimensions and a visible legend', async () => {
  let exported: Blob | null = null
  vi.stubGlobal('URL', Object.assign(class extends URL {}, { createObjectURL: vi.fn((blob: Blob) => { exported = blob; return 'blob:chart' }), revokeObjectURL: vi.fn() }))
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<LineChart ariaLabel="Export" xLabel="Time (s)" yLabel="Response (nm)" traces={[{ label: 'Sample', points: [[0, 0], [1, 1]] }]} />)
  fireEvent.click(screen.getByRole('button', { name: 'Export SVG chart' }))
  expect(click).toHaveBeenCalled()
  const text = await new Promise<string>((resolve) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.readAsText(exported!) })
  const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement
  if (svg.tagName === 'parsererror') throw new Error(svg.textContent ?? text)
  expect(svg.getAttribute('width')).toBe('640')
  expect(svg.getAttribute('height')).toBe('256')
  expect(svg.hasAttribute('style')).toBe(false)
  expect(svg.textContent).toContain('Sample · measured')
  click.mockRestore(); vi.unstubAllGlobals()
})
