import { Link, useSearchParams } from 'react-router'
import { Button } from '../components/ui/Button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/Tabs'
import { ProjectChooser } from '../features/projects/ProjectChooser'
import { useI18n } from '../lib/i18n'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { ProteinLibrary } from '../features/lab/ProteinLibrary'
import { InstrumentAnalysis } from '../features/lab/InstrumentAnalysis'

/** Project constructs, recorded instrument analysis and human quality review. */
export function LabPage() {
  const { language } = useI18n()
  const { projectId } = useProjectContext()
  const [search, setSearch] = useSearchParams()
  const section = search.get('section') === 'analysis' ? 'analysis' : 'library'
  const zh = language === 'zh'

  return (
    <div className="space-y-8" data-tour-id="lab-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-medium">{zh ? '项目实验' : 'Project lab'}</h1>
        <p className="text-text-secondary">{zh ? '管理项目蛋白与构建体，保存仪器分析并记录人工质控。' : 'Manage project proteins and constructs, record instrument analyses, and review measurement quality.'}</p>
      </header>
      <Button type="button" variant="outline" render={<Link to="/tools" />}>{zh ? '打开独立计算与预览工具' : 'Open standalone calculations and previews'}</Button>
      {!projectId ? <ProjectChooser compact /> : <Tabs value={section} onValueChange={(value) => {
        const next = new URLSearchParams(search)
        next.set('section', value === 'analysis' ? 'analysis' : 'library')
        next.set('project', projectId)
        setSearch(next)
      }}>
        <TabsList variant="line" aria-label={zh ? '项目实验分区' : 'Project lab sections'}>
          <TabsTrigger value="library">{zh ? '蛋白与构建体库' : 'Proteins & constructs'}</TabsTrigger>
          <TabsTrigger value="analysis">{zh ? '仪器分析与质控' : 'Instrument analysis & QC'}</TabsTrigger>
        </TabsList>
        <TabsContent value="library">{section === 'library' ? <ProteinLibrary key={projectId} projectId={projectId} /> : null}</TabsContent>
        <TabsContent value="analysis">{section === 'analysis' ? <InstrumentAnalysis key={projectId} projectId={projectId} /> : null}</TabsContent>
      </Tabs>}
    </div>
  )
}

export default LabPage
