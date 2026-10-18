import { reviewSections } from './reviewSections'

/** Select saved sections only; headings are navigation, never proof of completion. */
export function reviewOverview(markdown: string) {
  const sections = reviewSections(markdown)
  const objectives = sections.filter(section => /objective|research questions?|研究目标|研究问题|决策问题/i.test(section.title))
  const unresolved = sections.filter(section => /uncertainty|conflict|limits?|limitation|gat(?:e|ing)|next|open questions?|争议|矛盾|局限|下一步|闸门|待验证|未解决/i.test(section.title))
  const candidates = sections.filter(section => !objectives.includes(section) && !unresolved.includes(section) && !/route|method|design plan|路线|方法|方案/i.test(section.title))
  const results = candidates.filter(section => /conclusions?|results?|findings|summary|结论|结果|发现|成果|总结/i.test(section.title))
  const findings = results.length ? results : candidates.filter(section => /structure|signaling|mechanism|结构|信号|机制/i.test(section.title))
  return { objectives, findings, unresolved }
}

/** Keep an authored question list separate without generating or answering questions. */
export function splitObjectiveQuestions(markdown: string, title = '') {
  if (/questions?|问题/i.test(title) && !/objective|目标/i.test(title)) {
    return { objective: '', questions: markdown }
  }
  const lines = markdown.split('\n')
  let fence = ''
  const index = lines.findIndex(line => {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1]
    if (marker) {
      if (!fence) fence = marker[0]
      else if (marker[0] === fence) fence = ''
      return false
    }
    return !fence && /^\d+[.)]\s+/.test(line)
  })
  const numberedLines = lines.slice(index).filter(line => /^\d+[.)]\s+/.test(line))
  if (index < 0 || !numberedLines.every(line => /[?？]\s*$/.test(line))) return { objective: markdown, questions: '' }
  return { objective: lines.slice(0, index).join('\n').trim(), questions: lines.slice(index).join('\n').trim() }
}

export function findingReviewCounts(findings: readonly { id: string; evidence?: Record<string, unknown> }[]) {
  const counts = new Map<string, number>()
  const seen = new Set<string>()
  for (const finding of findings) {
    if (seen.has(finding.id)) continue
    seen.add(finding.id)
    const raw = finding.evidence?.review_status
    const status = typeof raw === 'string' && raw.trim() ? raw.trim() : 'unrecorded'
    counts.set(status, (counts.get(status) ?? 0) + 1)
  }
  return [...counts].sort(([a], [b]) => a.localeCompare(b))
}

/** Missing or invalid timestamps cannot establish which saved record is newer. */
export function isNewerSavedRecord(candidate: string | null | undefined, current: string | null | undefined) {
  const candidateTime = candidate ? Date.parse(candidate) : Number.NaN
  const currentTime = current ? Date.parse(current) : Number.NaN
  return Number.isFinite(candidateTime) && Number.isFinite(currentTime) && candidateTime > currentTime
}

/** Display verbatim prose for legacy notes without structured sections; never infer completion. */
export function unsectionedReportOverview(markdown: string) {
  let fence = ''
  const prose = markdown.split('\n').filter(line => {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1]
    if (marker) { if (!fence) fence = marker[0]; else if (marker[0] === fence) fence = ''; return false }
    return !fence
  }).join('\n')
  if (/^##\s+/m.test(prose)) return { excerpt: '', next: '' }
  const blocks = prose.split(/\n\s*\n/).map(block => block.trim()).filter(block => block && !/^#|^\||^---+$/.test(block))
  // A saved hold instruction overrides suggestions elsewhere in the historical note.
  const hold = blocks.find(block => /^(?:用户最新指示|最新执行状态|本轮状态)[：:].*(?:暂停|停止)/.test(block))
  const nextIndex = blocks.findIndex(block => /^(?:待[^：:\n]{0,24}补齐[：:]|下一(?:步|阶段)|Next steps?[:\s])/i.test(block) || /(?:^|[。；])下一阶段/.test(block))
  const nextBlocks = nextIndex < 0 ? [] : [blocks[nextIndex]]
  for (let index = nextIndex + 1; nextIndex >= 0 && index < blocks.length; index += 1) {
    if (!/^[-*]\s/.test(blocks[index])) break
    nextBlocks.push(blocks[index])
  }
  const next = hold ?? nextBlocks.join('\n\n')
  const excerptBlocks = blocks.slice(0, 2)
  // Keep a label and its following list together rather than showing an empty 'Completed:'.
  if (/[：:]$/.test(excerptBlocks.at(-1) ?? '')) {
    for (let index = 2; index < blocks.length && /^[-*]\s/.test(blocks[index]); index += 1) excerptBlocks.push(blocks[index])
  }
  return { excerpt: excerptBlocks.join('\n\n'), next }
}
