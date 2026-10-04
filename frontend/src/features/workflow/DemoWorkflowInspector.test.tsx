import { cleanup, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { renderWithProviders } from '../../test/renderWithProviders'
import { useAppStore } from '../../lib/store/appStore'
import { DemoWorkflowInspector } from './DemoWorkflowInspector'
import { getDemoWorkflow } from './demoWorkflow'

afterEach(cleanup)

describe('the read-only workflow example', () => {
  it.each(['en', 'zh'] as const)('uses the same localized data for all canvas nodes and inspector steps (%s)', (language) => {
    const graph = getDemoWorkflow(language)
    expect(graph.nodes).toHaveLength(8)
    expect(graph.nodes.map(node => node.id)).toEqual(graph.steps.map(step => step.node.id))
    expect(graph.nodes.every(node => node.data.status === 'demo')).toBe(true)
    expect(graph.nodes.every(node => !/\d/.test(node.data.footer))).toBe(true)
    expect(graph.edges.every(edge => !edge.animated)).toBe(true)
    for (const step of graph.steps) {
      expect(step.inputs).toBeTruthy()
      expect(step.outputs).toBeTruthy()
      expect(step.checks).toBeTruthy()
      expect(step.node.data.label).toBeTruthy()
    }
  })

  it.each(['en', 'zh'] as const)('explains the selected node without exposing execution controls (%s)', (language) => {
    useAppStore.setState({ language })
    const graph = getDemoWorkflow(language)
    const selectedStep = graph.steps.find(step => step.node.id === 'mpnn')!
    renderWithProviders(<DemoWorkflowInspector selectedStep={selectedStep} stepCount={graph.steps.length} />)
    expect(screen.getByText(selectedStep.node.data.label)).toBeInTheDocument()
    expect(screen.getByText(selectedStep.inputs)).toBeInTheDocument()
    expect(screen.getByText(selectedStep.outputs)).toBeInTheDocument()
    expect(screen.getByText(selectedStep.checks)).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(language === 'zh' ? '未执行计算' : 'has not executed')
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })
})
