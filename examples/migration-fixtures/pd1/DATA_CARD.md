# BDA PD1 Demo v1 data card

## Purpose and scope

This is a single-project demonstration of BDA's evidence, workflow, and artifact
interfaces. It contains one PD1/PD-L1 knowledge project, 12 curated public
bibliographic records, four evidence relations, four public structure references,
and six small PDB-format fixtures for three fictional candidates.

## Provenance

Bibliographic metadata and evidence relationships are derived from the public
sources linked in `frontend/public/research-packages/pd1-demo-v1.json`. Source
identifiers, URLs, roles, and verification status are retained. The demo fixture
coordinates were created for software migration and rendering tests; they are
not deposited experimental structures or outputs of a validated design model.

## Synthetic classification

The candidate IDs `a0172`, `b1923`, and `c4361`, every candidate metric, and all
files whose names begin `PD1Binder_` are synthetic. “DEMO” means precomputed test
content. Nothing in this package represents a new model run, binding result,
experimental conclusion, safety claim, or candidate recommendation.

## License and attribution

CC BY 4.0. Attribute as “BDA contributors, BDA PD1 Demo v1 (2026).” Third-party
papers and database pages retain their own terms. See `DATA_LICENSE.md`.

## Validation and limitations

The package schema is 1.1. CI validates the package semantic checksum, raw-file
checksum, reference closure, one-project scope, synthetic flags, manifest paths,
and all fixture hashes. This deliberately small package is not representative of
production scale, biological completeness, clinical validity, or model quality.
