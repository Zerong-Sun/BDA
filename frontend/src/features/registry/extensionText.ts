// Translate only known service messages; preserve unknown operator-supplied text.
const messages: Record<string, string> = {
  "A site runtime requires a host/cluster backend": "站点运行环境需要主机或集群后端。",
  "Site queue must be a single scheduler identifier": "站点队列必须是单个调度器标识。",
  "Site environment cannot replace platform BDA_* variables; use runtime_root": "站点环境不能替换平台 BDA_* 变量；请使用 runtime_root。",
  "Set a runtime_root, module_names or manifest runtime setup for the site runtime": "请为站点环境配置 runtime_root、module_names 或清单中的运行设置。",
  "A container runtime requires a concrete image": "容器运行环境需要具体镜像。",
  "Host site setup cannot be applied to a container runtime": "主机站点设置不能用于容器运行环境。",
  "Plugin site overrides are invalid": "插件站点覆盖配置无效。",
  "A logical conda runtime requires runtime_root or explicit setup": "逻辑 conda 环境需要 runtime_root 或显式设置。",
  "module_names must contain real site module names, not logical site URIs": "module_names 必须包含真实站点模块名称，不能使用逻辑站点 URI。",

  'Inspection uses stored declarations only; it does not contact hosts, resolve credentials, allocate resources, or establish scientific validity.': '仅检查已保存的声明；不连接主机、读取凭据、分配资源，也不证明科学有效性。',
  'Implementation is bundled with BDA; deployment health and performance are not probed.': '实现已随 BDA 提供；本次未探测部署健康状态或性能。',
  'No execution adapter is shipped for this extension. Requirements can be reviewed, but this assessment cannot install or run it.': '此扩展尚未提供执行适配器。可以查看要求，但此评估不能安装或运行扩展。',
  'Select a registered model plugin.': '请选择已登记的模型插件。',
  'The selected model plugin must be enabled.': '所选模型插件必须已启用。',
  'The model declaration must pass registry validation.': '模型声明必须通过注册表验证。',
  'Pin the model runtime to a checksummed plugin manifest.': '将模型运行环境锁定到有校验值的插件清单。',
  'Record runtime proof matching the current declaration fingerprint.': '请记录与当前声明指纹一致的运行证据。',
  'Record the exact checkpoint, license and intended-use review.': '请记录具体权重、许可及预期用途的审核。',
  'Declared site runtime resolves for the selected backend; host files have not been inspected.': '声明的站点环境可匹配所选后端；尚未检查主机文件。',
  'Select a registered compute node for resource review.': '请选择已登记的计算节点，以便审核资源。',
  'The selected compute node must be enabled.': '所选计算节点必须已启用。',
  'A scientific-model trial requires a real LSF or Docker backend; a demo declaration is not execution evidence.': '科学模型试验需要真实的 LSF 或 Docker 后端；演示声明不构成执行证据。',
  'The compute node needs a recorded healthy status; this inspector never probes the host.': '计算节点需要已记录的健康状态；此检查不会探测主机。',
  'The model requests a GPU; the selected node must declare enough gpu_count slots.': '模型需要 GPU；所选节点声明的 GPU 数量必须足够。',
  'GPU type, memory, scheduler availability and driver compatibility still need site validation.': 'GPU 类型、显存、调度器可用性及驱动兼容性仍需站点验证。',
  'Select a registered local model provider.': '请选择已登记的本地模型服务。',
  'The selected model provider must be enabled.': '所选模型服务必须已启用。',
  'Provider config must explicitly declare deployment_kind=local; an API-shaped URL alone does not prove local hosting.': '服务配置须明确声明 deployment_kind=local；仅有 API 地址不能证明本地托管。',
  'Provider model and credential reference must be declared; credentials are not read here.': '须声明服务模型和凭据引用；此处不会读取凭据。',
  'Connection, model identity, inference throughput and data egress require separate provider tests; no call was made.': '连接、模型身份、推理吞吐及数据出站需单独测试；本次未调用模型。',
  'Supply a reviewed code/weights/dependency license reference.': '请提供代码、权重及依赖许可的审核记录。',
  'Supply the data boundary and retention review reference.': '请提供数据边界与保留策略的审核记录。',
  'Supply the scoped benchmark/acceptance plan reference.': '请提供范围明确的基准或验收方案记录。',
  'Supply the reviewed labor/compute/experiment budget reference.': '请提供人工、计算及实验预算的审核记录。',
  'Supplied review references are declarations, not independently verified documents or spending approvals.': '填写的审核引用属于声明，不代表文件已经独立核验或开支已经批准。',
  'Model resources are malformed; review the registry declaration.': '模型资源格式有误，请复核注册表声明。',
  'No versioned checkpoint/use review is recorded. Confirm exact code, weights and intended-use terms before scientific deployment.': '尚未记录有版本的权重及用途审核；用于科学任务前，请确认具体代码、权重及用途条款。',
  'The recorded checkpoint/use-review contract is invalid.': '已记录的权重及用途审核契约无效。',
  'Qualification belongs to a different plugin key or version.': '资格审核属于其他插件标识或版本。',
  'Checkpoint/use review is pending or rejected.': '权重及用途审核尚未通过，或已被拒绝。',
  'Intended use is not covered by the recorded license review.': '记录的许可审核未涵盖预期用途。',
  'Research-only checkpoint terms do not authorize commercial use.': '仅限研究的权重条款不授权商业使用。',
  'Review timestamp is in the future.': '审核时间晚于当前时间。',
  'The recorded checkpoint/use review has expired.': '已记录的权重及用途审核已过期。',
}

export function extensionMessage(message: string, zh: boolean): string {
  if (!zh) return message
  if (messages[message]) return messages[message]
  const observed = /^(\d+) matching registry declarations exist\. Select exact resources for a scoped assessment; a record does not prove installation\.$/.exec(message)
  if (observed) return `已有 ${observed[1]} 条匹配的注册声明。请选择具体资源进行限定范围的评估；登记不证明已经安装。`
  const scope = /^Recorded use review is scoped to: (.*)\. It does not establish scientific validity or prove which files were loaded at runtime\.$/s.exec(message)
  if (scope) return `已记录的用途审核范围：${scope[1]}。这不证明科学有效性，也不证明运行时实际加载了哪些文件。`
  return message
}

export function extensionCheckStatus(status: string, zh: boolean): string {
  return zh ? ({ recorded: '已记录', missing: '待补充', blocked: '受阻', not_checked: '未检查' }[status] ?? status) : status
}
