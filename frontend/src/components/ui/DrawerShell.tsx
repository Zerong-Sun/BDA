import type { ReactNode } from 'react'
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from './sheet'

export function DrawerShell({
  open,
  onClose,
  widthClass = 'sm:max-w-md',
  title,
  header,
  footer,
  children,
}: {
  open: boolean
  onClose: () => void
  /**
   * Max-width utility for the drawer, `sm:`-scoped so the drawer stays
   * full-bleed on mobile. Must be written out in full (e.g. `sm:max-w-xl`)
   * rather than composed at runtime, so Tailwind's source scanner sees it.
   */
  widthClass?: string
  title: ReactNode
  header: ReactNode
  footer?: ReactNode
  children: ReactNode
}) {
  return (
    <Sheet open={open} onOpenChange={(nextOpen) => { if (!nextOpen) onClose() }}>
      <SheetContent
        side="right"
        className={`w-full ${widthClass}`}
        showCloseButton={false}
      >
        <SheetHeader className="h-16 shrink-0 border-b border-border-soft px-4 py-3">
          <SheetTitle className="sr-only">{title}</SheetTitle>
          {header}
        </SheetHeader>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        {footer ? (
          <SheetFooter className="shrink-0 flex-row justify-end border-t border-border-soft bg-surface-1 p-4">
            {footer}
          </SheetFooter>
        ) : null}
      </SheetContent>
    </Sheet>
  )
}
