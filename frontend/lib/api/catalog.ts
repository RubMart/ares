import { apiGet, type ApiGetOptions } from '@/lib/api/client'
import type { CatalogLayer } from '@/lib/api/types'

export function isHttpCogUrl(url: string | null | undefined): boolean {
  return typeof url === 'string' && /^https?:\/\//i.test(url.trim())
}

/**
 * On Windows, `localhost` often resolves to IPv6 (::1) first. Servers bound only
 * to IPv4 then fail with TypeError: Failed to fetch. Prefer 127.0.0.1 for local URLs.
 */
export function preferIpv4Localhost(url: string): string {
  try {
    const parsed = new URL(url.trim())
    if (parsed.hostname === 'localhost') {
      parsed.hostname = '127.0.0.1'
      return parsed.toString()
    }
  } catch {
    // keep original
  }
  return url.trim()
}

export async function fetchCatalog(
  options?: ApiGetOptions,
): Promise<CatalogLayer[]> {
  return apiGet<CatalogLayer[]>('/catalog', options)
}
