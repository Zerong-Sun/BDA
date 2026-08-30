# Contributing

Contributions are made through pull requests. Create a focused branch, add tests
for behavior changes, run the backend and frontend checks documented in the
README, and describe migration and security implications in the PR.

All commits must pass CI, public-data policy, secret scanning, and review. Do not
commit private research data, generated research runs, credentials, large binary
artifacts, or a second package manager lockfile. Frontend dependencies use npm;
Python dependencies must follow the repository lock policy.

By contributing software you agree that it is licensed under Apache-2.0. Data
contributions require a source, provenance, explicit license, data card, schema
version, checksum, and synthetic/real classification under `DATA_POLICY.md`.
