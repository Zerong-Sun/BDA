import { Dialog, DialogContent, DialogTitle } from '../../components/ui/dialog'
import { WorkflowSelect, WorkflowOption } from './WorkflowControls'
import { useMemo, useState } from 'react'
import { useI18n } from '../../lib/i18n'
import type { WorkflowNode } from '../../lib/schemas/workflow'
import type { ModelPlugin } from '../../lib/schemas/registry'
import { Button } from '../../components/ui/Button'

export function ConnectionPicker({
  nodes,
  plugins,
  source,
  target,
  onConnect,
  onClose,
}: {
  nodes: WorkflowNode[]
  plugins: ModelPlugin[]
  source?: string
  target?: string
  onConnect: (source: string, target: string, from: string, to: string) => Promise<void>
  onClose: () => void
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [src, setSrc] = useState(source ?? '')
  const [dst, setDst] = useState(target ?? '')
  const [pair, setPair] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const pairs = useMemo(() => {
    const from = plugins.find((p) => p.id === nodes.find((n) => n.id === src)?.model_plugin_id)
    const to = plugins.find((p) => p.id === nodes.find((n) => n.id === dst)?.model_plugin_id)
    return (from?.output_ports ?? []).flatMap((a) =>
      (to?.input_ports ?? [])
        .filter(
          (b) => b.kind === a.kind && (!b.accepts.length || b.accepts.includes(a.artifact_type)),
        )
        .map((b) => [a.name, b.name]),
    )
  }, [src, dst, plugins, nodes])
  const chosen = pairs.length === 1 ? pairs[0] : pairs.find((p) => JSON.stringify(p) === pair)
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !busy) onClose()
      }}
    >
      <DialogContent>
        <DialogTitle>{zh ? '连接节点' : 'Connect nodes'}</DialogTitle>
        <strong>{zh ? '连接上游输出与下游输入' : 'Connect output to input'}</strong>
        <label>
          {zh ? '上一步' : 'Source'}
          <WorkflowSelect
            className="w-full bg-surface-2 p-2"
            aria-label={zh ? '上一步' : 'Source'}
            disabled={busy}
            value={src}
            onChange={(e) => {
              setSrc(e.target.value)
              setPair('')
              setError('')
            }}
          >
            <WorkflowOption value="">—</WorkflowOption>
            {nodes
              .filter((n) => n.id !== dst)
              .map((n) => (
                <WorkflowOption key={n.id} value={n.id}>
                  {n.node_key}
                </WorkflowOption>
              ))}
          </WorkflowSelect>
        </label>
        <label>
          {zh ? '下一步' : 'Target'}
          <WorkflowSelect
            className="w-full bg-surface-2 p-2"
            aria-label={zh ? '下一步' : 'Target'}
            disabled={busy}
            value={dst}
            onChange={(e) => {
              setDst(e.target.value)
              setPair('')
              setError('')
            }}
          >
            <WorkflowOption value="">—</WorkflowOption>
            {nodes
              .filter((n) => n.id !== src)
              .map((n) => (
                <WorkflowOption key={n.id} value={n.id}>
                  {n.node_key}
                </WorkflowOption>
              ))}
          </WorkflowSelect>
        </label>
        {pairs.length === 1 ? (
          <p className="text-xs">{pairs[0].join(' → ')}</p>
        ) : (
          <WorkflowSelect
            aria-label={zh ? '兼容端口' : 'Ports'}
            disabled={busy}
            className="w-full bg-surface-2 p-2"
            value={pair}
            onChange={(e) => setPair(e.target.value)}
          >
            <WorkflowOption value="">
              {zh ? '选择兼容端口' : 'Select compatible ports'}
            </WorkflowOption>
            {pairs.map((p) => (
              <WorkflowOption key={JSON.stringify(p)} value={JSON.stringify(p)}>
                {p.join(' → ')}
              </WorkflowOption>
            ))}
          </WorkflowSelect>
        )}
        {src && dst && pairs.length === 0 && (
          <p role="alert">
            {zh
              ? '没有兼容端口，请检查插件的输入输出声明。'
              : 'No compatible ports. Check the plugin declarations.'}
          </p>
        )}
        {error && (
          <p role="alert" className="text-danger">
            {error}
          </p>
        )}
        <div className="flex gap-2">
          <Button
            type="button"
            disabled={!chosen || busy}
            onClick={async () => {
              if (!chosen) return
              setError('')
              setBusy(true)
              try {
                await onConnect(src, dst, chosen[0], chosen[1])
                onClose()
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e))
              } finally {
                setBusy(false)
              }
            }}
          >
            {busy ? (zh ? '正在保存连接…' : 'Saving connection…') : (zh ? '连接' : 'Connect')}
          </Button>
          <Button type="button" variant="ghost" disabled={busy} onClick={onClose}>
            {zh ? '关闭' : 'Close'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
