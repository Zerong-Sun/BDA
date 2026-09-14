"""Sequence-level analysis: what a construct will do before anyone expresses it.

A table-free domain, the same shape as `structures/`: `kernels.py` is pure
functions over a sequence string, `service.py` is the one impure step that
resolves an id to a sequence. Nothing is stored - every number here is derived
from a sequence the platform already holds, and a second copy would be a second
source of truth for something the source determines.

`codon.py` turns a protein into DNA for an expression host, weighted by
`codon_usage.py` - tables counted from annotated genomes by
`scripts/build_codon_usage.py`, not copied from a published page built on a
dozen genes. That is the one part of this domain with an HTTP surface
(`api.py`) and no copilot tool: the result is a sequence, and a tool's result
is written into the conversation transcript.
"""
