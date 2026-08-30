import { describe, expect, it } from 'vitest'
import { http, HttpResponse } from 'msw'

import {
  analyzeTargetIntelligence,
  applyRoutePlan,
  applyTargetDesignRoute,
  exportTargetDossier,
  getCopilotConfig,
  getTargetIntelligenceRun,
  planRoute,
  updateCopilotConfig,
} from './copilot'
import { server } from '../../test/mocks/handlers'

describe('target intelligence api', () => {
  it('parses copilot config responses without an API key preview', async () => {
    const configPayload = {
      id: 'config_test',
      project_id: 'proj_test',
      llm_provider_id: 'provider_test',
      api_key_configured: true,
      settings: {
        llm_api_base: 'https://api.openai.com/v1',
        llm_model: 'gpt-4o-mini',
        system_prompt: 'Use BDA scope.',
      },
      enabled_skills: ['knowledge'],
      version: 1,
    }

    server.use(
      http.get('/api/v2/copilot/projects/proj_test/config', () =>
        HttpResponse.json(configPayload),
      ),
      http.put('/api/v2/copilot/projects/proj_test/config', () =>
        HttpResponse.json(configPayload),
      ),
    )

    await expect(getCopilotConfig('proj_test')).resolves.toMatchObject({
      api_key_configured: true,
      llm_model: 'gpt-4o-mini',
    })
    await expect(updateCopilotConfig('proj_test', { llm_model: 'gpt-4o-mini' })).resolves.toMatchObject({
      api_key_configured: true,
      llm_api_base: 'https://api.openai.com/v1',
    })
  })

  it('keeps the capabilities a project already had when settings are saved', async () => {
    // A hard-coded list here silently revoked every capability added after it
    // was written — the bench tools and agent orchestration among them — so a
    // save could leave an agent run with no tools it was allowed to call.
    const configPayload = {
      id: 'config_keep',
      project_id: 'proj_keep',
      llm_provider_id: null,
      api_key_configured: false,
      settings: { llm_api_base: '', llm_model: '', system_prompt: '' },
      enabled_skills: ['project-read', 'agent-orchestration'],
      version: 4,
    }
    const sent: unknown[] = []
    server.use(
      http.get('/api/v2/copilot/projects/proj_keep/config', () => HttpResponse.json(configPayload)),
      http.put('/api/v2/copilot/projects/proj_keep/config', async ({ request }) => {
        sent.push(await request.json())
        return HttpResponse.json(configPayload)
      }),
    )

    await updateCopilotConfig('proj_keep', { llm_model: 'gpt-4o-mini' })

    expect(sent[0]).toMatchObject({
      enabled_skills: ['project-read', 'agent-orchestration'],
    })
  })

  it('falls back to the server-side default set for a project with none', async () => {
    const configPayload = {
      id: 'config_new',
      project_id: 'proj_new',
      llm_provider_id: null,
      api_key_configured: false,
      settings: { llm_api_base: '', llm_model: '', system_prompt: '' },
      enabled_skills: [],
      version: 1,
    }
    const sent: unknown[] = []
    server.use(
      http.get('/api/v2/copilot/projects/proj_new/config', () => HttpResponse.json(configPayload)),
      http.put('/api/v2/copilot/projects/proj_new/config', async ({ request }) => {
        sent.push(await request.json())
        return HttpResponse.json(configPayload)
      }),
    )

    await updateCopilotConfig('proj_new', { llm_model: 'gpt-4o-mini' })

    // "research" is an alias the server expands, so the client never has to
    // keep its own copy of the default set in step.
    expect(sent[0]).toMatchObject({ enabled_skills: ['research'] })
  })

  it('parses target intelligence endpoints', async () => {
    server.use(
      http.get('/api/v2/projects/proj_test/primary-target', () =>
        HttpResponse.json({ id: 'target_test' }),
      ),
      http.post('/api/v2/projects/proj_test/intelligence-runs', () =>
        HttpResponse.json({ id: 'target_run_test' }),
      ),
      http.get('/api/v2/intelligence-runs/target_run_test', () =>
        HttpResponse.json({
          run: {
              id: 'target_run_test',
              project_id: 'proj_test',
              target_id: 'target_test',
              query: { target_query: 'Example receptor', objective: 'design an antibody', modality: 'antibody' },
              status: 'succeeded',
              created_at: '2026-07-04T00:00:00Z',
              updated_at: '2026-07-04T00:00:00Z',
            },
          report: null,
          evidence: [],
          hotspots: [],
          routes: [],
        }),
      ),
      http.post('/api/v2/design-routes/antibody_diffab_cdr_design/apply', () =>
        HttpResponse.json({
          id: 'run_target', project_id: 'proj_test', name: 'Applied route', status: 'draft', graph: {}, version: 1,
        }),
      ),
      http.post('/api/v2/intelligence-runs/target_run_test/exports', () =>
        HttpResponse.json({ run_id: 'target_run_test', status: 'pending' }),
      ),
    )

    const analyzed = await analyzeTargetIntelligence({
      project_id: 'proj_test',
      target_query: 'Example receptor',
      objective: 'design an antibody',
      modality: 'antibody',
    })
    expect(analyzed.target.name).toBe('Example receptor')

    const detail = await getTargetIntelligenceRun('target_run_test')
    expect(detail.run.status).toBe('succeeded')

    const applied = await applyTargetDesignRoute('target_run_test', {
      project_id: 'proj_test',
      route_id: 'antibody_diffab_cdr_design',
      selected_module_ids: ['diffab'],
    })
    expect(applied.status).toBe('applied')

    const exported = await exportTargetDossier('target_run_test', 'markdown')
    expect(exported.filename).toMatch(/\.md$/)
  })

  it('maps route modules and creates an executable workflow graph', async () => {
    server.use(
      http.post('/api/v2/copilot/route-plans', () => HttpResponse.json({
        project_id: 'proj_test',
        goal: 'design a binder',
        recommended_route: 'de-novo-binder-pooled',
        rationale: ['Use structure-conditioned design.'],
        evidence_refs: [],
        workflow_spec: {
          name: 'design a binder',
          nodes: [{
            key: 'rfdiffusion-1',
            node_type: 'RFdiffusion',
            model_plugin: 'RFdiffusion',
            model_plugin_id: 'plugin-rf',
            container_image: 'rf:test',
            command: 'python run.py',
            parameters: { noise_scale_ca: 0 },
            parameter_schema: {},
            available: true,
          }],
          edges: [],
        },
        knowledge_context: [{
          knowledge_entry_id: 'knowledge-methods',
          title: 'Methods',
          category: 'methods',
          summary: 'De novo binder design methods for chronic-pain targets',
        }],
        route_options: [{
          route_id: 'de-novo-binder-pooled',
          label: 'De novo binder, pooled',
          rank: 1,
          recommended: true,
          summary: 'High-volume generation sized for a pooled screen.',
          rationale: ['Hotspot choice is the highest-variance decision.'],
          risks: ['Thresholds are a starting guess until a control target has been run.'],
          constraints: { tier_a: { pae_interaction: '< 15' } },
          estimated_steps: 1,
          modules: [{
            module_id: 'plugin-rf',
            model_plugin_id: 'plugin-rf',
            model_name: 'RFdiffusion',
            node_type: 'RFdiffusion',
            available: true,
            summary: 'Generate binder backbones against the selected hotspot set.',
            default_parameters: { noise_scale_ca: 0 },
            parameter_schema: {},
          }],
          workflow_spec: { name: 'design a binder', nodes: [], edges: [] },
        }],
      })),
      http.get('/api/v2/registry/model-plugins', () => HttpResponse.json({
        items: [{
          id: 'plugin-rf', plugin_key: 'RFdiffusion', plugin_version: '1',
          name: 'RFdiffusion', container_image: 'rf:test', command: 'python run.py',
          parameter_schema: {}, output_schema: {}, enabled: true, validation_status: 'valid',
          validated_at: null, validation_errors: [], version: 1,
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        }],
        next_cursor: null,
      })),
      http.post('/api/v2/projects/proj_test/workflow-runs', async ({ request }) => {
        const body = await request.json() as {
          nodes: Array<{ model_plugin_id: string; parameters: Record<string, unknown> }>
        }
        expect(body.nodes[0].model_plugin_id).toBe('plugin-rf')
        // The route's recommended defaults must survive onto the created node.
        expect(body.nodes[0].parameters).toEqual({ noise_scale_ca: 0 })
        return HttpResponse.json({
          id: 'workflow-route', project_id: 'proj_test', name: 'design a binder',
          status: 'draft', graph: {}, version: 1, created_by: 'user-test',
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        }, { status: 201 })
      }),
      http.get('/api/v2/workflow-runs/workflow-route/graph', () => HttpResponse.json({
        workflow: {
          id: 'workflow-route', project_id: 'proj_test', name: 'design a binder',
          status: 'draft', graph: {}, version: 1, created_by: 'user-test',
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        },
        nodes: [{
          id: 'node-rf', workflow_run_id: 'workflow-route', node_key: 'rfdiffusion-1',
          node_type: 'RFdiffusion', model_plugin: 'RFdiffusion', model_plugin_id: 'plugin-rf',
          container_image: 'rf:test', command: 'python run.py', queue: null, status: 'draft',
          parameters: {}, error_message: null, position: null, version: 1,
          created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z',
        }],
        edges: [],
        layout: {},
      })),
    )

    const planned = await planRoute({
      project_id: 'proj_test',
      objective: 'design a binder',
    })
    expect(planned.route_options[0].modules).toHaveLength(1)
    expect(planned.route_options[0].modules[0].default_parameters).toEqual({ noise_scale_ca: 0 })
    expect(planned.route_options[0].constraints).toEqual({ tier_a: { pae_interaction: '< 15' } })
    expect(planned.knowledge_context[0].title).toBe('Methods')

    const applied = await applyRoutePlan({
      project_id: 'proj_test',
      route_id: 'de-novo-binder-pooled',
      objective: 'design a binder',
      selected_module_ids: ['plugin-rf'],
      module_parameters: { 'plugin-rf': { noise_scale_ca: 0 } },
    })
    expect(applied.nodes[0].id).toBe('node-rf')
  })
})
