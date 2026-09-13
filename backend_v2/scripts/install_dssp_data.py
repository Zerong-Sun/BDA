"""Install the wwPDB CCD at image-build time so DSSP runs with networking disabled."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import urllib.request
from pathlib import Path

CCD_URL = "https://files.wwpdb.org/pub/pdb/data/monomers/components.cif.gz"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("/usr/share/libcifpp/components.cif.gz"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".download")
    with urllib.request.urlopen(CCD_URL, timeout=120) as source, temporary.open("wb") as destination:
        shutil.copyfileobj(source, destination)
    # libcifpp's Debian build expects the uncompressed CCD even when the
    # diagnostic mentions .gz. Install a plain file and validate the entire gzip.
    uncompressed = args.output.with_suffix("") if args.output.suffix == ".gz" else args.output
    with gzip.open(temporary, "rb") as data, uncompressed.open("wb") as destination:
        shutil.copyfileobj(data, destination)
    with temporary.open("rb") as data:
        checksum = hashlib.file_digest(data, "sha256").hexdigest()
    temporary.unlink()
    uncompressed.with_suffix(uncompressed.suffix + ".source-sha256").write_text(checksum + "\n")
    print(f"DSSP CCD sha256={checksum}")


if __name__ == "__main__":
    main()
