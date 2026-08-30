import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import type {
  ButtonHTMLAttributes,
  ReactElement,
  ReactNode,
} from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Project } from '../../lib/api/projects'
import type { ProjectTargetStructure, TargetReadiness } from '../../lib/schemas/target'
import { renderWithProviders } from '../../test/renderWithProviders'
import { ActiveProjectPanel } from './ActiveProjectPanel'

const hookState = vi.hoisted(() => ({
  target: null as ProjectTargetStructure | null,
  readiness: {
    stage: 'structure_prepared',
    ready_for_workflow: false,
    blockers: ['approval_required'],
    next_action: 'Approve structure',
    target_id: 'target_a',
    structure_artifact_id: 'artifact_a',
    identity_status: 'confirmed',
    structure_status: 'prepared',
  } satisfies TargetReadiness,
  prepare: vi.fn(),
  approve: vi.fn(),
}))

interface MockButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children?: ReactNode
  render?: ReactElement
  variant?: string
  size?: string
  nativeButton?: boolean
}

vi.mock('@/components/ui/Button', async () => {
  const { cloneElement, isValidElement } = await import('react')
  return {
    Button: (buttonProps: MockButtonProps) => {
      const { children, render, disabled, ...props } = buttonProps
      delete props.variant
      delete props.size
      delete props.nativeButton
      if (isValidElement<Record<string, unknown>>(render)) {
        return cloneElement(render, {
          ...props,
          'aria-disabled': disabled ? 'true' : undefined,
          children,
        })
      }
      return (
        <button
          type="button"
          data-slot="button"
          aria-disabled={disabled ? 'true' : undefined}
          {...props}
        >
          {children}
        </button>
      )
    },
  }
})

vi.mock('../../lib/hooks/useProjectTargetStructure', () => ({
  useProjectTargetStructure: () => ({
    data: hookState.target,
    isLoading: false,
  }),
  useTargetReadiness: () => ({
    data: hookState.readiness,
  }),
}))

vi.mock('../../lib/api/projects', async (importOriginal) => {
  const original = await importOriginal<typeof import('../../lib/api/projects')>()
  return {
    ...original,
    prepareTargetStructure: hookState.prepare,
    approveTargetStructure: hookState.approve,
  }
})

vi.mock('../pdb-viewer/ProjectTargetViewer', () => ({
  ProjectTargetViewer: () => <div>Target viewer</div>,
}))

vi.mock('./TargetStructureOverlay', () => ({
  TargetStructureOverlay: () => <div>Target overlay</div>,
}))

const project = {
  id: 'proj_test',
  organization_id: 'org_test',
  name: 'Read-only project',
  project_type: 'binder_design',
  status: 'active',
  owner_id: 'user_test',
  summary: '',
  prompt: null,
  primary_target_id: 'target_a',
  version: 1,
  created_at: '2026-07-01T00:00:00Z',
  updated_at: '2026-07-01T00:00:00Z',
} satisfies Project

const target = {
  target: {
    id: 'target_a',
    project_id: project.id,
    name: 'Target A',
    sequence: null,
    uniprot_accession: null,
    organism: null,
    identity_status: 'confirmed',
    structure_artifact_id: 'artifact_a',
    structure_status: 'prepared',
    target_kind: 'protein' as const,
    chemical_identity: {},
    version: 1,
    created_at: '2026-07-01T00:00:00Z',
    updated_at: '2026-07-01T00:00:00Z',
  },
  structure: {
    target_id: 'target_a',
    structure_status: 'prepared',
    current_artifact_id: 'artifact_a',
    approved_revision_id: null,
    latest_revision: {
      id: 'revision_a',
      target_id: 'target_a',
      source_artifact_id: 'artifact_a',
      prepared_artifact_id: 'artifact_a',
      status: 'prepared',
      approved: false,
      options: {},
      version: 1,
      created_at: '2026-07-01T00:00:00Z',
      updated_at: '2026-07-01T00:00:00Z',
    },
  },
  artifact: null,
} satisfies ProjectTargetStructure

describe('ActiveProjectPanel read-only mutation gates', () => {
  beforeEach(() => {
    hookState.target = target
    hookState.prepare.mockReset()
    hookState.approve.mockReset()
  })

  afterEach(cleanup)

  it('disables prepare and approve and guards both mutation endpoints', async () => {
    renderWithProviders(
      <ActiveProjectPanel
        project={project}
        projectQuery="?project=proj_test"
        readOnly
        onManage={vi.fn()}
        onCreate={vi.fn()}
      />,
    )

    const prepare = screen.getByRole('button', { name: 'Prepare structure' })
    const approve = screen.getByRole('button', { name: 'Approve prepared structure' })
    expect(prepare).toHaveAttribute('aria-disabled', 'true')
    expect(approve).toHaveAttribute('aria-disabled', 'true')
    fireEvent.click(prepare)
    expect(await screen.findByText('This demo project is read-only.')).toBeInTheDocument()
    fireEvent.click(approve)
    await waitFor(() =>
      expect(screen.getAllByText('This demo project is read-only.')).toHaveLength(2),
    )
    expect(hookState.prepare).not.toHaveBeenCalled()
    expect(hookState.approve).not.toHaveBeenCalled()
  })
})
