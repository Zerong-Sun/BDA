import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckIcon, CrosshairIcon, XIcon } from '@phosphor-icons/react'
import type { HotspotResidue, HotspotSetResponse } from '../../lib/api/generated'
import { ApiError } from '../../lib/api/client'
import { useI18n } from '../../lib/i18n'
import { ApiState } from '../../components/ui/ApiState'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Alert, AlertDescription } from '../../components/reui/alert'
import { Badge } from '../../components/reui/badge'
import { Frame, FramePanel } from '../../components/reui/frame'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'
import type { HighlightedResidue, StructureSource } from '../pdb-viewer/types'
import { useCopilotReadOnly } from '../copilot/commandAccess'
import {
  confirmHotspotSet,
  createHotspotSet,
  rejectHotspotSet,
  residueArgument,
  useHotspotSets,
} from './hotspotSets'

/**
 * Which residues a design targets, and who said so.
 *
 * The two halves of this panel are the two halves of the problem it solves. The
 * list is what an operator proposed, with the reason and the evidence, waiting
 * for a person to accept or refuse it - a proposal reaches no job until then.
 * The picker is the other direction: clicking residues on the structure records
 * a set the person chose, which was previously a sentence typed into a chat box
 * and retyped into a parameter field.
 *
 * `origin` is shown on every row and not summarised away. "A model suggested
 * this", "I chose this" and "a model suggested it and I accepted" are three
 * different claims about the same list of residues, and the third is the one
 * most of this work actually produces.
 */
