import './generatedTransport'
import { postBenchCalculationApiV2WetlabCalculationsPost } from './generated/sdk.gen'
import type { BenchCalculationResult, PostBenchCalculationApiV2WetlabCalculationsPostData } from './generated/types.gen'

export type BenchResult = BenchCalculationResult
export type BenchRequest = PostBenchCalculationApiV2WetlabCalculationsPostData['body']

export async function calculateBench(body: BenchRequest): Promise<BenchResult> {
  const result = await postBenchCalculationApiV2WetlabCalculationsPost<true>({ body, throwOnError: true })
  return result.data
}
