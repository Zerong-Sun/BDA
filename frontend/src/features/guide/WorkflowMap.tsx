import { useCallback, useEffect, useRef } from 'react'
import { getGuideWorkflowStations } from './guideWorkflowData'
import { WorkflowPath } from './WorkflowPath'
import { WorkflowProgress } from './WorkflowProgress'
import { WorkflowStation } from './WorkflowStation'
import { useI18n } from '../../lib/i18n'

interface WorkflowMapProps {
  activeStep: number
  onActiveStepChange: (step: number) => void
}

export function WorkflowMap({ activeStep, onActiveStepChange }: WorkflowMapProps) {
  const { language } = useI18n()
  const stations = getGuideWorkflowStations(language)
  const stationRefs = useRef<Map<number, HTMLElement>>(new Map())
  const onActiveStepChangeRef = useRef(onActiveStepChange)
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    onActiveStepChangeRef.current = onActiveStepChange
  }, [onActiveStepChange])

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (prefersReducedMotion) return

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)

        if (visible.length > 0) {
          const step = Number(visible[0].target.getAttribute('data-step'))
          if (step) {
            onActiveStepChangeRef.current(step)
          }
        }
      },
      {
        root: null,
        rootMargin: '-20% 0px -35% 0px',
        threshold: [0.15, 0.35, 0.55, 0.75],
      },
    )

    observerRef.current = observer
    stationRefs.current.forEach((el) => observer.observe(el))

    return () => {
      observer.disconnect()
      observerRef.current = null
    }
  }, [])

  const scrollToStep = useCallback((stepNumber: number) => {
    const el = stationRefs.current.get(stepNumber)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      onActiveStepChange(stepNumber)
    }
  }, [onActiveStepChange])

  const setStationRef = useCallback((stepNumber: number, el: HTMLElement | null) => {
    const existing = stationRefs.current.get(stepNumber)
    if (existing && observerRef.current) {
      observerRef.current.unobserve(existing)
    }

    if (el) {
      stationRefs.current.set(stepNumber, el)
      observerRef.current?.observe(el)
    } else {
      stationRefs.current.delete(stepNumber)
    }
  }, [])

  return (
    <section className="guide-workflow-map relative" aria-label={language === 'zh' ? '工作流站点' : 'Workflow stations'}>
      {/* Sticky progress — desktop, offset below the page header */}
      <div className="sticky top-[4.5rem] z-30 mb-8 hidden justify-center md:flex">
        <WorkflowProgress
          activeStep={activeStep}
          onStepClick={scrollToStep}
          orientation="horizontal"
          label={language === 'zh' ? '工作流步骤（跳转）' : 'Workflow steps (jump to step)'}
        />
      </div>

      <div className="relative">
        {/* Isometric campus atmosphere */}
        <div className="guide-campus-atmosphere pointer-events-none absolute inset-0 overflow-hidden rounded-3xl" aria-hidden="true">
          <div className="guide-campus-grid absolute inset-0" />
          <div className="guide-campus-mist absolute inset-0" />
        </div>

        <div className="relative grid gap-0 md:grid-cols-[12rem_1fr] lg:grid-cols-[14rem_1fr]">
          {/* Sticky progress — desktop sidebar */}
          <aside className="sticky top-[8rem] z-20 hidden self-start md:block">
            <WorkflowProgress
              activeStep={activeStep}
              onStepClick={scrollToStep}
              orientation="vertical"
              label={language === 'zh' ? '工作流步骤大纲' : 'Workflow steps outline'}
            />
          </aside>

          {/* Mobile progress */}
          <div className="mb-6 md:hidden">
            <WorkflowPath totalSteps={stations.length} activeStep={activeStep} orientation="horizontal" />
            <p className="mt-2 text-center text-xs text-text-muted">
              {language === 'zh' ? `第 ${activeStep} 步，共 ${stations.length} 步` : `Step ${activeStep} of ${stations.length}`}
            </p>
          </div>

          <div className="relative space-y-8 md:space-y-16 lg:space-y-20">
            <WorkflowPath
              totalSteps={stations.length}
              activeStep={activeStep}
              orientation="vertical"
            />

            {stations.map((station, index) => (
              <WorkflowStation
                key={station.id}
                ref={(el) => setStationRef(station.stepNumber, el)}
                station={station}
                isActive={activeStep === station.stepNumber}
                isPast={station.stepNumber < activeStep}
                index={index}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Reduced-motion static notice */}
      <p className="sr-only motion-reduce:not-sr-only mt-6 text-center text-xs text-text-muted">
        {language === 'zh'
          ? '已启用减少动态效果。工作流站点以静态布局显示。'
          : 'Reduced motion is enabled. Workflow stations are shown in a static layout without scroll-driven animations.'}
      </p>
    </section>
  )
}
