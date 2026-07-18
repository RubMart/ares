'use client'

import { useState } from 'react'
import { Search, Loader2, SlidersHorizontal, Eraser, CircleHelp } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ApiStatusBadge } from '@/components/ares/api-status-badge'
import { SearchHelpModal } from '@/components/ares/search-help-modal'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { LanguageSwitcher } from '@/components/ares/language-switcher'
import { ResultsTable } from '@/components/ares/results-table'
import type { ApiStatus } from '@/hooks/use-api-status'
import type { SearchResult } from '@/lib/api/types'
import { MAX_QUERY_LENGTH } from '@/lib/search-limits'
import { cn } from '@/lib/utils'

type SearchPanelProps = {
  query: string
  setQuery: (v: string) => void
  count: number
  setCount: (v: number) => void
  filterResults: boolean
  setFilterResults: (v: boolean) => void
  onSearch: () => void
  onClearResults: () => void
  loading: boolean
  hasSearched: boolean
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  activeQuery: string
  searchError: string | null
  unfilteredCount: number
  onMoreInfo: () => void
  moreInfoDisabled: boolean
  apiStatus: ApiStatus
  apiDetail?: string | null
  onApiRecheck: () => void
}

export function SearchPanel(props: SearchPanelProps) {
  const { t, i18n } = useTranslation()
  const [helpOpen, setHelpOpen] = useState(false)
  const examples = t('search.examples', { returnObjects: true })
  const exampleQueries = Array.isArray(examples) ? (examples as string[]) : []
  const {
    query,
    setQuery,
    count,
    setCount,
    filterResults,
    setFilterResults,
    onSearch,
    onClearResults,
    loading,
    hasSearched,
    results,
    selectedId,
    onSelect,
    activeQuery,
    searchError,
    unfilteredCount,
    onMoreInfo,
    moreInfoDisabled,
    apiStatus,
    apiDetail,
    onApiRecheck,
  } = props

  const canClear = hasSearched || results.length > 0 || unfilteredCount > 0

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.keyCode !== 229) {
      onSearch()
    }
  }

  return (
    <aside className="flex h-full w-full flex-col overflow-y-auto border-r border-border bg-sidebar">
      <div className="flex flex-col gap-6 p-6">
        <header>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <img
                src="/icon.svg"
                alt=""
                width={40}
                height={40}
                className="size-10 shrink-0"
              />
              <h1 className="font-display text-4xl font-bold tracking-[0.18em] text-primary">
                ARES
              </h1>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <LanguageSwitcher />
              <ApiStatusBadge
                status={apiStatus}
                detail={apiDetail}
                onRecheck={onApiRecheck}
              />
            </div>
          </div>
          <p className="mt-1.5 text-[0.7rem] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {t('brand.tagline')}
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {t('brand.subtitle')}
          </p>
        </header>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <label htmlFor="ares-query" className="text-sm font-medium text-foreground">
              {t('search.queryLabel')}
            </label>
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium text-primary transition-colors hover:bg-accent"
              aria-label={t('search.queryHelp')}
              title={t('search.queryHelp')}
            >
              <CircleHelp className="size-3.5" />
              {t('search.queryHelp')}
            </button>
          </div>
          <input
            id="ares-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('search.queryPlaceholder')}
            autoComplete="off"
            maxLength={MAX_QUERY_LENGTH}
            className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm text-foreground shadow-sm outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring/30"
          />
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">{t('search.examplesLabel')}</span>
            {exampleQueries.map((example) => (
              <button
                key={`${i18n.language}-${example}`}
                type="button"
                onClick={() => setQuery(example)}
                className="rounded-full border border-border bg-card px-2.5 py-0.5 text-xs text-primary transition-colors hover:border-primary hover:bg-accent"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label htmlFor="ares-count" className="text-sm font-medium text-foreground">
              {t('search.resultCount')}
            </label>
            <span className="rounded-md bg-secondary px-2 py-0.5 font-mono text-sm font-semibold tabular-nums text-primary">
              {count}
            </span>
          </div>
          <Slider
            id="ares-count"
            min={20}
            max={100}
            step={1}
            value={[count]}
            onValueChange={(next) => {
              const value = Array.isArray(next) ? next[0] : next
              if (typeof value === 'number') setCount(value)
            }}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>20</span>
            <span>100</span>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <ToggleRow
            icon={<SlidersHorizontal className="size-4" />}
            label={t('search.filterLowConfidence')}
            checked={filterResults}
            onChange={setFilterResults}
          />
        </div>

        <div className="flex gap-2">
          <Button
            onClick={onSearch}
            disabled={loading}
            className="h-11 flex-1 text-base font-semibold"
            size="lg"
          >
            {loading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                {t('search.searching')}
              </>
            ) : (
              <>
                <Search className="size-4" />
                {t('search.search')}
              </>
            )}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            className="h-11 shrink-0 gap-1.5 px-3"
            onClick={onClearResults}
            disabled={loading || !canClear}
            title={t('search.clearResults')}
            aria-label={t('search.clearResults')}
          >
            <Eraser className="size-4" />
            <span className="hidden sm:inline">{t('search.clearResults')}</span>
          </Button>
        </div>

        {searchError && (
          <p
            role="alert"
            className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          >
            <span className="font-medium">{t('search.error')}: </span>
            {searchError}
          </p>
        )}

        {hasSearched ? (
          results.length > 0 ? (
            <ResultsTable
              results={results}
              selectedId={selectedId}
              onSelect={onSelect}
              query={activeQuery}
              onMoreInfo={onMoreInfo}
              moreInfoDisabled={moreInfoDisabled}
            />
          ) : (
            <div className="space-y-3">
              {!loading && (
                <div className="flex items-center justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={onMoreInfo}
                    disabled={moreInfoDisabled}
                  >
                    {t('results.moreInfo')}
                  </Button>
                </div>
              )}
              <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
                {loading
                  ? t('search.searching')
                  : unfilteredCount > 0
                    ? t('search.filteredOut')
                    : t('search.noResults')}
              </p>
            </div>
          )
        ) : loading ? (
          <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
            {t('search.searching')}
          </p>
        ) : (
          <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
            {t('search.runSearch')}
          </p>
        )}
      </div>

      <SearchHelpModal open={helpOpen} onOpenChange={setHelpOpen} />
    </aside>
  )
}

function ToggleRow({
  icon,
  label,
  checked,
  onChange,
}: {
  icon: React.ReactNode
  label: string
  checked: boolean
  onChange: (v: boolean) => void
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 text-sm text-foreground">
      <span className="text-muted-foreground">{icon}</span>
      <span className="flex-1">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors',
          checked ? 'bg-primary' : 'bg-input',
        )}
      >
        <span
          className={cn(
            'inline-block size-4 rounded-full bg-card shadow transition-transform',
            checked ? 'translate-x-4' : 'translate-x-0.5',
          )}
        />
      </button>
    </label>
  )
}
