import { DrawerShell } from '../../components/ui/DrawerShell'
import { ProjectChooser } from '../projects/ProjectChooser'
import { useI18n } from '../../lib/i18n'

interface ManageProjectDrawerProps {
  open: boolean
  onClose: () => void
  creating: boolean
  onCreatingChange: (open: boolean) => void
}

export function ManageProjectDrawer({ open, onClose, creating, onCreatingChange }: ManageProjectDrawerProps) {
  const { t } = useI18n()

  return (
    <DrawerShell
      open={open}
      onClose={onClose}
      widthClass="sm:max-w-xl"
      title={t.projects.manageDrawer.title}
      header={
        <div>
          <p className="text-sm text-text-muted">{t.projects.manageDrawer.eyebrow}</p>
          <h2 className="text-lg font-semibold text-text-primary">{t.projects.manageDrawer.title}</h2>
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
        />
      </div>
    </DrawerShell>
  )
}
