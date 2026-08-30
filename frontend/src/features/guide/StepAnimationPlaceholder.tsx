import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Play } from '@phosphor-icons/react'
import { IconTile } from '@/components/reui/icon-tile'
import { useI18n } from '../../lib/i18n'

export interface StepAnimationPlaceholderProps {
  stepId: string
  animationComponent?: ReactNode
  label?: string
}

export function StepAnimationPlaceholder({
  stepId,
  animationComponent,
  label,
}: StepAnimationPlaceholderProps) {
  const { language } = useI18n()
  const resolvedLabel = label ?? (language === 'zh' ? '原理动画占位' : 'Principle animation placeholder')
  return (
    <div
      className="guide-animation-placeholder relative overflow-hidden rounded-xl border border-dashed border-accent-border bg-accent-bg/50"
      data-step-id={stepId}
      aria-label={resolvedLabel}
    >
      {animationComponent ? (
        <div className="aspect-video w-full">{animationComponent}</div>
      ) : (
        <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 px-6 py-8 text-center">
          <IconTile variant="soft" size="lg" radius="full" className={clsx('text-accent')} aria-hidden="true">
            <Play className="h-5 w-5 text-accent" />
          </IconTile>
          <p className="font-mono text-caption font-medium uppercase tracking-wider text-accent">{resolvedLabel}</p>
          <p className="max-w-xs text-caption leading-relaxed text-text-muted">
            {language === 'zh'
              ? '此处预留模型原理动画，后续可通过 animationComponent 属性接入。'
              : 'A model-principle animation can be inserted here later via the animationComponent prop.'}
          </p>
        </div>
      )}
    </div>
  )
}
