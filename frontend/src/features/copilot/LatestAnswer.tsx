import { Disclosure } from '../../components/ui/Disclosure'
import { ReviewMarkdown } from '../research/ReviewMarkdown'
import type { CitationRecord } from '../research/citationMarkers'
import { answerPresentation } from './answerPresentation'

export function LatestAnswer({ content, projectId, citations = [], zh }: { content: string; projectId: string; citations?: readonly CitationRecord[]; zh: boolean }) {
  const answer = answerPresentation(content)
  return <>
    <ReviewMarkdown presentation="chat" citations={citations} projectId={projectId}>{answer.visible || (zh ? '本条答复仅记录了操作过程，尚未单列项目结论；请查看上方项目报告与复核记录。' : 'This reply records process only, with no separate project conclusion. See the project report and review above.')}</ReviewMarkdown>
    {answer.folded ? <Disclosure title={zh ? '工具回读与过程记录' : 'Tool output and process records'}><ReviewMarkdown presentation="chat" citations={citations} projectId={projectId}>{answer.folded}</ReviewMarkdown></Disclosure> : null}
  </>
}
