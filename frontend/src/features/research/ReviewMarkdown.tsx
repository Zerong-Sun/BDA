import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Long-form research prose (project reviews, methods, validation notes) is
 * authored as GitHub-flavored markdown, so headings, tables, and fenced code
 * all need explicit styling: the Tailwind preflight strips their defaults.
 * Tables become their own block-level scroll container so a wide threshold
 * table scrolls inside the card instead of widening the page.
 */
const PROSE = [
  'max-w-none text-sm leading-6 text-text-secondary',
  '[&>*:first-child]:mt-0',
  '[&_a]:text-accent [&_a]:underline',
  '[&_blockquote]:border-l-2 [&_blockquote]:border-border-default [&_blockquote]:pl-3',
  '[&_code]:rounded [&_code]:bg-surface-2 [&_code]:px-1',
  '[&_h1]:mt-6 [&_h1]:text-base [&_h1]:font-semibold [&_h1]:text-text-primary',
  '[&_h2]:mt-6 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-text-primary',
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

export function ReviewMarkdown({ children }: { children: string }) {
  const headings = sectionHeadings(children)
  const idByHeading = new Map(headings.map((heading, index) => [heading, `section-${index + 1}`]))
  const showToc = headings.length >= TOC_THRESHOLD

  return (
    <div className={PROSE}>
      {showToc ? (
        <nav aria-label="Sections" className="mb-4 border border-border-soft bg-surface-2 p-3">
          <ol className="!ml-4 grid gap-0.5 text-xs sm:grid-cols-2">
            {headings.map((heading) => (
              <li key={heading}>
                <a className="text-accent hover:underline" href={`#${idByHeading.get(heading)}`}>
                  {heading}
                </a>
              </li>
            ))}
          </ol>
        </nav>
      ) : null}
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children: content, ...props }) => (
            <h2 {...props} id={idByHeading.get(headingText(content))}>
              {content}
            </h2>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  )
}
