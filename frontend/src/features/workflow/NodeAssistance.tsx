import { useRef } from 'react'
import { WorkflowSection, WorkflowSelect, WorkflowOption } from './WorkflowControls'
import { useState } from 'react'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import {
  importScript,
  suggestParameters,
  type ImportedScript,
  type Suggestions,
} from '../../lib/api/workflowGates'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import { useToastStore } from '../../components/ui/toastStore'
import { GatePolicyEditor } from './GatePolicyEditor'
import { emptyPolicy, type GatePolicy } from './gates'

export function NodeAssistance({
  workflowId,
  node,
  nodes,
  configuration,
  onConfiguration,
  onParameter,
  readOnly,
  allowedParameters,
}: {
  workflowId: string
  node: WorkflowNode
  nodes: WorkflowNode[]
  configuration: Record<string, unknown>
  onConfiguration: (v: Record<string, unknown>) => void
  onParameter: (key: string, value: unknown) => void
  readOnly: boolean
  allowedParameters: string[]
}) {
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { language } = useI18n()
  const zh = language === 'zh'
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null)
  const [nodeVersions, setNodeVersions] = useState('')
  const [busy, setBusy] = useState(false)
  const [imported, setImported] = useState<ImportedScript | null>(null)
  const [linkTarget, setLinkTarget] = useState('')
  const [linkNode, setLinkNode] = useState('')
  const [linkParameter, setLinkParameter] = useState('')
  const [linkMode, setLinkMode] = useState('upstream_parameter')
  const toast = useToastStore((s) => s.show)
  const versions = nodes.map((n) => `${n.id}:${n.version}`).join('|')
  const stale = !!suggestions && versions !== nodeVersions
  const script = configuration.script as ImportedScript | undefined
  const links = (configuration.parameter_links ?? {}) as Record<
    string,
    { source: string; from_node: string; parameter?: string }
  >
  const upstream = nodes.filter((n) => node.input_bindings.some((b) => b.from_node === n.node_key))
  return (
    <section className="my-3 grid gap-2 rounded border border-border-soft p-2 text-xs">
      <Button
        type="button"
        size="sm"
        disabled={busy || readOnly}
        onClick={async () => {
          setBusy(true)
          try {
            setSuggestions(await suggestParameters(workflowId, node.id))
            setNodeVersions(versions)
          } catch (e) {
            toast((e as Error).message, 'error')
          } finally {
            setBusy(false)
          }
        }}
      >
        {zh ? '根据上游配置' : 'Suggest from upstream'}
      </Button>
      {stale && (
        <p role="alert">
          {zh ? '上游配置已变化，请重新获取建议。' : 'Upstream changed. Refresh suggestions.'}
        </p>
      )}
      {suggestions && (
        <div>
          <p>{suggestions.objective}</p>
          {suggestions.upstream_results?.map((result) => (
            <p key={`${result.job_id}:${result.port}`} className="text-text-secondary">
              {result.node_key}.{result.port} · {zh ? '运行尝试' : 'Attempt'} {result.attempt} ·{' '}
              {result.count}{' '}
              {zh
                ? '条上游结果（最终数量以门控放行为准）'
                : 'upstream results (final count is resolved after release)'}{' '}
              · {result.metrics.join(', ')}
            </p>
          ))}
          {suggestions.suggestions.length === 0 && (
            <p>
              {zh
                ? '没有可确定的参数映射；可在下方显式关联上游参数。'
                : 'No unambiguous mapping. Link an upstream parameter below.'}
            </p>
          )}
          {suggestions.suggestions.map((s) => (
            <div key={s.parameter} className="my-2 rounded bg-surface-2 p-2">
              <strong>{s.parameter}</strong>
              <p className="break-all">
                {JSON.stringify(node.parameters[s.parameter] ?? s.current)} →{' '}
                {JSON.stringify(s.value)}
              </p>
              <p>
                {s.source} · {s.reason}
              </p>
              <Button
                type="button"
                size="sm"
                disabled={readOnly || stale}
                onClick={() => onParameter(s.parameter, s.value)}
              >
                {zh ? '应用此项' : 'Apply suggestion'}
              </Button>
            </div>
          ))}
        </div>
      )}
      <WorkflowSection
        title={<> {zh ? '显式关联上游参数' : 'Explicit upstream parameter links'} </>}
      >
        <div className="my-2 grid gap-2">
          <WorkflowSelect
            aria-label="Target parameter"
            className="bg-surface-2 p-2"
            value={linkTarget}
            onChange={(e) => setLinkTarget(e.target.value)}
          >
            <WorkflowOption value="">{zh ? '本节点参数' : 'Target parameter'}</WorkflowOption>
            {allowedParameters.map((p) => (
              <WorkflowOption key={p}>{p}</WorkflowOption>
            ))}
          </WorkflowSelect>
          <WorkflowSelect
            aria-label="Upstream node"
            className="bg-surface-2 p-2"
            value={linkNode}
            onChange={(e) => { setLinkNode(e.target.value); setLinkParameter('') }}
          >
            <WorkflowOption value="">{zh ? '上游节点' : 'Upstream node'}</WorkflowOption>
            {upstream.map((n) => (
              <WorkflowOption key={n.id}>{n.node_key}</WorkflowOption>
            ))}
          </WorkflowSelect>
          <WorkflowSelect
            className="bg-surface-2 p-2"
            value={linkMode}
            onChange={(e) => setLinkMode(e.target.value)}
          >
            <WorkflowOption value="upstream_parameter">
              {zh ? '上游参数值' : 'Upstream parameter value'}
            </WorkflowOption>
            <WorkflowOption value="selected_count">
              {zh ? '门控放行后的结果数' : 'Count after screening'}
            </WorkflowOption>
          </WorkflowSelect>
          {linkMode === 'upstream_parameter' && (
            <WorkflowSelect
              className="bg-surface-2 p-2"
              aria-label="Source parameter"
              value={linkParameter}
              onChange={(e) => setLinkParameter(e.target.value)}
            >
              <WorkflowOption value="">—</WorkflowOption>
              {Object.keys(upstream.find((n) => n.node_key === linkNode)?.parameters ?? {}).map(
                (p) => (
                  <WorkflowOption key={p}>{p}</WorkflowOption>
                ),
              )}
            </WorkflowSelect>
          )}
          <Button
            type="button"
            size="sm"
            disabled={
              readOnly ||
              !linkTarget ||
              !linkNode ||
              (linkMode === 'upstream_parameter' && !Object.hasOwn(upstream.find((n) => n.node_key === linkNode)?.parameters ?? {}, linkParameter))
            }
            onClick={() =>
              onConfiguration({
                ...configuration,
                parameter_links: {
                  ...links,
                  [linkTarget]: { source: linkMode, from_node: linkNode, parameter: linkParameter },
                },
              })
            }
          >
            {zh ? '添加关联' : 'Add link'}
          </Button>
          {Object.entries(links).map(([k, v]) => (
            <div key={k}>
              {k} ← {v.from_node}.{v.source === 'selected_count' ? 'selected_count' : v.parameter}
              <Button
                type="button"
                variant="ghost"
                disabled={readOnly}
                className="ml-2"
                onClick={() =>
                  onConfiguration({
                    ...configuration,
                    parameter_links: Object.fromEntries(
                      Object.entries(links).filter(([key]) => key !== k),
                    ),
                  })
                }
              >
                ×
              </Button>
            </div>
          ))}
        </div>
      </WorkflowSection>
      <WorkflowSection
        title={<> {zh ? '节点执行脚本：导入与绑定' : 'Node script: import and bind'} </>}
      >
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={readOnly || busy}
          onClick={() => fileInputRef.current?.click()}
        >
          {zh ? '导入节点脚本' : 'Import node script'}
        </Button>
        <input
          className="hidden"
          ref={fileInputRef}
          type="file"
          accept=".sh,.bash,.py,.lsf"
          aria-label="Import node script"
          disabled={readOnly || busy}
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (!file) return
            setBusy(true)
            try {
              setImported(await importScript(workflowId, file.name, await file.text()))
            } catch (error) {
              toast((error as Error).message, 'error')
            } finally {
              setBusy(false)
              e.target.value = ''
            }
          }}
        />
        {imported && (
          <div>
            <pre className="my-2 max-h-48 overflow-auto whitespace-pre-wrap break-all">
              {imported.source}
            </pre>
            <p>
              {zh ? '静态识别的命令' : 'Observed commands'}: {imported.commands?.join(' · ') || '—'}
            </p>
            <p>
              {zh ? '观察到的输入' : 'Observed inputs'}: {imported.inputs?.join(', ') || '—'}
            </p>
            <p>
              {zh ? '观察到的输出' : 'Observed outputs'}: {imported.outputs?.join(', ') || '—'}
            </p>
            {imported.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
            {Object.entries(imported.parameters).map(([k, v]) => (
              <div key={k}>
                {k} = {JSON.stringify(v)}{' '}
                <Button
                  type="button"
                  size="sm"
                  disabled={readOnly || !allowedParameters.includes(k)}
                  onClick={() => onParameter(k, v)}
                >
                  {zh ? '应用参数' : 'Apply parameter'}
                </Button>
              </div>
            ))}
            <Button
              type="button"
              size="sm"
              disabled={readOnly}
              onClick={() => onConfiguration({ ...configuration, script: imported })}
            >
              {zh ? '将此版本设为执行脚本' : 'Use this script version'}
            </Button>
          </div>
        )}
        {script && (
          <div className="mt-2 break-all">
            <p>
              {script.filename} · SHA256 {script.checksum_sha256}
            </p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={readOnly}
              onClick={() => onConfiguration({ ...configuration, script: null })}
            >
              {zh ? '恢复插件脚本' : 'Use plugin script'}
            </Button>
          </div>
        )}
      </WorkflowSection>
      <WorkflowSection
        title={
          <>
            {' '}
            {zh
              ? '输出合格标准（所有出边共用）'
              : 'Output standard (shared by all outgoing edges)'}{' '}
          </>
        }
      >
        <GatePolicyEditor
          output
          disabled={readOnly}
          value={(configuration.output_policy as GatePolicy) ?? emptyPolicy()}
          onChange={(value) => onConfiguration({ ...configuration, output_policy: value })}
        />
      </WorkflowSection>
      <p className="text-text-muted">
        {zh
          ? '应用后点击“保存参数”；提交时冻结脚本、参数及规则版本。'
          : 'Save parameters after applying changes. Submission freezes scripts, parameters and policy versions.'}
      </p>
    </section>
  )
}
