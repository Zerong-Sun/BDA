# 已退役的一次性脚本

这里的脚本跑完了它们要修的那一次，不会再跑第二次。留在树里是为了保住出处——私有研究记录里引用过它们的路径——而不是为了继续使用。它们仍在 `ruff` 与 `mypy` 覆盖范围内，所以必须保持可通过检查；但没有测试、没有 CI，**不要**把它们当作可依赖的运维工具。

如果同类问题再次出现，先判断它是不是一次性的：会反复出现的状态应该由迁移、seeder 或活跃脚本处理，见 [脚本说明](../README.md)。

## `repair_generated_research_projects.py`

- 原路径：`backend_v2/scripts/repair_generated_research_projects.py`
- 退役前 SHA-256：`e3da03c1266b842b321c43a1d3060b99627c9d7abc7d636501bb8faa436be058`
- 做过什么：订正 `source_package_id` 以 `copilot-research-v2:` 开头的生成式研究项目——从证据来源项目补回摘要与本地化文本、补建缺失的综述发现与研究靶点、把结构 artifact 从来源重新复制一份并在 lineage 上打 `repair_status: copied_from_evidence_source`。
- 为什么不留在活跃列表：它从 `app/research/generation` 导入了四个下划线私有函数（`_ensure_research_targets`、`_ensure_review_sections`、`_evidence_source_project`、`_localized_text`）。那是一次性订正可以接受的耦合，但作为常备工具会在这些内部实现改动时静默失配。生成路径本身的正确性应由 `research` 领域的服务与测试保证。
