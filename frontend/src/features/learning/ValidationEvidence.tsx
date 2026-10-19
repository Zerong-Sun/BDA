import { Disclosure } from '../../components/ui/Disclosure'
import { LearningTable } from '../../app/learningComponents'

type Copy = (cn: string, en: string) => string
const object = (value: unknown): Record<string, unknown> => value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
const rows = (value: unknown): Record<string, unknown>[] => Array.isArray(value) ? value.map(object) : []
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value.toPrecision(4) : '—'

export function FeatureExplanation({ version, copy }: { version: unknown; copy: Copy }) {
  return <p>{version === 'sequence-order-v1'
    ? copy('序列顺序特征 · 461 维：组成、长度、相邻残基对及首尾 10% 窗口。能够区分部分相同组成的序列，但不代表三维结构或基础模型表示。', 'Sequence-order features · 461 dimensions: composition, length, adjacent residue pairs and terminal 10% windows. Distinguishes some equal-composition sequences; does not represent 3D structure or foundation-model embeddings.')
    : copy('组成基线 · 21 维：氨基酸组成与长度，忽略残基顺序和结构。旧快照继续使用原始特征。', 'Composition baseline · 21 dimensions: amino-acid composition and length; ignores residue order and structure. Historical snapshots retain their original features.')}</p>
}

export function ValidationEvidence({ evaluation, unit, copy }: { evaluation: Record<string, unknown>; unit: string; copy: Copy }) {
  const quality = object(evaluation.data_quality)
  const predictions: Record<string, unknown>[] = rows(evaluation.folds).flatMap((fold) => rows(fold.test_predictions).map((prediction) => ({ ...prediction, group: fold.held_out_group })))
  return <div>
    <FeatureExplanation version={evaluation.feature_version} copy={copy} />
    <p>{copy('以下为冻结数据上的留出预测与真实测量对照；下一轮候选表中的预测尚未经过实验验证。', 'These held-out predictions are compared with frozen experimental observations. Predictions for the next candidate batch have not been experimentally validated.')}</p>
    {evaluation.data_quality != null && <p>{copy('交叉验证诊断', 'Validation diagnostics')}: {copy('家族重叠折数', 'Folds with family overlap')} {number(quality.family_overlap_fold_count)} · {copy('批次重叠折数', 'Folds with batch overlap')} {number(quality.batch_overlap_fold_count)}. {copy('精确重复序列已隔离；尚未证明同源序列隔离，家族标签需要科学审查。', 'Exact duplicate sequences are isolated. Homology isolation is not established; family labels require scientific review.')}</p>}
    {predictions.length > 0 && <Disclosure title={copy('比较留出预测与实测', 'Compare held-out predictions with observations')}>
      <div className="learning-scroll" tabIndex={0} role="region" aria-label={copy('验证预测与实测表', 'Validation predictions and observations')}>
        <LearningTable headings={[copy('留出组 / 序列摘要', 'Held-out group / sequence digest'), copy('实测值', 'Observed'), copy('留出预测', 'Held-out prediction'), copy('预测减实测', 'Prediction minus observation')]} cells={predictions.map((p) => [
          <>{String(p.group).slice(0, 24)} / {String(p.sequence_sha256).slice(0, 12)}</>,
          <>{number(p.observed)} {unit}</>, <>{number(p.predicted)} {unit}</>,
          <>{typeof p.predicted === 'number' && typeof p.observed === 'number' ? number(p.predicted - p.observed) : '—'} {unit}</>,
        ])} />
      </div>
    </Disclosure>}
  </div>
}
