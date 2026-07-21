'use client'

import { useEffect, useRef } from 'react'
import { Info } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { DownloadGeoJsonMenu } from '@/components/ares/download-geojson-menu'
import { Button } from '@/components/ui/button'
import type { SearchResult } from '@/lib/api/types'
import { confidenceColor } from '@/lib/map/confidence'
import { cn } from '@/lib/utils'

type ResultsTableProps = {
  results: SearchResult[]
  allResults: SearchResult[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  query: string
  onMoreInfo?: () => void
  moreInfoDisabled?: boolean
}

function confidenceClasses(confianza: number) {
  const color = confidenceColor(confianza)
  if (color === '#0e7490') return 'bg-primary/15 text-primary'
  if (color === '#d97706') return 'bg-amber-500/15 text-amber-700'
  return 'bg-slate-500/15 text-slate-600'
}

export function ResultsTable({
  results,
  allResults,
  selectedId,
  onSelect,
  query,
  onMoreInfo,
  moreInfoDisabled = false,
}: ResultsTableProps) {
  const { t } = useTranslation()
  const rowRefs = useRef(new Map<string, HTMLTableRowElement>())

  useEffect(() => {
    if (!selectedId) return
    const row = rowRefs.current.get(selectedId)
    row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selectedId])

  return (
    <section className="mt-6" aria-label={t('results.ariaLabel')}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-foreground">{t('results.title')}</h2>
          <p className="truncate text-xs text-muted-foreground">
            {query
              ? t('results.matchesFor', { count: results.length, query })
              : t('results.matches', { count: results.length })}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <DownloadGeoJsonMenu
            allResults={allResults}
            filteredResults={results}
            query={query}
          />
          {onMoreInfo && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onMoreInfo}
              disabled={moreInfoDisabled}
              className="shrink-0"
            >
              <Info className="size-3.5" />
              {t('results.moreInfo')}
            </Button>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <div className="max-h-[calc(100vh-22rem)] overflow-y-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="sticky top-0 z-10 bg-secondary text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-2 py-2 font-medium">
                  {t('results.id')}
                </th>
                <th scope="col" className="px-2 py-2 font-medium">
                  {t('results.class')}
                </th>
                <th scope="col" className="px-2 py-2 font-medium">
                  {t('results.confidence')}
                </th>
                <th scope="col" className="px-2 py-2 font-medium">
                  {t('results.layer')}
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => {
                const isSelected = r.id === selectedId
                const shortId = r.id.includes('/') ? r.id.split('/').pop()! : r.id
                return (
                  <tr
                    key={r.id}
                    ref={(el) => {
                      if (el) rowRefs.current.set(r.id, el)
                      else rowRefs.current.delete(r.id)
                    }}
                    onClick={() => onSelect(r.id)}
                    className={cn(
                      'cursor-pointer border-t border-border transition-colors',
                      isSelected ? 'bg-accent' : 'hover:bg-secondary',
                    )}
                  >
                    <td className="px-2 py-2 font-mono text-xs text-muted-foreground">
                      {shortId}
                    </td>
                    <td className="px-2 py-2 font-medium text-foreground">{r.claseYolo}</td>
                    <td className="px-2 py-2">
                      <span
                        className={cn(
                          'inline-block rounded-full px-2 py-0.5 text-xs font-semibold',
                          confidenceClasses(r.confianza),
                        )}
                      >
                        {(r.confianza * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td
                      className="max-w-[6rem] truncate px-2 py-2 text-xs text-muted-foreground"
                      title={r.layer}
                    >
                      {r.layer}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
