'use client'

import { useCallback, useEffect, useState } from 'react'
import { fetchCatalog } from '@/lib/api/catalog'
import type { CatalogLayer } from '@/lib/api/types'

export type CatalogState = {
  layers: CatalogLayer[]
  loading: boolean
  error: string | null
  /** Layer ids with visibility ON (default: all). */
  visibleIds: Set<number>
  toggleVisibility: (id: number) => void
  setVisible: (id: number, visible: boolean) => void
  refresh: () => void
}

export function useCatalog(): CatalogState {
  const [layers, setLayers] = useState<CatalogLayer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visibleIds, setVisibleIds] = useState<Set<number>>(new Set())
  const [reloadToken, setReloadToken] = useState(0)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const data = await fetchCatalog({ signal: controller.signal })
        if (controller.signal.aborted) return
        setLayers(data)
        setVisibleIds(new Set(data.map((layer) => layer.id)))
        setLoading(false)
      } catch (err) {
        if (controller.signal.aborted) return
        setLayers([])
        setVisibleIds(new Set())
        setError(err instanceof Error ? err.message : String(err))
        setLoading(false)
      }
    }

    void load()
    return () => {
      controller.abort()
    }
  }, [reloadToken])

  const toggleVisibility = useCallback((id: number) => {
    setVisibleIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }, [])

  const setVisible = useCallback((id: number, visible: boolean) => {
    setVisibleIds((prev) => {
      const next = new Set(prev)
      if (visible) next.add(id)
      else next.delete(id)
      return next
    })
  }, [])

  const refresh = useCallback(() => {
    setReloadToken((n) => n + 1)
  }, [])

  return {
    layers,
    loading,
    error,
    visibleIds,
    toggleVisibility,
    setVisible,
    refresh,
  }
}
