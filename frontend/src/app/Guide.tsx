import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ArrowLeft } from '@phosphor-icons/react'
import { AppFrame } from '@/components/ui/AppFrame'
import { GuideCTA, GuideHero, ModelPrinciples, WorkflowFAQ, WorkflowMap } from '../features/guide'
import { useI18n } from '../lib/i18n'

export function GuidePage() {
  const { t } = useI18n()
  const [activeStep, setActiveStep] = useState(1)
  const [searchParams] = useSearchParams()
  const isAuthenticated = Boolean(sessionStorage.getItem('bda_token'))
  const projectId = searchParams.get('project')
  const projectQuery = projectId ? `?project=${encodeURIComponent(projectId)}` : ''
  const backPath = isAuthenticated ? `/projects${projectQuery}` : '/login'
  const backLabel = isAuthenticated ? t.guide.nav.backToApp : t.guide.nav.back

  const handleActiveStepChange = useCallback((step: number) => {
    setActiveStep(step)
  }, [])

  return (
    <div className="guide-page min-h-screen overflow-x-clip bg-bg-app text-text-primary">
      <div className="sticky top-0 z-40 border-b border-border-soft/60 bg-bg-app/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link
            to={backPath}
            className="inline-flex items-center gap-2 text-sm text-text-secondary transition-colors hover:text-text-primary"
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
            {backLabel}
          </Link>
          <span className="font-mono text-caption font-medium uppercase tracking-wider text-accent">{t.guide.nav.label}</span>
        </div>
      </div>

      <main>
        <GuideHero />

        <div className="mx-auto max-w-5xl px-4 pb-8 sm:px-6">
          <AppFrame
            heading={<h2>{t.guide.map.title}</h2>}
            description={t.guide.map.subtitle}
            panelClassName="p-5 sm:p-6"
          />
          <div className="mt-6">
            <WorkflowMap activeStep={activeStep} onActiveStepChange={handleActiveStepChange} />
          </div>
        </div>

        <div className="mx-auto max-w-5xl px-4 sm:px-6">
          <ModelPrinciples />
          <WorkflowFAQ />
          <div className="pb-16">
            <GuideCTA />
          </div>
        </div>
      </main>
    </div>
  )
}
