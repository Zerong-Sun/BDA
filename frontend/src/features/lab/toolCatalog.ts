export type ToolCategory = 'protein' | 'nucleic' | 'solutions' | 'equipment'
export type CalculatorKind = 'protein-properties' | 'protein-a280' | 'nucleic-properties' | 'nucleic-a260' | 'concentration' | 'solution' | 'dilution' | 'dna-ratio' | 'copy-number' | 'centrifuge'
export type ToolId = CalculatorKind | 'serial-dilution' | 'bli' | 'akta' | 'enzyme'
type Copy = { en: string; zh: string }
export type ToolField = {
  name: string; label: Copy; type: 'number' | 'sequence' | 'select'; initial: string
  help?: Copy; options?: { value: string; label: Copy }[]; optional?: boolean
  min?: number; positive?: boolean; step?: string; visible?: (values: Record<string, string>) => boolean
}
export type BenchTool = { id: ToolId; category: ToolCategory; title: Copy; description: Copy; keywords: string; fields: ToolField[] }
const c = (zh: string, en: string): Copy => ({ zh, en })
const number = (name: string, zh: string, en: string, initial = '', extra: Partial<ToolField> = {}): ToolField => ({ name, label: c(zh, en), type: 'number', initial, min: 0, ...extra })
const options = (values: string[]) => values.map((value) => ({ value, label: c(value, value) }))
const choice = (name: string, zh: string, en: string, initial: string, items: { value: string; label: Copy }[]): ToolField => ({ name, label: c(zh, en), type: 'select', initial, options: items })
const mw = (optional = false): ToolField => number('molecular_weight_g_mol', '摩尔质量 / 分子量数值（g/mol）', 'Molar mass / molecular weight value (g/mol)', '', { optional, positive: true, help: c('数值与分子质量 Da 相同；请使用实际构建体或化合物的质量。', 'Numerically equal to molecular mass in Da. Use the actual construct or compound.') })
const sequence: ToolField = { name: 'sequence', type: 'sequence', label: c('序列', 'Sequence'), initial: '', help: c('粘贴一条纯序列，不含 FASTA 标题或终止符；允许空格与换行。未知残基会报错，不写入项目记录。', 'One raw sequence without FASTA headers or stop symbols. Spaces and line breaks are accepted. Unknown residues are rejected; no project record is written.') }
const CONCENTRATION_UNITS = ['M', 'mM', 'uM', 'nM', 'pM', 'g/L', 'mg/mL', 'mg/L', 'ug/mL', 'ng/uL']
const concentrationOptions = options(CONCENTRATION_UNITS).map((option) => ({ ...option, label: c(option.value.replaceAll('u', 'µ'), option.value.replaceAll('u', 'µ')) }))
const absorbanceFields = (wavelength: string): ToolField[] => [
  number('sample_absorbance', `样品 A${wavelength}（AU）`, `Sample A${wavelength} (AU)`, ''),
  number('blank_absorbance', `待扣除的空白 A${wavelength}（AU）`, `Blank A${wavelength} to subtract (AU)`, '0', { help: c('仪器已扣空白时填 0，避免重复扣除。', 'Use 0 if the instrument already subtracted the blank.') }),
  choice('absorbance_basis', '吸光度读数类型', 'Absorbance basis', 'normalized-1cm', [
    { value: 'normalized-1cm', label: c('仪器已归一化为 1 cm', 'Already normalized to 1 cm') },
    { value: 'raw', label: c('实际光程下的原始读数', 'Raw reading at the actual path length') },
  ]),
  number('path_length_cm', '实际光程（cm）', 'Actual path length (cm)', '1', { positive: true, visible: (v) => v.absorbance_basis === 'raw' }),
  number('dilution_factor', '测量前稀释倍数', 'Pre-measurement dilution factor', '1', { min: 1, help: c('未稀释填 1；结果折算为稀释前原样浓度。', 'Use 1 for an undiluted sample. Results refer to the original sample.') }),
]

export const TOOL_CATEGORIES: { id: ToolCategory; title: Copy }[] = [
  { id: 'protein', title: c('蛋白质', 'Protein') },
  { id: 'nucleic', title: c('核酸与克隆', 'Nucleic acids & cloning') },
  { id: 'solutions', title: c('溶液与稀释', 'Solutions & dilution') },
  { id: 'equipment', title: c('离心与仪器数据', 'Centrifugation & instrument data') },
]

