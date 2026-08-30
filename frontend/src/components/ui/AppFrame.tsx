import type { ComponentProps, ReactNode } from 'react'
import {
  Frame,
  FrameDescription,
  FrameFooter,
  FrameHeader,
  FramePanel,
  FrameTitle,
} from '@/components/reui/frame'
import { cn } from '@/lib/utils'

interface AppFrameProps extends ComponentProps<typeof Frame> {
  heading?: ReactNode
  description?: ReactNode
  actions?: ReactNode
  footer?: ReactNode
  panelClassName?: string
}

export function AppFrame({
  heading,
  description,
  actions,
  footer,
  children,
  className,
  panelClassName,
  ...props
}: AppFrameProps) {
  return (
    <Frame className={cn('min-w-0', className)} {...props}>
      <FramePanel className={cn('min-w-0', panelClassName)}>
        {heading || description || actions ? (
          <FrameHeader className="flex-row items-start justify-between gap-3">
            <div className="min-w-0">
              {heading ? <FrameTitle>{heading}</FrameTitle> : null}
              {description ? <FrameDescription>{description}</FrameDescription> : null}
            </div>
            {actions ? <div className="shrink-0">{actions}</div> : null}
          </FrameHeader>
        ) : null}
        {children}
        {footer ? <FrameFooter>{footer}</FrameFooter> : null}
      </FramePanel>
    </Frame>
  )
}
