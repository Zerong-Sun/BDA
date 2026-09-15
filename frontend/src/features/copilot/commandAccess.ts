import { useAppStore } from '../../lib/store/appStore'
import { useProjectContext } from '../../lib/hooks/useProjectContext'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { currentRole } from '../research/jsonHelpers'

/**
 * UI guard for demo mode, a global viewer, and a project the caller may only read.
 *
 * The project role narrows further than the global one: an organization
 * researcher can still be a viewer on one project. The API enforces all three;
 * this only keeps controls the server would refuse from looking usable.
 */
export function useCopilotReadOnly() {
  const demo = useAppStore((state) => state.appMode === 'demo')
  const { projectId } = useProjectContext()
  const access = useProjectAccess(projectId)
  return demo || currentRole() === 'viewer' || access.data?.permissions.write === false
}

export function requireCopilotWrite() {
  if (useAppStore.getState().appMode === 'demo' || currentRole() === 'viewer') {
    throw new Error(useAppStore.getState().language === 'zh' ? '当前工作区为只读模式。' : 'This workspace is read-only.')
  }
}
