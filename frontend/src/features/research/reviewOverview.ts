import { reviewSections } from './reviewSections'

/** Select saved sections only; headings are navigation, never proof of completion. */
export function reviewOverview(markdown: string) {
  const sections = reviewSections(markdown)
  const objectives = sections.filter(section => /objective|research questions?|研究目标|研究问题|决策问题/i.test(section.title))
  const unresolved = sections.filter(section => /uncertainty|conflict|limits?|limitation|gat(?:e|ing)|next|open questions?|readiness|当前准备判定|争议|矛盾|局限|下一步|闸门|待验证|未解决/i.test(section.title))
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

/** Keep section ancestry so historical plans and source text cannot become current instructions. */
function currentProseBlocks(markdown: string, preambleOnly = false) {
  const blocks: string[] = []
  const headings: { level: number; title: string }[] = []
  let paragraph: string[] = []
  let fence: { character: string; length: number } | undefined
  const excluded = () => headings.some(({ level, title }) =>
    /histor(?:y|ical)|previous|archiv|历史|过往|归档|references?|sources?|参考|引用|来源/i.test(title)
    || (preambleOnly && level >= 2)
    || (level >= 2 && !/results?|findings|conclusions?|summary|status|progress|next|pause|hold|stop|结果|结论|发现|总结|状态|进展|下一|暂停|停止|准备判定/.test(title.toLowerCase())))
  const flush = () => {
    const text = paragraph.join('\n').trim()
    if (text && !excluded() && !/^\||^---+$/.test(text)) blocks.push(text)
    paragraph = []
  }
  for (const line of markdown.split('\n')) {
    const marker = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/)
    if (fence) {
      if (marker && marker[1][0] === fence.character && marker[1].length >= fence.length && !marker[2].trim()) fence = undefined
      continue
    }
    if (marker) { flush(); fence = { character: marker[1][0], length: marker[1].length }; continue }
    const heading = line.match(/^ {0,3}(#{1,6})\s+(.+?)(?:\s+#+)?\s*$/)
    if (heading) {
      flush()
      const level = heading[1].length
      while (headings.length && headings[headings.length - 1].level >= level) headings.pop()
      headings.push({ level, title: heading[2] })
      // A status saved as a heading is still part of the authored record.
      if (!excluded() && /暂停|停止|\bpaused?\b|\bon hold\b|\bstop(?:ped)?\b/i.test(heading[2])) blocks.push(heading[2])
    } else if (!line.trim()) flush()
    else paragraph.push(line)
  }
  flush()
  return blocks
}

/** Surface authored hold context; never derive an instruction from historical/source sections. */
export function savedReportHold(markdown: string) {
  return currentProseBlocks(markdown).find(block => /暂停|停止|\bpaused?\b|\bon hold\b|\bstop(?:ped)?\b/i.test(block)) ?? ''
}

/** Display verbatim current prose, including a preamble before a references section. */
export function unsectionedReportOverview(markdown: string) {
  const blocks = currentProseBlocks(markdown, true)
  const hold = savedReportHold(markdown)
  const nextIndex = blocks.findIndex(block => /^(?:待[^：:\n]{0,24}补齐[：:]|下一(?:步|阶段)|Next steps?[:\s])/i.test(block) || /(?:^|[。；])下一阶段/.test(block))
  const nextBlocks = nextIndex < 0 ? [] : [blocks[nextIndex]]
  for (let index = nextIndex + 1; nextIndex >= 0 && index < blocks.length; index += 1) {
    if (!/^[-*]\s/.test(blocks[index])) break
    nextBlocks.push(blocks[index])
  }
  const next = hold || nextBlocks.join('\n\n')
  const excerptBlocks = blocks.slice(0, 2)
  // Keep a label and its following list together rather than showing an empty 'Completed:'.
  if (/[：:]$/.test(excerptBlocks.at(-1) ?? '')) {
    for (let index = 2; index < blocks.length && /^[-*]\s/.test(blocks[index]); index += 1) excerptBlocks.push(blocks[index])
  }
  return { excerpt: excerptBlocks.join('\n\n'), next }
}
