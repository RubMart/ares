'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHealth } from '@/lib/api/health'

export type ApiStatus = 'checking' | 'online' | 'degraded' | 'offline'

const POLL_MS = 15_000

export type ApiStatusState = {
  status: ApiStatus
  detail: string | null
  check: () => void
}

export function useApiStatus(): ApiStatusState {
  const [status, setStatus] = useState<ApiStatus>('checking')
  const [detail, setDetail] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const inFlightRef = useRef<AbortController | null>(null)

  const runCheck = useCallback(async () => {
    inFlightRef.current?.abort()
    const controller = new AbortController()
    inFlightRef.current = controller

    try {
      const health = await fetchHealth({ signal: controller.signal })
      if (!mountedRef.current || controller.signal.aborted) return
      const next: ApiStatus = health.status === 'ok' ? 'online' : 'degraded'
      setStatus(next)
      setDetail(
        next === 'degraded'
          ? `db=${health.database}, llm=${health.llm_status}`
          : null,
      )
    } catch {
      if (!mountedRef.current || controller.signal.aborted) return
      setStatus('offline')
      setDetail(null)
    }
  }, [])

  const check = useCallback(() => {
    setStatus((prev) => (prev === 'online' || prev === 'degraded' ? prev : 'checking'))
    void runCheck()
  }, [runCheck])

  useEffect(() => {
    mountedRef.current = true
    void runCheck()
    const id = window.setInterval(() => {
      void runCheck()
    }, POLL_MS)

    return () => {
      mountedRef.current = false
      inFlightRef.current?.abort()
      window.clearInterval(id)
    }
  }, [runCheck])

  return { status, detail, check }
}
