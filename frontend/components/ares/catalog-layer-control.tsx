'use client'

import { Eye, EyeOff, Layers, RefreshCw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { isHttpCogUrl } from '@/lib/api/catalog'
import type { CatalogLayer } from '@/lib/api/types'
import { cn } from '@/lib/utils'

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

  return (
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
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground disabled:opacity-50"
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
                      'flex w-full items-start gap-2 px-3 py-2 transition-colors hover:bg-secondary/80',
                      visible && 'bg-secondary/40',
                    )}
                  >
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation()
                        onToggle(layer.id)
                      }}
                      className="mt-0.5 rounded-md p-0.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
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
                      <span className="block truncate text-sm font-medium text-foreground">
                        {layer.nombre_capa}
                      </span>
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
  )
}
