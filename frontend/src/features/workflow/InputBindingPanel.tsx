import { useMemo } from 'react'
import type { InputPort, ModelPlugin } from '../../lib/schemas/registry'
import type { Artifact } from '../../lib/schemas/artifact'
import type { WorkflowInputBinding, WorkflowNode } from '../../lib/schemas/workflow'
import { useI18n } from '../../lib/i18n'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select'

/** An upstream node output that could feed a given input port. */
interface UpstreamOption {
  nodeKey: string
  portName: string
  label: string
}

export interface InputBindingPanelProps {
  node: WorkflowNode
  plugin?: ModelPlugin
  /** Every node in the workflow, used to offer upstream sources. */
  nodes: WorkflowNode[]
  pluginsByNodeKey: Record<string, ModelPlugin | undefined>
  artifacts: Artifact[]
  bindings: WorkflowInputBinding[]
  onChange: (bindings: WorkflowInputBinding[]) => void
  /** Show the bindings without allowing them to be rebound. */
  readOnly?: boolean
}

/**
 * Binds each declared input port to a concrete source.
 *
 * Compatibility is decided on `kind` and `artifact_type`, never on content type:
 * browsers mis-sniff scientific formats (a `.pdb` commonly uploads as
 * `application/vnd.palm`), so filtering on it would hide valid files.
 */
export function InputBindingPanel({
  node,
  plugin,
  nodes,
  pluginsByNodeKey,
  artifacts,
  bindings,
  onChange,
  readOnly = false,
}: InputBindingPanelProps) {
  const { t } = useI18n()
  const ports = useMemo(() => plugin?.input_ports ?? [], [plugin?.input_ports])

  const upstreamByPort = useMemo(() => {
    const map: Record<string, UpstreamOption[]> = {}
    for (const port of ports) {
      map[port.name] = nodes
        .filter((candidate) => candidate.id !== node.id)
        .flatMap((candidate) => {
          const outputs = pluginsByNodeKey[candidate.node_key]?.output_ports ?? []
          return outputs
            .filter(
              (output) =>
                output.kind === port.kind &&
                (port.accepts.length === 0 || port.accepts.includes(output.artifact_type)),
            )
            .map((output) => ({
              nodeKey: candidate.node_key,
              portName: output.name,
              label: `${candidate.node_key} · ${output.name}`,
            }))
        })
    }
    return map
  }, [node.id, nodes, pluginsByNodeKey, ports])

  const artifactsByPort = useMemo(() => {
    const map: Record<string, Artifact[]> = {}
    for (const port of ports) {
      map[port.name] = artifacts.filter(
        (artifact) => port.accepts.length === 0 || port.accepts.includes(artifact.artifact_type),
      )
    }
    return map
  }, [artifacts, ports])

  if (!plugin) {
    return (
      <p className="rounded border border-dashed border-border-soft p-3 text-xs text-text-secondary">
        {t.workflowExt.inspector.inputNoPluginPorts}
      </p>
    )
  }
  if (ports.length === 0) {
    return (
      <p className="rounded border border-dashed border-border-soft p-3 text-xs text-text-secondary">
        {t.workflowExt.inspector.inputNoPorts}
      </p>
    )
  }

  const bindingFor = (portName: string) => bindings.find((item) => item.port === portName)

  // A required port in an exclusive group is satisfied by any member, so the whole group
  // is judged together rather than flagging every alternative as missing.
  const groupSatisfied = (group: string) =>
    ports.some((item) => item.exclusive_group === group && bindingFor(item.name))

  const unsatisfied = (port: InputPort) => {
    if (!port.required || bindingFor(port.name)) return false
    return port.exclusive_group ? !groupSatisfied(port.exclusive_group) : true
  }

  const alternativesFor = (port: InputPort) =>
    port.exclusive_group
      ? ports.filter((item) => item.exclusive_group === port.exclusive_group && item.name !== port.name)
      : []

  const replace = (portName: string, next: WorkflowInputBinding | null) => {
    const port = ports.find((item) => item.name === portName)
    // Binding one alternative clears the others, so an exclusive group can never end up
    // with two bindings for the submission to reject.
    const siblings = port?.exclusive_group
      ? ports
          .filter((item) => item.exclusive_group === port.exclusive_group && item.name !== portName)
          .map((item) => item.name)
      : []
    const rest = bindings.filter((item) => item.port !== portName && !siblings.includes(item.port))
    onChange(next ? [...rest, next] : rest)
  }

  return (
    <div className="grid gap-2">
      {ports.map((port) => (
        <PortRow
          key={port.name}
          port={port}
          binding={bindingFor(port.name)}
          unsatisfied={unsatisfied(port)}
          alternatives={alternativesFor(port).map((item) => item.name)}
          artifacts={artifactsByPort[port.name] ?? []}
          upstream={upstreamByPort[port.name] ?? []}
          onChange={(next) => replace(port.name, next)}
          readOnly={readOnly}
        />
      ))}
    </div>
  )
}

