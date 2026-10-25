import { useId, useState } from 'react'
import { flushSync } from 'react-dom'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '../../components/ui/accordion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useI18n } from '../../lib/i18n'
import { CitationDetails } from './CitationDetails'
import { groupCitations } from './citationGroups'
import { remarkCitationMarkers, safeCitationUrl, type CitationRecord } from './citationMarkers'

/**
 * Long-form research prose (project reviews, methods, validation notes) is
 * authored as GitHub-flavored markdown, so headings, tables, and fenced code
 * all need explicit styling: the Tailwind preflight strips their defaults.
 * Tables become their own block-level scroll container so a wide threshold
 * table scrolls inside the card instead of widening the page.
 */
const PROSE = [
  'min-w-0 max-w-full text-sm leading-6 text-text-secondary [overflow-wrap:anywhere]',
  '[&>*:first-child]:mt-0',
  '[&_a]:text-accent [&_a]:underline',
  '[&_blockquote]:border-l-2 [&_blockquote]:border-border-default [&_blockquote]:pl-3',
  '[&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1',
  '[&_h1]:mt-6 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-text-primary',
  '[&_h2]:scroll-mt-32 [&_h2]:mt-6 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-text-primary',
  '[&_h3]:mt-4 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-text-primary',
  '[&_h4]:mt-4 [&_h4]:text-sm [&_h4]:font-semibold [&_h4]:text-text-primary',
  '[&_hr]:my-4 [&_hr]:border-border-soft',
  '[&_li]:my-1',
  '[&_ol]:ml-5 [&_ol]:list-decimal',
  '[&_p+p]:mt-2',
  '[&_pre]:mt-3 [&_pre]:overflow-x-auto [&_pre]:bg-surface-2 [&_pre]:p-3',
  '[&_pre_code]:bg-transparent [&_pre_code]:px-0',
  '[&_strong]:font-semibold [&_strong]:text-text-primary',
  '[&_table]:mt-3 [&_table]:block [&_table]:w-max [&_table]:max-w-full [&_table]:overflow-x-auto [&_table]:border-collapse [&_table]:text-xs',
  '[&_td]:border [&_td]:border-border-soft [&_td]:p-2 [&_td]:align-top',
  '[&_th]:border [&_th]:border-border-soft [&_th]:bg-surface-2 [&_th]:p-2 [&_th]:text-left [&_th]:font-semibold [&_th]:text-text-primary',
  '[&_ul]:ml-5 [&_ul]:list-disc',
].join(' ')

/** Top-level sections, in source order, for documents long enough to need an index. */
const TOC_THRESHOLD = 4

function sectionHeadings(markdown: string): string[] {
  const headings: string[] = []
  let inFence = false
  for (const line of markdown.split('\n')) {
    // A `## ` inside a fenced block is code, not a heading.
    if (line.startsWith('```')) inFence = !inFence
    else if (!inFence && line.startsWith('## ')) headings.push(line.slice(3).trim())
  }
  return headings
}

/**
 * Ids are assigned by matching heading text rather than by counting renders, so
 * StrictMode's double render cannot shift them out of step with the index.
 */
function headingText(node: React.ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(headingText).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    return headingText((node as { props: { children?: React.ReactNode } }).props.children)
  }
  return ''
}