export function HotspotSetPanel({
  projectId,
  targetId,
  source,
}: {
  projectId: string
  /** The target a newly picked set belongs to; picking is offered only with one. */
  targetId?: string | null
  /** The structure to pick on. Without it the panel reviews and does not pick. */
  source?: StructureSource | null
}) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const queryClient = useQueryClient()
  const readOnly = useCopilotReadOnly()
  const sets = useHotspotSets(projectId || null)
  const [picking, setPicking] = useState(false)
  const [picked, setPicked] = useState<HotspotResidue[]>([])
  const [label, setLabel] = useState('')
  const [failed, setFailed] = useState<string | null>(null)

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['hotspot-sets', projectId] })
  }
  const explain = (error: unknown) => {
    setFailed(
      error instanceof ApiError && error.status === 412
        ? zh ? '这组位点刚刚已被处理，请刷新后再看。' : 'Someone has already ruled on this set; reload to see it.'
        : zh ? '操作没有完成，请重试。' : 'That did not go through. Try again.',
    )
  }
  const rule = useMutation({
    mutationFn: ({ set, accept }: { set: HotspotSetResponse; accept: boolean }) =>
      accept ? confirmHotspotSet(set.id, set.version) : rejectHotspotSet(set.id, set.version),
    onSuccess: () => { setFailed(null); refresh() },
    onError: explain,
  })
  const save = useMutation({
    mutationFn: () => createHotspotSet(targetId as string, {
      label: label.trim(),
      residues: picked,
      structure_artifact_id: source?.artifactId ?? null,
      rationale: '',
    }),
    onSuccess: () => {
      setFailed(null)
      setPicked([])
      setLabel('')
      setPicking(false)
      refresh()
    },
    onError: explain,
  })

  const addPick = (residue: HighlightedResidue) => {
    setPicked((current) => {
      // Clicking a residue twice removes it: the second click on the same thing
      // is how a person un-picks, and a set that only grows is a trap.
      const existing = current.findIndex((item) => item.chain === residue.chainId && item.seq === residue.seq)
      if (existing >= 0) return current.filter((_item, index) => index !== existing)
      return [...current, { chain: residue.chainId, seq: residue.seq, name: null }]
    })
  }

  const originLabel = (origin: string): string => {
    if (origin === 'human') return zh ? '你选定' : 'Chosen by you'
    if (origin === 'agent_proposed_human_confirmed') return zh ? 'Bot 提出 · 你确认' : 'Proposed by a Bot · you confirmed'
    return zh ? 'Bot 提出' : 'Proposed by a Bot'
  }
  const statusVariant: Record<string, 'success' | 'warning' | 'destructive'> = {
    confirmed: 'success', proposed: 'warning', rejected: 'destructive',
  }
  const statusLabel = (status: string): string => {
    if (status === 'confirmed') return zh ? '已确认' : 'Confirmed'
    if (status === 'rejected') return zh ? '已否决' : 'Rejected'
    return zh ? '待确认' : 'Waiting for you'
  }

  return (
    <section className="hotspot-panel" aria-label={zh ? '结合位点' : 'Hotspot sets'}>
      <div className="hotspot-panel-header">
        <div>
          <h3>{zh ? '结合位点' : 'Hotspot sets'}</h3>
          <p>
            {zh
              ? 'Bot 提出的位点需要你确认后才能进入设计任务；你也可以直接在结构上点选。'
              : 'A proposed set reaches no design job until you confirm it. You can also pick residues on the structure yourself.'}
          </p>
        </div>
        {source && targetId && !readOnly ? (
          <Button type="button" variant="outline" size="sm" onClick={() => setPicking(!picking)} aria-expanded={picking}>
            <CrosshairIcon aria-hidden="true" />
            {picking ? (zh ? '结束点选' : 'Stop picking') : (zh ? '在结构上点选' : 'Pick on the structure')}
          </Button>
        ) : null}
      </div>

      {picking && source ? (
        <Frame>
          <FramePanel className="grid gap-3">
            <StructureViewerLazy source={source} height={320} onResiduePick={addPick} />
            <p className="hotspot-picked">
              {picked.length
                ? `${zh ? '已选' : 'Picked'}: ${residueArgument(picked)}`
                : zh ? '点击结构上的残基来选择；再次点击取消。' : 'Click residues on the structure to pick them; click again to remove.'}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                aria-label={zh ? '这组位点的名称' : 'Name for this set'}
                placeholder={zh ? '例如：CC’ loop 界面' : 'For example: CC’ loop face'}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
              <Button
                type="button"
                disabled={!picked.length || !label.trim() || save.isPending}
                onClick={() => save.mutate()}
              >
                {zh ? '保存为已确认位点' : 'Save as a confirmed set'}
              </Button>
            </div>
          </FramePanel>
        </Frame>
      ) : null}

      {failed ? (
        <Alert variant="destructive"><AlertDescription>{failed}</AlertDescription></Alert>
      ) : null}

      <ApiState isLoading={sets.isLoading} isError={sets.isError} error={sets.error} onRetry={() => void sets.refetch()}>
        {(sets.data ?? []).length === 0 ? (
          <p className="text-sm text-text-secondary">
            {zh ? '还没有位点集合。' : 'No hotspot set has been recorded yet.'}
          </p>
        ) : (
          <ul className="hotspot-list">
            {(sets.data ?? []).map((set) => (
              <li key={set.id} className="hotspot-row">
                <div className="min-w-0">
                  <p className="hotspot-row-label">
                    {set.label}
                    <Badge variant={statusVariant[set.status] ?? 'warning'} size="xs">{statusLabel(set.status)}</Badge>
                    <span className="hotspot-origin">{originLabel(set.origin)}</span>
                  </p>
                  <p className="hotspot-residues">{residueArgument(set.residues ?? [])}</p>
                  {set.rationale ? <p className="hotspot-rationale">{set.rationale}</p> : null}
                  {(set.evidence_refs ?? []).length ? (
                    <p className="hotspot-refs">{(set.evidence_refs ?? []).join(' · ')}</p>
                  ) : null}
                </div>
                {set.status === 'proposed' && !readOnly ? (
                  <div className="flex flex-wrap gap-2">
                    <Button type="button" size="sm" variant="outline" disabled={rule.isPending}
                      onClick={() => rule.mutate({ set, accept: true })}>
                      <CheckIcon aria-hidden="true" />{zh ? '确认' : 'Confirm'}
                    </Button>
                    <Button type="button" size="sm" variant="destructive" disabled={rule.isPending}
                      onClick={() => rule.mutate({ set, accept: false })}>
                      <XIcon aria-hidden="true" />{zh ? '否决' : 'Reject'}
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ApiState>
    </section>
  )
}
