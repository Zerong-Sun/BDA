import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { WorkflowSelect, WorkflowOption } from './WorkflowControls'
import { GatePolicyEditor } from './GatePolicyEditor'
import { NodeAssistance } from './NodeAssistance'
import { emptyPolicy } from './gates'
import type { WorkflowNode } from '../../lib/schemas/workflow'

vi.mock('../../lib/i18n', () => ({ useI18n: () => ({ language: 'zh' }) }))
vi.mock('../../lib/api/workflowGates', () => ({ importScript: vi.fn(), suggestParameters: vi.fn() }))

beforeEach(() => vi.clearAllMocks())

describe('workflow usability', () => {
  it('displays labels before opening and lets users return to the default selection', async () => {
    function Form() {
      const [value, setValue] = useState('job-uuid')
      return <WorkflowSelect aria-label="试运行数据" value={value} onChange={(event) => setValue(event.target.value)}>
        <WorkflowOption value="">当前上游结果</WorkflowOption>
        <WorkflowOption value="job-uuid">上游第 2 次运行</WorkflowOption>
      </WorkflowSelect>
    }
    render(<Form />)
    expect(screen.getByRole('combobox')).toHaveTextContent('上游第 2 次运行')
    fireEvent.click(screen.getByRole('combobox'))
    const option = await screen.findByRole('option', { name: '当前上游结果' })
    fireEvent.pointerDown(option, { button: 0 })
    fireEvent.pointerUp(option, { button: 0 })
    fireEvent.click(option)
    await waitFor(() => expect(screen.getByRole('combobox')).toHaveTextContent('当前上游结果'))
  })

  it('accepts design chains typed one character at a time and preserves a trailing separator', () => {
    const changed = vi.fn()
    function Form() {
      const [policy, setPolicy] = useState({ ...emptyPolicy(), structure: { chains: ['A'], min_helices: 2, min_helix_length: 4 } })
      return <GatePolicyEditor value={policy} onChange={(value) => { changed(value); setPolicy(value as typeof policy) }} />
    }
    render(<Form />)
    const chains = screen.getByLabelText('设计链（必填，逗号分隔）')
    fireEvent.change(chains, { target: { value: 'A,' } })
    expect(chains).toHaveValue('A,')
    fireEvent.change(chains, { target: { value: 'A,B' } })
    expect(changed.mock.lastCall?.[0].structure.chains).toEqual(['A', 'B'])
  })

  it('disables the visible script import action on a locked node', () => {
    render(<NodeAssistance workflowId="wf" node={{ input_bindings: [] } as unknown as WorkflowNode} nodes={[]} configuration={{}} onConfiguration={vi.fn()} onParameter={vi.fn()} readOnly allowedParameters={[]} />)
    fireEvent.click(screen.getByRole('button', { name: '节点执行脚本：导入与绑定' }))
    expect(screen.getByRole('button', { name: '导入节点脚本' })).toBeDisabled()
  })
})
