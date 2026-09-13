import { useAppStore } from '../../lib/store/appStore'
import { currentRole } from '../research/jsonHelpers'

/** UI guard for demo/global-viewer restrictions; the API enforces project ACLs. */
export function useCopilotReadOnly() {
  const demo = useAppStore((state) => state.appMode === 'demo')
  return demo || currentRole() === 'viewer'
}

export function requireCopilotWrite() {
  if (useAppStore.getState().appMode === 'demo' || currentRole() === 'viewer') {
    throw new Error(useAppStore.getState().language === 'zh' ? '当前工作区为只读模式。' : 'This workspace is read-only.')
  }
}
