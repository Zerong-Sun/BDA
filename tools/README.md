# tools/ — 小工具收纳区

这里放**辅助性**的工具：有用，但不是平台的主线。主线是 `backend_v2/` 与 `frontend/`。

放这里的判据是"平台不依赖它也能跑"。反例：`qm-scripts/` 看起来像工具，实际是计算路径依赖的集群作业库，CI 有一道插件目录漂移门禁校验 `qm-scripts/library/catalog.json` 与 `model_plugins` 注册表一致——它是一等契约面，所以留在仓库根目录，**不**收进这里。

## 当前内容

暂无独立脚本。从 protein-lab 移植过来的湿实验能力都进了正式领域（见下），因为它们是产品功能而不是旁支工具。

## 湿实验能力的当前状态

移植自 `QINGMINGMIKU/protein-lab`（分支 `ui-design2`）。**已移植 ≠ 已暴露**，下表如实区分：

| 能力 | 内核位置 | API / UI |
|---|---|---|
| 分子量 / 消光系数 | `wetlab/kernels/calculators.py` | ✅ 建构建体时自动计算并存储 |
| 浓度（Beer-Lambert） | 同上 | ✅ `GET /wetlab/concentration` + Lab 页 |
| 六单位浓度换算 | 同上 | ✅ `GET /wetlab/unit-conversion` + Lab 页 |
| BLI 梯度稀释规划 | 同上 | ✅ `GET /wetlab/dilution-series` + Lab 页 |
| 蛋白库 / FASTA 导入 | `wetlab/service.py` | ✅ 完整 CRUD + Lab 页 |
| **酶活动力学**（TECAN xlsx 解析、96 孔板、Michaelis-Menten、阴性扣除、孔分组） | `calculators.py` | ✅ `POST /wetlab/enzyme-analyses` + copilot 工具 + Lab 页 |
| **BLI 曲线分析**（ForteBio CSV 解析、五方法 KD 拟合、死曲线过滤、NS 扣除） | `bli.py` | ✅ `POST /wetlab/bli-analyses` + copilot 工具 + Lab 页 |
| **AKTA 峰图**（Unicorn zip 原生解析、峰检测、馏分区间、峰表） | `akta.py` | ✅ `POST /wetlab/akta-analyses` + copilot 工具 + Lab 页 |
| Weblogo（序列 logo） | — | ⬜ **未移植**（依赖 logomaker 绘图；按"绘图归前端"的决定，应在浏览器侧实现） |

三个仪器分析已接通，走的正是本平台的上传形态：客户端 PUT 到预签名 URL、完成上传，然后把 **artifact id** 交给分析端点（API 从不接收 multipart 文件体）。链路是

```
artifact id → 对象存储取字节 → 内核解析/拟合 → 写 experiment_results
              （result_metadata 存 params/results + 分析版本号，
                source_artifact_id 指向那份不可变的原始 artifact）
```

不需要 protein-lab 的 `experiment_raw` 表：artifact 本就只写一次且带校验和，正是它当初要的不可变语义。**重新分析同一份文件会新增一行结果，而不是改写旧行**，因此被推翻的结论仍与取代它的那条并列可见。

## 不做绘图

protein-lab 在服务端用 matplotlib 出 PNG，因为它是没有前端构建的 Jinja 应用。这里内核只返回数据，图由浏览器画——图表可交互，后端镜像里也不必装 matplotlib。

分析响应里的 `summary` 因此带上**抽稀后的曲线本身**（BLI 结合曲线、AKTA 色谱、各孔动力学，每条 ≤600 点，按步长抽取而非平滑，抽稀后的点仍是实测点）。曲线只返回、不入库：`result_metadata` 只存拟合出的数值，原始 artifact 才是那份轨迹唯一的不可变副本。前端 `features/lab/LineChart.tsx` 用内联 SVG 画，不引图表库。

详见 `docs/refactor/PRESERVED_PRINCIPLES.md`（含 AKTA zip 与 ForteBio CSV 的格式逆向结论）。
