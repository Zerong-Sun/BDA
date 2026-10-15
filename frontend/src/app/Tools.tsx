import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select'
import { useI18n } from '../lib/i18n'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { useSearchParamPatch } from '../lib/nav/useSearchParamPatch'
import { projectText } from '../lib/i18n/projectText'
import { InstrumentAnalysis } from '../features/lab/InstrumentAnalysis'
import { SerialDilutionPlanner } from '../features/lab/SerialDilutionPlanner'
import { BenchToolForm, type BenchDraft } from '../features/lab/BenchToolForm'
import { BENCH_TOOLS, TOOL_CATEGORIES, type ToolId } from '../features/lab/toolCatalog'
import { useAuthConfig } from '../lib/auth/account'
import { PrivateAccessLinks } from '../features/account/PrivateAccessLinks'
import { isPublicVisitor } from '../lib/auth/publicWorkspace'

function PrivateInstrumentAccess() {
  const { language } = useI18n()
  const config = useAuthConfig()
  return <div className="space-y-4"><p>{language === 'zh' ? '注册或登录 Private 后，上传仪器数据、分析并保存版本。' : 'Register or sign in to Private to upload instrument data, analyze it and save versions.'}</p><PrivateAccessLinks config={config.data} /></div>
}

function InstrumentPreview({ instrument }: { instrument: 'bli' | 'akta' | 'enzyme' }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const { visibleProjects, projectsError, refetchProjects } = useProjectContext()
  const [saveProject, setSaveProject] = useState('')
  const selectedProject = visibleProjects.find((project) => project.id === saveProject)
  return <div className="space-y-5">
    <div className="space-y-2 border-b pb-4"><label className="grid gap-2 text-sm"><span>{zh ? '需要保存时，明确选择项目（可选）' : 'Choose a project only when you want to save (optional)'}</span>
      <Select value={selectedProject?.id ?? ''} items={[{ value: '', label: zh ? '仅预览，不保存' : 'Preview only, do not save' }, ...visibleProjects.map((project) => ({ value: project.id, label: projectText(project, 'name', language) }))]} onValueChange={(value) => setSaveProject(value ?? '')}>
        <SelectTrigger className="w-full" aria-label={zh ? '结果保存项目' : 'Save results to project'}><SelectValue /></SelectTrigger><SelectContent><SelectItem value="">{zh ? '仅预览，不保存' : 'Preview only, do not save'}</SelectItem>{visibleProjects.map((project) => <SelectItem key={project.id} value={project.id}>{projectText(project, 'name', language)}</SelectItem>)}</SelectContent>
      </Select></label>
      {projectsError ? <p role="alert" className="text-sm">{zh ? '项目列表未加载；仍可预览。' : 'Projects could not be loaded; previews remain available.'}<Button type="button" variant="link" onClick={() => refetchProjects()}>{zh ? '重试' : 'Retry'}</Button></p> : null}
      {selectedProject ? <Link className="text-xs underline" to={`/lab?project=${encodeURIComponent(selectedProject.id)}&section=analysis`}>{zh ? '查看该项目的分析与审核记录' : 'View analysis and reviews in this project'}</Link> : null}
    </div>
    <InstrumentAnalysis instrument={instrument} previewOnly projectId={selectedProject?.id ?? ''} />
  </div>
}

