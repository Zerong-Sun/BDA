# Public data publication policy

`BDA` is a public software repository. Its only bundled dataset is the reviewed
`pd1-demo-v1` package and its six synthetic `DEMO` PDB fixtures. Private research
data belongs in the private `BDA-demo` overlay, never in this repository.

Every public data change requires:

1. a stable package ID and semantic version;
2. machine-readable schema version and SHA-256 checksums;
3. a data card with scope, provenance, limitations, license, and real/synthetic labels;
4. closed reference relationships and reproducible validation;
5. explicit reviewer confirmation that no confidential data, secrets, or unapproved large files are present.

Git stores code, small manifests, and reviewable demo data. Runtime artifacts use
MinIO; medium private files may use Git LFS only in the private overlay.
Published data is treated as disclosed permanently even if a repository is later
made private.
