import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { GateInspector } from './GateInspector'
import { GatePolicyEditor } from './GatePolicyEditor'
import { emptyPolicy, gateLabel, type GateSummary } from './gates'
import { releaseGate, gateResults, retryGate } from '../../lib/api/workflowGates'
import { WorkflowNodeCard } from './WorkflowNode'

vi.mock('../../lib/i18n', () => ({
  useI18n: () => ({ language: 'zh', t: { shared: { status: { notStarted: '未开始' } } } }),
}))
vi.mock('../../lib/api/workflowGates', () => ({
  gateResults: vi.fn(),
  releaseGate: vi.fn(),
  retryGate: vi.fn(),
  previewGate: vi.fn(),
  previewSources: vi.fn().mockResolvedValue({ items: [] }),
}))
vi.mock('../../lib/api/artifacts', () => ({
  getArtifact: vi.fn().mockRejectedValue(new Error('Synthetic preview error')),
}))
vi.mock('@xyflow/react', () => ({
  Handle: ({ id, type }: { id: string; type: string }) => (
    <span data-testid={`${type}-${id}`}>{id}</span>
  ),
  Position: { Left: 'left', Right: 'right' },
}))

const gate: GateSummary = {
  id: 'gate',
  edge_id: 'edge',
  status: 'awaiting_review',
  version: 3,
  revision: 1,
  preview: false,
  total: 2,
  passed: 1,
  selected: 0,
  selected_ids: [],
  created_at: '2026-09-08T00:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(gateResults).mockResolvedValue({
    gate,
    total: 2,
    items: [
      {
        id: 'keep',
        key: 'keep',
        passed: true,
        selected: false,
        reasons: [],
        metrics: { score: 90 },
        files: [],
      },
      {
        id: 'drop',
        key: 'drop',
        passed: false,
        selected: false,
        reasons: ['score too low'],
        metrics: { score: 10 },
        files: [],
      },
    ],
  })
  vi.mocked(releaseGate).mockResolvedValue({
    ...gate,
    status: 'materializing',
    selected_ids: ['keep'],
  })
})

function inspector(runs: GateSummary[] = [gate]) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={cache}>
      <GateInspector
        workflowId="wf"
        edge={{
          id: 'edge',
          source: 'mpnn',
          target: 'af2',
          source_port: 'sequences',
          target_port: 'sequences',
          gate: { ...emptyPolicy(), mode: 'review' },
        }}
        runs={runs}
        readOnly
        onSave={vi.fn()}
        onClose={vi.fn()}
        onSource={vi.fn()}
        onArtifact={vi.fn()}
        onEditMapping={vi.fn()}
        onDelete={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

describe('workflow gates', () => {
  it('shows the actual integrity contract without silently ignored candidate controls', () => {
    render(<GatePolicyEditor value={{ ...emptyPolicy(), mode: 'integrity' }} onChange={vi.fn()} />)
    expect(screen.getByText('完整性检查：核对文件大小和 SHA256 后放行。')).toBeVisible()
    expect(screen.queryByText('条件组合')).not.toBeInTheDocument()
  })
  it('keeps runtime review available on a locked graph and only submits qualified IDs', async () => {
    inspector()
    await screen.findByText('score too low')
    fireEvent.click(screen.getByRole('button', { name: '选择本页合格项' }))
    fireEvent.click(screen.getByRole('button', { name: '放行所选 (1)' }))
    await waitFor(() => expect(releaseGate).toHaveBeenCalledWith('wf', gate, ['keep']))
    expect(screen.getByRole('button', { name: '保存规则' })).toBeDisabled()
  })
  it('does not label a configured but unevaluated gate as passed', () => {
    expect(gateLabel({ ...emptyPolicy(), configured: true }, undefined, true)).toBe('等待上游')
    expect(gateLabel(emptyPolicy(), undefined, true)).toBe('待配置门控')
    expect(gateLabel(undefined, { ...gate, status: 'released', selected: 1 }, true)).toBe(
      '已放行 1 / 2',
    )
  })
  it('shows incomplete structure data as needing attention and excludes it from release', async () => {
    vi.mocked(gateResults).mockResolvedValue({
      gate,
      total: 1,
      items: [
        {
          id: 'incomplete',
          key: 'incomplete',
          passed: false,
          needs_attention: true,
          selected: false,
          reasons: ['backbone_atoms_missing:B'],
          metrics: {},
          files: [],
        },
      ],
    })
    inspector()
    expect(await screen.findByText('待处理')).toBeVisible()
    fireEvent.click(screen.getAllByRole('checkbox').at(-1)!)
    fireEvent.click(screen.getByRole('button', { name: '选择本页合格项' }))
    expect(screen.getByRole('button', { name: '不保留结果，结束分支' })).toBeVisible()
  })
  it('switches to the replacement evaluation after a retry', async () => {
    const failed = { ...gate, id: 'failed', status: 'error' }
    const replacement = { ...gate, id: 'replacement', revision: 2, status: 'waiting' }
    vi.mocked(retryGate).mockResolvedValue(replacement)
    inspector([failed, replacement])
    fireEvent.click(await screen.findByRole('button', { name: '重试筛选' }))
    await waitFor(() => expect(retryGate).toHaveBeenCalledWith('wf', 'failed'))
    await waitFor(() =>
      expect(gateResults).toHaveBeenCalledWith('wf', 'replacement', '', 0, '', true),
    )
  })
  it('opens file preview in an accessible dialog and dismisses with Escape', async () => {
    vi.mocked(gateResults).mockResolvedValue({
      gate,
      total: 1,
      items: [
        {
          id: 'file',
          key: 'file',
          passed: true,
          selected: false,
          reasons: [],
          metrics: {},
          files: [{ artifact_id: 'artifact', port: 'sequences', selector: { format: 'fasta' } }],
        },
      ],
    })
    inspector()
    fireEvent.click(await screen.findByRole('button', { name: '序列、指标与文件' }))
    fireEvent.click(await screen.findByRole('button', { name: '预览文件 · sequences' }))
    const dialog = await screen.findByRole('dialog')
    expect(dialog).toBeVisible()
    fireEvent.keyDown(dialog, { key: 'Escape' })
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
  it('renders explicit named input and output handles', () => {
    render(
      <WorkflowNodeCard
        {...({
          data: {
            label: 'Node',
            status: 'not_started',
            inputPorts: ['backbone'],
            outputPorts: ['sequences'],
          },
          selected: false,
          id: 'test-node',
          type: 'workflowNode',
          dragging: false,
          zIndex: 0,
          selectable: true,
          deletable: true,
          draggable: true,
          isConnectable: true,
          positionAbsoluteX: 0,
          positionAbsoluteY: 0,
        } as Parameters<typeof WorkflowNodeCard>[0])}
      />,
    )
    expect(screen.getByTestId('target-backbone')).toBeVisible()
    expect(screen.getByTestId('source-sequences')).toBeVisible()
  })
})
