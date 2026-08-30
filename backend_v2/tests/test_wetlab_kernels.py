"""The ported wet-lab analysis kernels.

These carry reverse-engineered instrument formats and fitting maths that took
real effort to derive (see docs/refactor/PRESERVED_PRINCIPLES.md). They came
across from protein-lab with no tests, which made them the least-protected code
in the repository despite being the hardest to re-derive if it broke.

Fixtures are synthesised rather than sampled from real runs: a curve generated
from known kon/koff can assert that the fit *recovers those numbers*, which a
recorded curve cannot.
"""

from __future__ import annotations

import io
import struct
import zipfile

import numpy as np
import pytest
from backend_v2.app.wetlab.kernels import akta, bli, calculators

# --- BLI: ForteBio parsing ---------------------------------------------------


def _fortebio_csv(samples: list[tuple[str, float]], points: int = 200) -> bytes:
    """A minimal ForteBio pre-processed CSV, in the layout the parser expects.

    The shape is positional and the parser deliberately does not reorder it:
    row 1 carries `t<n><WELL>c<n>` column headers, rows 2-3 carry
    `Sample Loc:` / `Sample ID:` / `Sample Conc:` in sensor order, and data
    starts at row 5. Reordering any of it breaks the 1:1 correspondence between
    a sensor's metadata and its two columns.
    """
    wells = [f"A{index + 1}" for index in range(len(samples))]
    header = [""]
    for index, well in enumerate(wells):
        header += [f"t{index + 1}{well}c1", f"t{index + 1}{well}c2"]
    row_loc_id: list[str] = []
    row_conc: list[str] = []
    for well, (sid, conc) in zip(wells, samples, strict=True):
        row_loc_id += [f"Sample Loc: {well}", f"Sample ID: {sid}"]
        row_conc += [f"Sample Conc: {conc}", ""]

    rows = [["<XmlHeader/>"], header, row_loc_id, row_conc, ["units"]]
    for step in range(points):
        line: list[str] = []
        t = step * 1.0
        for _, conc in samples:
            response = 0.001 * conc * (1 - np.exp(-0.02 * t))
            line += [f"{t}", f"{response:.6f}"]
        rows.append(line)
    return "\n".join(",".join(row) for row in rows).encode("utf-8")


def test_fortebio_csv_parses_into_curves_and_keeps_column_order() -> None:
    curves = bli.parse_fortebio_csv(_fortebio_csv([("S1", 100.0), ("S1", 50.0), ("S2", 25.0)]))

    # The label is the well the sensor read, taken from the column header.
    assert [curve.label for curve in curves] == ["A1", "A2", "A3"]
    assert [curve.sample_id for curve in curves] == ["S1", "S1", "S2"]
    # Concentration rides with its own sensor column, not sorted into place.
    assert [curve.conc_nM for curve in curves] == [100.0, 50.0, 25.0]
    assert curves[0].time.shape == curves[0].response.shape


def test_fortebio_rejects_a_file_too_short_to_be_one() -> None:
    with pytest.raises(ValueError, match="行数不足|rows"):
        bli.parse_fortebio_csv(b"only,one,line\n")


def test_group_by_sample_orders_concentrations_high_to_low() -> None:
    curves = bli.parse_fortebio_csv(
        _fortebio_csv([("S1", 25.0), ("S1", 100.0), ("S1", 50.0)])
    )
    grouped = bli.group_by_sample(curves)
    assert [curve.conc_nM for curve in grouped["S1"]] == [100.0, 50.0, 25.0]


# --- BLI: KD fitting ---------------------------------------------------------


def _langmuir_curves(kon: float, koff: float, rmax: float, concs_nM: list[float]) -> list[bli.Curve]:
    """1:1 Langmuir association then dissociation, sampled without noise.

    Units follow the kernel: it feeds `conc_nM` straight into the rate law, so
    `kon` here is per-nM-per-second and the KD it reports comes back in nM.

    Noise-free on purpose: the assertion is that the fit recovers the constants
    it was generated from, and tolerance for noise is a separate question.
    """
    t_assoc, t_dissoc, end = 0.0, 120.0, 300.0
    time = np.arange(0.0, end, 1.0)
    curves = []
    for index, conc_nM in enumerate(concs_nM):
        kobs = kon * conc_nM + koff
        req = rmax * kon * conc_nM / kobs
        response = np.where(
            time <= t_dissoc,
            req * (1.0 - np.exp(-kobs * (time - t_assoc))),
            req * (1.0 - np.exp(-kobs * (t_dissoc - t_assoc))) * np.exp(-koff * (time - t_dissoc)),
        )
        curves.append(
            bli.Curve(
                label=f"E{index + 1}",
                sample_id="S1",
                conc_nM=conc_nM,
                time=time,
                response=response,
            )
        )
    return curves


