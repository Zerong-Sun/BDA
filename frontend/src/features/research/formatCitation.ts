import { safeCitationUrl } from './citationMarkers'

export interface FormattedCitation {
  label: string
  href?: string
  title: string
}

function cleanDoi(value: string): string {
  let doi = value.replace(/[.,;]+$/, '')
  while (doi.endsWith(')') && (doi.match(/\)/g)?.length ?? 0) > (doi.match(/\(/g)?.length ?? 0)) doi = doi.slice(0, -1)
  return doi
}

export function formatCitation(raw: string): FormattedCitation {
  const value = raw.trim()
  const href = safeCitationUrl(value)
  if (href) {
    const url = new URL(href)
    const host = url.hostname.replace(/^www\./, '').toLowerCase()
    let label = host
    const segments = url.pathname.split('/').filter(Boolean)
    if (host === 'pubmed.ncbi.nlm.nih.gov' && /^\d+$/.test(segments[0] ?? '')) label = `PMID ${segments[0]}`
    else if (host === 'rcsb.org' && segments[0] === 'structure' && /^[0-9][A-Z0-9]{3}$/i.test(segments[1] ?? '')) label = `PDB ${segments[1].toUpperCase()}`
    else if (host === 'uniprot.org' && segments[0] === 'uniprotkb' && /^[A-Z0-9]{6,10}(?:-\d+)?$/i.test(segments[1] ?? '')) label = `UniProt ${segments[1]}`
    else if (host === 'doi.org' && /^10\.\d{4,9}\//.test(url.pathname.slice(1))) label = `DOI ${url.pathname.slice(1)}`
    return { label, href: value, title: value }
  }
  // A rejected URL must not be relabelled as a trusted identifier by a substring in its path.
  if (/^[a-z][a-z\d+.-]*:\/\//i.test(value)) return { label: value, title: value }
  const pmid = value.match(/^PMID[:\s]+(\d+)$/i)?.[1]
  if (pmid) return { label: `PMID ${pmid}`, href: `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`, title: value }
  const pdb = value.match(/^PDB[:\s]+([0-9][A-Z0-9]{3})$/i)?.[1]?.toUpperCase()
  if (pdb) return { label: `PDB ${pdb}`, href: `https://www.rcsb.org/structure/${pdb}`, title: value }
  const uniprot = value.match(/^UniProt[:\s]+([A-Z0-9]{6,10}(?:-\d+)?)$/i)?.[1]
  if (uniprot) return { label: `UniProt ${uniprot}`, href: `https://www.uniprot.org/uniprotkb/${uniprot}/entry`, title: value }
  const doi = value.match(/^(?:doi:\s*)?(10\.\d{4,9}\/[-._;()/:A-Z0-9]+)$/i)?.[1]
  if (doi) { const clean = cleanDoi(doi); return { label: `DOI ${clean}`, href: `https://doi.org/${clean}`, title: value } }
  return { label: value, title: value }
}
