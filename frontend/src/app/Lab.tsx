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
export function LabPage() {
  const { t } = useI18n()
  const { projectId } = useProjectContext()

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-medium">{t.lab.title}</h1>
        <p className="text-text-secondary">{t.lab.subtitle}</p>
      </header>
      {projectId ? (
        <>
          <ProteinLibrary projectId={projectId} />
          <BenchCalculators projectId={projectId} />
          <InstrumentAnalysis projectId={projectId} />
        </>
      ) : null}
    </div>
  )
}

export default LabPage
