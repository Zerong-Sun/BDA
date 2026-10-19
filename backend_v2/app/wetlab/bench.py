"""Stateless bench arithmetic. No persistence, sequence logging or external calls."""
from __future__ import annotations

import math
from dataclasses import asdict

from Bio.SeqUtils import molecular_weight
from Bio.SeqUtils.ProtParam import ProteinAnalysis

from ..core.problem import DomainError
from .bench_schemas import (
    BenchCalculationInput,
    BenchCalculationResult,
    BenchDilutionStep,
    BenchReference,
    BenchValue,
    CalculationKind,
    CentrifugeInput,
    ConcentrationInput,
    CopyNumberInput,
    DilutionInput,
    DNARatioInput,
    NucleicA260Input,
    NucleicPropertiesInput,
    ProteinA280Input,
    ProteinPropertiesInput,
    SerialDilutionInput,
    SolutionInput,
)
from .kernels.calculators import calc_dilution_series

AVOGADRO = 6.02214076e23  # Exact SI mol^-1.
REFERENCES = {
    "protein": BenchReference(title="ExPASy ProtParam documentation", url="https://web.expasy.org/protparam/protparam-doc.html"),
    "biopython": BenchReference(title="Biopython SeqUtils molecular_weight", url="https://biopython.org/docs/latest/api/Bio.SeqUtils.html"),
    "absorbance": BenchReference(title="NanoDrop One user guide, nucleic acid calculations and 1 cm normalization",
        url="https://assets.thermofisher.com/TFS-Assets/MSD/manuals/nanodrop-one-user-guide-EN-309102-REV-A.pdf.pdf"),
    "ratio": BenchReference(title="NEBioCalculator: ligation and molar calculations", url="https://nebiocalculator.neb.com/"),
    "copy": BenchReference(title="Promega: Nucleotides and Nucleic Acids (average mass approximations)",
        url="https://nld.promega.com/-/media/files/resources/technical-references/nucleotides-and-nucleic-acids.pdf"),
    "si": BenchReference(title="BIPM: SI Brochure", url="https://www.bipm.org/en/publications/si-brochure"),
    "centrifuge": BenchReference(title="Eppendorf Rotor R19A operating manual: RCF and speed",
        url="https://www.eppendorf.com/product-media/doc/en/5952434/Centrifugation_Operating-manual_Rotor-R19A.pdf"),
}
# Factor to mol/L for molar units and g/L for mass units.
UNITS = {"M": ("molar", 1.0), "mM": ("molar", 1e-3), "uM": ("molar", 1e-6),
         "nM": ("molar", 1e-9), "pM": ("molar", 1e-12), "g/L": ("mass", 1.0),
         "mg/mL": ("mass", 1.0), "mg/L": ("mass", 1e-3), "ug/mL": ("mass", 1e-3),
         "ng/uL": ("mass", 1e-3)}


def _value(key: str, label: str, zh: str, value: float, unit: str, *, positive: bool = False) -> BenchValue:
    if not math.isfinite(value) or (positive and value <= 0):
        raise DomainError("calculation_numeric_range", "The result is outside the supported numerical range; rescale the inputs", status_code=422)
    return BenchValue(key=key, label=label, label_zh=zh, value=value, unit=unit)


def _result(kind: CalculationKind, values: list[BenchValue], formula: str, assumptions: list[tuple[str, str]],
            refs: list[str], warnings: list[tuple[str, str]] | None = None,
            steps: list[BenchDilutionStep] | None = None) -> BenchCalculationResult:
    warnings = warnings or []
    return BenchCalculationResult(kind=kind, values=values, formula=formula,
        assumptions=[a[0] for a in assumptions], assumptions_zh=[a[1] for a in assumptions],
        warnings=[w[0] for w in warnings], warnings_zh=[w[1] for w in warnings],
        references=[REFERENCES[key] for key in refs], steps=steps or [])