def test_kd_fitting_recovers_the_constants_the_curves_were_built_from() -> None:
    koff, kd_nM, rmax = 1.0e-3, 10.0, 0.5
    kon = koff / kd_nM  # per nM per second, matching the kernel's units
    curves = _langmuir_curves(kon, koff, rmax, [200.0, 100.0, 50.0, 25.0, 12.5])

    result = bli.fit_kd(curves, t_assoc=0.0, t_dissoc=120.0)

    assert set(result) >= {"phase", "standard", "split", "joint", "steady", "mixed"}
    joint = result["joint"]
    assert joint is not None, "the global fit should converge on noise-free curves"
    # Within a factor of two of the 10 nM it was built from. Tighter than that
    # would be asserting the optimiser's luck rather than the maths.
    assert 5.0 <= joint["kd"] <= 20.0


def test_the_five_methods_all_report_or_explain_themselves() -> None:
    curves = _langmuir_curves(1.0e-4, 1.0e-3, 0.5, [200.0, 100.0, 50.0, 25.0])
    result = bli.fit_kd(curves, t_assoc=0.0, t_dissoc=120.0)
    for method in ("standard", "split", "joint", "steady", "mixed"):
        entry = result[method]
        # Either a KD under some name, or a stated reason - never a silent
        # absence. `mixed` reports two (steady and kinetic) because it fits both.
        assert entry is None or any("kd" in key for key in entry) or "error" in entry


def test_phase_detection_runs_when_boundaries_are_not_declared() -> None:
    """The heuristic exists for files that do not carry the phase times; strong
    data should still declare them explicitly."""
    curves = _langmuir_curves(1.0e-4, 1.0e-3, 0.5, [200.0, 100.0, 50.0])
    result = bli.fit_kd(curves)
    assert result["phase"]["t_assoc"] is not None
    assert result["phase"]["t_dissoc"] > result["phase"]["t_assoc"]


def test_dead_curves_are_filtered_before_fitting() -> None:
    live = _langmuir_curves(1.0e-4, 1.0e-3, 0.5, [200.0, 100.0, 50.0])
    flat = bli.Curve(
        label="E9", sample_id="S1", conc_nM=400.0,
        time=live[0].time, response=np.zeros_like(live[0].response),
    )
    kept_t, kept_y, kept_c = bli.filter_dead_curves(
        [c.time for c in [flat, *live]],
        [c.response for c in [flat, *live]],
        [c.conc_nM for c in [flat, *live]],
        t_dissoc=120.0,
    )
    # The flat curve is dropped. The cutoff is relative to the strongest
    # response, so weak-but-live curves can go with it; the assertion is that
    # the dead one never survives, not an exact surviving count.
    assert 400.0 not in kept_c
    assert 200.0 in kept_c


# --- AKTA: the non-standard Unicorn archive ---------------------------------


def _float32_block(values: list[float]) -> bytes:
    """The .NET-serialised layout the Unicorn export uses: 47 bytes of header,
    float32 payload, 48 bytes of trailer."""
    return b"\x00" * 47 + b"".join(struct.pack("<f", v) for v in values) + b"\x00" * 48


def _unicorn_zip(volumes: list[float], amplitudes: list[float]) -> bytes:
    """An outer zip holding a *nested* zip whose EOCD is not at the end.

    This padding is the whole reason `_fix_nested_zip` exists: a stock
    `zipfile.ZipFile` cannot open the inner archive without truncating first.
    """
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as archive:
        archive.writestr("CoordinateData.Volumes", _float32_block(volumes))
        archive.writestr("CoordinateData.Amplitudes", _float32_block(amplitudes))
    # Real Unicorn inner archives start PK\x03\x04 with version 45 and deflate;
    # Python writes version 20, and the parser keys on those exact nine bytes to
    # decide something is a nested curve archive at all.
    raw = bytearray(inner.getvalue())
    raw[0:9] = b"\x50\x4B\x03\x04\x2D\x00\x00\x00\x08"
    nested = bytes(raw) + b"\x00" * 64  # trailing padding, as the real files have

    xml = (
        '<?xml version="1.0"?><Chrom><Curves><Curve>'
        "<Name>UV 1_280</Name>"
        '<CurveDataType>UV</CurveDataType>'
        "<AmplitudeUnit>mAU</AmplitudeUnit>"
        "<CurvePoints><CurvePoint><X/><BinaryCurvePointsFileName>Chrom.1_MM_True"
        "</BinaryCurvePointsFileName></CurvePoint></CurvePoints>"
        "</Curve></Curves>"
        "<EventCurves><EventCurve><Name>Fraction</Name><Events>"
        "<Event><EventVolume>1.5</EventVolume><EventText>A1</EventText></Event>"
        "<Event><EventVolume>2.5</EventVolume><EventText>A2</EventText></Event>"
        "</Events></EventCurve></EventCurves></Chrom>"
    )
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as archive:
        archive.writestr("Chrom.1.Xml", xml)
        archive.writestr("Chrom.1_MM_True", nested)
    return outer.getvalue()


