/** A marker resolves only against supplied source records. No source-to-claim inference. */
export type CitationRecord = Record<string, unknown>
type MarkdownNode = { type: string; value?: string; url?: string; children?: MarkdownNode[]; data?: { hProperties: Record<string, unknown> } }

export function citationText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

const CITATION_LABELS: Record<string, [string, string]> = {
  scientific_literature: ['科学文献', 'Scientific literature'], research_workspace: ['项目研究资料', 'Project research'],
  project_database: ['项目记录', 'Project record'], external_reference: ['外部参考来源', 'External reference'],
  pending: ['待处理', 'Pending'], pending_review: ['待人工审阅', 'Awaiting review'], pending_human_review: ['待人工审阅', 'Awaiting review'],
  accepted: ['已接受', 'Accepted'], rejected: ['已拒绝', 'Rejected'], available: ['已保存', 'Saved'], metadata_only: ['仅书目信息', 'Metadata only'],
  verified: ['元数据已核对', 'Metadata checked'], verified_europe_pmc: ['Europe PMC 元数据已核对', 'Metadata checked in Europe PMC'],
  verified_europe_pmc_metadata: ['Europe PMC 元数据已核对', 'Metadata checked in Europe PMC'],
  verified_crossref: ['Crossref 元数据已核对', 'Metadata checked in Crossref'], verified_rcsb: ['RCSB 元数据已核对', 'Metadata checked in RCSB'],
  metadata_mismatch: ['元数据不一致', 'Metadata mismatch'], linked_from_review: ['来自研究综述', 'Linked from review'],
  verified_epo_ops_metadata: ['EPO OPS 元数据已核对', 'Metadata checked in EPO OPS'], unverified: ['尚未核对', 'Unchecked'],
  completed: ['完成', 'Completed'], failed: ['失败', 'Failed'], search: ['检索', 'Search'], search_hit: ['命中记录', 'Search hit'],
  metadata_verification: ['元数据核验', 'Metadata verification'], full_text: ['全文获取请求', 'Full-text retrieval request'], abstract: ['摘要获取', 'Abstract retrieval'],
}

export function citationValueLabel(value: unknown, language: 'zh' | 'en'): string {
  return CITATION_LABELS[String(value)]?.[language === 'zh' ? 0 : 1] ?? String(value)
}

export function safeCitationUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : undefined
  } catch { return undefined }
}

export function citationAliases(citations: readonly CitationRecord[]): Map<string, number> {
  const aliases = new Map<string, number>()
  const ambiguous = new Set<string>()
  citations.forEach((citation, index) => {
    const values = [citation.entity_id, citation.ref_id, citation.bibliography_number, ...(Array.isArray(citation.reference_ids) ? citation.reference_ids : [])]
    for (const value of values) {
      const alias = citationText(value).trim()
      if (!alias || ambiguous.has(alias)) continue
      if (aliases.has(alias) && aliases.get(alias) !== index) { aliases.delete(alias); ambiguous.add(alias) }
      else aliases.set(alias, index)
    }
  })
  // The answer-local catalogue is authoritative even if an external ID happens to look like cite:N.
  citations.forEach((_, index) => aliases.set(`cite:${index + 1}`, index))
  return aliases
}

function resolveTag(token: string, citations: readonly CitationRecord[], aliases: Map<string, number>): number | undefined {
  if (!token.startsWith('document_id=')) return aliases.get(token)
  const fields = Object.fromEntries(token.split(';').map((entry) => {
    const equals = entry.indexOf('=')
    return [entry.slice(0, equals).trim(), entry.slice(equals + 1).trim()]
  }))
  const required = ['document_id', 'chunk_id', 'content_kind', 'content_checksum_sha256', 'retrieval_trace_id']
  if (!required.every((key) => fields[key])) return undefined
  const index = citations.findIndex((citation) => required.every((key) => citationText(citation[key]) === fields[key]))
  return index < 0 ? undefined : index
}

function resolveGroup(token: string, citations: readonly CitationRecord[], aliases: Map<string, number>): number[] {
  const direct = resolveTag(token, citations, aliases)
  if (direct !== undefined) return [direct]
  if (!/^\d+(?:\s*[,，–-]\s*\d+)+$/.test(token)) return []
  const numbers: string[] = []
  for (const part of token.split(/[,，]/)) {
    const range = part.trim().split(/[–-]/).map(Number)
    if (range.length === 1) numbers.push(String(range[0]))
    else {
      if (range[1] < range[0] || range[1] - range[0] > 50) return []
      for (let number = range[0]; number <= range[1]; number++) numbers.push(String(number))
    }
  }
  // A partially missing bibliography must remain visible, not become a complete-looking citation.
  if (!numbers.every((number) => aliases.has(number))) return []
  return [...new Set(numbers.map((number) => aliases.get(number)!))]
}

/** Transform text nodes only: links, code and raw source text never become new citations. */
export function remarkCitationMarkers({ citations }: { citations: readonly CitationRecord[] }) {
  const aliases = citationAliases(citations)
  return (tree: MarkdownNode) => {
    const visit = (parent: MarkdownNode) => {
      if (!parent.children || ['link', 'code', 'inlineCode', 'html'].includes(parent.type)) return
      parent.children = parent.children.flatMap((node) => {
        if (node.type !== 'text' || !node.value) { visit(node); return [node] }
        const result: MarkdownNode[] = []
        let offset = 0
        for (const match of node.value.matchAll(/\[([^\]\n[]+)\]/g)) {
          const indices = resolveGroup(match[1], citations, aliases)
          if (!indices.length) continue
          if (match.index > offset) result.push({ type: 'text', value: node.value.slice(offset, match.index) })
          for (const index of indices) result.push({ type: 'link', url: `#bda-citation-${index + 1}`, data: { hProperties: { 'data-bda-citation': true } }, children: [{ type: 'text', value: `[${index + 1}]` }] })
          offset = match.index + match[0].length
        }
        if (!result.length) return [node]
        if (offset < node.value.length) result.push({ type: 'text', value: node.value.slice(offset) })
        return result
      })
    }
    visit(tree)
  }
}