def _protein(p: ProteinPropertiesInput) -> BenchCalculationResult:
    analysis = ProteinAnalysis(p.sequence)
    mw = analysis.molecular_weight()
    reduced, oxidized = analysis.molar_extinction_coefficient()
    warnings = []
    if not reduced:
        warnings.append(("No Trp or Tyr: the reduced-chain A280 coefficient is zero and cannot quantify this protein.",
                         "序列不含色氨酸或酪氨酸：还原态 A280 消光系数为零，不能据此定量。"))
    if p.sequence.count("C") % 2:
        warnings.append(("An odd cysteine remains unpaired in the maximum-paired cystine estimate.",
                         "半胱氨酸数为奇数，最大配对估算中仍有一个未配对。"))
    return _result(p.kind, [
        _value("length", "Sequence length", "序列长度", len(p.sequence), "aa"),
        _value("molecular_weight_g_mol", "Average molecular weight", "平均分子量", mw, "g/mol", positive=True),
        _value("epsilon_reduced", "Reduced-chain extinction coefficient", "还原态摩尔消光系数", reduced, "M^-1 cm^-1"),
        _value("epsilon_cystines", "Maximum-paired cystine extinction coefficient", "最大二硫键配对摩尔消光系数", oxidized, "M^-1 cm^-1"),
        _value("a280_1mg_mL_reduced", "A280 at 1 mg/mL, 1 cm (reduced)", "1 mg/mL、1 cm 下 A280（还原态）", reduced / mw, "AU"),
    ], "MW = Σ(amino-acid mass) − (n−1)×18.0153; εred = 5500×W + 1490×Y; εcystines = εred + 125×floor(C/2)", [
        ("Average isotopic mass of one unmodified linear chain with free N/C termini; no disulfide mass correction, tags beyond the supplied sequence, glycans or cofactors.",
         "采用单条未修饰线性链的平均同位素质量、游离 N/C 末端；不校正二硫键质量，不计序列外标签、糖基或辅因子。"),
        ("Cystine coefficient assumes the maximum number of cysteine pairs; sequence alone does not establish disulfide connectivity.",
         "二硫键态消光系数按最多可配对数估算；序列本身不能证明实际二硫键连接。"),
    ], ["protein", "biopython"], warnings)


def _nucleic(p: NucleicPropertiesInput) -> BenchCalculationResult:
    mw = molecular_weight(p.sequence, seq_type=p.molecule, double_stranded=p.strandedness == "ds", circular=p.topology == "circular")
    return _result(p.kind, [
        _value("length", "Length of supplied strand", "输入链长度", len(p.sequence), "bp" if p.strandedness == "ds" else "nt"),
        _value("molecular_weight_g_mol", "Average molecular weight", "平均分子量", mw, "g/mol", positive=True),
        _value("gc_percent", "GC content", "GC 含量", 100 * (p.sequence.count("G") + p.sequence.count("C")) / len(p.sequence), "%"),
    ], "MWlinear = Σ(nucleotide mass) − (n−1)×18.0153; MWcircular = MWlinear − 18.0153 per strand", [
        ("Biopython average isotopic mass; linear nucleotide sequences have a 5′ phosphate and 3′ hydroxyl. Terminal chemistry differs from many unphosphorylated synthetic oligos.",
         "使用 Biopython 平均同位素质量；线性核酸假定 5′ 磷酸、3′ 羟基，可能不同于未磷酸化的合成寡核苷酸。"),
        (f"Selected molecule: {p.molecule}, {p.strandedness}, {p.topology}. Double-stranded mass adds a fully complementary strand; circular mass assumes both strands are covalently closed when ds is selected.",
         f"所选分子：{p.molecule}、{'双链' if p.strandedness == 'ds' else '单链'}、{'环状' if p.topology == 'circular' else '线性'}。双链按完全互补链相加；双链环状假定两条链均共价闭合。"),
    ], ["biopython"], [("No modified bases, counterions, conjugates or secondary-structure feasibility are modeled.",
                         "不包含修饰碱基、反离子、偶联物，也不判断二级结构或环化的可行性。")])


