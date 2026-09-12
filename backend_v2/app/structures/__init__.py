"""Read-only structure analysis.

A table-free domain: structures arrive as artifacts, which are already
write-once and checksummed, so there is nothing here to persist. `kernels`
holds pure functions over structure text; `service` adds the one impure step
that fetches an artifact's bytes.
"""