export function ReviewMarkdown({ children, citations = [], projectId, compactCitations = true, presentation = 'document' }: { children: string; citations?: readonly CitationRecord[]; projectId?: string; compactCitations?: boolean; presentation?: 'document' | 'chat' }) {
  const { language } = useI18n()
  const [sourcesOpen, setSourcesOpen] = useState(false)
  const prefix = `review-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const sourceGroups = groupCitations(citations)
  const headings = sectionHeadings(children)
  const idByHeading = new Map(headings.map((heading, index) => [heading, `${prefix}-section-${index + 1}`]))
  const showToc = presentation !== 'chat' && headings.length >= TOC_THRESHOLD
  const emphasis = (content: React.ReactNode) => {
    if (presentation !== 'chat') return undefined
    const text = headingText(content).replace(/^[\d\s.、:：()（）-]+/, '')
    if (/^(?:结论|当前进展|一句话结论|Conclusion\b|Summary\b)/i.test(text)) return 'conclusion'
    if (/^(?:下一步|下一个|建议下一步|Next steps?\b|Next action\b)/i.test(text)) return 'next-step'
    return undefined
  }

  const toc = showToc ? (
        <nav aria-label={language === 'zh' ? '章节' : 'Sections'} className="my-4 border border-border-soft bg-surface-2 p-3">
          <ol className="!ml-0 !list-none grid gap-0.5 text-xs sm:grid-cols-2">
            {headings.map((heading) => (
              <li key={heading}>
                <a className="text-accent hover:underline" href={`#${idByHeading.get(heading)}`}
                  onClick={(event) => {
                    event.preventDefault()
                    document.getElementById(idByHeading.get(heading)!)?.scrollIntoView({ block: 'start' })
                  }}>
                  {heading}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      ) : null

  return (
    <div className={`${PROSE}${presentation === 'chat' ? ' review-markdown--chat' : ''}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, [remarkCitationMarkers, { citations }]]}
        components={{
          p: ({ children: content }) => <p data-chat-emphasis={emphasis(content)}>{content}</p>,
          h1: ({ children: content }) => <h1 data-chat-emphasis={emphasis(content)}>{content}</h1>,
          h3: ({ children: content }) => <h3 data-chat-emphasis={emphasis(content)}>{content}</h3>,
          // Retrieved and model-authored Markdown is untrusted. An image URL
          // can encode research data, so never fetch it automatically.
          img: ({ src, alt }) => {
            const href = safeCitationUrl(src)
            const label = alt || (language === 'zh' ? '查看图片' : 'Open image')
            return href ? <a href={href} target="_blank" rel="noopener noreferrer">{label}</a> : <span>{label}</span>
          },
          a: ({ href, children: content, node }) => {
            const match = node?.properties['data-bda-citation'] === true ? href?.match(/^#bda-citation-(\d+)$/) : null
            if (!match || !citations[Number(match[1]) - 1]) return <a href={href} target={href?.startsWith('http') ? '_blank' : undefined} rel="noopener noreferrer">{content}</a>
            const index = Number(match[1])
            const sourceNumber = sourceGroups.find(group => group.numbers.includes(index))?.numbers[0] ?? index
            const id = `${prefix}-source-${sourceNumber}`
            return <sup><a href={`#${id}`} aria-label={`${language === 'zh' ? '查看来源' : 'View source'} ${index}`} onClick={(event) => {
              event.preventDefault()
              // Mount the compact source list before locating the exact source.
              // The source's own disclosure can then open without changing the app hash.
              if (compactCitations && !sourcesOpen) flushSync(() => setSourcesOpen(true))
              const detail = document.getElementById(id)
              const trigger = detail?.querySelector<HTMLButtonElement>('[data-slot="accordion-trigger"]')
              if (trigger?.getAttribute('aria-expanded') === 'false') trigger.click()
              detail?.scrollIntoView?.({ block: 'nearest' })
            }}>{content}</a></sup>
          },
          h2: ({ children: content, ...props }) => (
            <>{headingText(content) === headings[0] ? toc : null}<h2 {...props} id={idByHeading.get(headingText(content))} data-chat-emphasis={emphasis(content)}>
              {content}
            </h2></>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
      {compactCitations && citations.length ? (
        <Accordion className="mt-2" value={sourcesOpen ? ['sources'] : []} onValueChange={value => setSourcesOpen(value.includes('sources'))}>
          <AccordionItem value="sources" className="border-0">
            <AccordionTrigger heading={false} className="py-1.5">{language === 'zh' ? `参考资料（${sourceGroups.length}）` : `Reference materials (${sourceGroups.length})`}</AccordionTrigger>
            <AccordionContent><CitationDetails citations={citations} prefix={prefix} projectId={projectId} /></AccordionContent>
          </AccordionItem>
        </Accordion>
      ) : <CitationDetails citations={citations} prefix={prefix} projectId={projectId} />}
    </div>
  )
}
