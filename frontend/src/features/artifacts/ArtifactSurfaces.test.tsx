import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { downloadArtifact, uploadArtifact } from '../../lib/api/artifacts'
import { useToastStore } from '../../components/ui/toastStore'
import type { Artifact } from '../../lib/schemas/artifact'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ArtifactBrowser } from './ArtifactBrowser'
import { ArtifactUploadDropzone } from './ArtifactUploadDropzone'

vi.mock('../../lib/api/artifacts', () => ({
  downloadArtifact: vi.fn(),
  uploadArtifact: vi.fn(),
}))

const artifact: Artifact = {
  id: 'artifact-one',
  project_id: 'project-one',
  artifact_type: 'target_structure',
  filename: 'target.pdb',
  content_type: 'chemical/x-pdb',
  status: 'available',
  size_bytes: 2048,
  checksum_sha256: 'checksum',
  lineage: { route: 'structure', sequence_count: 1 },
  version: 1,
  created_at: '2026-07-29T00:00:00Z',
  updated_at: '2026-07-29T00:00:00Z',
  download_url: '/api/v2/artifacts/artifact-one/download',
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((next, fail) => {
    resolve = next
    reject = fail
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.clearAllMocks()
  useToastStore.getState().clear()
})

afterEach(cleanup)

describe('ArtifactBrowser', () => {
  it('exposes separate sibling selection and download registry buttons', async () => {
    const onSelect = vi.fn()
    vi.mocked(downloadArtifact).mockResolvedValue()
    renderWithProviders(
      <ArtifactBrowser artifacts={[artifact]} selectedArtifactId={artifact.id} onSelect={onSelect} />,
    )

    const selectButton = screen.getByRole('button', { name: 'Select target.pdb' })
    const downloadButton = screen.getByRole('button', { name: 'Download target.pdb' })
    expect(selectButton).toHaveAttribute('data-slot', 'button')
    expect(downloadButton).toHaveAttribute('data-slot', 'button')
    expect(selectButton.contains(downloadButton)).toBe(false)
    expect(selectButton).toHaveAttribute('aria-pressed', 'true')

    fireEvent.click(selectButton)
    expect(onSelect).toHaveBeenCalledWith(artifact)
    fireEvent.click(downloadButton)
    await waitFor(() => expect(downloadArtifact).toHaveBeenCalledWith(artifact))
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('keeps a download failure visible in a persistent Alert', async () => {
    vi.mocked(downloadArtifact).mockRejectedValueOnce(new Error('Signed URL expired'))
    renderWithProviders(<ArtifactBrowser artifacts={[artifact]} onSelect={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Download target.pdb' }))

    const message = await screen.findByText('Signed URL expired')
    expect(message.closest('[data-slot="alert"]')).toBeInTheDocument()
  })
})

describe('ArtifactUploadDropzone', () => {
  it('retains one hidden input and calls onUploaded only after persistence completes', async () => {
    const pending = deferred<Artifact>()
    const onUploaded = vi.fn()
    vi.mocked(uploadArtifact).mockReturnValueOnce(pending.promise)
    renderWithProviders(
      <ArtifactUploadDropzone projectId="project-one" onUploaded={onUploaded} />,
    )

    const input = screen.getByLabelText('Artifact file')
    const trigger = screen.getByRole('button', { name: 'Browse artifact files' })
    expect(input).toHaveAttribute('type', 'file')
    expect(input).toHaveClass('hidden')
    expect(document.querySelectorAll('input[type="file"]')).toHaveLength(1)
    expect(trigger).toHaveAttribute('data-slot', 'button')

    const file = new File(['ATOM'], 'target.pdb', { type: 'chemical/x-pdb' })
    fireEvent.change(input, { target: { files: [file] } })
    expect(uploadArtifact).toHaveBeenCalledWith(file, 'project-one')
    expect(onUploaded).not.toHaveBeenCalled()
    expect(document.querySelector('[data-slot="progress"]')).toBeInTheDocument()

    pending.resolve(artifact)
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith(artifact, file))
    expect(useToastStore.getState()).toMatchObject({
      message: 'Uploaded: target.pdb',
      tone: 'success',
    })
    expect(document.querySelector('[data-slot="progress"]')).not.toBeInTheDocument()
  })

  it('guards drop mutations when disabled while leaving a persistent error for failures', async () => {
    const onUploaded = vi.fn()
    const { rerender } = renderWithProviders(
      <ArtifactUploadDropzone projectId="project-one" onUploaded={onUploaded} readOnly />,
    )
    const file = new File(['ATOM'], 'target.pdb', { type: 'chemical/x-pdb' })

    expect(screen.getByRole('button', { name: 'Browse artifact files' })).toBeDisabled()
    fireEvent.drop(screen.getByTestId('artifact-dropzone'), {
      dataTransfer: { files: [file] },
    })
    expect(uploadArtifact).not.toHaveBeenCalled()

    vi.mocked(uploadArtifact).mockRejectedValueOnce(new Error('Object upload failed (403)'))
    rerender(<ArtifactUploadDropzone projectId="project-one" onUploaded={onUploaded} />)
    fireEvent.change(screen.getByLabelText('Artifact file'), { target: { files: [file] } })

    const message = await screen.findByText('Object upload failed (403)')
    expect(message.closest('[data-slot="alert"]')).toBeInTheDocument()
    expect(onUploaded).not.toHaveBeenCalled()
  })
})
