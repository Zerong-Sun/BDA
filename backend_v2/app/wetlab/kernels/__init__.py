"""Pure analysis kernels for wet-lab instrument data.

Ported from the protein-lab workbench (`QINGMINGMIKU/protein-lab`, branch
`ui-design2`). These modules carry reverse-engineered instrument formats that
cost real effort to derive and are documented in
`docs/refactor/PRESERVED_PRINCIPLES.md`:

* `akta`  — AKTA Unicorn zip read with the standard library only (no pycorn).
            The nested `Chrom.N_MM_True` zip is non-standard: its EOCD is not
            at the end, so it must be truncated at `rindex(EOCD)+22`; inside,
            `CoordinateData` holds .NET-serialised float32 starting at offset
            47 with 48 trailing bytes to skip.
* `bli`   — ForteBio CSV parsing (metadata order == column order, never
            reorder) and 1:1 Langmuir KD fitting by five methods.
* `calculators` — MW / extinction coefficient / Beer-Lambert concentration,
            the six-unit concentration kernel, BLI dilution planning, and
            TECAN enzyme-kinetics parsing and fitting.

Two deliberate departures from the source:

* **No plotting.** protein-lab rendered PNGs with matplotlib because it was a
  Jinja app with no frontend build. Here the kernels return data and the
  browser draws it, so charts are interactive and matplotlib stays out of the
  backend image. Fitted-curve *data* is still produced, for the dashed overlay.
* **Parsers accept bytes.** The API never receives file bodies (uploads go
  straight to object storage), so each parser takes a path *or* raw bytes.

They keep no framework dependency, exactly as they had none in protein-lab.
"""
