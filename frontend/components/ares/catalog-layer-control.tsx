'use client'

import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Eye, EyeOff, Info, Layers, RefreshCw, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { isHttpCogUrl } from '@/lib/api/catalog'
import type { CatalogLayer } from '@/lib/api/types'
import { cn } from '@/lib/utils'

const DISCLAIMER_TOAST_MS = 12_000

type CatalogLayerControlProps = {
  layers: CatalogLayer[]
  loading: boolean
  error: string | null
  visibleIds: Set<number>
  onToggle: (id: number) => void
  onZoomTo: (id: number) => void
  onRefresh: () => void
}

export function CatalogLayerControl({
  layers,
  loading,
  error,
  visibleIds,
  onToggle,
  onZoomTo,
  onRefresh,
}: CatalogLayerControlProps) {
  const { t } = useTranslation()
  const [disclaimerOpen, setDisclaimerOpen] = useState(false)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    if (!disclaimerOpen) return
    const timer = window.setTimeout(() => setDisclaimerOpen(false), DISCLAIMER_TOAST_MS)
    return () => window.clearTimeout(timer)
  }, [disclaimerOpen])

  return (
    <>
      <div className="w-64 overflow-hidden rounded-lg border border-border bg-card shadow-md">
        <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <Layers className="size-4 shrink-0 text-primary" />
            {t('map.catalog')}
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="cursor-pointer rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
            title={t('map.catalogRefresh')}
            aria-label={t('map.catalogRefresh')}
          >
            <RefreshCw className={cn('size-3.5', loading && 'animate-spin')} />
          </button>
        </div>

        <div className="max-h-56 overflow-y-auto">
          {error ? (
            <p className="px-3 py-3 text-xs text-destructive">{error}</p>
          ) : loading && layers.length === 0 ? (
            <p className="px-3 py-3 text-xs text-muted-foreground">{t('map.catalogLoading')}</p>
          ) : layers.length === 0 ? (
            <p className="px-3 py-3 text-xs text-muted-foreground">{t('map.catalogEmpty')}</p>
          ) : (
            <ul className="divide-y divide-border">
              {layers.map((layer) => {
                const visible = visibleIds.has(layer.id)
                const httpOk = isHttpCogUrl(layer.cog_url)
                return (
                  <li key={layer.id}>
                    <div
                      onDoubleClick={() => onZoomTo(layer.id)}
                      title={t('map.catalogZoomHint')}
                      className={cn(
                        'flex w-full cursor-pointer items-start gap-2 px-3 py-2 transition-colors hover:bg-secondary/80',
                        visible && 'bg-secondary/40',
                      )}
                    >
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          onToggle(layer.id)
                        }}
                        className="mt-0.5 cursor-pointer rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                        title={visible ? t('map.catalogHide') : t('map.catalogShow')}
                        aria-label={visible ? t('map.catalogHide') : t('map.catalogShow')}
                        aria-pressed={visible}
                      >
                        {visible ? (
                          <Eye className="size-3.5 text-primary" />
                        ) : (
                          <EyeOff className="size-3.5" />
                        )}
                      </button>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start gap-1">
                          <span className="block min-w-0 flex-1 truncate text-sm font-medium text-foreground">
                            {layer.nombre_capa}
                          </span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation()
                              setDisclaimerOpen(true)
                            }}
                            className="mt-0.5 shrink-0 cursor-pointer rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                            title={t('map.catalogDisclaimerToggle')}
                            aria-label={t('map.catalogDisclaimerToggle')}
                          >
                            <Info className="size-3.5" />
                          </button>
                        </div>
                        {!httpOk && (
                          <span className="mt-0.5 block text-[10px] leading-tight text-amber-700 dark:text-amber-400">
                            {t('map.catalogNoHttp')}
                          </span>
                        )}
                      </div>
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>

      {mounted &&
        disclaimerOpen &&
        createPortal(
          <div
            role="status"
            aria-live="polite"
            className="fixed bottom-4 right-4 z-[2000] w-[min(22rem,calc(100vw-2rem))] rounded-lg border border-border bg-card p-3 shadow-lg"
          >
            <div className="mb-1.5 flex items-start justify-between gap-2">
              <p className="text-xs font-semibold text-foreground">
                {t('map.catalogDisclaimerTitle')}
              </p>
              <button
                type="button"
                onClick={() => setDisclaimerOpen(false)}
                className="shrink-0 cursor-pointer rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                title={t('map.catalogDisclaimerClose')}
                aria-label={t('map.catalogDisclaimerClose')}
              >
                <X className="size-3.5" />
              </button>
            </div>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {t('map.catalogDisclaimer')}
            </p>
          </div>,
          document.body,
        )}
    </>
  )
}