export function ToolsPage({ publicPreview = false }: { publicPreview?: boolean }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [params, patch] = useSearchParamPatch()
  const [search, setSearch] = useState('')
  const [catalogOpen, setCatalogOpen] = useState(false)
  const [handoff, setHandoff] = useState<{ tool: ToolId; values: Record<string, string>; serial: number } | null>(null)
  const [drafts, setDrafts] = useState<Partial<Record<ToolId, BenchDraft>>>({})
  const rawTool = params.get('tool')
  const selected = BENCH_TOOLS.find((tool) => tool.id === rawTool) ?? BENCH_TOOLS[0]
  useEffect(() => { if (!rawTool) patch({ tool: selected.id }, { replace: true }) }, [rawTool, selected.id, patch])
  const matches = BENCH_TOOLS.filter((tool) => `${tool.title.zh} ${tool.title.en} ${tool.keywords}`.toLowerCase().includes(search.trim().toLowerCase()))
  function choose(id: ToolId) { setHandoff(null); setCatalogOpen(false); patch({ tool: id }) }
  function useResult(id: ToolId, values: Record<string, string>) { setDrafts((current) => ({ ...current, [id]: undefined })); setHandoff({ tool: id, values, serial: Date.now() }); setSearch(''); patch({ tool: id }) }
  const instrument = selected.id === 'bli' || selected.id === 'akta' || selected.id === 'enzyme' ? selected.id : null
  const currentPrefill = handoff?.tool === selected.id ? handoff : null
  return <div data-testid="lab-tools-page" className="space-y-6">
    <header className="space-y-2"><p className="font-mono text-xs uppercase tracking-wider text-muted-foreground">LAB TOOLS</p><h1 className="text-3xl font-semibold">{zh ? '实验工具' : 'Lab tools'}</h1><p className="max-w-3xl text-sm leading-6 text-muted-foreground">{zh ? '分子生物学与合成生物学的日常计算，按用途集中放置。选择一个工具即可使用，无需创建项目。' : 'Everyday molecular and synthetic biology calculations, organized by purpose. Choose a tool; no project is required.'}</p></header>
    <div className="grid items-start gap-6 lg:grid-cols-[16rem_minmax(0,1fr)]">
      <Button type="button" variant="outline" className="justify-between lg:hidden" aria-expanded={catalogOpen} aria-controls="lab-tool-catalog" onClick={() => setCatalogOpen((open) => !open)}>{catalogOpen ? (zh ? '收起工具目录' : 'Hide tool catalog') : (zh ? '选择其他工具（14 项）' : 'Choose another tool (14)')}</Button>
      <aside id="lab-tool-catalog" className={`${catalogOpen ? 'block' : 'hidden lg:block'} space-y-4 lg:sticky lg:top-4`}><Input aria-label={zh ? '搜索实验工具' : 'Search lab tools'} placeholder={zh ? '搜索：分子量、A260、稀释…' : 'Search: mass, A260, dilution…'} value={search} onChange={(event) => setSearch(event.target.value)} />
        <nav aria-label={zh ? '实验工具分类' : 'Lab tool categories'} className="grid gap-4">{TOOL_CATEGORIES.map((category) => {
          const tools = matches.filter((tool) => tool.category === category.id)
          return tools.length ? <section key={category.id}><h2 className="mb-2 px-3 text-xs font-semibold tracking-wide text-muted-foreground">{category.title[language]}</h2><div className="grid gap-1">{tools.map((tool) => <Button key={tool.id} type="button" variant={selected.id === tool.id ? 'secondary' : 'ghost'} className="h-auto min-h-9 justify-start whitespace-normal px-3 py-2 text-left text-sm" aria-current={selected.id === tool.id ? 'page' : undefined} onClick={() => choose(tool.id)}>{tool.title[language]}</Button>)}</div></section> : null
        })}</nav>
        {!matches.length ? <div className="space-y-2 text-sm text-muted-foreground"><p>{zh ? '没有匹配的工具。' : 'No matching tools.'}</p><Button type="button" variant="outline" size="sm" onClick={() => setSearch('')}>{zh ? '清除搜索' : 'Clear search'}</Button></div> : null}
      </aside>
      <section className="lab-tool-workbench min-w-0 space-y-5 border bg-background p-5 sm:p-6" aria-label={selected.title[language]}>
        {rawTool && !BENCH_TOOLS.some((tool) => tool.id === rawTool) ? <p role="status" className="text-sm text-muted-foreground">{zh ? '链接中的工具不存在，下面显示蛋白分子量工具。' : 'The linked tool is unavailable. Protein molecular mass is shown below.'}</p> : null}
        <div className="space-y-2 border-b pb-4"><h2 className="text-xl font-semibold">{selected.title[language]}</h2><p className="text-sm leading-6 text-muted-foreground">{selected.description[language]}</p></div>
        {currentPrefill ? <p role="status" className="text-sm text-muted-foreground">{zh ? '已带入上一个工具的结果，请补齐其余输入并确认适用条件。' : 'Values from the previous tool are filled in. Complete the remaining inputs and check assumptions.'}</p> : null}
        {instrument ? (publicPreview || isPublicVisitor() ? <PrivateInstrumentAccess /> : <InstrumentPreview key={instrument} instrument={instrument} />) : selected.id === 'serial-dilution' ? <SerialDilutionPlanner hideTitle /> : <BenchToolForm key={`${selected.id}-${currentPrefill?.serial ?? 'fresh'}`} tool={selected} prefill={currentPrefill?.values} draft={drafts[selected.id]} onDraft={(draft) => setDrafts((current) => ({ ...current, [selected.id]: draft }))} onUse={useResult} />}
      </section>
    </div>
  </div>
}
