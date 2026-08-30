# BDA Copilot 科研检索与集群任务指南

## 1. Copilot 的专业边界

Copilot 面向蛋白质设计、蛋白/多肽生物材料、结构预测、结合蛋白、酶与自组装材料。

回答中应区分：

- 实验结构与计算结构。
- 论文报告结果与 Copilot 综合判断。
- 实测性质与序列/结构预测。
- 蛋白结合、通路相关性和已验证功能机制。

Copilot 不应把 docking、AlphaFold、Rosetta、语言模型评分或序列启发式指标描述为已验证的结合、功能或安全性结论。

## 2. 联网科研工具

### RCSB PDB

可让 Copilot：

- 按靶点、蛋白名称、配体或复合物搜索 PDB。
- 获取 PDB ID、标题、实验方法、分辨率、发布日期和主要引用。
- 返回 RCSB 页面及 mmCIF 下载链接。

示例：

> 搜索人源 PD-1 与 PD-L1 复合物的实验结构，比较分辨率、构建体和结合状态，并推荐适合 binder design 的模板。

### Europe PMC

可让 Copilot：

- 搜索生命科学论文。
- 返回标题、作者、期刊、年份、DOI、PMID/PMCID、引用数、开放获取状态和摘要。
- 根据论文元数据和摘要综合方法、结果、限制与设计启示。

示例：

> 搜索最近关于 RFdiffusion 和 ProteinMPNN 设计蛋白 binder 的论文，按实验验证程度排序，并给出 DOI/PMID。

Copilot 只能在开放许可允许时使用全文；否则以摘要和元数据为依据，并应明确说明。

### UniProt

可查询蛋白 accession、标准名称、基因名、物种、序列长度、人工审核状态、功能注释和通路注释。
设计靶点时应优先检查物种、isoform、构建体边界与 reviewed 状态。

### Reactome

可将 UniProt accession 或基因标识符提交到 Reactome Analysis Service，返回相关通路及富集统计。
通路成员关系和富集结果属于数据库注释与统计证据，不自动证明该蛋白在具体细胞或实验体系中的因果机制。

### 序列性质

可计算长度、近似分子量、疏水残基比例、芳香残基比例、半胱氨酸数量、电荷代理值和 280 nm 消光系数估计。

这些指标只适合初筛，不能替代溶解性、稳定性、表达、聚集、亲和力、免疫原性或毒性实验。

## 3. 集群任务流程

### 生成草稿

向 Copilot 描述：

- 输入 artifact。
- 使用的软件和环境。
- CPU/GPU 队列。
- 参数。
- 预期输出。

Copilot 只能创建 `awaiting_confirmation` 草稿，不能直接提交。

### 审核

打开：

1. 顶部 `Copilot`。
2. 点击 `Cluster jobs`。
3. 展开 `Review LSF script`。
4. 检查队列、CPU/GPU、环境、输入路径、命令和输出。
5. 确认脚本 SHA-256 未发生变化。

### 提交

点击 `Confirm and submit` 后，后端才会：

1. 在 `/work/bme-sunzr/bda/copilot-jobs/<draft_id>` 建立任务目录。
2. 上传保存过的不可变脚本。
3. 执行 `bsub < submit.lsf`。
4. 保存 LSF Job ID。

### 查看与下载

- `Refresh` 查询 `bjobs`/`bhist`。
- 页面显示 stdout/stderr 尾部。
- 完成后列出 `output/` 中的文件。
- 点击文件即可通过鉴权接口下载。

## 4. 安全限制

草稿会阻止明显危险命令，包括：

- `sudo`
- 递归强制删除
- 关机、重启、格式化磁盘
- 二次 SSH/SCP
- `curl | sh`、`wget | sh`
- 将密码、Token 或 API Key 写进命令

真实提交和取消必须由用户明确确认。

## 5. 当前实现限制

- PDB 全文搜索可能返回名称相近但物种或功能不相关的结果，Copilot需要继续检查条目详情。
- 知识库当前有 9 条人工整理条目，尚未采用向量检索。
- Europe PMC 主要提供元数据和摘要；并非所有论文都有开放全文。
- Reactome 返回的通路可能包含疾病、药物或跨上下文上位通路，需要结合物种、细胞类型和实验问题筛选。

## 6. 文献学习与审核

管理员可通过 `POST /api/v1/copilot/literature/ingest` 摄取 Europe PMC 检索结果。开放获取且带
PMCID 的文献会尝试读取全文 XML；否则保存元数据和摘要。全文按章节分块，每个块保留标题、
章节路径和内容哈希。

配置 LLM 后，系统可以为文献块生成摘要，并抽取方法、实验、参数、结果、限制和假设。
每条科学主张必须附带能够在原始块中逐字定位的证据摘录，否则不会写入数据库。新主张和
主张间的支持、限定或矛盾关系默认都是 `pending_review`，不能直接视为人工确认知识。

主要接口：

