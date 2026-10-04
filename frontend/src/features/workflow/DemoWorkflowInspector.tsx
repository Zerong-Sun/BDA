import { Alert, AlertDescription } from '../../components/reui/alert'
import { Frame, FrameHeader, FramePanel, FrameTitle } from '../../components/reui/frame'
import { ScrollArea } from '../../components/ui/scroll-area'
import { useI18n } from '../../lib/i18n'
import type { DemoWorkflowStep } from './demoWorkflow'

export function DemoWorkflowInspector({ selectedStep, stepCount }: { selectedStep?: DemoWorkflowStep; stepCount: number }) {
  const { language } = useI18n()
  const zh = language === 'zh'
  return (
    <Frame variant="inverse" spacing="xs" className="h-full min-h-[32rem] w-full shrink-0 2xl:min-h-0" data-testid="demo-workflow-inspector">
      <FrameHeader><FrameTitle>{zh ? '演示步骤详情' : 'Example step details'}</FrameTitle></FrameHeader>
      <FramePanel className="min-h-0 overflow-hidden">
        <ScrollArea className="h-full">
          <div className="space-y-4 pr-3">
            <Alert><AlertDescription>{zh
              ? '这是只读流程示例，未执行计算，也不代表本项目的计算或实验结果。'
              : 'This read-only example has not executed. It does not represent this project’s computational or experimental results.'}</AlertDescription></Alert>
            {selectedStep ? <>
              <div><h3 className="text-sm font-semibold">{selectedStep.node.data.label}</h3>
                <p className="mt-1 text-sm text-text-secondary">{selectedStep.node.data.description}</p></div>
              <dl className="grid gap-3 text-sm">
                {[[zh ? '输入' : 'Inputs', selectedStep.inputs], [zh ? '预期输出' : 'Expected outputs', selectedStep.outputs], [zh ? '检查项' : 'Checks', selectedStep.checks]].map(([label, value]) => (
                  <div key={label}><dt className="font-medium">{label}</dt><dd className="mt-1 leading-6 text-text-secondary">{value}</dd></div>
                ))}
              </dl>
            </> : <p className="text-sm text-text-secondary">{zh
              ? `${stepCount} 个演示步骤。选择画布节点，查看输入、预期输出和检查项。`
              : `${stepCount} example steps. Select a canvas node to inspect inputs, expected outputs and checks.`}</p>}
          </div>
        </ScrollArea>
      </FramePanel>
    </Frame>
  )
}
