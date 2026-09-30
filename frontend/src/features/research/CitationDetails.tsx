import { Disclosure } from '../../components/ui/Disclosure'
import { Link } from 'react-router'
import { useI18n } from '../../lib/i18n'
import { citationText, citationValueLabel, safeCitationUrl, type CitationRecord } from './citationMarkers'
import { citationLabel } from './citationLabel'

const CONTENT_KINDS: Record<string, [string, string]> = {
  metadata_only: ['仅书目信息', 'Bibliographic metadata only'],
  database_abstract: ['数据库摘要', 'Database abstract'],
  provided_abstract: ['提供的摘要', 'Provided abstract'],
  open_access_abstract: ['开放文献 XML 中的摘要', 'Abstract from open-access XML'],
  open_access_full_text: ['开放获取全文片段', 'Excerpt from open-access full text'],
  uploaded_text: ['上传的文本', 'Uploaded text'],
}

export function CitationDetails({ citations, prefix, projectId }: { citations: readonly CitationRecord[]; prefix: string; projectId?: string }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  if (!citations.length) return null
  return <div className="mt-3 border-t border-border-soft pt-2 text-xs" data-testid="citation-details">
    <p className="text-text-muted">{zh
      ? '标记对应前一句；段末引用须支持整段。来源清单不代表所有论断已有依据，未标注内容需核实。'
      : 'Markers support the preceding sentence, or a fully supported paragraph. Listed sources do not verify every claim; check unmarked text separately.'}</p>
    {citations.map((citation, index) => {
      const label = citationLabel(citation, language, index)
      const href = safeCitationUrl(citation.url)
      const workspaceType = citationText(citation.workspace_type)
      const tab = workspaceType === 'reference' ? 'references'
        : workspaceType === 'structure' ? 'structures'
          : ['dataset', 'research_target'].includes(workspaceType) ? 'data'
            : workspaceType === 'method' ? 'methods' : 'evidence'
      const projectHref = citation.source_type === 'research_workspace' && projectId
        ? `/research?tab=${tab}&project=${encodeURIComponent(projectId)}` : undefined
      const kind = citationText(citation.content_kind)
      const contentKind = CONTENT_KINDS[kind]?.[zh ? 0 : 1] || kind || (zh ? '内容范围未记录' : 'Content scope not recorded')
      const fields = [
        [zh ? '内容范围' : 'Content scope', contentKind],
        [zh ? '来源类型' : 'Source type', citation.source_type === 'external' ? (zh ? '外部参考来源' : 'External reference') : citation.source_type ? citationValueLabel(citation.source_type, language) : undefined],
        [zh ? '审阅状态' : 'Review status', citation.review_status ? citationValueLabel(citation.review_status, language) : undefined],
        [zh ? '证据等级' : 'Evidence grade', citation.evidence_grade],
        [zh ? '文献 ID' : 'Document ID', citation.document_id],
        [zh ? '文献标识' : 'Reference identifiers', Array.isArray(citation.reference_ids) ? citation.reference_ids.join(', ') : citation.ref_id],
        [zh ? '片段 ID' : 'Chunk ID', citation.chunk_id],
        [zh ? '片段位置（从 0 起）' : 'Chunk position (zero-based)', citation.chunk_position],
        [zh ? '片段版本' : 'Chunk version', citation.chunk_version],
        [zh ? '来源 SHA-256' : 'Source SHA-256', citation.content_checksum_sha256],
        [zh ? '原始摘录 SHA-256' : 'Original excerpt SHA-256', citation.excerpt_checksum_sha256],
        [zh ? '检索记录 ID' : 'Retrieval trace ID', citation.retrieval_trace_id],
        [zh ? '获取时间' : 'Retrieved at', citation.retrieved_at],
      ].filter(([, value]) => value !== undefined && value !== null && value !== '')
      return <div key={index} id={`${prefix}-source-${index + 1}`} className="mt-2 rounded border border-border-soft p-2"><Disclosure title={`[${index + 1}] ${label}`}>
        {href ? <a href={href} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block">{zh ? '打开原始来源' : 'Open original source'} · {label}</a> : null}
        {projectHref ? <Link to={projectHref} className="mt-2 block">{zh ? '查看项目资料' : 'View project material'}</Link> : null}
        <dl className="mt-2 grid gap-1 sm:grid-cols-[auto_1fr]">{fields.map(([name, value]) => <div key={String(name)} className="contents"><dt className="text-text-muted">{String(name)}</dt><dd className="break-all">{String(value)}</dd></div>)}</dl>
        {citationText(citation.excerpt) ? <><p className="mt-2 font-medium">{zh ? '保存的原文片段' : 'Saved source excerpt'}{citation.excerpt_truncated ? (zh ? '（预览已截短）' : ' (preview truncated)') : ''}</p><blockquote className="mt-1 whitespace-pre-wrap border-l-2 pl-2">{citationText(citation.excerpt)}</blockquote></> : <p className="mt-2 text-text-muted">{zh ? '未附原文片段，需查阅来源内容核实。' : 'No excerpt attached. Check the source content to verify the claim.'}</p>}
      </Disclosure></div>
    })}
  </div>
}