def _absorbance(p: ProteinA280Input | NucleicA260Input) -> BenchCalculationResult:
    corrected = p.sample_absorbance - p.blank_absorbance
    normalized = corrected / p.path_length_cm
    assumptions = [
        ("Sample and blank use the same wavelength and absorbance normalization. Dilution factor is final diluted volume / original aliquot volume.",
         "样本与空白须采用相同波长和吸光度归一化方式；稀释倍数为稀释后总体积 / 原液取样体积。"),
        ("Reported concentrations refer to the original sample before dilution; absorbance values refer to the measured diluted solution.",
         "浓度结果对应稀释前原样本；吸光度对应实际测量的稀释液。"),
    ]
    if p.absorbance_basis == "normalized-1cm":
        assumptions.append(("Input already normalized to 1 cm: no further physical path-length correction is applied.",
                            "输入已归一化到 1 cm：不再按仪器实际光程重复校正。"))
    else:
        assumptions.append(("Raw absorbance is divided by the supplied physical optical path length in cm.",
                            "输入为原始吸光度，按所填实际光程（cm）校正。"))
    values = [_value("blank_corrected_absorbance", "Blank-corrected absorbance", "扣除空白后的吸光度", corrected, "AU"),
              _value("absorbance_1cm", "Blank-corrected 1 cm absorbance", "扣空白且归一化 1 cm 的吸光度", normalized, "AU", positive=corrected > 0)]
    warnings = [("Beer–Lambert arithmetic does not assess purity, scattering, detector linearity or detection limits.",
                 "比尔–朗伯换算不能判断纯度、散射、仪器线性范围或检出限。")]
    if corrected == 0:
        warnings.append(("Zero blank-corrected absorbance is not proof that analyte is absent.", "扣空白后的零吸光度不等于证明没有待测物。"))
    if isinstance(p, ProteinA280Input):
        molar = normalized / p.epsilon_M_inv_cm_inv * p.dilution_factor
        values += [_value("concentration_M", "Original sample molarity", "原样本摩尔浓度", molar, "M", positive=corrected > 0),
                   _value("concentration_uM", "Original sample micromolarity", "原样本微摩尔浓度", molar * 1e6, "uM"),
                   _value("concentration_mg_mL", "Original sample mass concentration", "原样本质量浓度", molar * p.molecular_weight_g_mol, "mg/mL", positive=corrected > 0)]
        return _result(p.kind, values, "c(M) = (Asample − Ablank) × dilution_factor / (ε × path_cm); c(mg/mL) = c(M) × MW(g/mol)", assumptions, ["protein", "absorbance"], warnings)
    factor = {"dsDNA": 50.0, "ssDNA": 33.0, "RNA": 40.0}[p.material]
    mass = normalized * factor * p.dilution_factor
    values += [_value("concentration_ng_uL", "Original sample mass concentration", "原样本质量浓度", mass, "ng/uL", positive=corrected > 0),
               _value("factor_ng_uL_per_AU", "Approximate 1 cm conversion factor", "1 cm 近似换算系数", factor, "ng/uL/AU")]
    assumptions.append((f"{p.material}: 1 AU at 260 nm and 1 cm ≈ {factor:g} ng/µL. RNA uses a bulk single-stranded RNA approximation.",
                        f"{p.material}：260 nm、1 cm 下 1 AU 约为 {factor:g} ng/µL；RNA 使用常规单链 RNA 近似。"))
    warnings.append(("This bulk factor is sequence-dependent and approximate; use sequence-specific extinction coefficients for precise oligo quantification.",
                     "该通用系数为近似值，实际受序列影响；精确寡核苷酸定量应采用序列特异的消光系数。"))
    return _result(p.kind, values, "c(ng/µL) ≈ (Asample − Ablank) × factor × dilution_factor / path_cm", assumptions, ["absorbance"], warnings)


def _concentration(p: ConcentrationInput) -> BenchCalculationResult:
    source_kind, source_factor = UNITS[p.from_unit]
    target_kind, target_factor = UNITS[p.to_unit]
    value = p.value * source_factor
    assumptions = [("Unit conversion only; molecular weight is in g/mol (numerically equal to molecular mass in Da).",
                    "仅进行单位换算；摩尔质量单位为 g/mol，数值等于分子质量 Da。")]
    if source_kind != target_kind:
        if p.molecular_weight_g_mol is None:
            raise DomainError("calculation_molecular_weight_required", "Mass/molar conversion requires molecular_weight_g_mol", status_code=422)
        value = value * p.molecular_weight_g_mol if source_kind == "molar" else value / p.molecular_weight_g_mol
    return _result(p.kind, [_value("converted_value", "Converted concentration", "换算后浓度", value / target_factor, p.to_unit, positive=p.value > 0)],
        "c(g/L) = c(mol/L) × MW(g/mol); 1 mg/mL = 1 g/L; 1 ng/µL = 1 µg/mL = 1 mg/L", assumptions, ["si"])


