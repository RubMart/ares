'use client'

import { useEffect, useId, useRef, useState } from 'react'
import { ChevronDown, Download } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { downloadSearchResultsGeoJson } from '@/lib/geojson/download'
import type { SearchResult } from '@/lib/api/types'
import { cn } from '@/lib/utils'

type DownloadGeoJsonMenuProps = {
  allResults: SearchResult[]
  filteredResults: SearchResult[]
  query: string
  className?: string
}

export function DownloadGeoJsonMenu({
  allResults,
  filteredResults,
  query,
  className,
}: DownloadGeoJsonMenuProps) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const menuId = useId()
  const disabled = allResults.length === 0

  useEffect(() => {
    if (!open) return

    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('pointerdown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  function download(scope: 'all' | 'filtered') {
    const rows = scope === 'all' ? allResults : filteredResults
    downloadSearchResultsGeoJson(rows, query, scope)
    setOpen(false)
  }

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={disabled}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={open ? menuId : undefined}
        onClick={() => setOpen((v) => !v)}
        className="shrink-0"
      >
        <Download className="size-3.5" />
        {t('results.download')}
        <ChevronDown
          className={cn(
            'size-3.5 opacity-70 transition-transform',
            open && 'rotate-180',
          )}
        />
      </Button>

      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={t('results.downloadMenu')}
          className="absolute right-0 z-30 mt-1.5 w-56 overflow-hidden rounded-lg border border-border bg-card py-1 shadow-md"
        >
          <p className="px-3 pb-1 pt-1.5 text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
            {t('results.downloadMenu')}
          </p>
          <MenuOption
            label={t('results.downloadAll')}
            count={allResults.length}
            disabled={allResults.length === 0}
            onSelect={() => download('all')}
          />
          <MenuOption
            label={t('results.downloadFiltered')}
            count={filteredResults.length}
            disabled={filteredResults.length === 0}
            onSelect={() => download('filtered')}
          />
        </div>
      )}
    </div>
  )
}

function MenuOption({
  label,
  count,
  disabled,
  onSelect,
}: {
  label: string
  count: number
  disabled: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      role="menuitem"
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        'flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors',
        disabled
          ? 'cursor-not-allowed text-muted-foreground/50'
          : 'text-foreground hover:bg-secondary',
      )}
    >
      <span>{label}</span>
      <span className="tabular-nums text-xs text-muted-foreground">{count}</span>
    </button>
  )
}
