import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { downloadArtifact, getArtifact } from '../../lib/api/artifacts'
import { useI18n } from '../../lib/i18n'
import { Button } from '../../components/ui/Button'
import { ApiState } from '../../components/ui/ApiState'
import { Disclosure } from '../../components/ui/Disclosure'
import { StructureViewerLazy } from '../pdb-viewer/StructureViewerLazy'

const Residues = z.array(z.object({ chain: z.string(), seq: z.number().int(), insertion_code: z.string().nullable().optional(), name: z.string().optional() })).max(200)
export function ArtifactEvidence({ projectId, artifactId, residues }: { projectId: string; artifactId: string; residues: string | null }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  const [downloadError, setDownloadError] = useState('')
  const artifact = useQuery({ queryKey: ['result-artifact', projectId, artifactId], queryFn: async () => {
    const artifact = await getArtifact(artifactId)
    if (artifact.project_id !== projectId) throw new Error(zh ? '文件不属于当前项目。' : 'This artifact does not belong to the selected project.')
    return artifact
  } })
  let selected: z.infer<typeof Residues> = []
  try { selected = Residues.parse(JSON.parse(residues ?? '[]')) } catch { /* Invalid URL selections are never applied. */ }
  const structure = artifact.data && /\.(pdb|cif|mmcif)$/i.test(artifact.data.filename)
  return <section className="mb-5 space-y-3 rounded border border-border-soft p-4" aria-label={zh ? '所选证据' : 'Selected evidence'}>
    <h2 className="font-semibold">{zh ? '所选工具证据' : 'Selected tool evidence'}</h2>
    <ApiState isLoading={artifact.isLoading} isError={artifact.isError} error={artifact.error} onRetry={() => void artifact.refetch()}>
      {artifact.data ? <>
        <p className="break-all text-sm">{artifact.data.filename} · {artifact.data.artifact_type}</p>
        <p className="break-all font-mono text-xs">SHA-256: {artifact.data.checksum_sha256}</p>
        {selected.length ? <p className="break-words text-sm">{zh ? '选中残基' : 'Selected residues'}: {selected.map((residue) => `${residue.chain}:${residue.seq}${residue.insertion_code ?? ''}`).join(', ')}</p> : null}
        {structure ? <StructureViewerLazy source={{ projectId, artifactId, url: artifact.data.download_url, format: /\.(cif|mmcif)$/i.test(artifact.data.filename) ? 'mmcif' : 'pdb', proteinName: artifact.data.filename, highlightedResidues: selected.map((residue) => ({ chainId: residue.chain, seq: residue.seq, insertionCode: residue.insertion_code ?? '', label: residue.name })) }} height={420} /> : null}
        <Button type="button" variant="outline" size="sm" onClick={() => { setDownloadError(''); void downloadArtifact(artifact.data!).catch((error: unknown) => setDownloadError(error instanceof Error ? error.message : String(error))) }}>{zh ? '下载源文件' : 'Download source'}</Button>
        {downloadError ? <p role="alert" className="text-destructive">{downloadError}</p> : null}
        <Disclosure title={zh ? '来源与处理记录' : 'Source and processing lineage'}><pre className="max-h-64 overflow-auto whitespace-pre-wrap break-all text-xs">{JSON.stringify(artifact.data.lineage, null, 2)}</pre></Disclosure>
      </> : null}
    </ApiState>
  </section>
}
