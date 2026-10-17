/** Reorder existing prose only. Never summarize tool output into a scientific claim. */
const processTitle = /^(?:本次所做工作|本轮所做工作|本次工作|本轮性质|工具(?:调用|回读|返回|结果)|执行过程|操作过程|调用记录|过程记录|已调用工具|work performed|tool (?:calls?|results?|output)|execution log)/i
const nextTitle = /^(?:下一(?:步|项|个)|后续(?:工作|顺序|队列)|建议下一步|next (?:steps?|actions?))/i
const resultTitle = /^(?:结论|项目结论|当前结论|当前进展|(?:作业|工作流)?真实状态|三类状态|按三类状态|状态分类|结果|研究结果|主要发现|conclusions?|results?|summary|findings)/i
const reviewTitle = /^(?:复核|审阅结论|review|关键约束|主要风险|未关闭|项目整体还差)/i
const cleanTitle = (value: string) => value.replace(/[*_`]/g, '').replace(/^[\s一二三四五六七八九十\d.、:：()（）-]+/, '').trim()
const knownTitle = (value: string) => [processTitle, nextTitle, resultTitle, reviewTitle].some(pattern => pattern.test(cleanTitle(value)))

function priority(title: string) {
  const value = cleanTitle(title)
  return resultTitle.test(value) ? 0 : reviewTitle.test(value) ? 1 : nextTitle.test(value) ? 2 : 3
}

export function answerPresentation(markdown: string) {
  const sections: { title: string; lines: string[] }[] = []
  let current = { title: '', lines: [] as string[] }
  let fence = ''
  for (const line of markdown.split('\n')) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1]
    if (marker) { if (!fence) fence = marker[0]; else if (marker[0] === fence) fence = '' }
    const bold = line.match(/^\s*\*\*(.+?)\*\*(.*)$/)
    const heading = !fence && !marker && (line.match(/^#{1,6}\s+(.+)$/)?.[1]
      ?? (bold && (!bold[2].trim() || knownTitle(bold[1])) ? bold[1] : undefined)
      ?? (line.trim().length < 90 && knownTitle(line) ? line.trim() : undefined))
    if (heading) {
      if (current.lines.length) sections.push(current)
      current = { title: heading, lines: [line] }
    } else current.lines.push(line)
  }
  if (current.lines.length) sections.push(current)
  const folded: string[] = []
  const visible: { title: string; text: string }[] = []
  for (const section of sections) {
    const text = section.lines.join('\n').trim()
    if (!text) continue
    if (processTitle.test(cleanTitle(section.title))) { folded.push(text); continue }
    const blocks: string[] = []
    let block: string[] = []
    fence = ''
    for (const line of section.lines) {
      const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1]
      if (marker) { if (!fence) fence = marker[0]; else if (marker[0] === fence) fence = '' }
      if (!line.trim() && !fence) { if (block.length) blocks.push(block.join('\n')); block = [] }
      else block.push(line)
    }
    if (block.length) blocks.push(block.join('\n'))
    const prose = blocks.map(value => value.replace(
      /(?:^|(?<=。)|\n)[ \t]*(?:[-*]\s+)?`?(?:get|list|search|read|fetch)_[a-z_]+`?(?:\([^\n)]*\))?`?\s*(?:当前|本次)?(?:返回|→|->|=)[^。\n]*。/g,
      statement => { folded.push(statement.trim()); return '' },
    )).filter(value => {
      if (!value.trim()) return false
      const start = value.trim().replace(/^(?:[-*]|\d+[.)])\s+/, '').replace(/^`/, '')
      const toolOutput = /^(?:(?:get|list|search|read|fetch)_[a-z_]+)(?:`?\s*\([^\n]*\))?`?\s*(?:→|->|返回|=)/i.test(start)
      const onlyLog = /^\s*(?:```|~~~)/.test(value) || (!value.includes('\n') && /project-refresh-\d+/.test(value)) || /^工作流 ID 备查[：:]/.test(start)
      if (toolOutput || onlyLog) { folded.push(value); return false }
      return true
    }).join('\n\n').trim()
    // A heading without any remaining prose should not occupy the default view.
    if (prose && !(section.title && prose === section.lines[0]?.trim() && prose !== text)) visible.push({ title: section.title, text: prose })
  }
  return { visible: visible.sort((a, b) => priority(a.title) - priority(b.title)).map(section => section.text).join('\n\n'), folded: folded.join('\n\n') }
}
