# BDA 内置研究包、PDB结构与 BYOK 使用指南

状态：活跃

最后核验：2026-08-29（Asia/Shanghai；本轮核验格式、索引与链接）

权威范围：本文标题所述主题；当前平台与科研总状态以 docs/refactor/CURRENT_STATE_2026-08-29.md 为准。

数据来源：仓库内版本化代码、配置、测试与本文列明的来源。

替代关系：如正文未另行声明，则不取代其他权威文档。

## 1. 打开完整研究包

进入 **研究**，选择项目后可切换综述与证据、参考文献、PDB 结构、数据表和研究方法五个标签。项目综述正文显示在对应项目的“综述与证据”页顶部；页面只从后端 `GET /api/v2/projects/{project_id}/research-workspace` 读取展示数据，后端是 Research 展示的唯一权威来源，静态 JSON 不参与页面渲染。页面结构、标签职责和验收规则见 [Research 界面使用逻辑指南](RESEARCH_INTERFACE_USAGE_GUIDE.md)。

内置研究包仍由 `scripts/build_bundled_research_package.py` 从 `deliverables/protein_knowledge_pain_targets_20260719/` 确定性生成，用于首次同步和版本更新。更新原始 CSV/JSON/Markdown 后重新运行脚本，再通过研究包同步接口补齐后端项目。

当前内置包使用 `schema_version: "1.1"`：每条参考文献显式声明 `project_ids`，每个项目的中英文综述包含且仅包含一次对应参考文献。后端只在字段完全未声明时兼容 1.0；显式空值、非字符串或未知版本都会被拒绝。1.1 包执行综述 bibliography 格式校验，所有版本都通过同一规范化模型执行结构化项目、文献、关系、结构和候选引用闭包校验。PMID、DOI、可信 URL 和核验状态必须符合服务端格式及来源白名单；只有规范化 checksum 命中随服务端发布的内置包信任清单时，文献状态才直接写为 `verified`，其他合法包进入 `pending_review`。

## 2. 同步4个可编辑项目

管理员或研究员打开项目库时，每个登录会话会在授权范围内执行一次幂等同步。viewer 不触发写操作；包版本较旧时只显示更新提示。同步会：

1. 创建四个独立 Project；
2. 创建并确认各项目 primary target；
3. 对有实验结构的主靶标发起 PDB mmCIF 导入；
4. 将项目综述、每条机制关系和12个疼痛候选写入对应项目；
5. 将研究方法、检索策略和核验参考文献写入 Knowledge Entry；
6. 保留 `package_id`、`claim_id`、证据等级、assertion class 和原始论文 URL。

同步以研究包族和 `source_project_key` 定位项目，不会重复创建。若历史库中存在同一内置项目的多份记录，项目列表只展示候选、结构、文献、发现和知识条目最完整的一份；重复同步按稳定 ID 创建、更新或删除带研究包 lineage 的托管候选、关系和参考文献，并取消已从新版本移除且尚未发布的结构导入任务；没有包来源标记的用户笔记和自建数据会被保留。共享论文会分别关联到需要它的项目。接口统计唯一论文数和项目—论文关联数，便于区分内容去重与项目可见性。

中英文切换同时作用于界面、项目元数据、综述、证据、候选和方法正文，切换时不会重新请求 workspace。单语普通项目或 Copilot 导入项目缺少当前语言译文时显示原文和回退提示，不会自动调用模型翻译。

## 3. PDB结构目录

Mol* 只载入后端 artifact 返回的授权下载地址，并提供链筛选、表示方式、着色、相机重置和全屏。项目中保存的内置结构包括：

- 大麻素：5TGZ、5U09、6N4B、5ZTY、3LS4；
- 杀虫蛋白：1CIY、1DLC、6TFJ；
- PD‑1：3BIK、3BP5、5IUS、6JBT。

每条结构保存 PDB ID、实验方法、分辨率、机制角色、参考文献编号和 RCSB 链接。疼痛候选无合适实验PDB时不伪造条目，应在“靶标智能分析”中检索 PDB/AlphaFold 或上传自定义结构。

## 4. 使用自己的 API Key

1. 选择一个项目；
2. 打开 **设置 → Copilot API**；
3. 填写 OpenAI-compatible API base、模型名和 API Key；
4. 保存并点击“测试连接”；
5. 返回 **研究 → 综述与证据 → 生成同类研究**，填写主题、疾病分层、候选数和截止日期；
6. 点击“在Copilot中生成”，检查自动生成的严格提示后发送；
7. 在回答下点击“保存到项目综述”，人工复核后可转成工作流。

开发环境中的 API Key 不写入 `copilot_configs.settings` 或普通业务表。API 将密钥写入 `BDA_V2_LLM_LOCAL_SECRET_DIR` 下权限为 `0600` 的文件，只在数据库保存 `file:` credential reference；Docker Compose 使用只读共享卷让 Copilot worker 读取。响应仅返回末四位预览。

生产环境禁止浏览器提交原始 API Key。管理员必须在 secret manager 中配置密钥，并在 LLM Provider Registry 使用 `env:` 或 `file:` credential reference。

## 5. 同类研究的实现方法

内置生成提示强制以下阶段：

1. 明确项目边界、术语本体和纳入/排除标准；
2. 保存完整检索式、日期、原始命中和筛选决定；
3. 用 PMID/DOI/PDB/UniProt 精确核验元数据；
4. 将来源、证据记录、结论和关系证据拆分，支持支持/反驳/限定多证据；
5. 对候选执行同口径历史/近5年/综述/试验/专利计量；
6. 评分后生成研究卡和 LGALSL 式验证链；
7. 将组学、空间表达、直接结合、结构界面、细胞/回路、行为、干预和否定性实验写成阶段闸门；
8. 人工审核后写入 Project Review/Knowledge，再转为 Workflow。

平台不会把 LLM 输出自动标为已证实事实。新生成内容默认需要人工审核；无法核验的引用、因果外推和“未检出=从未研究”必须拒绝。

### 结构化结果与导入

“在 Copilot 中生成”会要求返回 `schema_version: "1.0"` 的单个 JSON 对象。结果按 `project`、`primary_target`、`references`、`nodes`、`edges` 和 `candidates` 分层；关系边只能引用已声明节点，每个结论引用只能指向 `references` 中存在且带 PMID、DOI 或 HTTP(S) URL 的条目。

Copilot 消息下方的“校验并一键导入”调用 `/api/v2/copilot-research-imports`。后端先完成 JSON 语法、严格 schema、ID 唯一性、节点闭包和引用闭包校验，再开始数据库写入。错误以 `$.edges[0].reference_ids[0]` 形式定位，并附带出错的引用 ID。任何校验或写入失败都会回滚整个请求，不修改当前项目；成功后创建独立的可编辑项目、draft Research Brief、结构化关系 findings、pending-review 文献和研究候选。相同内容按规范化 JSON 的 SHA-256 幂等，不重复创建项目。
