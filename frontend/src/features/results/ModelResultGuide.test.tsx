import { readFileSync } from 'node:fs'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAppStore } from '../../lib/store/appStore'
import { ModelResultGuide, ModelResultGuideLibrary } from './ModelResultGuide'
import { findModelResultGuide, modelResultGuides } from './modelResultGuides'

afterEach(cleanup)

describe('model result guidance', () => {
  it('covers every QM registry plugin without ambiguous aliases', () => {
    const registry = JSON.parse(readFileSync('../qm-scripts/plugins/registry.json', 'utf8'))
    for (const plugin of registry.plugins) {
      expect(findModelResultGuide(plugin.plugin_key)?.pluginKey).toBe(plugin.plugin_key)
    }
    for (const guide of modelResultGuides) {
      for (const alias of guide.aliases) {
        expect(findModelResultGuide(alias)?.pluginKey).toBe(guide.pluginKey)
      }
    }
    expect(findModelResultGuide('RFdiffusion3 (atom-level motif)')?.pluginKey).toBe('RFdiffusion3')
    expect(findModelResultGuide('ProteinHunter (Boltz)')?.pluginKey).toBe('proteinhunter_boltz')
    expect(findModelResultGuide('Rosetta InterfaceAnalyzer')?.pluginKey).toBe('Rosetta')
    expect(findModelResultGuide('unknown-af3-derived-model')).toBeUndefined()
  })

  it('opens Chinese AF3 guidance with uncertainty and original documentation', () => {
    useAppStore.setState({ language: 'zh' })
    render(<ModelResultGuide pluginKey="af3" />)
    fireEvent.click(screen.getByText('AlphaFold 3 · 结果判读指南'))
    expect(screen.getByText(/不能仅凭 pLDDT >80 放行/)).toBeVisible()
    expect(screen.getByText(/缺失、非有限值或量纲不明/)).toBeVisible()
    expect(screen.getByRole('link', { name: '指标说明来源' })).toHaveAttribute(
      'href', 'https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md',
    )
  })

  it('keeps Rosetta thresholds scoped to interface ddG and matching protocols', () => {
    useAppStore.setState({ language: 'en' })
    render(<ModelResultGuide pluginKey="Rosetta" />)
    fireEvent.click(screen.getByText('Rosetta · Result interpretation guide'))
    expect(screen.getByText(/Do not apply to total_score/)).toBeVisible()
    expect(screen.getByText(/after control calibration/)).toBeVisible()
  })

  it('provides an unassessed fallback for future plugins and a complete library', () => {
    useAppStore.setState({ language: 'en' })
    const { unmount } = render(<ModelResultGuide pluginKey="Custom model" />)
    fireEvent.click(screen.getByText('Custom model · Result interpretation guide'))
    expect(screen.getByText(/No model-specific guide is registered/)).toBeVisible()
    unmount()
    render(<ModelResultGuideLibrary />)
    fireEvent.click(screen.getByText('Model outputs · Interpretation reference library'))
    expect(screen.getAllByRole('button', { name: /· Result interpretation guide/ })).toHaveLength(modelResultGuides.length)
  })
})
