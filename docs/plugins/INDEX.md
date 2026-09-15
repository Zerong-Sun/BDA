# BDA 插件说明总览

状态：活跃

最后核验：2026-09-16（整合验证）

权威范围：插件配置、参数解释与已记录的验证边界。

数据来源：版本化插件声明、参数定义及本文列出的来源。

替代关系：补充插件接口文档；配置覆盖不代表真实运行通过。

盘点日期：2026-09-15。19 个模型键（含 3 个 authoring 草稿），23 条模型版本记录，另有 4 个方法插件；合计 23 个独立插件键。

[统一解释与使用规范](STANDARD.md) · [审计与审阅记录](REVIEW.md)

覆盖表统计当前 library/BDA 已知字段；上游未接入功能和科学证据不足逐页列出。运行状态以当前声明指纹匹配为准。

| 插件 | 版本数 | 必须解释字段 | 已解释字段（含上游扩展） | 模式 | 输出定义 | 待解决缺口 |
|---|---:|---:|---:|---:|---:|---:|
| [APBS+PDB2PQR](../../qm-scripts/plugins/apbs-pdb2pqr/REFERENCE.md) | 1 | 3 | 5 | 3 | 17 | 3 |
| [AlphaFold 3](../../qm-scripts/plugins/alphafold3/REFERENCE.md) | 1 | 49 | 49 | 6 | 6 | 5 |
| [AlphaFold2](../../qm-scripts/plugins/alphafold2/REFERENCE.md) | 2 | 35 | 35 | 5 | 4 | 5 |
| [BindCraft](../../qm-scripts/plugins/bindcraft/REFERENCE.md) | 1 | 292 | 292 | 6 | 42 | 4 |
| [Boltz](../../qm-scripts/plugins/boltz/REFERENCE.md) | 1 | 39 | 39 | 7 | 7 | 5 |
| [Boltz-authoring-6810138a](../../qm-scripts/plugins/boltz-authoring-6810138a/REFERENCE.md) | 1 | 39 | 39 | 7 | 7 | 5 |
| [Chai-1](../../qm-scripts/plugins/chai1/REFERENCE.md) | 1 | 24 | 24 | 6 | 5 | 6 |
| [DiffAb](../../qm-scripts/plugins/diffab/REFERENCE.md) | 1 | 6 | 28 | 6 | 3 | 4 |
| [Foldseek](../../qm-scripts/plugins/foldseek/REFERENCE.md) | 1 | 4 | 8 | 5 | 7 | 5 |
| [Mask RGN](../../qm-scripts/plugins/mask-rgn/REFERENCE.md) | 1 | 54 | 54 | 3 | 3 | 5 |
| [ProteinMPNN](../../qm-scripts/plugins/proteinmpnn/REFERENCE.md) | 2 | 40 | 37 | 8 | 6 | 11 |
| [ProteinMPNN-authoring-6810138a](../../qm-scripts/plugins/proteinmpnn-authoring-6810138a/REFERENCE.md) | 1 | 37 | 37 | 8 | 6 | 11 |
| [RFdiffusion](../../qm-scripts/plugins/rfdiffusion/REFERENCE.md) | 1 | 135 | 119 | 8 | 3 | 9 |
| [RFdiffusion-authoring-6810138a](../../qm-scripts/plugins/rfdiffusion-authoring-6810138a/REFERENCE.md) | 1 | 135 | 119 | 8 | 3 | 9 |
| [RFdiffusion3](../../qm-scripts/plugins/rfdiffusion3/REFERENCE.md) | 1 | 8 | 62 | 9 | 4 | 10 |
| [Rosetta](../../qm-scripts/plugins/rosetta/REFERENCE.md) | 3 | 90 | 90 | 7 | 13 | 6 |
| [US-align](../../qm-scripts/plugins/us-align/REFERENCE.md) | 1 | 2 | 9 | 4 | 6 | 4 |
| [method_affinity_score](../../qm-scripts/plugins/method-affinity-score/REFERENCE.md) | 1 | 0 | 0 | 1 | 0 | 3 |
| [method_diversity_cap](../../qm-scripts/plugins/method-diversity-cap/REFERENCE.md) | 1 | 0 | 0 | 1 | 0 | 3 |
| [method_expression_risk](../../qm-scripts/plugins/method-expression-risk/REFERENCE.md) | 1 | 0 | 0 | 1 | 0 | 3 |
| [method_hydrophobic_patch](../../qm-scripts/plugins/method-hydrophobic-patch/REFERENCE.md) | 1 | 0 | 0 | 1 | 0 | 3 |
| [proteinhunter_boltz](../../qm-scripts/plugins/proteinhunter-boltz/REFERENCE.md) | 1 | 22 | 22 | 7 | 6 | 7 |
| [superfold](../../qm-scripts/plugins/superfold/REFERENCE.md) | 1 | 13 | 13 | 4 | 6 | 5 |