export const BENCH_TOOLS: BenchTool[] = [
  { id: 'protein-properties', category: 'protein', title: c('蛋白分子量与消光系数', 'Protein mass & extinction'), description: c('由序列计算分子量及还原态、氧化态的 A280 摩尔消光系数。', 'Calculate sequence-based molecular mass and reduced / oxidized A280 extinction coefficients.'), keywords: 'MW molecular weight epsilon sequence 分子量 蛋白 消光 序列', fields: [sequence] },
  { id: 'protein-a280', category: 'protein', title: c('蛋白 A280 → 浓度', 'Protein A280 → concentration'), description: c('使用 Beer–Lambert 定律，同时报告摩尔浓度与质量浓度。', 'Use Beer–Lambert law to obtain molar and mass concentration.'), keywords: 'protein absorbance nanodrop 光密度 吸光 折算', fields: [...absorbanceFields('280'), number('epsilon_M_inv_cm_inv', '摩尔消光系数 ε（M⁻¹·cm⁻¹）', 'Molar extinction coefficient ε (M⁻¹·cm⁻¹)', '', { positive: true }), mw()] },
  { id: 'nucleic-properties', category: 'nucleic', title: c('DNA / RNA 分子量', 'DNA / RNA molecular mass'), description: c('按序列、链型和拓扑计算分子质量与 GC 含量。', 'Calculate sequence-based molecular mass and GC content with explicit strand and topology assumptions.'), keywords: 'nucleic DNA RNA GC molecular weight 核酸 分子量', fields: [sequence,
    choice('molecule', '核酸类型', 'Nucleic acid type', 'DNA', options(['DNA', 'RNA'])),
    choice('strandedness', '链型', 'Strandedness', 'ds', [{ value: 'ss', label: c('单链', 'Single-stranded') }, { value: 'ds', label: c('双链', 'Double-stranded') }]),
    choice('topology', '拓扑', 'Topology', 'linear', [{ value: 'linear', label: c('线性', 'Linear') }, { value: 'circular', label: c('环状', 'Circular') }]),
  ] },
  { id: 'nucleic-a260', category: 'nucleic', title: c('核酸 A260 → 浓度', 'Nucleic acid A260 → concentration'), description: c('根据 dsDNA、ssDNA 或 RNA 的常用系数估算质量浓度。', 'Estimate mass concentration using standard dsDNA, ssDNA or RNA conversion factors.'), keywords: 'DNA RNA OD260 nanodrop absorbance 光密度 吸光 折算', fields: [choice('material', '样品类型', 'Sample type', 'dsDNA', options(['dsDNA', 'ssDNA', 'RNA'])), ...absorbanceFields('260')] },
  { id: 'dna-ratio', category: 'nucleic', title: c('DNA 插入片段与载体配比', 'DNA insert / vector ratio'), description: c('将指定的摩尔比换算为需要的插入片段质量。', 'Convert a chosen insert-to-vector molar ratio into insert mass.'), keywords: 'ligation cloning assembly synthetic biology 连接 克隆 组装 合成生物', fields: [number('vector_mass_ng', '载体质量（ng）', 'Vector mass (ng)', '', { positive: true }), number('vector_length_bp', '载体长度（bp）', 'Vector length (bp)', '', { min: 1, step: '1' }), number('insert_length_bp', '插入片段长度（bp）', 'Insert length (bp)', '', { min: 1, step: '1' }), number('insert_to_vector_molar_ratio', '插入片段 : 载体摩尔比', 'Insert : vector molar ratio', '3', { positive: true })] },
  { id: 'copy-number', category: 'nucleic', title: c('核酸质量 → 拷贝数', 'Nucleic acid mass → copies'), description: c('按已知分子量计算；只有长度时可明确选择近似估算。', 'Use a known molar mass, or explicitly choose a length-based approximation.'), keywords: 'copies molecules qPCR 拷贝 数量 分子数', fields: [
    number('mass_ng', '核酸总质量（ng）', 'Total nucleic acid mass (ng)'),
    choice('_mass_basis', '分子量来源', 'Molar mass basis', 'known', [{ value: 'known', label: c('已知分子量', 'Known molar mass') }, { value: 'length', label: c('按长度近似估算', 'Approximate from length') }]),
    { ...mw(), visible: (v) => v._mass_basis !== 'length' },
    { ...choice('material', '核酸类型', 'Material', 'dsDNA', options(['dsDNA', 'ssDNA', 'RNA'])), visible: (v) => v._mass_basis === 'length' },
    number('length', '长度（双链为 bp，单链为 nt）', 'Length (bp for duplex, nt for single strand)', '', { min: 1, step: '1', visible: (v) => v._mass_basis === 'length' }),
  ] },
  { id: 'concentration', category: 'solutions', title: c('质量浓度 ⇄ 摩尔浓度', 'Mass ⇄ molar concentration'), description: c('在常用浓度单位之间换算，跨质量和摩尔单位时使用分子量。', 'Convert concentration units. Crossing mass and molar units requires molecular weight.'), keywords: 'M mM uM nM mg/mL ng/uL concentration 浓度 换算', fields: [number('value', '浓度数值', 'Concentration value'), choice('from_unit', '原单位', 'From unit', 'mg/mL', concentrationOptions), choice('to_unit', '目标单位', 'To unit', 'uM', concentrationOptions), { ...mw(), visible: (v) => ['M', 'mM', 'uM', 'nM', 'pM'].includes(v.from_unit) !== ['M', 'mM', 'uM', 'nM', 'pM'].includes(v.to_unit) }] },
  { id: 'solution', category: 'solutions', title: c('溶液配制质量', 'Solution preparation mass'), description: c('由目标摩尔浓度、终体积与摩尔质量计算称量值。', 'Calculate solute mass from target molarity, final volume and molar mass.'), keywords: 'stock molarity mass buffer preparation 溶液 配制 称量 缓冲', fields: [number('concentration_mM', '目标浓度（mM）', 'Target concentration (mM)'), number('volume_mL', '溶液终体积（mL）', 'Final solution volume (mL)', '', { positive: true }), mw()] },
  { id: 'dilution', category: 'solutions', title: c('单次稀释 C₁V₁ = C₂V₂', 'Single dilution C₁V₁ = C₂V₂'), description: c('计算原液取用量与稀释液加入量。', 'Calculate stock and diluent volumes.'), keywords: 'stock dilution volume 稀释 定容', fields: [number('stock_concentration', '原液浓度', 'Stock concentration', '', { positive: true }), number('target_concentration', '目标浓度', 'Target concentration'), choice('concentration_unit', '两种浓度使用同一单位', 'Shared concentration unit', 'uM', concentrationOptions), number('final_volume_uL', '终体积（µL）', 'Final volume (µL)', '', { positive: true })] },
  { id: 'serial-dilution', category: 'solutions', title: c('连续梯度稀释', 'Serial dilution planner'), description: c('考虑后续取样和死体积，逐步列出移液量。', 'Plan each transfer with downstream withdrawals and dead volume.'), keywords: 'BLI serial dilution series 梯度 稀释', fields: [] },
  { id: 'centrifuge', category: 'equipment', title: c('离心 RPM ⇄ RCF', 'Centrifuge RPM ⇄ RCF'), description: c('根据转子有效半径换算转速与相对离心力。', 'Convert rotational speed and relative centrifugal force using rotor radius.'), keywords: 'rpm rcf g centrifuge 离心 转速', fields: [number('radius_cm', '有效旋转半径（cm）', 'Effective rotor radius (cm)', '', { positive: true }), choice('from_unit', '已知量', 'Known quantity', 'rpm', [{ value: 'rpm', label: c('转速（rpm）', 'Speed (rpm)') }, { value: 'rcf', label: c('相对离心力（×g）', 'Relative centrifugal force (×g)') }]), number('value', '已知数值（单位见上方）', 'Known value (unit selected above)')] },
  { id: 'bli', category: 'equipment', title: c('BLI 数据预览', 'BLI data preview'), description: c('查看结合曲线、拟合结果及诊断。', 'Inspect binding curves, fits and diagnostics.'), keywords: 'binding affinity KD kinetics 生物层 干涉 亲和力', fields: [] },
  { id: 'akta', category: 'equipment', title: c('AKTA 数据预览', 'AKTA data preview'), description: c('查看层析曲线、峰与积分边界。', 'Inspect chromatography traces, peaks and integration boundaries.'), keywords: 'chromatography purification 层析 纯化 色谱', fields: [] },
  { id: 'enzyme', category: 'equipment', title: c('酶活数据预览', 'Enzyme activity preview'), description: c('查看反应曲线、斜率与拟合诊断。', 'Inspect activity traces, slopes and fit diagnostics.'), keywords: 'enzyme activity kinetics 酶活 反应 动力学', fields: [] },
]