def _solution(p: SolutionInput) -> BenchCalculationResult:
    mass_mg = p.concentration_mM * p.volume_mL * p.molecular_weight_g_mol / 1000
    return _result(p.kind, [_value("mass_mg", "Required solute mass", "所需溶质质量", mass_mg, "mg", positive=p.concentration_mM > 0),
                            _value("amount_umol", "Solute amount", "溶质物质的量", p.concentration_mM * p.volume_mL, "umol", positive=p.concentration_mM > 0)],
        "mass(mg) = concentration(mM) × final_volume(mL) × MW(g/mol) / 1000", [
            ("Use the molecular weight of the actual chemical form, including any salt or hydrate. Assumes 100% purity.",
             "须使用实际化学形式的分子量（含盐型或水合物），此处假定纯度 100%。"),
            ("Dissolve, then bring to the specified FINAL solution volume; do not add this volume of solvent directly.",
             "先溶解，再定容到指定的最终溶液体积；不是直接加入同体积溶剂。"),
        ], ["si"])


def _dilution(p: DilutionInput) -> BenchCalculationResult:
    stock = p.final_volume_uL * (p.target_concentration / p.stock_concentration)
    return _result(p.kind, [_value("stock_volume_uL", "Stock aliquot", "原液取样体积", stock, "uL", positive=p.target_concentration > 0),
        _value("diluent_volume_uL", "Diluent volume", "稀释液体积", p.final_volume_uL - stock, "uL"),
        _value("final_volume_uL", "Final volume", "最终体积", p.final_volume_uL, "uL")],
        "C1 × V1 = C2 × V2; Vdiluent = V2 − V1", [
            (f"Stock and target concentrations both use {p.concentration_unit}; assumes additive volumes and no analyte loss or reaction.",
             f"原液和目标浓度均用 {p.concentration_unit}；假定体积可相加、无待测物损失或反应。"),
        ], ["si"], [("Check the calculated aliquot against your pipette's validated working range; no instrument-specific minimum is assumed.",
                     "请核对取样量是否在移液器验证范围内；此计算不假设特定仪器的最小体积。")])


def _dna_ratio(p: DNARatioInput) -> BenchCalculationResult:
    mass = p.vector_mass_ng * (p.insert_length_bp / p.vector_length_bp) * p.insert_to_vector_molar_ratio
    return _result(p.kind, [_value("insert_mass_ng", "Required insert mass", "所需插入片段质量", mass, "ng", positive=True)],
        "insert_mass = vector_mass × (insert_bp / vector_bp) × insert_to_vector_molar_ratio", [
            ("Unmodified double-stranded DNA; uses the same average mass per base pair for vector and insert.",
             "用于未修饰双链 DNA，假定载体与插入片段每碱基对平均质量相同。"),
            ("The selected ratio is input, not an optimized ligation recommendation; sequence composition and reaction efficiency are not modeled.",
             "所填比例是用户输入，不代表优化过的连接建议；不模拟序列组成差异与反应效率。"),
        ], ["ratio"])


def _copy_number(p: CopyNumberInput) -> BenchCalculationResult:
    warnings = []
    assumptions = [("Counts whole input molecules, not amplifiable targets, intact genomes, viable cells or target copies per genome.",
                    "计数对象为输入的完整分子；不等于可扩增靶标、完整基因组、活细胞或每基因组靶标拷贝数。")]
    if p.molecular_weight_g_mol is not None:
        mw = p.molecular_weight_g_mol
        assumptions.append(("Uses the explicitly supplied molecular weight of one molecule.", "使用明确提供的单个分子的摩尔质量。"))
    else:
        assert p.material is not None and p.length is not None
        factor = {"dsDNA": 660.0, "ssDNA": 330.0, "RNA": 340.0}[p.material]
        mw = p.length * factor
        unit = "bp" if p.material == "dsDNA" else "nt"
        assumptions.append((f"Promega conventional approximation: {p.material}, {factor:g} g/mol per {unit}; RNA means single-stranded RNA.",
                            f"采用 Promega 常规近似：{p.material} 每 {unit} 为 {factor:g} g/mol；RNA 指单链 RNA。"))
        warnings.append(("Length-based mass ignores sequence, termini, topology, counterions and modifications. Other conventions differ; prefer a known sequence-specific molecular weight.",
                         "长度估算忽略序列、末端、拓扑、反离子及修饰；不同质量约定存在差异，优先使用已知的序列特异分子量。"))
    amount = p.mass_ng / mw * 1e-9
    return _result(p.kind, [_value("molecular_weight_g_mol", "Molecular weight used", "采用的分子量", mw, "g/mol", positive=True),
        _value("amount_mol", "Amount of molecules", "分子物质的量", amount, "mol", positive=p.mass_ng > 0),
        _value("copy_number", "Estimated number of molecules", "估算分子数", amount * AVOGADRO, "molecules", positive=p.mass_ng > 0)],
        "N = mass(ng) × 10^-9 / MW(g/mol) × 6.02214076×10^23 mol^-1", assumptions, ["copy", "si"], warnings)


