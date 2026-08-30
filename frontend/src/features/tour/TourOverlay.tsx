import {
  ArrowCounterClockwiseIcon,
  CaretLeftIcon,
  CaretRightIcon,
  CheckCircleIcon,
  QuestionIcon,
  WarningIcon,
  XIcon,
} from '@phosphor-icons/react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'
import {
  Stepper,
  StepperContent,
  StepperIndicator,
  StepperItem,
  StepperNav,
  StepperPanel,
  StepperSeparator,
  StepperTrigger,
} from '../../components/reui/stepper'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Button } from '../../components/ui/Button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog'
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverTitle,
} from '../../components/ui/popover'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import { findDemoProject } from './demoProject'
import { getTourSection, getTourStep, TOUR_SECTIONS, type TourSection, type TourStep } from './tourData'

const ANCHOR_ATTEMPTS = 40
const ANCHOR_POLL_MS = 125
const POSITIONING_DELAY_MS = 220
const TARGET_ADVANCE_DELAY_MS = 180

type AnchorResolution = {
  stepId: string
  target: HTMLElement | null
  missing: boolean
}

function routeWithProject(route: string, projectId: string): string {
  const [pathname, rawSearch = ''] = route.split('?')
  const search = new URLSearchParams(rawSearch)
  if (projectId) search.set('project', projectId)
  const query = search.toString()
  return `${pathname}${query ? `?${query}` : ''}`
}

function usePrefersReducedMotion(): boolean {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  )

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (event: MediaQueryListEvent) => setPrefersReducedMotion(event.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  return prefersReducedMotion
}

function useTourAnchor(
  step: TourStep | undefined,
  active: boolean,
  prefersReducedMotion: boolean,
  advanceTour: () => void,
): AnchorResolution {
  const [resolution, setResolution] = useState<AnchorResolution>({
    stepId: '',
    target: null,
    missing: false,
  })

  useEffect(() => {
    if (!active || !step?.anchor) return

    let disposed = false
    let attempts = 0
    let target: HTMLElement | null = null
    const pendingTimers = new Set<number>()
    let removeTargetListener: () => void = () => undefined
    const schedule = (callback: () => void, delay: number) => {
      const timer = window.setTimeout(() => {
        pendingTimers.delete(timer)
        callback()
      }, delay)
      pendingTimers.add(timer)
    }

    const connect = () => {
      if (disposed || target) return
      const candidate = document.querySelector<HTMLElement>(step.anchor!.selector)
      if (!candidate) {
        attempts += 1
        if (attempts === ANCHOR_ATTEMPTS) {
          setResolution({ stepId: step.id, target: null, missing: true })
        }
        return
      }

      target = candidate
      candidate.scrollIntoView?.({
        behavior: prefersReducedMotion ? 'auto' : 'smooth',
        block: 'center',
        inline: 'nearest',
      })
      setResolution({ stepId: step.id, target: candidate, missing: false })

      if (!prefersReducedMotion) {
        schedule(() => {
          if (!disposed && candidate.isConnected) {
            setResolution({ stepId: step.id, target: candidate, missing: false })
          }
        }, POSITIONING_DELAY_MS)
      }

      if (step.advance === 'target-click') {
        const onClick = () => {
          if (prefersReducedMotion) {
            advanceTour()
            return
          }
          schedule(advanceTour, TARGET_ADVANCE_DELAY_MS)
        }
        candidate.addEventListener('click', onClick, { once: true })
        removeTargetListener = () => candidate.removeEventListener('click', onClick)
      }
    }

    connect()
    const interval = window.setInterval(() => {
      if (target && !target.isConnected) {
        removeTargetListener()
        removeTargetListener = () => undefined
        target = null
        setResolution({ stepId: step.id, target: null, missing: false })
      }
      connect()
    }, ANCHOR_POLL_MS)

    return () => {
      disposed = true
      removeTargetListener()
      pendingTimers.forEach((timer) => window.clearTimeout(timer))
      pendingTimers.clear()
      window.clearInterval(interval)
    }
  }, [active, advanceTour, prefersReducedMotion, step])

  if (!step || resolution.stepId !== step.id) {
    return { stepId: step?.id ?? '', target: null, missing: false }
  }
  return resolution
}

type TourCardProps = {
  section: TourSection
  step: TourStep
  stepIndex: number
  anchorMissing: boolean
  modal: boolean
  backTour: () => void
  advanceTour: () => void
  skipTour: () => void
}

