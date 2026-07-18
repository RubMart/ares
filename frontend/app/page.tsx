'use client'

import { useCallback, useMemo, useState } from 'react'
import dynamic from 'next/dynamic'
import { Map as MapIcon, Satellite } from 'lucide-react'
import { SearchPanel } from '@/components/ares/search-panel'
import { runSemanticSearch, type SearchResult } from '@/lib/search'
import { cn } from '@/lib/utils'

const MapView = dynamic(() => import('@/components/ares/map-view'), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center bg-muted text-sm text-muted-foreground">
      Loading map…
    </div>
  ),
})

type Basemap = 'streets' | 'satellite'

export default function Page() {
  const [query, setQuery] = useState('')
  const [count, setCount] = useState(50)
  const [clustering, setClustering] = useState(false)
  const [filterResults, setFilterResults] = useState(true)

  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [rawResults, setRawResults] = useState<SearchResult[]>([])
  const [activeQuery, setActiveQuery] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [basemap, setBasemap] = useState<Basemap>('streets')

  const handleSearch = useCallback(() => {
    setLoading(true)
    setSelectedId(null)
    const q = query
    // Simulate an async semantic search request.
    setTimeout(() => {
      const results = runSemanticSearch(q, count)
      setRawResults(results)
      setActiveQuery(q)
      setHasSearched(true)
      setLoading(false)
    }, 650)
  }, [query, count])

  const results = useMemo(
    () => (filterResults ? rawResults.filter((r) => r.score >= 0.7) : rawResults),
    [rawResults, filterResults],
  )

  return (
    <main className="flex h-screen w-full overflow-hidden bg-background">
      {/* Left: search */}
      <div className="w-full max-w-md shrink-0 md:w-[26rem]">
        <SearchPanel
          query={query}
          setQuery={setQuery}
          count={count}
          setCount={setCount}
          clustering={clustering}
          setClustering={setClustering}
          filterResults={filterResults}
          setFilterResults={setFilterResults}
          onSearch={handleSearch}
          loading={loading}
          hasSearched={hasSearched}
          results={results}
          selectedId={selectedId}
          onSelect={setSelectedId}
          activeQuery={activeQuery}
        />
      </div>

      {/* Right: map */}
      <div className="relative hidden h-full min-h-0 flex-1 md:block">
        <div className="absolute inset-0">
          <MapView
            results={results}
            selectedId={selectedId}
            onSelect={setSelectedId}
            basemap={basemap}
          />
        </div>

        {/* Basemap switcher */}
        <div className="absolute right-4 top-4 z-[1000] flex overflow-hidden rounded-lg border border-border bg-card shadow-md">
          <BasemapButton
            active={basemap === 'streets'}
            onClick={() => setBasemap('streets')}
            icon={<MapIcon className="size-4" />}
            label="Streets"
          />
          <BasemapButton
            active={basemap === 'satellite'}
            onClick={() => setBasemap('satellite')}
            icon={<Satellite className="size-4" />}
            label="Satellite"
          />
        </div>

        {/* Result count badge */}
        {hasSearched && (
          <div className="absolute left-4 top-4 z-[1000] rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-md">
            <span className="font-semibold text-primary">{results.length}</span>{' '}
            <span className="text-muted-foreground">features plotted</span>
          </div>
        )}

        {/* Legend */}
        {hasSearched && results.length > 0 && (
          <div className="absolute bottom-6 left-4 z-[1000] rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
            <div className="mb-1 font-semibold text-foreground">Confidence</div>
            <div className="flex flex-col gap-1">
              <LegendItem color="#0e7490" label="High (85%+)" />
              <LegendItem color="#d97706" label="Medium (70–85%)" />
              <LegendItem color="#64748b" label="Low (under 70%)" />
            </div>
          </div>
        )}
      </div>
    </main>
  )
}

function BasemapButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean
  onClick: () => void
  icon: React.ReactNode
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex items-center gap-1.5 px-3 py-2 text-sm font-medium transition-colors',
        active ? 'bg-primary text-primary-foreground' : 'text-foreground hover:bg-secondary',
      )}
    >
      {icon}
      {label}
    </button>
  )
}

function LegendItem({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2 text-muted-foreground">
      <span className="inline-block size-3 rounded-full" style={{ backgroundColor: color }} />
      <span>{label}</span>
    </div>
  )
}
