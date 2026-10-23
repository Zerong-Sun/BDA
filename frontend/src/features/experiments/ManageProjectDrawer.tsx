import { DrawerShell } from '../../components/ui/DrawerShell'
import { ProjectChooser } from '../projects/ProjectChooser'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { XIcon } from '@phosphor-icons/react'

interface ManageProjectDrawerProps {
  open: boolean
  onClose: () => void
  creating: boolean
  onCreatingChange: (open: boolean) => void
}

export function ManageProjectDrawer({ open, onClose, creating, onCreatingChange }: ManageProjectDrawerProps) {
  const { t, language } = useI18n()

  return (
    <DrawerShell
      open={open}
      onClose={onClose}
      widthClass="sm:max-w-xl"
      title={t.projects.manageDrawer.title}
      header={
        <div className="flex items-center justify-between gap-2">
          <div>
            <p className="text-sm text-text-muted">{t.projects.manageDrawer.eyebrow}</p>
            <h2 className="text-lg font-semibold text-text-primary">{t.projects.manageDrawer.title}</h2>
          </div>
          <Button type="button" variant="ghost" size="icon-sm" onClick={onClose} aria-label={language === 'zh' ? '关闭项目管理' : 'Close project manager'}><XIcon aria-hidden="true" /></Button>
        </div>
      }
    >
      <div className="p-4">
        <ProjectChooser
          title={t.projects.manageDrawer.chooserTitle}
          description={t.projects.manageDrawer.chooserDescription}
          compact
          creating={creating}
          onCreatingChange={onCreatingChange}
          onCreated={onClose}
        />
      </div>
    </DrawerShell>
  )
}
