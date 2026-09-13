// Reference guidance only: never consumed by execution or candidate pass/fail logic.
// Reviewed 2026-09-07. BDA route examples: backend_v2/app/copilot/route_catalog.py.
export interface ModelResultGuide {
  pluginKey: string
  aliases: string[]
  zh: { metrics: string; reference: string; next: string }
  en: { metrics: string; reference: string; next: string }
  source: string | null
}

export const modelResultGuides: ModelResultGuide[] = [
  {
    "pluginKey": "AlphaFold2",
    "aliases": [
      "AlphaFold2 (initial guess)",
      "af2",
      "alphafold2"
    ],
    "zh": {
      "metrics": "pLDDT：局部置信度，0–100，越高越可信；PAE：相对位置误差，Å，越低越好。分别检查目标区域、binder 和界面，不能只看全局均值。",
      "reference": "pLDDT：≥90 很高，70–<90 较可信，50–<70 低，<50 很低。这是置信度分档，不是结合或功能通过线。",
      "next": "结合设计需结合界面指标、结构叠合及多 seed 一致性；缺失指标记为未评估。"
    },
    "en": {
      "metrics": "pLDDT measures local confidence (0–100, higher is better); PAE estimates relative-position error (Å, lower is better). Inspect the target region, binder and interface separately.",
      "reference": "pLDDT: ≥90 very high, 70–<90 confident, 50–<70 low, <50 very low. These are confidence bands, not binding or function criteria.",
      "next": "For binder design, inspect interface metrics, structural alignment and agreement across seeds. Missing metrics remain unassessed."
    },
    "source": "https://www.ebi.ac.uk/training/online/courses/alphafold/inputs-and-outputs/evaluating-alphafolds-predicted-structures-using-confidence-scores/plddt-understanding-local-confidence/"
  },
  {
    "pluginKey": "AlphaFold 3",
    "aliases": [
      "af3",
      "alphafold3"
    ],
    "zh": {
      "metrics": "pLDDT 是逐原子的局部置信度（0–100）；ipTM 是界面置信度（0–1）；PAE 单位 Å。多链体系检查目标链对。",
      "reference": "官方参考：ipTM >0.8 高置信度，0.6–0.8 不确定，<0.6 提示预测可能失败。不能仅凭 pLDDT >80 放行。",
      "next": "检查目标区域 pLDDT、跨链 PAE、has_clash 和多 seed 姿态一致性，再按已校准路线决定是否进入 Rosetta；小分子体系需另校准。"
    },
    "en": {
      "metrics": "pLDDT is per-atom local confidence (0–100); ipTM is interface confidence (0–1); PAE is in Å. Inspect the relevant chain pair.",
      "reference": "Official reference: ipTM >0.8 confident, 0.6–0.8 uncertain, <0.6 suggests possible prediction failure. pLDDT >80 alone is insufficient.",
      "next": "Check local pLDDT, cross-chain PAE, has_clash and pose agreement across seeds before route-specific Rosetta selection. Calibrate small-molecule cases separately."
    },
    "source": "https://github.com/google-deepmind/alphafold3/blob/main/docs/output.md"
  },
  {
    "pluginKey": "superfold",
    "aliases": [
      "superfold (AlphaFold2 + initial guess)",
      "superfold"
    ],
    "zh": {
      "metrics": "AF2 wrapper：读取 pLDDT、pTM 和重折叠结构；scRMSD 是与设计骨架叠合后的误差（Å），需明确残基集合。",
      "reference": "BDA AF2 binder 路线建议：A 档 pLDDT >70、界面 PAE <15 Å、Cα RMSD <3 Å；B 档 >85、<7 Å、<1.5 Å。三项共同判断。",
      "next": "上述是待校准路线建议。单体或未输出界面 PAE 的运行不能据此判定结合通过；确认实际启用的 initial_guess、模型及 recycle。"
    },
    "en": {
      "metrics": "AF2 wrapper: read pLDDT, pTM and refolded coordinates. scRMSD measures alignment to the design backbone (Å); specify the residue set.",
      "reference": "BDA AF2 binder route suggestions: Tier A pLDDT >70, interface PAE <15 Å, Cα RMSD <3 Å; Tier B >85, <7 Å, <1.5 Å. Assess jointly.",
      "next": "These route suggestions require calibration. Monomer runs or missing interface PAE cannot establish a binder pass. Verify initial_guess, model and recycles."
    },
    "source": "https://github.com/RosettaCommons/RFdiffusion"
  },
  {
    "pluginKey": "ProteinMPNN",
    "aliases": [
      "proteinmpnn",
      "mpnn"
    ],
    "zh": {
      "metrics": "score 为设计位点平均负对数概率，越低表示模型认为序列更适配骨架；global_score 的残基范围不同。",
      "reference": "无通用绝对通过分数。仅在相同权重、骨架及评分位点定义下比较；低分不等于稳定或高亲和力。",
      "next": "核对固定残基、链分配、长度及序列数，去重后进入独立重折叠，联合 pLDDT 与 scRMSD 筛选。"
    },
    "en": {
      "metrics": "score is mean negative log probability over designed positions; lower means greater model compatibility with the backbone. global_score covers a different residue set.",
      "reference": "No universal cutoff. Compare matching weights, backbone and scoring masks; a low score does not establish stability or affinity.",
      "next": "Check fixed residues, chain assignment, length and sequence count. Deduplicate and independently refold; assess pLDDT together with scRMSD."
    },
    "source": "https://github.com/dauparas/ProteinMPNN"
  },
  {
    "pluginKey": "RFdiffusion",
    "aliases": [
      "rfdiffusion",
      "rfd1"
    ],
    "zh": {
      "metrics": "输出骨架/结构与生成记录；检查长度、链连续性、碰撞和 motif/热点/配体条件是否实际满足。",
      "reference": "没有跨任务通用的生成分数通过线；几何约束需要按本次设计目标设置，生成成功不等于可折叠。",
      "next": "通过几何与输出完整性检查后进入序列设计，再独立重折叠并比较 scRMSD 和置信度。"
    },
    "en": {
      "metrics": "Outputs are generated structures and generation records. Check length, chain continuity, clashes and realized motif/hotspot/ligand conditioning.",
      "reference": "No universal generation-score cutoff across tasks. Set geometry criteria for the design objective; generation success does not establish foldability.",
      "next": "After geometry and output-completeness checks, design sequences, independently refold and assess scRMSD with confidence."
    },
    "source": "https://github.com/RosettaCommons/RFdiffusion"
  },
  {
    "pluginKey": "RFdiffusion3",
    "aliases": [
      "rfdiffusion3",
      "rfd3",
      "RFdiffusion3 (atom-level motif)"
    ],
    "zh": {
      "metrics": "输出骨架/结构与生成记录；检查长度、链连续性、碰撞和 motif/热点/配体条件是否实际满足。",
      "reference": "没有跨任务通用的生成分数通过线；几何约束需要按本次设计目标设置，生成成功不等于可折叠。",
      "next": "通过几何与输出完整性检查后进入序列设计，再独立重折叠并比较 scRMSD 和置信度。"
    },
    "en": {
      "metrics": "Outputs are generated structures and generation records. Check length, chain continuity, clashes and realized motif/hotspot/ligand conditioning.",
      "reference": "No universal generation-score cutoff across tasks. Set geometry criteria for the design objective; generation success does not establish foldability.",
      "next": "After geometry and output-completeness checks, design sequences, independently refold and assess scRMSD with confidence."
    },
    "source": "https://github.com/RosettaCommons/foundry"
  },
  {
    "pluginKey": "Rosetta",
    "aliases": [
      "Rosetta InterfaceAnalyzer",
      "rosetta"
    ],
    "zh": {
      "metrics": "total_score、每残基分数和界面 ddG 是不同指标；通常以 REU 表示，相同协议下越低越有利。",
      "reference": "BDA binder 路线建议：界面 ddG A 档 <−20 REU，B 档 <−40 REU，配套 beta_nov16。不得套用到 total_score、每残基分数或其他 score function。",
      "next": "检查 relax 后结构、重复结果、碰撞与界面质量；结合独立预测和实验决定候选。REU 不能直接换算 Kd。"
    },
    "en": {
      "metrics": "total_score, score per residue and interface ddG are distinct metrics, usually in REU; lower is more favorable within a matching protocol.",
      "reference": "BDA binder route suggestions: interface ddG <−20 REU (A) or <−40 REU (B), with beta_nov16. Do not apply to total_score, per-residue scores or other score functions.",
      "next": "Inspect relaxed geometry, repeats, clashes and interface quality alongside independent prediction and experiments. REU does not directly convert to Kd."
    },
    "source": "https://docs.rosettacommons.org/docs/latest/application_documentation/analysis/interface-analyzer"
  },
  {
    "pluginKey": "Boltz",
    "aliases": [
      "boltz",
      "boltz2"
    ],
    "zh": {
      "metrics": "检查 pLDDT、ipTM、PAE 与对应链对；以输出 schema 确认 pLDDT 是 0–1 还是 0–100。亲和力读数与结构置信度分开判读。",
      "reference": "无 BDA 统一放行阈值；不能把 AF3 的 ipTM 分档直接当作 Boltz 已校准的通过标准。",
      "next": "检查样本完整性、碰撞与不同 seed 一致性；若设计过程已优化 Boltz 分数，需用独立方法验证。"
    },
    "en": {
      "metrics": "Inspect pLDDT, ipTM, PAE and the relevant chain pair. Confirm whether pLDDT uses 0–1 or 0–100 in the output schema. Assess affinity outputs separately.",
      "reference": "No unified BDA gate. AF3 ipTM bands are not calibrated Boltz acceptance criteria.",
      "next": "Check sample completeness, clashes and seed agreement. Designs optimized against Boltz scores require independent validation."
    },
    "source": "https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md"
  },
  {
    "pluginKey": "proteinhunter_boltz",
    "aliases": [
      "proteinhunterboltz",
      "proteinhunter"
    ],
    "zh": {
      "metrics": "逐 cycle 检查内部 Boltz 置信度、序列和 best 结构；同时统计全部轨迹与缺失输出。",
      "reference": "内部优化分数只能作为生成过程读数；高 ipTM/pLDDT 不构成独立验证，没有统一跨 plugin 放行值。",
      "next": "去重，检查可开发性，并交由独立重折叠/结构评估；保留失败轨迹及分母，不能只汇总 best。"
    },
    "en": {
      "metrics": "Inspect internal Boltz confidence, sequences and best structures per cycle; count all trajectories and missing outputs.",
      "reference": "Optimization scores describe the generation process. High ipTM/pLDDT is not independent validation; no unified handoff cutoff exists.",
      "next": "Deduplicate, assess developability and independently refold/evaluate. Retain failed trajectories and denominators, not just best outputs."
    },
    "source": "https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md"
  },
  {
    "pluginKey": "BindCraft",
    "aliases": [
      "bindcraft"
    ],
    "zh": {
      "metrics": "联合读取 pLDDT、界面 PAE、ipTM、界面能量等，以及每个 filter 的通过/失败原因。",
      "reference": "以本次冻结的 filters JSON 为准；不同 preset 的阈值不同，accepted 仅表示通过内部过滤。",
      "next": "同时保留 target、filters、advanced 配置与拒绝记录；进入独立结构及可开发性验证，不能把内部过滤重复计为独立证据。"
    },
    "en": {
      "metrics": "Read pLDDT, interface PAE, ipTM, interface energy and individual filter outcomes together.",
      "reference": "Use the run’s frozen filters JSON. Presets differ; accepted means internal filters passed.",
      "next": "Preserve target, filters, advanced settings and rejection records. Independently evaluate structure and developability; do not count internal filters as independent evidence."
    },
    "source": "https://github.com/martinpacesa/BindCraft"
  },
  {
    "pluginKey": "Chai-1",
    "aliases": [
      "chai1",
      "chai"
    ],
    "zh": {
      "metrics": "检查结构、置信度和样本排名；以实际版本确认 pLDDT、pTM、ipTM 等字段及量纲。",
      "reference": "无 BDA 已校准通用阈值；排名第一不等于高质量，不能照搬其他预测器的阈值。",
      "next": "核对全部样本、目标链对、碰撞及 seed 一致性，再进行独立结构评估；指南不代表该插件已具备运行条件。"
    },
    "en": {
      "metrics": "Inspect structures, confidence and sample ranking; verify pLDDT, pTM, ipTM fields and scales for the actual version.",
      "reference": "No calibrated universal BDA threshold. Rank 1 does not imply quality; do not transplant cutoffs from other predictors.",
      "next": "Check all samples, relevant chain pairs, clashes and seed agreement, then evaluate independently. This guide does not establish runtime readiness."
    },
    "source": "https://github.com/chaidiscovery/chai-lab"
  },
  {
    "pluginKey": "DiffAb",
    "aliases": [
      "diffab"
    ],
    "zh": {
      "metrics": "检查抗体/CDR 序列与结构、框架保留、链及编号映射、抗原界面几何。",
      "reference": "无通用采样分数通过线；CDR RMSD 必须注明参考结构与叠合范围，低 RMSD 不证明结合。",
      "next": "先核对设计区域与完整性，再做独立复合物预测和可开发性评估；运行可用性另由插件状态决定。"
    },
    "en": {
      "metrics": "Inspect antibody/CDR sequences and structures, framework retention, chain/number mapping and antigen-interface geometry.",
      "reference": "No universal sampling-score cutoff. Specify reference and alignment scope for CDR RMSD; low RMSD does not prove binding.",
      "next": "Check design regions and completeness before independent complex prediction and developability assessment. Runtime availability is separate."
    },
    "source": "https://github.com/luost26/diffab"
  },
  {
    "pluginKey": "Mask RGN",
    "aliases": [
      "maskrgn"
    ],
    "zh": {
      "metrics": "实验性插件：先核对当前版本的输出 schema、序列/结构、checkpoint 和样本数。",
      "reference": "尚无经验证的通用指标量纲与放行阈值；未知字段不自动解释为置信度或通过。",
      "next": "使用已知对照校准读数并独立重折叠；未建立指标定义前标为未评估。"
    },
    "en": {
      "metrics": "Experimental plugin: first verify the version’s output schema, sequences/structures, checkpoint and sample count.",
      "reference": "No validated universal metric scale or acceptance cutoff. Unknown fields must not be interpreted as confidence or a pass.",
      "next": "Calibrate readouts on known controls and independently refold. Mark results unassessed until metric definitions are established."
    },
    "source": null
  },
  {
    "pluginKey": "Foldseek",
    "aliases": [
      "Foldseek (structure search)",
      "foldseek"
    ],
    "zh": {
      "metrics": "联合查看 E-value（越低越显著）、比对覆盖率及结构相似度；记录数据库和搜索模式。",
      "reference": "无统一命中通过线。E-value 依赖数据库规模；局部高相似度不能替代全长覆盖，也不能证明功能相同。",
      "next": "检查 query/target 双侧覆盖、比对区域及参考结构质量；需要定量叠合时继续 US-align。"
    },
    "en": {
      "metrics": "Read E-value (lower is more significant), alignment coverage and structural similarity together; record database and search mode.",
      "reference": "No universal hit cutoff. E-value depends on database size; local similarity cannot replace full-length coverage or prove shared function.",
      "next": "Inspect query/target coverage, aligned regions and reference quality; use US-align for pairwise structural assessment."
    },
    "source": "https://github.com/steineggerlab/foldseek"
  },
  {
    "pluginKey": "US-align",
    "aliases": [
      "US-align (TM-score)",
      "usalign"
    ],
    "zh": {
      "metrics": "TM-score 为 0–1，越高越相似；RMSD 单位 Å，越低越接近。同时报告比对长度与归一化所用链长。",
      "reference": "没有对所有长度、复合物和核酸都通用的通过值；短片段低 RMSD 不等于全结构一致。",
      "next": "按预先定义的残基/链映射判断结构保持；结合置信度与功能证据，不把结构相似直接解释为功能相同。"
    },
    "en": {
      "metrics": "TM-score ranges from 0–1 (higher is more similar); RMSD is in Å (lower is closer). Report aligned length and normalization length.",
      "reference": "No universal pass value across lengths, complexes and nucleic acids. Low RMSD over a short fragment does not establish global agreement.",
      "next": "Assess preservation using predefined residue/chain mappings alongside confidence and functional evidence; similarity does not establish shared function."
    },
    "source": "https://github.com/pylelab/USalign"
  },
  {
    "pluginKey": "APBS+PDB2PQR",
    "aliases": [
      "APBS + PDB2PQR (surface electrostatics)",
      "apbspdb2pqr",
      "apbs",
      "pdb2pqr"
    ],
    "zh": {
      "metrics": "检查 PQR、DX 电势与完整原子结构；电势单位以输出为准，记录 pH、力场、离子强度及网格。",
      "reference": "无通用电势通过阈值；仅在相同单位、参数与可比较表面区域下比较，正负电势不等于亲和力。",
      "next": "先检查质子化、缺失原子、网格与边界设置，再分析界面静电；与结构和实验信息联合判读。"
    },
    "en": {
      "metrics": "Inspect PQR, DX potential and full-atom coordinates. Confirm output units and record pH, force field, ionic strength and grid.",
      "reference": "No universal potential cutoff. Compare matching units, settings and surface regions; potential sign is not affinity.",
      "next": "Check protonation, missing atoms, grid and boundary settings before assessing interface electrostatics with structural and experimental evidence."
    },
    "source": "https://apbs.readthedocs.io/"
  }
]

const normalize = (key: string) => key.toLowerCase().replace(/[^a-z0-9]/g, '')
export function findModelResultGuide(pluginKey: string) {
  const key = normalize(pluginKey)
  return modelResultGuides.find((guide) =>
    [guide.pluginKey, ...guide.aliases].some((alias) => normalize(alias) === key),
  )
}
