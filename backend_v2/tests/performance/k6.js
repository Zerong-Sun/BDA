import http from 'k6/http'
import { check } from 'k6'

export const options = {
  scenarios: {
    non_compute_api: {
      executor: 'constant-vus',
      vus: 50,
      duration: '60s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.01'],
  },
}

const base = __ENV.BDA_V2_BASE_URL
const token = __ENV.BDA_V2_ACCESS_TOKEN
const project = __ENV.BDA_V2_PROJECT_ID

export default function () {
  const response = http.get(`${base}/api/v2/projects/${project}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      traceparent: '00-00000000000000000000000000000001-0000000000000001-01',
    },
  })
  check(response, { 'resource returned': (value) => value.status === 200 })
}
