export interface FormattedCitation {
  label: string
  href?: string
  title: string
}

const DOI_PATTERN = /(?:doi\.org\/|doi:\s*)?(10\.\d{4,9}\/[-._;()/:A-Z0-9]+)/i
const PMID_PATTERN = /(?:pubmed\.ncbi\.nlm\.nih\.gov\/|PMID[:\s]*)(\d+)/i
const PDB_PATTERN = /(?:rcsb\.org\/structure\/|PDB[:\s]*)([0-9][A-Z0-9]{3})/i
const UNIPROT_PATTERN = /(?:uniprot(?:kb)?\/|UniProt[:\s]*)([A-Z0-9]+)(?:\/entry)?/i

function domainLabel(value: string): string | undefined {
  try {
    const url = new URL(value)
    return url.hostname.replace(/^www\./, '')
  } catch {
    return undefined
  }
}

function hrefFor(value: string): string | undefined {
  if (/^https?:\/\//i.test(value)) return value
  const doi = value.match(DOI_PATTERN)?.[1]
  if (doi) return `https://doi.org/${doi}`
  const pmid = value.match(PMID_PATTERN)?.[1]
  if (pmid) return `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`
  const pdb = value.match(PDB_PATTERN)?.[1]
  if (pdb) return `https://www.rcsb.org/structure/${pdb.toUpperCase()}`
  const uniprot = value.match(UNIPROT_PATTERN)?.[1]
  if (uniprot) return `https://www.uniprot.org/uniprotkb/${uniprot}/entry`
  return undefined
}

export function formatCitation(raw: string): FormattedCitation {
  const value = raw.trim()
  const pdb = value.match(PDB_PATTERN)?.[1]
  if (pdb) return { label: `PDB ${pdb.toUpperCase()}`, href: hrefFor(value), title: value }

  const pmid = value.match(PMID_PATTERN)?.[1]
  if (pmid) return { label: `PMID ${pmid}`, href: hrefFor(value), title: value }

  const uniprot = value.match(UNIPROT_PATTERN)?.[1]
  if (uniprot) return { label: `UniProt ${uniprot}`, href: hrefFor(value), title: value }

  const doi = value.match(DOI_PATTERN)?.[1]
  if (doi) return { label: `DOI ${doi}`, href: hrefFor(value), title: value }

  const domain = domainLabel(value)
  if (domain) return { label: domain, href: value, title: value }

  return { label: value, title: value }
}
