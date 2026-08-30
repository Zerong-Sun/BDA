import { readinessApiV2HealthReadyGet } from './generated/sdk.gen'
import './generatedTransport'

export function getHealth() {
  return readinessApiV2HealthReadyGet<true>({ throwOnError: true }).then(({ data }) => data)
}
