import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { server } from '../../test/mocks/handlers'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { CopilotResearchImportButton } from './CopilotResearchImportButton'
import { GenerateSimilarResearchPanel } from './GenerateSimilarResearchPanel'

const copilotJson = JSON.stringify({
  schema_version: '1.0',
  project: { name: 'Imported graph' },
  references: [],
  nodes: [],
})

describe('Copilot research import flow', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('validates and imports an assistant JSON result with one action', async () => {
    const onImported = vi.fn()
    server.use(
      http.post('/api/v2/copilot-research-imports', async ({ request }) => {
        expect(await request.json()).toEqual({ organization_id: 'org_test', result: copilotJson })
        return HttpResponse.json({
          project_id: 'proj_imported',
          project_name: 'Imported graph',
          status: 'created',
          checksum: 'abc123',
          counts: { projects: 1, references: 1, nodes: 2, edges: 1, candidates: 1 },
        }, { status: 201 })
      }),
    )

    renderWithProviders(
      <CopilotResearchImportButton
        organizationId="org_test"
        content={copilotJson}
        onImported={onImported}
      />,
    )
    const importButton = screen.getByRole('button', { name: 'Validate and import' })
    expect(importButton).toHaveAttribute('data-slot', 'button')
    fireEvent.click(importButton)

    await waitFor(() => expect(onImported).toHaveBeenCalledWith(expect.objectContaining({ project_id: 'proj_imported' })))
    expect(screen.getByText(/Created editable project “Imported graph”/)).toBeInTheDocument()
  })

  it('renders exact backend field and reference locations and does not report success', async () => {
    const onImported = vi.fn()
    server.use(
      http.post('/api/v2/copilot-research-imports', () => HttpResponse.json({
        type: 'https://bda.invalid/problems/invalid_copilot_research_references',
        title: 'Invalid Copilot Research References',
        status: 422,
        detail: 'Copilot research result contains invalid fields or references',
        instance: '/api/v2/copilot-research-imports',
        error_code: 'invalid_copilot_research_references',
        trace_id: 'trace_test',
        errors: [{
          kind: 'unknown_reference',
          path: '$.edges[0].reference_ids[0]',
          reference: 'REF-MISSING',
          message: 'Referenced citation is not declared in $.references',
        }],
      }, { status: 422, headers: { 'Content-Type': 'application/problem+json' } })),
    )

    renderWithProviders(
      <CopilotResearchImportButton
        organizationId="org_test"
        content={copilotJson}
        onImported={onImported}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Validate and import' }))

    expect(await screen.findByText(/\$\.edges\[0\]\.reference_ids\[0\].*REF-MISSING/)).toBeInTheDocument()
    expect(onImported).not.toHaveBeenCalled()
    expect(screen.queryByText(/Created editable project/)).not.toBeInTheDocument()
  })

  it('builds and previews a validated v2 draft before import', async () => {
    useAppStore.setState({ language: 'en', activeProjectId: 'proj_test' })
    window.location.hash = '/research?project=proj_test'
    server.use(
      http.get('/api/v2/projects', () => HttpResponse.json({ items: [{
        id: 'proj_test', organization_id: 'org_test', owner_id: 'user_test', name: 'Source',
        project_type: 'research', summary: 'Source summary', status: 'active', primary_target_id: null,
        version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }], next_cursor: null })),
      http.post('/api/v2/projects/proj_test/research-generations', async ({ request }) => {
        expect(await request.json()).toEqual(expect.objectContaining({
          topic: 'Ion channels in pain',
          evidence_cutoff: '2025-12-31',
        }))
        return HttpResponse.json({
          generation_id: 'generation-1', operation_id: 'operation-1', status: 'pending',
        }, { status: 202 })
      }),
      http.get('/api/v2/research-generations/generation-1', () => HttpResponse.json({
        id: 'generation-1', source_project_id: 'proj_test', status: 'ready',
        request: { topic: 'Ion channels in pain', strata: '', candidate_count: 10, language: 'en' },
        draft: {
          counts: { references: 2, methods: 2, datasets: 3 },
          references: [{
            document_id: 'doc-inherited',
            ref_id: 'R001',
            title: { default: 'Inherited evidence paper' },
            authors: 'Source Author',
            doi: '10.1000/inherited',
            verification_status: 'verified',
            metadata: { origin: 'source_project', retrieval_scope: 'full_text' },
          }, {
            document_id: 'doc-discovered',
            ref_id: 'PMID:12345678',
            title: { default: 'New related evidence paper' },
            authors: 'New Author',
            pmid: '12345678',
            verification_status: 'verified_europe_pmc',
            metadata: { origin: 'external_discovery', retrieval_scope: 'metadata_only' },
          }],
          review_sections: [],
          research_targets: [],
          graph_edges: [],
          provenance: { reference_counts: { copied_from_source: 1, newly_discovered: 1 } },
        },
        validation: { valid: true, issues: [], citation_coverage: 1 },
        checksum: 'a'.repeat(64), imported_project_id: null, error: null, version: 2,
      })),
      http.post('/api/v2/research-generations/generation-1/import', () => HttpResponse.json({
        generation_id: 'generation-1',
        project_id: 'proj_generated',
        project_name: 'Ion channels in pain',
        status: 'created',
        checksum: 'a'.repeat(64),
        counts: { references: 2, methods: 2, datasets: 3 },
      }, { status: 201 })),
    )
    renderWithProviders(<GenerateSimilarResearchPanel defaultTopic="Ion channels in pain" />)
    const generateButton = screen.getByRole('button', { name: 'Generate and preview draft' })
    await waitFor(() => expect(generateButton).toBeEnabled())
    fireEvent.change(screen.getByLabelText('Evidence cutoff'), { target: { value: '2025-12-31' } })
    fireEvent.click(generateButton)

    expect(await screen.findByTestId('research-generation-preview')).toBeInTheDocument()
    expect(screen.getByText('references: 2')).toBeInTheDocument()
    expect(screen.getByText('Inherited evidence paper')).toBeInTheDocument()
    expect(screen.getByText('New related evidence paper')).toBeInTheDocument()
    expect(screen.getByText('Inherited: 1')).toBeInTheDocument()
    expect(screen.getByText('Newly discovered: 1')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'DOI 10.1000/inherited' })).toHaveAttribute(
      'href',
      'https://doi.org/10.1000/inherited',
    )
    expect(screen.getByRole('button', { name: 'Confirm and create pending-review project' })).toBeInTheDocument()
    expect(screen.queryByText('Review sections (0)')).not.toBeInTheDocument()

    const recordDetails = screen.getByRole('button', { name: 'Research record details' })
    fireEvent.click(recordDetails)
    expect(screen.getByText('Review sections (0)')).toBeInTheDocument()
    fireEvent.click(recordDetails)
    await waitFor(() => expect(screen.queryByText('Review sections (0)')).not.toBeInTheDocument())

    fireEvent.click(generateButton)
    expect(screen.queryByTestId('research-generation-preview')).not.toBeInTheDocument()
    expect(await screen.findByTestId('research-generation-preview')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Confirm and create pending-review project' }))
    await waitFor(() => expect(window.location.hash).toContain(
      '/research?project=proj_generated&tab=references',
    ))
  })

  it('blocks confirmation when a required category is missing', async () => {
    useAppStore.setState({ language: 'en', activeProjectId: 'proj_test' })
    window.location.hash = '/research?project=proj_test'
    server.use(
      http.get('/api/v2/projects', () => HttpResponse.json({ items: [{
        id: 'proj_test', organization_id: 'org_test', owner_id: 'user_test', name: 'Source',
        project_type: 'research', summary: 'Source summary', status: 'active', primary_target_id: null,
        version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }], next_cursor: null })),
      http.post('/api/v2/projects/proj_test/research-generations', () => HttpResponse.json({
        generation_id: 'generation-incomplete', operation_id: 'operation-2', status: 'pending',
      }, { status: 202 })),
      http.get('/api/v2/research-generations/generation-incomplete', () => HttpResponse.json({
        id: 'generation-incomplete', source_project_id: 'proj_test', status: 'ready',
        request: { topic: 'Incomplete', strata: '', candidate_count: 10, language: 'en' },
        draft: { counts: { references: 1 }, references: [], provenance: {} },
        validation: {
          valid: false,
          issues: [{ kind: 'missing_required_category', detail: 'research_targets must contain a record' }],
          missing_categories: ['research_targets'],
        },
        checksum: 'b'.repeat(64), imported_project_id: null,
        error: 'draft_confirmation_blocked', version: 2,
      })),
    )

    renderWithProviders(<GenerateSimilarResearchPanel defaultTopic="Incomplete" />)
    const generateButton = screen.getByRole('button', { name: 'Generate and preview draft' })
    await waitFor(() => expect(generateButton).toBeEnabled())
    fireEvent.click(generateButton)

    expect(await screen.findByText('Draft incomplete; confirmation is blocked')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm and create pending-review project' })).toBeDisabled()
  })

  it('fails closed when a legacy ready draft has no explicit valid result', async () => {
    useAppStore.setState({ language: 'en', activeProjectId: 'proj_test' })
    server.use(
      http.get('/api/v2/projects', () => HttpResponse.json({ items: [{
        id: 'proj_test', organization_id: 'org_test', owner_id: 'user_test', name: 'Source',
        project_type: 'research', summary: 'Source summary', status: 'active', primary_target_id: null,
        version: 1, created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
      }], next_cursor: null })),
      http.post('/api/v2/projects/proj_test/research-generations', () => HttpResponse.json({
        generation_id: 'generation-legacy', operation_id: 'operation-legacy', status: 'pending',
      }, { status: 202 })),
      http.get('/api/v2/research-generations/generation-legacy', () => HttpResponse.json({
        id: 'generation-legacy', source_project_id: 'proj_test', status: 'ready',
        request: { topic: 'Legacy draft', strata: '', candidate_count: 10, language: 'en' },
        draft: { counts: { references: 1 }, references: [], provenance: {} },
        validation: { issues: [] },
        checksum: 'c'.repeat(64), imported_project_id: null, error: null, version: 1,
      })),
    )

    renderWithProviders(<GenerateSimilarResearchPanel defaultTopic="Legacy draft" />)
    const generateButton = screen.getByRole('button', { name: 'Generate and preview draft' })
    await waitFor(() => expect(generateButton).toBeEnabled())
    fireEvent.click(generateButton)

    expect(await screen.findByText('Draft incomplete; confirmation is blocked')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirm and create pending-review project' })).toBeDisabled()
  })

  it('updates an untouched default topic without overwriting a user edit', async () => {
    useAppStore.setState({ language: 'en', activeProjectId: 'proj_test' })
    const rendered = renderWithProviders(<GenerateSimilarResearchPanel defaultTopic="First project" />)
    const topic = screen.getByRole('textbox', { name: 'Research topic' })
    expect(topic).toHaveValue('First project')

    rendered.rerender(<GenerateSimilarResearchPanel defaultTopic="Second project" />)
    expect(topic).toHaveValue('Second project')

    fireEvent.change(topic, { target: { value: 'My custom topic' } })
    rendered.rerender(<GenerateSimilarResearchPanel defaultTopic="第三个项目" />)
    expect(topic).toHaveValue('My custom topic')
  })
})