- `GET /api/v1/copilot/literature?q=...`：检索本地文献证据。
- `GET /api/v1/copilot/literature/{document_id}`：查看文献、分块、主张和证据。
- `GET /api/v1/copilot/literature/claims`：列出待审核或已审核主张。
- `PATCH /api/v1/copilot/literature/claims/{claim_id}`：接受或拒绝主张。
- `POST /api/v1/copilot/literature/relations/detect`：检测主张间关系。
- `PATCH /api/v1/copilot/literature/relations/{relation_id}`：审核关系。
- `GET/POST /api/v1/copilot/literature/subscriptions`：管理自动阅读订阅。
- `POST /api/v1/copilot/literature/subscriptions/{subscription_id}/run`：立即运行订阅。

Celery Beat 每 15 分钟扫描到期订阅。每个订阅独立保存检索式、运行间隔、结果数量、全文读取和
LLM 抽取开关；失败只记录在该订阅，不会阻断其他查询。

DeepSeek OpenAI-compatible 配置示例：

```dotenv
LLM_API_BASE=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-pro
LLM_API_KEY=在本地环境中配置，不要提交到 Git
```

结构化抽取和工具调用会关闭 DeepSeek thinking 模式，避免无用推理开销以及多轮工具消息中
`reasoning_content` 的兼容问题；普通无工具聊天仍使用服务端默认推理设置。

## 7. Campaign 自动化闭环

Campaign 位于单轮 workflow DAG 之上，用于表达：

`设计 → 预测/评分 → 实验结果 → 评价 → 参数调整建议 → 人工审批 → 下一轮`

每轮保持无环 workflow。跨轮关系由 `campaign_rounds` 管理，避免在 workflow graph 中添加回边。
评价器可以使用候选数量、节点指标、任务状态，以及 BLI/SEC 等实验通过率。停止条件、预算和
参数调整规则都以结构化 JSON 保存。

安全边界：

- 有运行中任务时不能评价该轮。
- 同一轮只能产生一次正式评价。
- 参数 patch 必须匹配模型注册表中的真实参数。
- 继续、重试或停止都先生成 `proposed` decision。
- 研究员可以在审批前修改 patch。
- 审批后只创建下一轮 draft workflow，不自动提交计算。
- 湿实验步骤始终是人工操作与结果回传，不由 Campaign 自动执行。

主要接口：

- `POST /api/v1/campaigns`
- `GET /api/v1/projects/{project_id}/campaigns`
- `GET /api/v1/campaigns/{campaign_id}`
- `POST /api/v1/campaigns/{campaign_id}/rounds/{round_number}/evaluate`
- `PATCH /api/v1/campaign-decisions/{decision_id}`
- `POST /api/v1/campaign-decisions/{decision_id}/review`

前端顶部 `Research` 页面现按职责拆分为 4 个主要区域，避免和 `Project research review`
撞车：

- `Project review`：项目级研究综述与唯一事实底稿。所有要进入设计约束、工作流或 round plan
  的结论，最终都应沉淀到这里。每条卡片可展开或在卡片内滚动查看完整论点，并保留证据等级、
  审核状态、更新时间、不确定性与引用来源。
- `Target intelligence`：靶标情报 intake 流程。负责解析 target identity、收集可追溯 evidence、
  审核 evidence、确认 hotspots、生成 design routes，并可把已接受 evidence 直接写入
  `Project review` 的“靶点机制、功能、结构、序列与热点”等章节。
- `Knowledge & evidence`：共享证据库层，内部再分为：
  - `Evidence library`：文献摄取、本地检索、Claim/关系审核。已接受 claim 可写回
    `Project review` 的参考文献、机制、验证或风险章节。
  - `Curated notes`：人工整理的知识条目与经验笔记，不直接替代项目综述，而是作为可复用
    knowledge source。
- `Campaign loop`：多轮闭环优化与审批。表达 `设计 → 预测/评分 → 实验结果 → 评价 → 参数调整建议
  → 人工审批 → 下一轮`，不承担文献综述或靶标证据沉淀职责。

推荐信息流：

`Target intelligence / Evidence library / Curated notes -> Project review -> Workflow/Campaign`

这样分层后：

- intake 与 library 面板负责“收集、审核、整理原始证据”；
- `Project review` 负责“按 11 个研究章节综合为项目论点”；
- `Campaign loop` 负责“在已形成约束和验证策略后推动多轮执行”。

### Project review 写作规范

完整规则见 [RESEARCH_REVIEW_WRITING_STANDARD.md](RESEARCH_REVIEW_WRITING_STANDARD.md)。要点：

- **每条 finding**：独立摘要标题（6–15 词）+ 正文段落；不设字数上限，但不重复、不废话。
- **`references_reading`**：每个 source 一条，按文献精读结构写（Summary → Rationale → Innovations → Significance → Critical Evaluation → Questions → 本项目启示）。
- **其他章节**：按主题综合（机制、路线、争议、方法），不要逐篇流水账重复 references 全文。
- **禁止**：platform value、operating contract、decision gate、用章节名当标题、从正文首句截断标题（如 `E. coli` 被切成 `screen E`）。
