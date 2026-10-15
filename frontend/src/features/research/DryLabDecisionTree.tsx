import { Link } from 'react-router'
import { GitBranchIcon } from '@phosphor-icons/react'
import { Frame, FrameDescription, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { Button } from '../../components/ui/Button'
import { useI18n } from '../../lib/i18n'

/** Contextual methods entry; full trees and reasoning live in Research's timeline tab. */
export function DryLabDecisionTree({ projectId }: { projectId: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  return (
    <Frame data-tour-id="dry-lab-decision-tree">
      <FramePanel className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <FrameHeader className="px-0 py-0">
          <div className="flex items-center gap-2">
            <GitBranchIcon aria-hidden="true" className="size-5 text-primary" />
            <FrameTitle>{zh ? '方法选择依据' : 'Reasoning behind method choices'}</FrameTitle>
          </div>
          <FrameDescription>{zh ? '比较方法时，可在决策记录中查看完整目标树、采用或排除的路线及其证据。' : 'Compare methods with the full goal tree, chosen or rejected routes and their evidence in the decision record.'}</FrameDescription>
        </FrameHeader>
        <Button type="button" variant="outline" className="justify-self-start" render={<Link to={projectId ? `/research?project=${encodeURIComponent(projectId)}&tab=timeline` : '/projects'} />}>
          {projectId ? (zh ? '查看决策记录' : 'Open decision record') : (zh ? '选择项目' : 'Choose a project')}
        </Button>
      </FramePanel>
    </Frame>
  )
}