export function initialToolValues(tool: BenchTool, prefill: Record<string, string> = {}): Record<string, string> {
  return Object.fromEntries(tool.fields.map((field) => [field.name, prefill[field.name] ?? field.initial]))
}

/** Reject missing, infinite and silently underflowed user numbers before transport. */
export function parseBenchNumber(raw: string): number {
  const value = Number(raw)
  if (!raw.trim() || !Number.isFinite(value) || (value === 0 && /[1-9]/.test(raw.split(/[eE]/)[0]))) {
    throw new Error('数值缺失或超出范围 / Number missing or outside numeric range')
  }
  return value
}

/** Scalar conversion only; scientific arithmetic is owned by the backend. */
export function calculationPayload(tool: BenchTool, values: Record<string, string>): Record<string, unknown> {
  const body: Record<string, unknown> = { kind: tool.id }
  for (const field of tool.fields) {
    if (field.name.startsWith('_') || (field.visible && !field.visible(values))) continue
    const raw = values[field.name]?.trim() ?? ''
    if (!raw && field.optional) continue
    if (!raw) throw new Error(`${field.label.zh} / ${field.label.en}`)
    if (field.type === 'number') {
      const value = parseBenchNumber(raw)
      if ( (field.positive && value <= 0) || (field.min !== undefined && value < field.min) || (field.step === '1' && !Number.isInteger(value))) throw new Error(`${field.label.zh} / ${field.label.en}`)
      body[field.name] = value
    } else body[field.name] = raw
  }
  // Normalized absorbance has a 1 cm basis, irrespective of a hidden raw-path draft.
  if (body.absorbance_basis === 'normalized-1cm') body.path_length_cm = 1
  return body
}
