"""Bounded, finite inputs for stateless wet-lab calculations."""
from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Positive = Annotated[float, Field(gt=0, le=1e15, allow_inf_nan=False, strict=True)]
Nonnegative = Annotated[float, Field(ge=0, le=1e15, allow_inf_nan=False, strict=True)]
ConcentrationUnit = Literal["M", "mM", "uM", "nM", "pM", "g/L", "mg/mL", "mg/L", "ug/mL", "ng/uL"]
CalculationKind = Literal["protein-properties", "nucleic-properties", "protein-a280", "nucleic-a260",
                          "concentration", "solution", "dilution", "dna-ratio", "copy-number", "centrifuge", "serial-dilution"]


class BenchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ProteinPropertiesInput(BenchInput):
    kind: Literal["protein-properties"]
    sequence: str = Field(min_length=1, max_length=200_000)

    @field_validator("sequence")
    @classmethod
    def canonical_sequence(cls, value: str) -> str:
        sequence = "".join(value.split()).upper()
        if not sequence or len(sequence) > 100_000 or set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
            raise ValueError("Use one canonical protein sequence (1–100000 residues); headers, stop symbols and unknown residues are not accepted")
        return sequence


class NucleicPropertiesInput(BenchInput):
    kind: Literal["nucleic-properties"]
    sequence: str = Field(min_length=1, max_length=200_000)
    molecule: Literal["DNA", "RNA"]
    strandedness: Literal["ss", "ds"]
    topology: Literal["linear", "circular"]

    @model_validator(mode="after")
    def canonical_sequence(self) -> Self:
        sequence = "".join(self.sequence.split()).upper()
        alphabet = set("ACGT" if self.molecule == "DNA" else "ACGU")
        if not sequence or len(sequence) > 100_000 or set(sequence) - alphabet:
            raise ValueError("Use one unambiguous sequence matching DNA (ACGT) or RNA (ACGU), 1–100000 nucleotides")
        self.sequence = sequence
        return self


class AbsorbanceInput(BenchInput):
    sample_absorbance: Annotated[float, Field(ge=0, le=1e4, allow_inf_nan=False, strict=True)]
    blank_absorbance: Annotated[float, Field(ge=0, le=1e4, allow_inf_nan=False, strict=True)] = 0.0
    path_length_cm: Annotated[float, Field(gt=0, le=1e3, allow_inf_nan=False, strict=True)] = 1.0
    dilution_factor: Annotated[float, Field(ge=1, le=1e12, allow_inf_nan=False, strict=True)] = 1.0
    absorbance_basis: Literal["raw", "normalized-1cm"] = "raw"

    @model_validator(mode="after")
    def absorbance_consistency(self) -> Self:
        if self.sample_absorbance < self.blank_absorbance:
            raise ValueError("Blank-corrected absorbance is negative; check blank and sample before calculating concentration")
        if self.absorbance_basis == "normalized-1cm" and self.path_length_cm != 1:
            raise ValueError("A 1 cm-normalized absorbance must use path_length_cm=1; do not correct the physical path twice")
        return self


class ProteinA280Input(AbsorbanceInput):
    kind: Literal["protein-a280"]
    epsilon_M_inv_cm_inv: Positive
    molecular_weight_g_mol: Positive


class NucleicA260Input(AbsorbanceInput):
    kind: Literal["nucleic-a260"]
    material: Literal["dsDNA", "ssDNA", "RNA"]


class ConcentrationInput(BenchInput):
    kind: Literal["concentration"]
    value: Nonnegative
    from_unit: ConcentrationUnit
    to_unit: ConcentrationUnit
    molecular_weight_g_mol: Positive | None = None


class SolutionInput(BenchInput):
    kind: Literal["solution"]
    concentration_mM: Nonnegative
    volume_mL: Positive
    molecular_weight_g_mol: Positive


class DilutionInput(BenchInput):
    kind: Literal["dilution"]
    stock_concentration: Positive
    target_concentration: Nonnegative
    concentration_unit: ConcentrationUnit
    final_volume_uL: Positive

    @model_validator(mode="after")
    def feasible(self) -> Self:
        if self.target_concentration > self.stock_concentration:
            raise ValueError("Dilution cannot make a concentration higher than the stock")
        return self


class DNARatioInput(BenchInput):
    kind: Literal["dna-ratio"]
    vector_mass_ng: Positive
    vector_length_bp: Annotated[int, Field(ge=1, le=1_000_000_000, strict=True)]
    insert_length_bp: Annotated[int, Field(ge=1, le=1_000_000_000, strict=True)]
    insert_to_vector_molar_ratio: Positive


class CopyNumberInput(BenchInput):
    kind: Literal["copy-number"]
    mass_ng: Nonnegative
    molecular_weight_g_mol: Positive | None = None
    material: Literal["dsDNA", "ssDNA", "RNA"] | None = None
    length: Annotated[int, Field(ge=1, le=1_000_000_000, strict=True)] | None = None

    @model_validator(mode="after")
    def one_mass_definition(self) -> Self:
        if self.molecular_weight_g_mol is not None:
            if self.material is not None or self.length is not None:
                raise ValueError("Provide molecular weight OR material and length, not both")
        elif self.material is None or self.length is None:
            raise ValueError("Provide molecular weight, or explicitly select material and length for an approximation")
        return self


class CentrifugeInput(BenchInput):
    kind: Literal["centrifuge"]
    radius_cm: Annotated[float, Field(gt=0, le=1e4, allow_inf_nan=False, strict=True)]
    from_unit: Literal["rpm", "rcf"]
    value: Nonnegative


class SerialDilutionInput(BenchInput):
    kind: Literal["serial-dilution"]
    stock_conc_uM: Positive
    start_conc_uM: Positive
    dilution_factor: Annotated[float, Field(gt=1, le=1e6, allow_inf_nan=False, strict=True)]
    n_steps: Annotated[int, Field(ge=1, le=24, strict=True)]
    vol_per_well_uL: Positive
    extra_dead_vol_uL: Nonnegative = 0.0


BenchCalculationInput = Annotated[
    ProteinPropertiesInput | NucleicPropertiesInput | ProteinA280Input | NucleicA260Input |
    ConcentrationInput | SolutionInput | DilutionInput | DNARatioInput | CopyNumberInput |
    CentrifugeInput | SerialDilutionInput,
    Field(discriminator="kind"),
]


class BenchValue(BaseModel):
    key: str
    label: str
    label_zh: str
    value: Annotated[float, Field(allow_inf_nan=False)]
    unit: str


class BenchReference(BaseModel):
    title: str
    url: str


class BenchDilutionStep(BaseModel):
    step: int
    conc_uM: Annotated[float, Field(allow_inf_nan=False)]
    stock_vol_uL: Annotated[float, Field(allow_inf_nan=False)]
    buffer_vol_uL: Annotated[float, Field(allow_inf_nan=False)]
    total_vol_uL: Annotated[float, Field(allow_inf_nan=False)]


class BenchCalculationResult(BaseModel):
    kind: CalculationKind
    calculation_version: Literal["bench-v1"] = "bench-v1"
    values: list[BenchValue]
    formula: str
    assumptions: list[str]
    assumptions_zh: list[str]
    warnings: list[str] = Field(default_factory=list)
    warnings_zh: list[str] = Field(default_factory=list)
    references: list[BenchReference]
    steps: list[BenchDilutionStep] = Field(default_factory=list)
