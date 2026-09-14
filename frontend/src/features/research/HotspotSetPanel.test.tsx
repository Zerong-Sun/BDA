import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { HotspotSetPanel } from './HotspotSetPanel'

/**
 * Who chose the residues a design will target.
 *
 * The panel's job is to keep three claims apart on screen - a Bot proposed
 * this, I chose this, a Bot proposed it and I accepted - and to make sure the
 * only control that turns the first into the third is a person's click.
 *
 * The viewer is mocked. What matters here is that a pick becomes a residue in
 * the set and that saving sends it; rendering a molecule is Mol*'s job and is
 * covered by the browser matrix.
 */

vi.mock('../pdb-viewer/StructureViewerLazy', () => ({
  StructureViewerLazy: ({ onResiduePick }: { onResiduePick?: (residue: { chainId: string; seq: number }) => void }) => (
    <div>
      <button type="button" onClick={() => onResiduePick?.({ chainId: 'A', seq: 164 })}>pick A164</button>
      <button type="button" onClick={() => onResiduePick?.({ chainId: 'A', seq: 168 })}>pick A168</button>
    </div>
  ),
}))

afterEach(cleanup)

const PROPOSED = {
  id: 'hs1', project_id: 'proj_test', target_id: 'tgt1', structure_artifact_id: null,
  label: "CC' loop face", residues: [{ chain: 'A', seq: 124, name: 'LEU' }, { chain: 'A', seq: 126, name: null }],
  rationale: 'Covers the native interface', evidence_refs: ['artifact:1'], origin: 'agent',
  status: 'proposed', created_by: 'user_test', confirmed_by: null, version: 1,
  created_at: '2026-09-14T08:00:00Z', updated_at: '2026-09-14T08:00:00Z',
}

function stub(items: unknown[]) {
  useAppStore.setState({ activeProjectId: 'proj_test' })
  server.use(
    http.get('/api/v2/projects/:projectId/hotspot-sets', () => HttpResponse.json({ items })),
  )
}

describe('HotspotSetPanel', () => {
  it('says who proposed a set and shows what it rests on', async () => {
    stub([PROPOSED])
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" />)

    expect(await screen.findByText("CC' loop face")).toBeInTheDocument()
    expect(screen.getByText('Proposed by a Bot')).toBeInTheDocument()
    expect(screen.getByText('A124,A126')).toBeInTheDocument()
    expect(screen.getByText('Covers the native interface')).toBeInTheDocument()
    expect(screen.getByText('artifact:1')).toBeInTheDocument()
  })

  it('confirms a proposal with the version it was read at', async () => {
    stub([PROPOSED])
    let sent: string | null = null
    server.use(
      http.post('/api/v2/hotspot-sets/:id/confirmations', ({ request }) => {
        sent = request.headers.get('If-Match')
        return HttpResponse.json({ ...PROPOSED, status: 'confirmed', origin: 'agent_proposed_human_confirmed', version: 2 })
      }),
    )
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }))

    await vi.waitFor(() => expect(sent).toBe('W/"1"'))
  })

  it('offers no ruling on a set that was already settled', async () => {
    stub([{ ...PROPOSED, status: 'confirmed', origin: 'agent_proposed_human_confirmed' }])
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" />)

    expect(await screen.findByText('Proposed by a Bot · you confirmed')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument()
  })

  it('turns residues picked on the structure into a set the person owns', async () => {
    stub([])
    let body: { label?: string; residues?: { chain: string; seq: number }[] } = {}
    server.use(
      http.post('/api/v2/targets/:targetId/hotspot-sets', async ({ request }) => {
        body = (await request.json()) as typeof body
        return HttpResponse.json({ ...PROPOSED, origin: 'human', status: 'confirmed' })
      }),
    )
    renderWithProviders(
      <HotspotSetPanel projectId="proj_test" targetId="tgt1" source={{ url: '/s.pdb', artifactId: 'art1' }} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pick on the structure' }))
    fireEvent.click(screen.getByRole('button', { name: 'pick A164' }))
    fireEvent.click(screen.getByRole('button', { name: 'pick A168' }))
    fireEvent.change(screen.getByLabelText('Name for this set'), { target: { value: 'My face' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as a confirmed set' }))

    await vi.waitFor(() => expect(body.label).toBe('My face'))
    expect(body.residues).toEqual([
      { chain: 'A', seq: 164, name: null },
      { chain: 'A', seq: 168, name: null },
    ])
  })

  it('lets a second click on the same residue take it back out', async () => {
    stub([])
    renderWithProviders(
      <HotspotSetPanel projectId="proj_test" targetId="tgt1" source={{ url: '/s.pdb' }} />,
    )

    fireEvent.click(await screen.findByRole('button', { name: 'Pick on the structure' }))
    fireEvent.click(screen.getByRole('button', { name: 'pick A164' }))
    fireEvent.click(screen.getByRole('button', { name: 'pick A168' }))
    expect(screen.getByText('Picked: A164,A168')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'pick A164' }))

    expect(screen.getByText('Picked: A168')).toBeInTheDocument()
  })

  it('reviews without offering to pick when there is no structure to pick on', async () => {
    stub([PROPOSED])
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" />)

    await screen.findByText("CC' loop face")
    expect(screen.queryByRole('button', { name: 'Pick on the structure' })).not.toBeInTheDocument()
  })

  it('explains a set somebody else already ruled on instead of overwriting them', async () => {
    stub([PROPOSED])
    server.use(
      http.post('/api/v2/hotspot-sets/:id/confirmations', () =>
        HttpResponse.json({ detail: 'version_conflict' }, { status: 412 }),
      ),
    )
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" />)

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText(/already ruled on this set/i)).toBeInTheDocument()
  })

  it('shows a read-only reviewer the record and none of the controls', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ role: 'viewer' }))
    stub([PROPOSED])
    renderWithProviders(<HotspotSetPanel projectId="proj_test" targetId="tgt1" source={{ url: '/s.pdb' }} />)

    const row = (await screen.findByText("CC' loop face")).closest('li') as HTMLElement
    expect(within(row).queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Pick on the structure' })).not.toBeInTheDocument()
    sessionStorage.clear()
  })
})
