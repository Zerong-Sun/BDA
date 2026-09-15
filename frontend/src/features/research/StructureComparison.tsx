import { useNavigate, useSearchParams } from 'react-router'
import type { ResearchWorkspaceStructure } from '../../lib/api/generated/types.gen'
import { workspaceText } from '../../lib/api/researchWorkspace'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { Button } from '../../components/ui/Button'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../components/ui/select'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import { structureSourceFromUrl } from '../pdb-viewer/types'

export function StructureComparison({ structures, projectId }: { structures: ResearchWorkspaceStructure[]; projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const navigate = useNavigate()
  const [search, setSearch] = useSearchParams()
  const compare = search.get('compare') === '1' && structures.length > 1
  const left = structures.find((item) => item.artifact_id === search.get('structureA')) ?? structures[0]
  const right = structures.find((item) => item.artifact_id === search.get('structureB') && item.artifact_id !== left?.artifact_id)
    ?? structures.find((item) => item.artifact_id !== left?.artifact_id)
  const selectStructure = (side: 'left' | 'right', value: string) => {
    const next = new URLSearchParams(search)
    next.set(side === 'left' ? 'structureA' : 'structureB', value)
    if (side === 'left' && value === right?.artifact_id && left) next.set('structureB', left.artifact_id)
    setSearch(next, { replace: true })
  }
  const toggleCompare = () => {
    const next = new URLSearchParams(search)
    if (compare) next.delete('compare')
    else next.set('compare', '1')
    if (left) next.set('structureA', left.artifact_id)
    if (right) next.set('structureB', right.artifact_id)
    setSearch(next, { replace: true })
  }
  const ask = () => {
    const items = compare && right ? [left, right] : [left]
    const state = useAppStore.getState()
    state.setActiveProjectId(projectId)
    state.setCopilotSelectedEntityIds(
      items.map((item) => item.artifact_id),
      projectId,
      Object.fromEntries(items.map((item) => [item.artifact_id, `${item.pdb_id ? `${item.pdb_id} · ` : ''}${workspaceText(item.name, language)}`])),
    )
    state.setCopilotDraft(zh
      ? `请根据项目已有证据解释以下结构：${items.map((item) => `${workspaceText(item.name, language)} (${item.pdb_id || item.artifact_id})`).join('、')}。引用结构和文献来源，区分观察、推断与信息缺口。并排展示不代表结构已经对齐。`
      : `Explain these structures using existing project evidence: ${items.map((item) => `${workspaceText(item.name, language)} (${item.pdb_id || item.artifact_id})`).join('; ')}. Cite structure and literature sources. Distinguish observations, inference and gaps. Side-by-side views do not imply structural alignment.`)
    navigate(`/bots?project=${encodeURIComponent(projectId)}&view=chat`)
  }
  if (!left) return <p className="text-sm text-text-secondary">{zh ? '尚无可用结构。' : 'No structures available yet.'}</p>
  const pane = (item: ResearchWorkspaceStructure, side: 'left' | 'right') => <div className="structure-comparison-pane">
    <div className="text-sm font-medium">{side === 'left' ? (zh ? '结构 A' : 'Structure A') : (zh ? '结构 B' : 'Structure B')}
      <Select items={structures.map((option) => ({ value: option.artifact_id, label: `${option.pdb_id || '—'} · ${workspaceText(option.name, language)}` }))} value={item.artifact_id} onValueChange={(value) => { if (value) selectStructure(side, value) }}>
        <SelectTrigger className="mt-2 w-full" aria-label={side === 'left' ? (zh ? '结构 A' : 'Structure A') : (zh ? '结构 B' : 'Structure B')}><SelectValue /></SelectTrigger>
        <SelectContent>{structures.map((option) => <SelectItem key={option.artifact_id} value={option.artifact_id} disabled={side === 'right' && option.artifact_id === left.artifact_id}>{option.pdb_id || '—'} · {workspaceText(option.name, language)}</SelectItem>)}</SelectContent>
      </Select>
    </div>
    <div className="mt-4">{item.download_url ? <StructureViewerLazy key={item.artifact_id} source={structureSourceFromUrl(item.download_url, {
      projectId, artifactId: item.artifact_id, pdbId: item.pdb_id, proteinName: workspaceText(item.name, language),
      chains: Array.isArray(item.lineage?.chains) ? item.lineage.chains.filter((chain): chain is string => typeof chain === 'string') : undefined,
    })} height={400} showMetadata /> : <div className="science-empty"><p>{zh ? '结构文件尚不可用' : 'Structure file unavailable'}</p><span className="text-xs">{item.status.replaceAll('_', ' ')}</span></div>}</div>
    <h3>{workspaceText(item.name, language)}</h3>
    <p className="text-sm text-text-secondary">{workspaceText(item.role, language)}</p>
    <p className="mt-2 text-xs text-text-muted">{workspaceText(item.method, language) || (zh ? '方法未注明' : 'Method unspecified')} · {item.resolution ? `${item.resolution} Å` : (zh ? '分辨率未注明' : 'Resolution unspecified')}{item.reference_id ? ` · ${item.reference_id}` : ''}</p>
    {item.rcsb_url ? <a className="mt-3 inline-block text-sm text-accent underline" href={item.rcsb_url} target="_blank" rel="noopener noreferrer">{zh ? '查看 RCSB 来源' : 'View RCSB source'}</a> : null}
  </div>
  return <section className="structure-comparison" aria-label={zh ? '交互式结构对照' : 'Interactive structure comparison'}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="text-lg font-medium">{zh ? '在结构之间，发现差异。' : 'Explore structures in context.'}</h2><p className="mt-1 text-sm text-text-secondary">{zh ? '旋转、选择链与切换表示。并排查看为独立视角，不作自动结构对齐。' : 'Rotate, select chains and change representation. Side-by-side views are independent, without automatic alignment.'}</p></div>
      <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" aria-pressed={compare} disabled={structures.length < 2} onClick={toggleCompare}>{zh ? (compare ? '返回单结构' : '并排对照') : (compare ? 'Single structure' : 'Compare side by side')}</Button><Button type="button" onClick={ask}>{zh ? '交给 Bot 解读' : 'Discuss with a Bot'}</Button></div>
    </div>
    <div className="structure-comparison-panes" data-single={!compare}>{pane(left, 'left')}{compare && right ? pane(right, 'right') : null}</div>
  </section>
}
