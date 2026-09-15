import { Link } from 'react-router'
import { Badge } from '../../components/reui/badge'
import { useI18n } from '../../lib/i18n'

/**
 * What an answer rests on, rendered the same way wherever the answer appears.
 *
 * This was inline in `CopilotChat`, which was fine while the chat was the only
 * place an assistant message was read. The research room reads the same
 * messages from the server, and a second copy of this block would have been the
 * usual outcome: two surfaces showing the same citation with different
 * emphasis, and no test that fails when they drift.
 *
 * A project citation links into the Research workspace tab that holds it, an
 * external one opens its URL, and one with neither is still shown - a citation
 * the client cannot address is not a citation to hide, because the alternative
 * is an answer that looks unsupported when it is not.
 */
export function CopilotCitations({
  citations,
  projectId,
}: {
  citations: ReadonlyArray<Record<string, unknown>>
  projectId?: string
}) {
  const { t, format } = useI18n()
  if (!citations.length) return null
  return (
    <div className="mt-3 flex flex-wrap gap-1.5 border-t pt-2">
      {citations.map((citation, citationIndex) => {
        const url = typeof citation.url === 'string' ? citation.url : ''
        const label = String(
          citation.label ||
            citation.entity_id ||
            citation.workspace_type ||
            format(t.copilot.chat.citationSourceFallback, {
              index: citationIndex + 1,
            }),
        )
        const evidence = [citation.evidence_grade, citation.review_status]
          .filter(Boolean)
          .join(' · ')
        const internal = citation.source_type === 'research_workspace'
        const origin = internal
          ? t.copilot.chat.citationProject
          : t.copilot.chat.citationExternal
        const accessibleLabel = [label, origin, evidence].filter(Boolean).join(' ')
        const kind = String(citation.workspace_type || '')
        const tab =
          kind === 'reference'
            ? 'references'
            : kind === 'structure'
              ? 'structures'
              : ['dataset', 'research_target'].includes(kind)
                ? 'data'
                : kind === 'method'
                  ? 'methods'
                  : 'evidence'
        const badge = (
          <Badge
            variant={internal ? 'info-light' : 'outline'}
            size="xs"
            className="h-auto whitespace-normal py-1"
          >
            <span>{label}</span>
            <span className="text-[9px] uppercase">
              {origin}
              {evidence ? ` · ${String(evidence)}` : ''}
            </span>
          </Badge>
        )
        const key = `${String(citation.entity_id)}-${citationIndex}`
        return url ? (
          <a
            key={key}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={accessibleLabel}
            className="hover:underline"
          >
            {badge}
          </a>
        ) : internal && projectId ? (
          <Link
            key={key}
            to={`/research?tab=${tab}&project=${encodeURIComponent(projectId)}`}
            aria-label={accessibleLabel}
            className="hover:underline"
          >
            {badge}
          </Link>
        ) : (
          <span key={key}>{badge}</span>
        )
      })}
    </div>
  )
}
