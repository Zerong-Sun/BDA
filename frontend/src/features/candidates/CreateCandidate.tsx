import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Textarea } from '../../components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '../../components/ui/dialog'
import { createCandidate, getCandidate, updateCandidate } from '../../lib/api/candidates'
import { ApiError, type ProblemDetails } from '../../lib/api/client'
import { useProjectAccess } from '../../lib/hooks/useProjectAccess'
import { useI18n } from '../../lib/i18n'
import { useAppStore } from '../../lib/store/appStore'
import type { Candidate } from '../../lib/schemas/candidate'

/** A proposal can precede both computation and a known sequence. Never supply
 * predicted scores or experimental success just to populate an empty table. */
export function CreateCandidate({ projectId, candidate, onCreated }: { projectId: string; candidate?: Candidate; onCreated: (candidate: Candidate) => void }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const access = useProjectAccess(projectId)
  const demo = useAppStore((state) => state.appMode === 'demo')
  const writable = Boolean(projectId && access.data?.permissions.write && !access.isError && !demo && (!candidate || candidate.project_id === projectId))
  const client = useQueryClient()
  const mounted = useRef(true)
  useEffect(() => { mounted.current = true; return () => { mounted.current = false } }, [])
  const [open, setOpen] = useState(false)
  const [base, setBase] = useState(candidate)
  const [name, setName] = useState(candidate?.name ?? '')
  const [sequence, setSequence] = useState(String(candidate?.properties.sequence ?? ''))
  const [rationale, setRationale] = useState(String(candidate?.properties.design_rationale ?? ''))
  const existingLinks = Array.isArray(base?.properties.evidence_links) ? base.properties.evidence_links.filter((v): v is string => typeof v === 'string') : []
  const [source, setSource] = useState(existingLinks[0] ?? '')
  // Stable across retries after a network error; a retry must not create a new key.
  const [key, setKey] = useState(() => `manual-${crypto.randomUUID()}`)
  const normalizedSequence = sequence.replace(/\s/g, '').toUpperCase()
  const sequenceValid = Boolean(base?.properties.sequence) || !normalizedSequence || /^[ACDEFGHIKLMNPQRSTVWY]+$/.test(normalizedSequence)
  const sourceValid = !source.trim() || (() => { try { return ['https:', 'http:'].includes(new URL(source.trim()).protocol) } catch { return false } })()
  const save = useMutation({
    mutationFn: () => {
      if (!writable || !name.trim() || !rationale.trim() || !sequenceValid || !sourceValid) throw new Error(zh ? '请检查必填字段和输入格式。' : 'Check required fields and input formats.')
      const properties = { ...base?.properties, design_rationale: rationale.trim(),
        evidence_links: [...new Set([...(source.trim() ? [source.trim()] : []), ...existingLinks.slice(1)])],
        ...(!base?.properties.sequence && normalizedSequence ? { sequence: normalizedSequence } : {}) }
      if (base) return updateCandidate(base.id, base.version, { name: name.trim(), properties })
      return createCandidate(projectId, {
        candidate_key: key, name: name.trim(), candidate_kind: 'design_candidate', status: 'proposed',
        properties: { ...properties, source: 'manual', review_status: 'pending_review', experimental_status: 'not_tested' },
      })
    },
    onSuccess: (updated) => {
      for (const prefix of ['candidates', 'all-candidates', 'candidate-funnel', 'project-overview']) void client.invalidateQueries({ queryKey: [prefix, projectId] })
      if (!mounted.current) return
      onCreated(updated)
      if (candidate) loadFields(updated)
      else { setName(''); setSequence(''); setRationale(''); setSource(''); setKey(`manual-${crypto.randomUUID()}`) }
      setOpen(false)
    },
  })
  function loadFields(value: Candidate) {
    setBase(value); setName(value.name); setSequence(String(value.properties.sequence ?? ''))
    setRationale(String(value.properties.design_rationale ?? ''))
    setSource(Array.isArray(value.properties.evidence_links) ? String(value.properties.evidence_links[0] ?? '') : '')
  }
  const conflict = save.error instanceof ApiError ? save.error : null
  const conflictBody = conflict?.payload as Partial<ProblemDetails> | undefined
  const duplicateId = conflict?.status === 409 && conflictBody?.error_code === 'candidate_key_conflict' ? conflictBody.errors?.[0]?.candidate_id : undefined
  const recover = useMutation({
    mutationFn: () => {
      const id = typeof duplicateId === 'string' ? duplicateId : base?.id
      if (!id) throw new Error(zh ? '未找到已保存候选。' : 'No saved candidate was found.')
      return getCandidate(id)
    },
    onSuccess: (latest) => {
      if (!mounted.current || latest.project_id !== projectId) return
      for (const prefix of ['candidates', 'all-candidates', 'candidate-funnel', 'project-overview']) void client.invalidateQueries({ queryKey: [prefix, projectId] })
      if (candidate) loadFields(latest)
      else { onCreated(latest); setOpen(false); setName(''); setRationale(''); setSequence(''); setSource(''); setKey(`manual-${crypto.randomUUID()}`) }
      save.reset()
    },
  })
  return <>
    <Button type="button" variant={candidate ? 'outline' : 'default'} disabled={!writable} onClick={() => { if (candidate && candidate.version > (base?.version ?? 0)) loadFields(candidate); save.reset(); recover.reset(); setOpen(true) }} title={writable ? undefined : zh ? '需要项目编辑权限；演示模式只读。' : 'Project edit access is required; demo mode is read-only.'}>{candidate ? (zh ? '编辑候选依据' : 'Edit candidate rationale') : (zh ? '手动添加候选' : 'Add candidate manually')}</Button>
    {access.isError ? <Button type="button" variant="outline" onClick={() => void access.refetch()}>{zh ? '重试权限检查' : 'Retry permission check'}</Button> : null}
    <Dialog open={open} onOpenChange={(next) => { if (!save.isPending && !recover.isPending) setOpen(next) }}>
      <DialogContent>
        <DialogHeader><DialogTitle>{candidate ? (zh ? '编辑候选依据' : 'Edit candidate rationale') : (zh ? '添加候选草稿' : 'Add a candidate proposal')}</DialogTitle><DialogDescription>{candidate ? (zh ? '补充设计依据和来源。已有序列保持原样；序列变化请新增候选以保留计算与实验的对应关系。' : 'Update rationale and sources. To change an existing sequence, create a new candidate so prior computations and experiments retain their identity.') : (zh ? '先记录设计依据，序列和文献链接可后续补齐。保存为待复核、未实验的提案。' : 'Record the design rationale first; sequence and literature may follow. Saved as a proposal pending review, with no experimental validation.')}</DialogDescription></DialogHeader>
        <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); save.mutate() }}>
          <fieldset disabled={!writable || save.isPending || recover.isPending} className="space-y-3">
            <label className="block space-y-1 text-sm"><span>{zh ? '候选名称' : 'Candidate name'}</span><Input required maxLength={240} value={name} onChange={(event) => setName(event.target.value)} /></label>
            <label className="block space-y-1 text-sm"><span>{zh ? '设计依据与待验证问题' : 'Design rationale and open questions'}</span><Textarea required maxLength={10000} value={rationale} onChange={(event) => setRationale(event.target.value)} /></label>
            <label className="block space-y-1 text-sm"><span>{zh ? '论文或来源链接（可选）' : 'Paper or source URL (optional)'}</span><Input type="url" maxLength={2000} value={source} onChange={(event) => setSource(event.target.value)} /></label>
            <label className="block space-y-1 text-sm"><span>{zh ? '氨基酸序列（可选，20 种标准残基）' : 'Amino-acid sequence (optional, 20 standard residues)'}</span><Textarea readOnly={Boolean(base?.properties.sequence)} maxLength={20000} value={sequence} onChange={(event) => setSequence(event.target.value)} /></label>
            {!sequenceValid ? <p role="alert">{zh ? '请输入氨基酸单字母序列，不含 FASTA 标题、数字或终止符。' : 'Use amino-acid single-letter codes, without FASTA headers, digits or stop symbols.'}</p> : null}
            {!sourceValid ? <p role="alert">{zh ? '来源必须为 HTTP 或 HTTPS 链接。' : 'Use an HTTP or HTTPS source URL.'}</p> : null}
            <Button type="submit" disabled={!name.trim() || !rationale.trim() || !sequenceValid || !sourceValid}>{save.isPending ? (zh ? '保存中…' : 'Saving…') : candidate ? (zh ? '保存候选依据' : 'Save candidate rationale') : (zh ? '保存候选草稿' : 'Save candidate proposal')}</Button>
          </fieldset>
          {save.isError ? <p role="alert" className="text-sm text-destructive">{save.error.message}</p> : null}
          {(conflict?.status === 412 && base) || typeof duplicateId === 'string' ? <Button type="button" variant="outline" disabled={save.isPending || recover.isPending} onClick={() => recover.mutate()}>{zh ? '放弃当前修改并读取已保存候选' : 'Discard edits and load saved candidate'}</Button> : null}
          {recover.isError ? <p role="alert">{recover.error.message}</p> : null}
        </form>
      </DialogContent>
    </Dialog>
  </>
}
