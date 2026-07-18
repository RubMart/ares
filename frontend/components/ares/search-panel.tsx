'use client'

import { Search, Loader2, Layers, SlidersHorizontal } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { ResultsTable } from '@/components/ares/results-table'
import type { SearchResult } from '@/lib/search'
import { cn } from '@/lib/utils'

type SearchPanelProps = {
  query: string
  setQuery: (v: string) => void
  count: number
  setCount: (v: number) => void
  clustering: boolean
  setClustering: (v: boolean) => void
  filterResults: boolean
  setFilterResults: (v: boolean) => void
  onSearch: () => void
  loading: boolean
  hasSearched: boolean
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string) => void
  activeQuery: string
}

export function SearchPanel(props: SearchPanelProps) {
  const {
    query,
    setQuery,
    count,
    setCount,
    clustering,
    setClustering,
    filterResults,
    setFilterResults,
    onSearch,
    loading,
    hasSearched,
    results,
    selectedId,
    onSelect,
    activeQuery,
  } = props

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' && !e.nativeEvent.isComposing && e.keyCode !== 229) {
      onSearch()
    }
  }

  return (
    <aside className="flex h-full w-full flex-col overflow-y-auto border-r border-border bg-sidebar">
      <div className="flex flex-col gap-6 p-6">
        {/* Brand */}
        <header>
          <div className="flex items-baseline gap-2.5">
            <h1 className="font-display text-4xl font-bold tracking-[0.18em] text-primary">
              ARES
            </h1>
          </div>
          <p className="mt-1.5 text-[0.7rem] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            AI Retrieval of Entities in Space
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Búsqueda semántica sobre detecciones aéreas
          </p>
        </header>

        {/* Search input */}
        <div className="flex flex-col gap-2">
          <label htmlFor="ares-query" className="text-sm font-medium text-foreground">
            Consulta
          </label>
          <input
            id="ares-query"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="piscinas, coches rojos, paneles solares, coches cerca de rotonda…"
            className="w-full rounded-lg border border-input bg-card px-3 py-2.5 text-sm text-foreground shadow-sm outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-ring/30"
          />
        </div>

        {/* Number of results slider */}
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label htmlFor="ares-count" className="text-sm font-medium text-foreground">
              Number of results
            </label>
            <span className="font-mono text-sm font-semibold text-primary">{count}</span>
          </div>
          <input
            id="ares-count"
            type="range"
            min={20}
            max={100}
            step={1}
            value={count}
            onChange={(e) => setCount(Number(e.target.value))}
            className="ares-slider w-full"
            aria-valuemin={20}
            aria-valuemax={100}
            aria-valuenow={count}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>20</span>
            <span>100</span>
          </div>
        </div>

        {/* Toggles */}
        <div className="flex flex-col gap-3">
          <ToggleRow
            icon={<Layers className="size-4" />}
            label="Enable clustering"
            checked={clustering}
            onChange={setClustering}
          />
          <ToggleRow
            icon={<SlidersHorizontal className="size-4" />}
            label="Filter low-confidence results"
            checked={filterResults}
            onChange={setFilterResults}
          />
        </div>

        {/* Search button */}
        <Button
          onClick={onSearch}
          disabled={loading}
          className="h-11 w-full text-base font-semibold"
          size="lg"
        >
          {loading ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Searching…
            </>
          ) : (
            <>
              <Search className="size-4" />
              Search
            </>
          )}
        </Button>

        {/* Results */}
        {hasSearched ? (
          results.length > 0 ? (
            <ResultsTable
              results={results}
              selectedId={selectedId}
              onSelect={onSelect}
              query={activeQuery}
            />
          ) : (
            <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
              No results matched your query.
            </p>
          )
        ) : (
          <p className="rounded-lg border border-dashed border-border py-8 text-center text-sm text-muted-foreground">
            Run a search to see ranked results here.
          </p>
        )}
      </div>
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