function TourCard({
  section,
  step,
  stepIndex,
  anchorMissing,
  modal,
  backTour,
  advanceTour,
  skipTour,
}: TourCardProps) {
  const { t, language } = useI18n()
  const labels = t.tour
  const copy = step.copy[language]
  const Heading = modal ? DialogTitle : PopoverTitle
  const Description = modal ? DialogDescription : PopoverDescription

  return (
    <div className="grid min-w-0 gap-3" data-testid="tour-card">
      <div className="flex min-w-0 items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-primary">
            {labels.controls.chapter} · {section.title[language]} · {stepIndex + 1}/{section.steps.length}
          </p>
          <Heading className="mt-1 text-base">{copy.title}</Heading>
        </div>
        {modal ? (
          <DialogClose
            render={(
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label={labels.controls.pause}
              />
            )}
          >
            <XIcon aria-hidden="true" />
          </DialogClose>
        ) : (
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={skipTour}
            aria-label={labels.controls.pause}
          >
            <XIcon aria-hidden="true" />
          </Button>
        )}
      </div>

      <Stepper
        value={stepIndex + 1}
        onValueChange={() => undefined}
        className="grid gap-3"
      >
        <StepperNav aria-label={`${labels.controls.chapter}: ${section.title[language]}`}>
          {section.steps.map((sectionStep, index) => {
            const itemStep = index + 1
            return (
              <StepperItem
                key={sectionStep.id}
                step={itemStep}
                completed={index < stepIndex}
                disabled
              >
                <StepperTrigger
                  aria-label={`${labels.controls.step} ${itemStep}: ${sectionStep.copy[language].title}`}
                >
                  <StepperIndicator>
                    {index < stepIndex ? <CheckCircleIcon aria-hidden="true" /> : itemStep}
                  </StepperIndicator>
                </StepperTrigger>
                {index < section.steps.length - 1 ? <StepperSeparator /> : null}
              </StepperItem>
            )
          })}
        </StepperNav>

        <StepperPanel>
          {section.steps.map((sectionStep, index) => (
            <StepperContent key={sectionStep.id} value={index + 1}>
              <Description>{sectionStep.copy[language].body}</Description>
              {sectionStep.copy[language].interactionHint && !anchorMissing ? (
                <p className="mt-3 bg-info/10 px-3 py-2 text-xs text-info">
                  {sectionStep.copy[language].interactionHint}
                </p>
              ) : null}
              {anchorMissing ? (
                <Alert className="mt-3" variant="warning">
                  <WarningIcon aria-hidden="true" />
                  <AlertDescription>{labels.fallback.unavailable}</AlertDescription>
                </Alert>
              ) : null}
            </StepperContent>
          ))}
        </StepperPanel>
      </Stepper>

      <div className="flex items-center justify-between gap-2">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          disabled={stepIndex === 0}
          onClick={backTour}
        >
          <CaretLeftIcon aria-hidden="true" />
          {labels.controls.back}
        </Button>
        {step.advance === 'button' || anchorMissing ? (
          <Button type="button" size="sm" onClick={advanceTour}>
            {labels.controls.next}
            <CaretRightIcon aria-hidden="true" />
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export function TourOverlay() {
  const { language } = useI18n()
  const navigate = useNavigate()
  const location = useLocation()
  const { projectId } = useProjectContext()
  const {
    tourState,
    tourMenuOpen,
    advanceTour,
    backTour,
    skipTour,
    setCopilotOpen,
    setSettingsOpen,
  } = useAppStore()
  const step = getTourStep(tourState.sectionId, tourState.stepId)
  const section = getTourSection(tourState.sectionId)
  const prefersReducedMotion = usePrefersReducedMotion()
  const focusOriginRef = useRef<HTMLElement | null>(null)
  const [focusOriginTarget, setFocusOriginTarget] = useState<HTMLElement | null>(null)
  const [menuReturnFocusTarget, setMenuReturnFocusTarget] = useState<HTMLElement | null>(null)
  const anchorResolution = useTourAnchor(
    step,
    tourState.status === 'active' && !tourMenuOpen,
    prefersReducedMotion,
    advanceTour,
  )
  const rememberFocusOrigin = useCallback((preferred?: HTMLElement | null) => {
    if (preferred?.isConnected) {
      focusOriginRef.current = preferred
      setFocusOriginTarget(preferred)
      return
    }
    const activeElement = document.activeElement
    if (
      activeElement instanceof HTMLElement
      && activeElement !== document.body
      && activeElement.isConnected
    ) {
      focusOriginRef.current = activeElement
      setFocusOriginTarget(activeElement)
    }
  }, [])
  const handleSkip = useCallback(() => {
    let returnTarget = focusOriginRef.current
    if (anchorResolution.target?.isConnected) {
      rememberFocusOrigin(anchorResolution.target)
      returnTarget = anchorResolution.target
    } else if (!focusOriginRef.current?.isConnected) {
      rememberFocusOrigin()
      returnTarget = document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    }
    setMenuReturnFocusTarget(returnTarget?.isConnected ? returnTarget : null)
    skipTour()
  }, [anchorResolution.target, rememberFocusOrigin, skipTour])
  const handleAdvance = useCallback(() => {
    const returnTarget = anchorResolution.target?.isConnected
      ? anchorResolution.target
      : focusOriginRef.current?.isConnected
        ? focusOriginRef.current
        : null
    setMenuReturnFocusTarget(returnTarget)
    advanceTour()
  }, [advanceTour, anchorResolution.target])
  const handleModalInitialFocus = useCallback(() => {
    rememberFocusOrigin()
    return true
  }, [rememberFocusOrigin])

  useEffect(() => {
    if (tourState.status !== 'active' || tourMenuOpen || !step) return
    const targetRoute = routeWithProject(step.route, projectId)
    const [targetPath, targetSearch = ''] = targetRoute.split('?')
    const desired = new URLSearchParams(targetSearch)
    const current = new URLSearchParams(location.search)
    const searchMatches = [...desired.entries()].every(([key, value]) => current.get(key) === value)
    if (location.pathname !== targetPath || !searchMatches) navigate(targetRoute)
  }, [location.pathname, location.search, navigate, projectId, step, tourMenuOpen, tourState.status])

  useEffect(() => {
    if (tourState.status !== 'active' || tourMenuOpen || !step) return
    if (step.prepare === 'copilot') {
      setSettingsOpen(false)
      setCopilotOpen(true)
    } else if (step.prepare === 'settings') {
      setCopilotOpen(false)
      setSettingsOpen(true)
    }
  }, [setCopilotOpen, setSettingsOpen, step, tourMenuOpen, tourState.status])

  useEffect(() => {
    if (tourState.status !== 'active' || tourMenuOpen) return
    const onKeyDown = (event: KeyboardEvent) => {
      const waitingForAnchor = Boolean(
        step?.anchor && !anchorResolution.target && !anchorResolution.missing,
      )
      if (event.key === 'Escape' && waitingForAnchor) handleSkip()
      if (event.key === 'ArrowLeft') backTour()
      if (event.key === 'ArrowRight' && step?.advance === 'button') handleAdvance()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [
    anchorResolution.missing,
    anchorResolution.target,
    backTour,
    handleAdvance,
    handleSkip,
    step?.advance,
    step?.anchor,
    tourMenuOpen,
    tourState.status,
  ])

  const connectedMenuReturnTarget = anchorResolution.target?.isConnected
    ? anchorResolution.target
    : menuReturnFocusTarget?.isConnected
      ? menuReturnFocusTarget
      : focusOriginTarget?.isConnected
        ? focusOriginTarget
        : null

  if (tourMenuOpen) {
    return (
      <TourMenu
        returnFocusTarget={tourState.status === 'paused' ? connectedMenuReturnTarget : null}
      />
    )
  }
  if (tourState.status !== 'active' || !step || !section) return null

  const stepIndex = Math.max(0, section.steps.findIndex((item) => item.id === step.id))
  const card = (
    <TourCard
      section={section}
      step={step}
      stepIndex={stepIndex}
      anchorMissing={anchorResolution.missing}
      modal={!step.anchor || anchorResolution.missing}
      backTour={backTour}
      advanceTour={handleAdvance}
      skipTour={handleSkip}
    />
  )

  if (!step.anchor || anchorResolution.missing) {
    return (
      <Dialog
        open
        onOpenChange={(open) => {
          if (!open) handleSkip()
        }}
        disablePointerDismissal
      >
        <DialogContent
          showCloseButton={false}
          className="max-h-[calc(100vh-2rem)] max-w-md overflow-y-auto motion-reduce:animate-none motion-reduce:duration-0"
          initialFocus={handleModalInitialFocus}
        >
          {card}
        </DialogContent>
      </Dialog>
    )
  }

  if (!anchorResolution.target) {
    return <span className="sr-only" aria-live="polite">{step.copy[language].title}</span>
  }

  return (
    <>
      <div
        className="pointer-events-none fixed inset-0 z-40 bg-foreground/10 motion-reduce:transition-none"
        aria-hidden="true"
      />
      <Popover
        open
        modal={false}
        onOpenChange={(open, eventDetails) => {
          if (!open && eventDetails.reason === 'escape-key') handleSkip()
        }}
      >
        <PopoverContent
          anchor={anchorResolution.target}
          positionMethod="fixed"
          collisionBoundary={document.documentElement}
          collisionPadding={12}
          sticky
          side="bottom"
          sideOffset={14}
          align="start"
          initialFocus={false}
          finalFocus={false}
          className="w-[min(22.5rem,calc(100vw-1.5rem))] motion-reduce:animate-none motion-reduce:duration-0"
          data-tour-anchor={step.anchor.id}
          aria-live="polite"
        >
          {card}
        </PopoverContent>
      </Popover>
    </>
  )
}

function restoreFocus(element: HTMLElement | null) {
  queueMicrotask(() => {
    if (element?.isConnected) element.focus()
  })
}

export function TourMenu({
  returnFocusTarget = null,
}: {
  returnFocusTarget?: HTMLElement | null
}) {
  const { t, language } = useI18n()
  const { projects, setProjectId } = useProjectContext()
  const { tourState, startTour, restartTour, setTourMenuOpen, setAppMode } = useAppStore()
  const [demoUnavailable, setDemoUnavailable] = useState(false)
  const returnFocusRef = useRef<HTMLElement | null>(
    returnFocusTarget?.isConnected
      ? returnFocusTarget
      : document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null,
  )
  const labels = t.tour

  const closeMenu = useCallback(() => {
    const returnTarget = returnFocusRef.current
    setTourMenuOpen(false)
    restoreFocus(returnTarget)
  }, [setTourMenuOpen])

  const prepareDemo = () => {
    const demo = findDemoProject(projects)
    if (!demo) {
      setDemoUnavailable(true)
      return false
    }
    setDemoUnavailable(false)
    setAppMode('demo')
    setProjectId(demo.id)
    return true
  }

  const startChapter = (sectionId: TourSection['id']) => {
    if (prepareDemo()) startTour(sectionId)
  }

  const restart = () => {
    if (prepareDemo()) restartTour()
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) closeMenu()
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="max-h-[min(44rem,calc(100vh-2rem))] max-w-xl overflow-y-auto motion-reduce:animate-none motion-reduce:duration-0"
        finalFocus={returnFocusRef}
        data-testid="tour-menu"
      >
        <DialogHeader>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <DialogTitle className="flex items-center gap-2 text-lg">
                <QuestionIcon className="size-5 text-primary" aria-hidden="true" />
                {labels.menu.title}
              </DialogTitle>
              <DialogDescription className="mt-1">{labels.menu.body}</DialogDescription>
            </div>
            <DialogClose
              render={(
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={labels.menu.close}
                />
              )}
            >
              <XIcon aria-hidden="true" />
            </DialogClose>
          </div>
        </DialogHeader>

        <div className="grid gap-2 sm:grid-cols-2">
          {TOUR_SECTIONS.map((tourSection) => {
            const completed = tourState.completedSections.includes(tourSection.id)
            const accessibleStatus = completed ? `, ${labels.menu.completed}` : ''
            return (
              <Button
                key={tourSection.id}
                type="button"
                variant="outline"
                className="h-auto min-h-20 items-start justify-start whitespace-normal p-3 text-left"
                onClick={() => startChapter(tourSection.id)}
                aria-label={`${tourSection.title[language]}${accessibleStatus}`}
                data-testid="tour-chapter"
              >
                <span className="grid min-w-0 flex-1 gap-1">
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    <span>{tourSection.title[language]}</span>
                    {completed ? <CheckCircleIcon className="size-4 text-success" aria-hidden="true" /> : null}
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {tourSection.description[language]}
                  </span>
                </span>
              </Button>
            )
          })}
        </div>

        {demoUnavailable ? (
          <Alert variant="warning">
            <WarningIcon aria-hidden="true" />
            <AlertDescription>{labels.demo.unavailable}</AlertDescription>
          </Alert>
        ) : null}

        <div>
          <Button type="button" variant="outline" size="sm" onClick={restart}>
            <ArrowCounterClockwiseIcon aria-hidden="true" />
            {labels.menu.restart}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
