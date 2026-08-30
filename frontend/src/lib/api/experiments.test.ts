import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'

import { server } from '../../test/mocks/handlers'
import { uploadExperimentResults } from './experiments'

describe('manual experiment result imports', () => {
  it('waits for completion and returns the actual imported row count', async () => {
    const file = new File(
      ['candidate_ref,experiment_type,pass_status,value,unit\nc-1,BLI_Kd,pass,42,nM\n'],
      'results.csv',
      { type: 'text/csv' },
    )
    server.use(
      http.post('/api/v2/artifact-uploads', () => HttpResponse.json({
        id: 'upload-results',
        upload_url: 'http://minio.test/results',
        required_headers: { 'Content-Type': 'text/csv' },
      }, { status: 201 })),
      http.put('http://minio.test/results', () => new HttpResponse(null, { status: 200 })),
      http.post('/api/v2/artifact-uploads/upload-results/complete', () => HttpResponse.json({
        id: 'artifact-results', project_id: 'project-results', artifact_type: 'score_table',
        filename: file.name, content_type: file.type, status: 'available', size_bytes: file.size,
        checksum_sha256: 'a'.repeat(64), lineage: {}, version: 1,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        download_url: '/api/v2/artifacts/artifact-results',
      })),
      http.post('/api/v2/projects/project-results/experiment-results/imports', () =>
        HttpResponse.json({
          operation_id: 'operation-results',
          artifact_id: 'artifact-results',
          status: 'pending',
        }, { status: 202 })),
      http.get('/api/v2/operations/operation-results', () => HttpResponse.json({
        id: 'operation-results', project_id: 'project-results', organization_id: 'org-results',
        kind: 'experiment_results.import', resource_type: 'artifact', resource_id: 'artifact-results',
        status: 'succeeded', progress: {}, result: { imported: 1 },
        error_code: null, error_message: null, started_at: '2026-07-01T00:00:00Z',
        finished_at: '2026-07-01T00:00:01Z', version: 2,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:01Z',
      })),
    )

    await expect(uploadExperimentResults(file, 'project-results')).resolves.toEqual({
      imported: 1,
      batch_id: 'operation-results',
    })
  })

  it('surfaces a terminal import failure instead of reporting zero imported rows', async () => {
    const file = new File(['experiment_type,value\nBLI_Kd,42\n'], 'invalid-results.csv', {
      type: 'text/csv',
    })
    server.use(
      http.post('/api/v2/artifact-uploads', () => HttpResponse.json({
        id: 'upload-invalid-results',
        upload_url: 'http://minio.test/invalid-results',
        required_headers: { 'Content-Type': 'text/csv' },
      }, { status: 201 })),
      http.put('http://minio.test/invalid-results', () => new HttpResponse(null, { status: 200 })),
      http.post('/api/v2/artifact-uploads/upload-invalid-results/complete', () => HttpResponse.json({
        id: 'artifact-invalid-results', project_id: 'project-results', artifact_type: 'score_table',
        filename: file.name, content_type: file.type, status: 'available', size_bytes: file.size,
        checksum_sha256: 'b'.repeat(64), lineage: {}, version: 1,
        created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        download_url: '/api/v2/artifacts/artifact-invalid-results',
      })),
      http.post('/api/v2/projects/project-results/experiment-results/imports', () =>
        HttpResponse.json({
          operation_id: 'operation-invalid-results',
          artifact_id: 'artifact-invalid-results',
          status: 'pending',
        }, { status: 202 })),
      http.get('/api/v2/operations/operation-invalid-results', () => HttpResponse.json({
        id: 'operation-invalid-results', project_id: 'project-results',
        organization_id: 'org-results', kind: 'experiment_results.import',
        resource_type: 'artifact', resource_id: 'artifact-invalid-results',
        status: 'failed', progress: {}, result: {},
        error_code: 'invalid_experiment_rows', error_message: 'No valid experiment rows',
        started_at: '2026-07-01T00:00:00Z', finished_at: '2026-07-01T00:00:01Z',
        version: 2, created_at: '2026-07-01T00:00:00Z',
        updated_at: '2026-07-01T00:00:01Z',
      })),
    )

    await expect(uploadExperimentResults(file, 'project-results')).rejects.toThrow(
      'No valid experiment rows',
    )
  })
})
