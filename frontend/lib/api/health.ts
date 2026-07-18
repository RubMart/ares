import { apiGet, type ApiGetOptions } from '@/lib/api/client'
import type { HealthResponse } from '@/lib/api/types'

const HEALTH_TIMEOUT_MS = 4_000

export async function fetchHealth(
  options: ApiGetOptions = {},
): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health', {
    ...options,
    timeoutMs: options.timeoutMs ?? HEALTH_TIMEOUT_MS,
  })
}
