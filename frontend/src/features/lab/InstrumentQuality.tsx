import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import type { z } from 'zod'
import { Button } from '../../components/ui/Button'
import { Disclosure } from '../../components/ui/Disclosure'
import { Textarea } from '../../components/ui/textarea'
import { useI18n } from '../../lib/i18n'
import { reviewInstrumentAnalysis, type AnalysisRecord } from '../../lib/api/wetlab'
import type { InstrumentQCSchema } from '../../lib/schemas/instrumentAnalysis'

const chineseChecks: Record<string, string> = {
  missing_points: '已排除非有限观测点，请检查缺失区间及其原因。',
  unusable_curve: '曲线至少需要五个有限、严格按时间递增的数据点，以及已知正浓度。',
  insufficient_concentrations: '当前浓度序列分析至少需要两个不同的正浓度。',
  inferred_phase_boundaries: '相界由信号自动推断，请与仪器协议核对。',
  invalid_phase_boundaries: '相界时间须为有限数值，结合起点须早于解离起点。',
  insufficient_phase_points: '曲线已排除：当前动力学方法要求每个拟合相至少五个点。',
  insufficient_signal_series: '相界与既有信号筛选后不足两个浓度；拟合不可用不等于不结合。',
  method_not_fitted: '此方法未产生可用的拟合估计。',
  endpoint_fit_degrees_of_freedom: '混合终点模型有三个参数；三个或更少浓度无法独立估计残差方差。',
  numerical_fit_warning: '数值求解器发出警告，请核查参数可辨识性与下方方法详情。',
  joint_not_converged: '作为主结果的全局动力学优化器没有确认收敛。',
  parameter_at_bound: '优化器报告参数位于约束边界，数值可能受到搜索范围限制。',
  rank_deficient_fit: '缩放后的 Jacobian 数值秩不足，当前拟合无法分别确定这些动力学参数。',
  kinetic_assumptions: '1:1 模型依赖正确参比与浓度，并假设传质或再结合不限制观测；拟合本身不能验证这些条件。',
  steady_state_assumption: '终点等温线使用末两秒数据，不能据此证明已经达到平衡。',
  invalid_volume_axis: '积分至少需要五个有限且体积严格递增的数据点。',
  non_uv_channel: '所选通道未被识别为 UV，不作为蛋白 UV 峰面积记录。',
  unknown_amplitude_unit: '缺少幅度单位，无法确认定量峰面积的单位。',
  boundary_truncated_peak: '积分窗口触及曲线边界，可能没有观测到完整峰面积。',
  overlapping_peak_windows: '峰积分窗口重叠，不能把这些面积当作独立组分直接相加。',
  peak_identity_unverified: 'UV 峰及扣基线面积不证明身份、纯度或产量；基线采用平滑后的 5% 分位数。',
  initial_rate_window_unverified: '当前拟合使用整个观测窗口；线性趋势不自动等于酶初始速率。',
  well_mapping_unverified: '摘要取各孔斜率最大值，接受前须核实样品/对照角色及候选与孔位对应关系。',
  background_unavailable: '请求了背景扣除，但文件中没有已标注的阴性或空白对照。',
  well_not_fitted: '该孔缺少足够且有序的有限时间点，没有赋予数值速率。',
  insufficient_residual_dof: '两个点决定的直线无法估计残差方差或斜率区间。',
  constant_response: '未观测到响应变化，不能区分无活性、检测限或仪器失败。',
}

export function InstrumentQuality({ quality, record, projectId, onReviewed }: {
  quality: z.infer<typeof InstrumentQCSchema> | null; record: AnalysisRecord; projectId: string;
  onReviewed: (record: AnalysisRecord) => void;
}) {
  const { language } = useI18n()
  const copy = (cn: string, en: string) => language === 'zh' ? cn : en
  const [rationale, setRationale] = useState('')
  const review = useMutation({
    mutationFn: (accept: boolean) => reviewInstrumentAnalysis(projectId, record, accept, rationale.trim()),
    onSuccess: (result) => {
      onReviewed({ ...record, version: result.version, qc_review: result.review })
      setRationale('')
    },
  })
  if (!quality) return <p className="text-sm text-text-secondary">{copy('此历史分析没有版本化质控诊断。请重新分析原始文件后审阅，不能将缺失诊断视为通过。', 'This historical analysis has no versioned QC diagnostics. Re-analyse the source before review; missing diagnostics do not mean QC passed.')}</p>
  const status = record.qc_review?.status ?? 'pending'
  return <section className="space-y-3 rounded-lg border border-border p-4" aria-label={copy('测量与拟合质控', 'Measurement and fit quality review')}>
    <h4 className="font-medium">{copy('测量与拟合质控', 'Measurement and fit quality review')} · {quality.version}</h4>
    <p className="text-sm">{copy('拟合数值不等于验证成功。保存的结果默认待审，只有人工接受后才进入候选实测指标；这仍不代表结合、活性或测定方法已验证。', 'A fitted value does not establish experimental success. Saved results stay pending until human acceptance projects a measured candidate metric; acceptance still does not validate binding, activity or the assay.')}</p>
    <ul className="space-y-2 text-sm">{quality.checks.map((check, index) => <li key={`${check.code}-${index}`}>
      <strong>{check.status === 'review' ? copy('需检查', 'Review') : copy('方法假设', 'Method assumption')} · {check.code}</strong>: {language === 'zh' ? chineseChecks[check.code] ?? check.message : check.message}
      {Object.keys(check.details).length > 0 && <span className="ml-2 font-mono text-xs">{JSON.stringify(check.details)}</span>}
    </li>)}</ul>
    <Disclosure title={copy('查看诊断数值与方法解释', 'Inspect diagnostic values and assumptions')}><pre className="overflow-auto text-xs">{JSON.stringify(quality, null, 2)}</pre></Disclosure>
    {record.experiment_result_id && record.version != null ? <form className="space-y-2" onSubmit={(event) => { event.preventDefault(); review.mutate(true) }}>
      <p className="text-sm">{copy('质控审阅状态', 'QC review status')}: {language === 'zh' ? ({ pending: '待审阅', accepted: '已接受质控', rejected: '已拒绝' } as Record<string, string>)[String(status)] ?? String(status) : String(status)}</p>
      <label className="block text-sm">{copy('记录来源、相界 / 窗口、对照及诊断的审阅依据', 'Record the source, phase/window, controls and diagnostic review rationale')}
        <Textarea value={rationale} onChange={(event) => setRationale(event.target.value)} required maxLength={2000} disabled={review.isPending} />
      </label>
      <div className="flex flex-wrap gap-2">
        <Button type="submit" disabled={!rationale.trim() || review.isPending || record.value == null}>{copy('接受拟合质控', 'Accept fit QC')}</Button>
        <Button type="button" variant="outline" disabled={!rationale.trim() || review.isPending} onClick={() => review.mutate(false)}>{copy('拒绝此拟合', 'Reject this fit')}</Button>
      </div>
      {review.error && <p role="alert" className="text-sm text-destructive">{review.error instanceof Error ? review.error.message : String(review.error)}</p>}
    </form> : <p className="text-sm text-text-secondary">{copy('预览未保存；保存原始文件与结果后才能记录质控审阅。', 'Unsaved preview: save the source and result before recording a QC review.')}</p>}
  </section>
}
