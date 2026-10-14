import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation, useNavigate } from 'react-router'
import { useAppStore } from '../lib/store/appStore'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { LabPage } from './Lab'

vi.mock('../lib/hooks/useProjectContext', () => ({ useProjectContext: vi.fn() }))
vi.mock('../features/lab/ProteinLibrary', () => ({ ProteinLibrary: ({ projectId }: { projectId: string }) => <section aria-label="Library content">{projectId}</section> }))
vi.mock('../features/lab/InstrumentAnalysis', () => ({ InstrumentAnalysis: ({ projectId }: { projectId: string }) => <section aria-label="Analysis content">{projectId}</section> }))
vi.mock('../features/projects/ProjectChooser', () => ({ ProjectChooser: () => <p>Choose project</p> }))

function LocationControls() {
  const location = useLocation()
  const navigate = useNavigate()
  return <><output aria-label="Current URL">{location.pathname}{location.search}</output><button type="button" onClick={() => navigate(-1)}>Back</button><button type="button" onClick={() => navigate(1)}>Forward</button></>
}

function open(url = '/lab?project=p1') {
  return render(<MemoryRouter initialEntries={[url]}><LabPage /><LocationControls /></MemoryRouter>)
}

beforeEach(() => {
  useAppStore.setState({ language: 'en' })
  vi.mocked(useProjectContext).mockReturnValue({ projectId: 'p1' } as ReturnType<typeof useProjectContext>)
})
afterEach(cleanup)

describe('Project lab sections', () => {
  it('defaults to constructs and does not mount instrument analysis or calculators', () => {
    open()
    expect(screen.getByRole('tab', { name: 'Proteins & constructs' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('region', { name: 'Library content' })).toHaveTextContent('p1')
    expect(screen.queryByRole('region', { name: 'Analysis content' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open standalone calculations and previews' })).toHaveAttribute('href', '/tools')
    expect(screen.queryByRole('button', { name: 'Plan dilution' })).not.toBeInTheDocument()
  })

  it('keeps project and unrelated URL state when switching, including browser back and forward', async () => {
    open('/lab?project=p1&source=review')
    fireEvent.click(screen.getByRole('tab', { name: 'Instrument analysis & QC' }))
    expect(screen.getByRole('region', { name: 'Analysis content' })).toHaveTextContent('p1')
    expect(screen.queryByRole('region', { name: 'Library content' })).not.toBeInTheDocument()
    expect(screen.getByLabelText('Current URL')).toHaveTextContent('/lab?project=p1&source=review&section=analysis')
    fireEvent.click(screen.getByRole('button', { name: 'Back' }))
    await waitFor(() => expect(screen.getByRole('region', { name: 'Library content' })).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: 'Forward' }))
    await waitFor(() => expect(screen.getByRole('region', { name: 'Analysis content' })).toBeInTheDocument())
  })

  it('restores an analysis deep link on mount and falls back from an unknown section', () => {
    const page = open('/lab?project=p1&section=analysis')
    expect(screen.getByRole('tab', { name: 'Instrument analysis & QC' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('region', { name: 'Analysis content' })).toBeInTheDocument()
    page.unmount()
    open('/lab?project=p1&section=old-calculators')
    expect(screen.getByRole('region', { name: 'Library content' })).toBeInTheDocument()
  })

  it('requires a project before mounting project data', () => {
    vi.mocked(useProjectContext).mockReturnValue({ projectId: '' } as ReturnType<typeof useProjectContext>)
    open('/lab')
    expect(screen.getByText('Choose project')).toBeInTheDocument()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })
})