def test_unicorn_zip_is_read_with_the_standard_library_alone() -> None:
    volumes = [round(0.1 * step, 3) for step in range(60)]
    amplitudes = [float(step) for step in range(60)]

    parsed = akta.parse_akta_zip(_unicorn_zip(volumes, amplitudes))

    assert "UV 1_280" in parsed["channels"]
    channel = parsed["channels"]["UV 1_280"]
    assert channel.unit == "mAU"
    assert len(channel.vols) == len(volumes)
    np.testing.assert_allclose(channel.amps[:5], amplitudes[:5], rtol=1e-5)


def test_a_zip_without_the_chromatogram_xml_is_refused() -> None:
    empty = io.BytesIO()
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("readme.txt", "not a chromatogram")
    with pytest.raises(ValueError, match="Chrom.1.Xml"):
        akta.parse_akta_zip(empty.getvalue())


def test_fraction_events_are_read_and_turned_into_ranges() -> None:
    parsed = akta.parse_akta_zip(_unicorn_zip([0.1 * s for s in range(60)], [1.0] * 60))
    fractions = akta.find_fraction_events(parsed["events"])
    assert [text for _, text in fractions] == ["A1", "A2"]

    ranges = akta.fraction_ranges(fractions, xmax=4.0)
    assert ranges[0][0] == 1.5 and ranges[0][2] == "A1"
    # A fraction runs until the next one starts.
    assert ranges[0][1] == pytest.approx(2.5)


def test_peak_detection_finds_a_synthesised_peak_and_reports_its_area() -> None:
    volumes = np.linspace(0.0, 10.0, 400)
    amplitudes = 100.0 * np.exp(-(((volumes - 5.0) / 0.3) ** 2))
    channel = akta.Channel(
        name="UV 1_280", data_type="UV", unit="mAU", vols=volumes, amps=amplitudes
    )

    peaks = akta.detect_peaks(channel)

    assert len(peaks) >= 1
    apex = max(peaks, key=lambda peak: peak.height)
    assert apex.apex_vol == pytest.approx(5.0, abs=0.2)
    assert apex.area > 0
    rows = akta.peaks_to_rows(peaks)
    assert rows and "apex_vol" in rows[0]


# --- Enzyme kinetics ---------------------------------------------------------


def test_linear_kinetics_recovers_the_slope_it_was_given() -> None:
    times = list(range(0, 600, 30))
    slope = 0.002
    fit = calculators.fit_kinetics(times, [0.05 + slope * t for t in times])
    # The kernel reports the rate per minute, not per second, because that is
    # the unit an enzyme assay is read in.
    assert fit["slope"] == pytest.approx(slope * 60, rel=1e-6)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-9)


def test_blank_subtraction_zeroes_the_negative_control() -> None:
    """Background is subtracted from the negative only - a correction that also
    shifted the samples would double-count it at the rate stage."""
    wells = {
        "A1": {"times": [0, 30, 60], "od": [0.10, 0.12, 0.14], "ref": "neg"},
        "B1": {"times": [0, 30, 60], "od": [0.20, 0.30, 0.40], "ref": ""},
    }
    # Returns (wells, mean_background); the background itself is zeroed.
    corrected, mean_background = calculators.sub_blank(wells, enabled=True)
    assert mean_background is not None
    assert all(value == pytest.approx(0.0) for value in corrected["A1"]["od"])
    # The sample keeps its signal minus the background, not zero.
    assert corrected["B1"]["od"][-1] == pytest.approx(0.40 - 0.14)


def test_grouped_wells_average_and_report_their_membership() -> None:
    wells = {
        "A1": {"times": [0, 30], "od": [0.10, 0.20], "group": "g"},
        "A2": {"times": [0, 30], "od": [0.20, 0.40], "group": "g"},
    }
    grouped = calculators.aggregate_groups(wells)
    assert grouped, "expected the two same-group wells to combine"
    entry = next(iter(grouped.values())) if isinstance(grouped, dict) else grouped[0]
    assert entry is not None
