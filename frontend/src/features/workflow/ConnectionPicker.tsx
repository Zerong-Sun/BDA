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
  onConnect: (source: string, target: string, from: string | null, to: string | null) => Promise<void>
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
  // `ORDERING` is a valid answer, not a fallback for failure: two stages can legitimately
  // need to run in order while sharing no data. Without it, a pair of plugins with no
  // compatible port could not be connected at all - the dialog said "no compatible ports"
  // and left the Connect button disabled with nothing else to choose.
  const ORDERING = '__ordering__'
  const ordering = pair === ORDERING
  const chosen = ordering
    ? null
    : pairs.length === 1
      ? pairs[0]
      : pairs.find((p) => JSON.stringify(p) === pair)
  const canConnect = Boolean(src && dst && (chosen || ordering))
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
        <WorkflowSelect
          aria-label={zh ? '连接方式' : 'Connection'}
          disabled={busy}
          className="w-full bg-surface-2 p-2"
          value={pair || (pairs.length === 1 ? JSON.stringify(pairs[0]) : '')}
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
          <WorkflowOption value={ORDERING}>
            {zh ? '仅次序：等待上一步完成，不传数据' : 'Ordering only: wait for the previous step, pass no data'}
          </WorkflowOption>
        </WorkflowSelect>
        {src && dst && pairs.length === 0 && (
          <p role="alert" className="text-xs text-text-secondary">
            {zh
              ? '两个节点没有兼容的数据端口。可以只建立次序关系，或检查插件的输入输出声明。'
              : 'These two nodes share no compatible data port. Connect them for ordering only, or check the plugin declarations.'}
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
            disabled={!canConnect || busy}
            onClick={async () => {
              if (!canConnect) return
              setError('')
              setBusy(true)
              try {
                await onConnect(src, dst, chosen?.[0] ?? null, chosen?.[1] ?? null)
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