def _centrifuge(p: CentrifugeInput) -> BenchCalculationResult:
    if p.from_unit == "rpm":
        value, key, unit, label, zh = 1.118e-5 * p.radius_cm * p.value ** 2, "rcf", "×g", "Relative centrifugal force", "相对离心力"
    else:
        value, key, unit, label, zh = math.sqrt(p.value / (1.118e-5 * p.radius_cm)), "rpm", "rpm", "Rotational speed", "转速"
    return _result(p.kind, [_value(key, label, zh, value, unit, positive=p.value > 0)],
        "RCF(×g) = 1.118×10^-5 × r(cm) × rpm²; rpm = sqrt(RCF / (1.118×10^-5 × r))", [
            ("Radius is the distance from the axis to the sample position. Use the rotor manufacturer's stated radius (e.g. rmax for maximum RCF).",
             "半径指转轴到样本位置的距离；应采用转子厂家规定半径（例如最大 RCF 使用 rmax）。"),
        ], ["centrifuge"], [("This conversion does not check rotor/tube speed ratings or certify an operating condition; check the manufacturer's limits.",
                            "换算不校验转子或离心管额定转速，也不验证运行条件；须核对厂家限值。")])


def _serial(p: SerialDilutionInput) -> BenchCalculationResult:
    steps = calc_dilution_series(p.stock_conc_uM, p.start_conc_uM, p.dilution_factor, p.n_steps,
                                p.vol_per_well_uL, p.extra_dead_vol_uL)
    return _result(p.kind, [_value("total_buffer_uL", "Total diluent required", "稀释液总量", sum(step.buffer_vol_uL for step in steps), "uL"),
        _value("initial_stock_uL", "Original stock aliquot", "初始原液取样量", steps[0].stock_vol_uL, "uL", positive=True)],
        "Vi = ceil_to_5µL(well_volume + dead_volume + V(i+1)/factor); Ci = Cstart/factor^(i−1)", [
            ("Work backwards from the final tube. Each tube retains the requested well volume and dead volume after supplying the next tube; prepared totals round up to 5 µL.",
             "从末管向前计算；每管向下一管转移后，仍保留所需用量及死体积；配制总体积向上取整到 5 µL。"),
            ("From step 2, stock_vol_uL is transferred from the previous tube; mix before transferring. Tube totals may differ.",
             "从第 2 步起，stock_vol_uL 指从上一管转移的体积；转移前须混匀，各管总体积可能不同。"),
        ], ["si"], [("Concentrations and transfers are not rounded to a pipette increment; check instrument capability before preparing.",
                     "浓度和转移量未按移液器步进取整，配制前须核对仪器能力。")],
        [BenchDilutionStep(**asdict(step)) for step in steps])


def calculate(payload: BenchCalculationInput) -> BenchCalculationResult:
    """Dispatch validated inputs; numerical failures become explicit 422s, never zero."""
    try:
        if isinstance(payload, ProteinPropertiesInput):
            return _protein(payload)
        if isinstance(payload, NucleicPropertiesInput):
            return _nucleic(payload)
        if isinstance(payload, ProteinA280Input | NucleicA260Input):
            return _absorbance(payload)
        if isinstance(payload, ConcentrationInput):
            return _concentration(payload)
        if isinstance(payload, SolutionInput):
            return _solution(payload)
        if isinstance(payload, DilutionInput):
            return _dilution(payload)
        if isinstance(payload, DNARatioInput):
            return _dna_ratio(payload)
        if isinstance(payload, CopyNumberInput):
            return _copy_number(payload)
        if isinstance(payload, CentrifugeInput):
            return _centrifuge(payload)
        if isinstance(payload, SerialDilutionInput):
            return _serial(payload)
        raise DomainError("calculation_unknown", "Unsupported calculation", status_code=422)
    except (ArithmeticError, ValueError) as exc:
        raise DomainError("calculation_invalid", "Inputs do not define a representable calculation; check units, dilution feasibility and numeric range", status_code=422) from exc