function PortRow({
  port,
  binding,
  unsatisfied,
  alternatives,
  artifacts,
  upstream,
  onChange,
  readOnly,
}: {
  port: InputPort
  binding?: WorkflowInputBinding
  unsatisfied: boolean
  alternatives: string[]
  artifacts: Artifact[]
  upstream: UpstreamOption[]
  onChange: (next: WorkflowInputBinding | null) => void
  readOnly: boolean
}) {
  const { t } = useI18n()
  const source = binding?.source ?? 'none'

  const selectSource = (value: string) => {
    if (value === 'none') return onChange(null)
    if (value === 'artifact') return onChange({ port: port.name, source: 'artifact', artifact_id: '' })
    return onChange({ port: port.name, source: 'upstream', from_node: '', from_port: '' })
  }

  return (
    <div
      data-testid={`input-port-${port.name}`}
      className={`rounded-md border p-2 ${
        unsatisfied ? 'border-status-danger/50 bg-status-danger/5' : 'border-border-soft bg-bg-app'
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-text-primary">{port.name}</span>
        <span className="text-[10px] uppercase tracking-wide text-text-secondary">
          {port.required ? t.workflowExt.inspector.inputPortRequired : t.workflowExt.inspector.inputPortOptional}
        </span>
      </div>
      {port.description ? (
        <p className="mt-0.5 text-[11px] text-text-secondary">{port.description}</p>
      ) : null}
      {alternatives.length > 0 ? (
        <p className="mt-0.5 text-[10px] text-text-muted">
          {t.workflowExt.inspector.inputAlternative}: {alternatives.join(', ')}
        </p>
      ) : null}

      <Select
        value={source}
        disabled={readOnly}
        onValueChange={(value) => selectSource(value ?? 'none')}
      >
        <SelectTrigger aria-label={port.name} className="mt-2 w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="none">{t.workflowExt.inspector.inputSourceNone}</SelectItem>
          <SelectItem value="artifact">{t.workflowExt.inspector.inputSourceArtifact}</SelectItem>
          <SelectItem value="upstream">{t.workflowExt.inspector.inputSourceUpstream}</SelectItem>
        </SelectContent>
      </Select>

      {source === 'artifact' ? (
        artifacts.length === 0 ? (
          <p className="mt-1 text-[11px] text-text-secondary">{t.workflowExt.inspector.inputNoCandidates}</p>
        ) : (
          <Select
            value={binding?.artifact_id ?? ''}
            disabled={readOnly}
            onValueChange={(value) =>
              onChange({ port: port.name, source: 'artifact', artifact_id: value ?? '' })
            }
          >
            <SelectTrigger aria-label={`${port.name} artifact`} className="mt-1 w-full">
              <SelectValue placeholder={t.workflowExt.inspector.inputChooseArtifact} />
            </SelectTrigger>
            <SelectContent>
            {artifacts.map((artifact) => (
              <SelectItem key={artifact.id} value={artifact.id}>
                {artifact.filename} · {artifact.artifact_type}
              </SelectItem>
            ))}
            </SelectContent>
          </Select>
        )
      ) : null}

      {source === 'upstream' ? (
        upstream.length === 0 ? (
          <p className="mt-1 text-[11px] text-text-secondary">{t.workflowExt.inspector.inputNoUpstream}</p>
        ) : (
          <Select
            value={binding?.from_node && binding?.from_port ? `${binding.from_node}::${binding.from_port}` : ''}
            disabled={readOnly}
            onValueChange={(value) => {
              const [fromNode, fromPort] = (value ?? '').split('::')
              onChange({ port: port.name, source: 'upstream', from_node: fromNode, from_port: fromPort })
            }}
          >
            <SelectTrigger aria-label={`${port.name} upstream`} className="mt-1 w-full">
              <SelectValue placeholder={t.workflowExt.inspector.inputChooseUpstream} />
            </SelectTrigger>
            <SelectContent>
            {upstream.map((option) => (
              <SelectItem key={option.label} value={`${option.nodeKey}::${option.portName}`}>
                {option.label}
              </SelectItem>
            ))}
            </SelectContent>
          </Select>
        )
      ) : null}

      {port.accepts.length > 0 ? (
        <p className="mt-1 text-[10px] text-text-muted">
          {t.workflowExt.inspector.inputAccepts}: {port.accepts.join(', ')}
        </p>
      ) : null}
    </div>
  )
}
