import { Disclosure } from '../components/ui/Disclosure'
import { Link } from 'react-router'
import { Button } from '../components/ui/Button'
import { ProjectChooser } from '../features/projects/ProjectChooser'
import { useI18n } from '../lib/i18n'
import { useProjectContext } from '../lib/hooks/useProjectContext'
import { ProteinLibrary } from '../features/lab/ProteinLibrary'
import { BenchCalculators } from '../features/lab/BenchCalculators'
import { InstrumentAnalysis } from '../features/lab/InstrumentAnalysis'

/**
 * The wet-lab bench: the constructs in hand and the numbers a run starts from.
 *
 * Sits between Candidates and Results in the loop, because this is where a
 * design becomes something measurable and where the measurement comes from.
 */
export function LabPage({ toolbox = false }: { toolbox?: boolean }) {
  const { t, language } = useI18n()
  const { projectId } = useProjectContext()

  return (
    <div className="space-y-8" data-tour-id="lab-page">
      <header className="space-y-1">
        <h1 className="text-2xl font-medium">{toolbox ? (language === 'zh' ? '实验工具箱' : 'Lab toolbox') : t.lab.title}</h1>
        <p className="text-text-secondary">{toolbox ? (language === 'zh' ? '直接计算或预览仪器数据，需要保存时再关联项目。' : 'Calculate or preview instrument data. Associate a project when you want to save.') : t.lab.subtitle}</p>
      </header>
      {toolbox ? <Disclosure className="rounded-lg border border-border-soft p-4" title={language === 'zh' ? '选择保存项目（可选）' : 'Choose a project for saving (optional)'}><ProjectChooser compact /></Disclosure> : <Button variant="outline" render={<Link to="/tools" />}>{language === 'zh' ? '独立使用工具箱' : 'Open standalone toolbox'}</Button>}
      {projectId && !toolbox ? <ProteinLibrary projectId={projectId} /> : null}
      <BenchCalculators projectId={projectId || ''} />
      <InstrumentAnalysis projectId={projectId || ''} previewOnly={toolbox} />

    </div>
  )
}

export default LabPage
