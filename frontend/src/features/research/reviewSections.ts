/** Read saved prose without changing the source or inventing goal completion. */
export function reviewSections(markdown: string) {
  const sections: { title: string; body: string }[] = []
  let current = { title: '', body: '' }
  let fence = ''
  for (const line of markdown.split('\n')) {
    const marker = line.match(/^\s*(`{3,}|~{3,})/)?.[1]
    if (marker) { if (!fence) fence = marker[0]; else if (marker[0] === fence) fence = '' }
    const heading = !fence && line.match(/^##\s+(.+)/)
    if (heading) { if (current.body.trim()) sections.push({ ...current, body: current.body.trim() }); current = { title: heading[1], body: '' } }
    else current.body += `${line}\n`
  }
  if (current.body.trim()) sections.push({ ...current, body: current.body.trim() })
  return sections.filter((section) => section.title && !/^(references?|参考文献|文献)$/i.test(section.title))
}

