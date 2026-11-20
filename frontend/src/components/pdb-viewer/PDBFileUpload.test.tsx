import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { PDBFileUpload } from './PDBFileUpload'

function pdbFile(name = 'reference-target.pdb') {
  return new File(['ATOM      1  N   GLY A   1      11.104  13.207  14.099\nEND\n'], name, {
    type: 'chemical/x-pdb',
  })
}

afterEach(cleanup)

describe('PDBFileUpload persistence semantics', () => {
  it('uses a registry upload trigger and one hidden file input in either display branch', () => {
    const onFileSelected = vi.fn()
    const { container, rerender } = renderWithProviders(
      <PDBFileUpload onFileSelected={onFileSelected} />,
    )

    expect(screen.getByRole('button', { name: /browse structure file/i })).toHaveAttribute(
      'data-slot',
      'button',
    )
    expect(screen.getByRole('group', { name: /structure upload/i })).toHaveAttribute(
      'data-slot',
      'frame',
    )
    expect(container.querySelectorAll('input[type="file"]')).toHaveLength(1)
    expect(container.querySelector('input[type="file"]')).toHaveClass('hidden')

    rerender(
      <PDBFileUpload
        selectedFile={pdbFile('selected.pdb')}
        onFileSelected={onFileSelected}
      />,
    )

    expect(screen.getByRole('button', { name: /replace selected\.pdb/i })).toHaveAttribute(
      'data-slot',
      'button',
    )
    expect(container.querySelectorAll('input[type="file"]')).toHaveLength(1)
  })

  it('blocks both picker and drop upload paths in read-only mode', () => {
    const onFileSelected = vi.fn()
    const { container } = renderWithProviders(
      <PDBFileUpload readOnly onFileSelected={onFileSelected} />,
    )
    const input = container.querySelector('input[type="file"]')
    const dropSurface = screen
      .getByRole('group', { name: /structure upload/i })
      .querySelector('[data-slot="frame-panel"]')

    expect(screen.getByRole('button', { name: /browse structure file/i })).toBeDisabled()
    expect(input).toBeDisabled()
    expect(dropSurface).toBeInstanceOf(HTMLDivElement)
    fireEvent.drop(dropSurface!, { dataTransfer: { files: [pdbFile()] } })
    expect(onFileSelected).not.toHaveBeenCalled()
  })

  it('keeps the read-only explanation visible after a local file is selected', () => {
    renderWithProviders(
      <PDBFileUpload
        readOnly
        selectedFile={pdbFile('selected.pdb')}
        onFileSelected={vi.fn()}
      />,
    )

    expect(screen.getByRole('alert')).toHaveTextContent(/read-only demo mode/i)
    expect(screen.getByRole('button', { name: /replace selected\.pdb/i })).toBeDisabled()
  })

  it('keeps local file preview separate from persisted structure state until upload succeeds', async () => {
    const onFileSelected = vi.fn()
    const onUploaded = vi.fn()
    const file = pdbFile()
    const events: string[] = []
    onFileSelected.mockImplementation(() => events.push('preview'))
    onUploaded.mockImplementation(() => events.push('persisted'))

    server.use(
      http.post('/api/v2/artifact-uploads', async ({ request }) => {
        const body = await request.json() as { project_id: string }
        expect(body.project_id).toBe('proj_layer8')
        return HttpResponse.json({
          id: 'upload_layer8', upload_url: 'http://minio.test/upload', required_headers: { 'Content-Type': 'chemical/x-pdb' },
        })
      }),
      http.put('http://minio.test/upload', () => new HttpResponse(null, { status: 200 })),
      http.post('/api/v2/artifact-uploads/upload_layer8/complete', () => HttpResponse.json({
        id: 'file_layer8_target', project_id: 'proj_layer8', artifact_type: 'target_structure',
        filename: file.name, content_type: 'chemical/x-pdb', status: 'available', size_bytes: file.size,
        checksum_sha256: 'a'.repeat(64), lineage: {}, version: 1, created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:00Z', download_url: '/api/v2/artifacts/file_layer8_target',
      })),
      http.get('/api/v2/projects/proj_layer8/primary-target', () =>
        HttpResponse.json({ detail: 'Project has no primary target' }, { status: 404 })),
      http.post('/api/v2/projects/proj_layer8/targets', async ({ request }) => {
        const body = await request.json() as { name: string }
        expect(body.name).toBe('reference-target')
        return HttpResponse.json({
          id: 'target_layer8', project_id: 'proj_layer8', name: body.name,
          sequence: null, uniprot_accession: null, organism: null, identity_status: 'unconfirmed',
          structure_artifact_id: null, structure_status: 'missing', version: 1,
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        }, { status: 201 })
      }),
      http.put('/api/v2/projects/proj_layer8/primary-target', () => HttpResponse.json({
        id: 'target_layer8', project_id: 'proj_layer8', name: 'reference-target',
        sequence: null, uniprot_accession: null, organism: null, identity_status: 'unconfirmed',
        structure_artifact_id: null, structure_status: 'missing', version: 1,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      })),
      http.put('/api/v2/targets/target_layer8/structure-artifact', async ({ request }) => {
        const body = await request.json() as { artifact_id: string }
        expect(body.artifact_id).toBe('file_layer8_target')
        return HttpResponse.json({
          id: 'target_layer8', project_id: 'proj_layer8', name: 'reference-target',
          sequence: null, uniprot_accession: null, organism: null, identity_status: 'unconfirmed',
          structure_artifact_id: 'file_layer8_target', structure_status: 'available', version: 2,
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        })
      }),
    )

    const { container } = renderWithProviders(
      <PDBFileUpload
        projectId="proj_layer8"
        onFileSelected={onFileSelected}
        onUploaded={onUploaded}
      />,
    )

    const input = container.querySelector('input[type="file"]')
    expect(input).toBeInstanceOf(HTMLInputElement)
    fireEvent.change(input!, { target: { files: [file] } })

    expect(onFileSelected).toHaveBeenCalledWith(file)
    expect(screen.getByRole('progressbar')).toHaveAttribute('data-slot', 'progress')
    await waitFor(() =>
      expect(onUploaded).toHaveBeenCalledWith('/api/v2/artifacts/file_layer8_target'),
    )
    expect(events).toEqual(['preview', 'persisted'])
  })

  it('does not report a persisted structure when the upload endpoint fails', async () => {
    const onFileSelected = vi.fn()
    const onUploaded = vi.fn()
    const file = pdbFile('transient-preview.pdb')
    let requestCount = 0

    server.use(
      http.post('/api/v2/artifact-uploads', () => {
        requestCount += 1
        return HttpResponse.json({ message: 'storage_unavailable' }, { status: 503 })
      }),
    )

    const { container } = renderWithProviders(
      <PDBFileUpload
        projectId="proj_layer8"
        onFileSelected={onFileSelected}
        onUploaded={onUploaded}
      />,
    )

    const input = container.querySelector('input[type="file"]')
    expect(input).toBeInstanceOf(HTMLInputElement)
    fireEvent.change(input!, { target: { files: [file] } })

    expect(onFileSelected).toHaveBeenCalledWith(file)
    await waitFor(() => expect(requestCount).toBe(1))
    expect(onUploaded).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveAttribute('data-slot', 'alert')
    expect(screen.getByRole('alert')).toHaveTextContent(/upload could not be persisted/i)
  })
})
