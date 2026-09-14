"""Sequence-level analysis: what a construct will do before anyone expresses it.

A table-free domain, the same shape as `structures/`: `kernels.py` is pure
functions over a sequence string, `service.py` is the one impure step that
resolves an id to a sequence. Nothing is stored - every number here is derived
from a sequence the platform already holds, and a second copy would be a second
source of truth for something the source determines.
"""
