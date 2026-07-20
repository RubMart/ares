'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { Map as MapIcon, Satellite } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { CatalogLayerControl } from '@/components/ares/catalog-layer-control'
import { InterpretationModal } from '@/components/ares/interpretation-modal'
import {
  ResultFiltersControl,
  type MetricRange,
  type ResultFilterBounds,
  type ResultFilterState,
} from '@/components/ares/result-filters-control'
import { SearchPanel } from '@/components/ares/search-panel'
import { useApiStatus } from '@/hooks/use-api-status'
import { useCatalog } from '@/hooks/use-catalog'
import { ApiError } from '@/lib/api/client'
import { featuresToSearchResults, searchDetections } from '@/lib/api/search'
import type {
  ReferenceFeatureCollection,
  SearchMetadata,
  SearchResult,
} from '@/lib/api/types'
import {
  CONFIDENCE_LEVELS,
  confidenceLevel,
  type ConfidenceLevel,
} from '@/lib/map/confidence'
import { MAX_QUERY_LENGTH } from '@/lib/search-limits'
import { cn } from '@/lib/utils'

const MapView = dynamic(() => import('@/components/ares/map-view'), {
  ssr: false,
  loading: () => <MapLoading />,
})

function MapLoading() {
  const { t } = useTranslation()
  return (
    <div className="flex h-full w-full items-center justify-center bg-muted text-sm text-muted-foreground">
      {t('map.loading')}
    </div>
  )
}

type Basemap = 'streets' | 'satellite'

const DEFAULT_BOUNDS: ResultFilterBounds = {
  similarity: { min: 0, max: 1 },
}

const ALL_CONFIDENCE_LEVELS = new Set<ConfidenceLevel>(CONFIDENCE_LEVELS)

function computeBounds(rows: SearchResult[]): ResultFilterBounds {
  const bounds: ResultFilterBounds = {
    similarity: { min: Infinity, max: -Infinity },
  }

  for (const row of rows) {
    bounds.similarity.min = Math.min(bounds.similarity.min, row.similarity)
    bounds.similarity.max = Math.max(bounds.similarity.max, row.similarity)
  }

  if (!Number.isFinite(bounds.similarity.min)) {
    bounds.similarity = { ...DEFAULT_BOUNDS.similarity }
  }
  if (bounds.similarity.min === bounds.similarity.max) {
    bounds.similarity.max = Math.min(1, bounds.similarity.min + 0.01)
  }

  return bounds
}

function buildFiltersFromResults(rows: SearchResult[]): {
  bounds: ResultFilterBounds
  filters: ResultFilterState
} {
  const bounds = computeBounds(rows)
  return {
    bounds,
    filters: {
      enabledLayers: new Set(rows.map((r) => r.layer)),
      enabledClasses: new Set(rows.map((r) => r.claseYolo)),
      confidenceLevels: new Set(ALL_CONFIDENCE_LEVELS),
      similarity: { ...bounds.similarity },
    },
  }
}

function passesFilters(row: SearchResult, filters: ResultFilterState) {
  if (!filters.enabledLayers.has(row.layer)) return false
  if (!filters.enabledClasses.has(row.claseYolo)) return false
  if (!filters.confidenceLevels.has(confidenceLevel(row.confianza))) return false
  if (row.similarity < filters.similarity.min || row.similarity > filters.similarity.max) {
    return false
  }
  return true
}

function emptyResultFilters(bounds: ResultFilterBounds = DEFAULT_BOUNDS): ResultFilterState {
  return {
    enabledLayers: new Set(),
    enabledClasses: new Set(),
    confidenceLevels: new Set(ALL_CONFIDENCE_LEVELS),
    similarity: { ...bounds.similarity },
  }
}

export default function Page() {
  const { t } = useTranslation()
  const api = useApiStatus()
  const catalog = useCatalog()
  const wasOnlineRef = useRef(false)
  const hadOfflineRef = useRef(false)
  const searchAbortRef = useRef<AbortController | null>(null)

  const [query, setQuery] = useState('')
  const [count, setCount] = useState(50)
  const [filterResults, setFilterResults] = useState(false)

  const [loading, setLoading] = useState(false)
  const [hasSearched, setHasSearched] = useState(false)
  const [rawResults, setRawResults] = useState<SearchResult[]>([])
  const [filterBounds, setFilterBounds] = useState<ResultFilterBounds>(DEFAULT_BOUNDS)
  const [resultFilters, setResultFilters] = useState<ResultFilterState>(emptyResultFilters)
  const [metadata, setMetadata] = useState<SearchMetadata | null>(null)
  const [referenceFeatures, setReferenceFeatures] =
    useState<ReferenceFeatureCollection | null>(null)
  const [activeQuery, setActiveQuery] = useState('')
  const [searchError, setSearchError] = useState<string | null>(null)
  const [infoOpen, setInfoOpen] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showDetectionDetails, setShowDetectionDetails] = useState(false)
  const [basemap, setBasemap] = useState<Basemap>('streets')
  const [fitSelectionRequest, setFitSelectionRequest] = useState<{
    id: string
    token: number
  } | null>(null)
  const [fitCatalogRequest, setFitCatalogRequest] = useState<{
    id: number
    token: number
  } | null>(null)

  const handleZoomToCatalogLayer = useCallback((id: number) => {
    setFitCatalogRequest({ id, token: Date.now() })
  }, [])

  useEffect(() => {
    if (api.status === 'offline') {
      hadOfflineRef.current = true
      wasOnlineRef.current = false
      return
    }
    const online = api.status === 'online' || api.status === 'degraded'
    if (online && hadOfflineRef.current && !wasOnlineRef.current) {
      catalog.refresh()
    }
    if (online) wasOnlineRef.current = true
  }, [api.status, catalog.refresh])

  useEffect(() => {
    return () => {
      searchAbortRef.current?.abort()
    }
  }, [])

  const visibleResults = useMemo(
    () =>
      [...rawResults]
        .filter((row) => passesFilters(row, resultFilters))
        .sort((a, b) => b.confianza - a.confianza),
    [rawResults, resultFilters],
  )

  const layerCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of rawResults) {
      counts.set(row.layer, (counts.get(row.layer) || 0) + 1)
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }, [rawResults])

  const classCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of rawResults) {
      counts.set(row.claseYolo, (counts.get(row.claseYolo) || 0) + 1)
    }
    return [...counts.entries()]
      .map(([name, count]) => ({ name, count }))
      .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name))
  }, [rawResults])

  // Drop selection quietly when filters hide the selected row (no map camera move).
  useEffect(() => {
    if (selectedId && !visibleResults.some((r) => r.id === selectedId)) {
      setSelectedId(null)
      setShowDetectionDetails(false)
    }
  }, [visibleResults, selectedId])

  const selectFromTable = useCallback((id: string | null) => {
    setSelectedId(id)
    setShowDetectionDetails(false)
    if (id) setFitSelectionRequest({ id, token: Date.now() })
  }, [])

  const selectFromMap = useCallback((id: string | null) => {
    setSelectedId(id)
    setShowDetectionDetails(id != null)
  }, [])

  const handleClearResults = useCallback(() => {
    searchAbortRef.current?.abort()
    searchAbortRef.current = null
    setLoading(false)
    setSelectedId(null)
    setShowDetectionDetails(false)
    setSearchError(null)
    setInfoOpen(false)
    setRawResults([])
    setFilterBounds(DEFAULT_BOUNDS)
    setResultFilters(emptyResultFilters())
    setMetadata(null)
    setReferenceFeatures(null)
    setActiveQuery('')
    setHasSearched(false)
    setFitSelectionRequest(null)
  }, [])

  const handleSearch = useCallback(async () => {
    const q = query.trim()
    if (!q) {
      setSearchError(t('search.emptyQuery'))
      return
    }
    if (q.length > MAX_QUERY_LENGTH) {
      setSearchError(t('search.queryTooLong', { max: MAX_QUERY_LENGTH }))
      return
    }
    if (api.status === 'offline') {
      setSearchError(t('search.apiOffline'))
      return
    }

    searchAbortRef.current?.abort()
    const controller = new AbortController()
    searchAbortRef.current = controller

    setLoading(true)
    setSelectedId(null)
    setShowDetectionDetails(false)
    setSearchError(null)
    setInfoOpen(false)
    // Clear previous hits immediately so the map/table don't keep stale data.
    setRawResults([])
    setFilterBounds(DEFAULT_BOUNDS)
    setResultFilters(emptyResultFilters())
    setMetadata(null)
    setReferenceFeatures(null)
    setFitSelectionRequest(null)

    try {
      const response = await searchDetections({
        query: q,
        top_k: count,
        min_confidence: filterResults ? 0.7 : 0.0,
        signal: controller.signal,
      })

      if (controller.signal.aborted) return

      const mapped = featuresToSearchResults(response.features ?? [])
      const ranked = [...mapped].sort((a, b) => b.confianza - a.confianza)
      const top = ranked[0] ?? null
      const next = buildFiltersFromResults(mapped)
      setRawResults(mapped)
      setFilterBounds(next.bounds)
      setResultFilters(next.filters)
      setMetadata(response.metadata ?? null)
      setReferenceFeatures(response.metadata?.reference_features ?? null)
      setActiveQuery(q)
      setHasSearched(true)
      if (top) {
        setSelectedId(top.id)
        setShowDetectionDetails(false)
        setFitSelectionRequest({ id: top.id, token: Date.now() })
      }
    } catch (error) {
      if (controller.signal.aborted) return
      if (error instanceof ApiError) {
        setSearchError(error.message)
      } else {
        setSearchError(error instanceof Error ? error.message : String(error))
      }
      setRawResults([])
      setFilterBounds(DEFAULT_BOUNDS)
      setResultFilters(emptyResultFilters())
      setMetadata(null)
      setReferenceFeatures(null)
      setActiveQuery(q)
      setHasSearched(true)
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [query, count, filterResults, api.status, t])

  const toggleLayer = useCallback((layer: string) => {
    setResultFilters((prev) => {
      const enabledLayers = new Set(prev.enabledLayers)
      if (enabledLayers.has(layer)) enabledLayers.delete(layer)
      else enabledLayers.add(layer)
      return { ...prev, enabledLayers }
    })
  }, [])

  const enableAllLayers = useCallback(() => {
    setResultFilters((prev) => ({
      ...prev,
      enabledLayers: new Set(layerCounts.map((c) => c.name)),
    }))
  }, [layerCounts])

  const disableAllLayers = useCallback(() => {
    setResultFilters((prev) => ({
      ...prev,
      enabledLayers: new Set(),
    }))
  }, [])

  const toggleClass = useCallback((className: string) => {
    setResultFilters((prev) => {
      const enabledClasses = new Set(prev.enabledClasses)
      if (enabledClasses.has(className)) enabledClasses.delete(className)
      else enabledClasses.add(className)
      return { ...prev, enabledClasses }
    })
  }, [])

  const enableAllClasses = useCallback(() => {
    setResultFilters((prev) => ({
      ...prev,
      enabledClasses: new Set(classCounts.map((c) => c.name)),
    }))
  }, [classCounts])

  const disableAllClasses = useCallback(() => {
    setResultFilters((prev) => ({
      ...prev,
      enabledClasses: new Set(),
    }))
  }, [])

  const setConfidenceLevel = useCallback((level: ConfidenceLevel) => {
    setResultFilters((prev) => {
      const confidenceLevels = new Set(prev.confidenceLevels)
      if (confidenceLevels.has(level)) {
        // Keep at least one level selected so the map doesn't go blank by accident.
        if (confidenceLevels.size <= 1) return prev
        confidenceLevels.delete(level)
      } else {
        confidenceLevels.add(level)
      }
      return { ...prev, confidenceLevels }
    })
  }, [])

  const setSimilarity = useCallback((range: MetricRange) => {
    setResultFilters((prev) => ({ ...prev, similarity: range }))
  }, [])

  return (
    <main className="flex h-screen w-full overflow-hidden bg-background">
      <div className="w-full max-w-md shrink-0 md:w-[26rem]">
        <SearchPanel
          query={query}
          setQuery={setQuery}
          count={count}
          setCount={setCount}
          filterResults={filterResults}
          setFilterResults={setFilterResults}
          onSearch={handleSearch}
          onClearResults={handleClearResults}
          loading={loading}
          hasSearched={hasSearched}
          results={visibleResults}
          selectedId={selectedId}
          onSelect={selectFromTable}
          activeQuery={activeQuery}
          searchError={searchError}
          unfilteredCount={rawResults.length}
          onMoreInfo={() => setInfoOpen(true)}
          moreInfoDisabled={!metadata}
          apiStatus={api.status}
          apiDetail={api.detail}
          onApiRecheck={api.check}
        />
      </div>

      <div className="relative hidden h-full min-h-0 flex-1 md:block">
        <div className="absolute inset-0">
          <MapView
            results={visibleResults}
            selectedId={selectedId}
            onSelect={selectFromMap}
            showDetectionDetails={showDetectionDetails}
            basemap={basemap}
            catalogLayers={catalog.layers}
            visibleCatalogIds={catalog.visibleIds}
            fitCatalogRequest={fitCatalogRequest}
            fitSelectionRequest={fitSelectionRequest}
            referenceFeatures={referenceFeatures}
          />
        </div>

        <div className="absolute right-4 top-4 z-[1000] flex flex-col items-end gap-2">
          <div className="flex overflow-hidden rounded-lg border border-border bg-card shadow-md">
            <BasemapButton
              active={basemap === 'streets'}
              onClick={() => setBasemap('streets')}
              icon={<MapIcon className="size-4" />}
              label={t('map.streets')}
            />
            <BasemapButton
              active={basemap === 'satellite'}
              onClick={() => setBasemap('satellite')}
              icon={<Satellite className="size-4" />}
              label={t('map.satellite')}
            />
          </div>

          <CatalogLayerControl
            layers={catalog.layers}
            loading={catalog.loading}
            error={catalog.error}
            visibleIds={catalog.visibleIds}
            onToggle={catalog.toggleVisibility}
            onZoomTo={handleZoomToCatalogLayer}
            onRefresh={catalog.refresh}
          />

          {hasSearched && rawResults.length > 0 && (
            <ResultFiltersControl
              layerCounts={layerCounts}
              classCounts={classCounts}
              bounds={filterBounds}
              filters={resultFilters}
              visibleCount={visibleResults.length}
              totalCount={rawResults.length}
              onToggleLayer={toggleLayer}
              onEnableAllLayers={enableAllLayers}
              onDisableAllLayers={disableAllLayers}
              onToggleClass={toggleClass}
              onEnableAllClasses={enableAllClasses}
              onDisableAllClasses={disableAllClasses}
              onToggleConfidenceLevel={setConfidenceLevel}
              onSimilarityChange={setSimilarity}
            />
          )}
        </div>

        {hasSearched && !loading && (
          <div className="absolute left-4 top-4 z-[1000] rounded-lg border border-border bg-card px-3 py-2 text-sm shadow-md">
            <span className="font-semibold text-primary">{visibleResults.length}</span>{' '}
            <span className="text-muted-foreground">{t('map.featuresPlotted')}</span>
          </div>
        )}

        {hasSearched && !loading && visibleResults.length > 0 && (
          <div className="absolute bottom-16 left-4 z-[1000] rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
            <div className="mb-1 font-semibold text-foreground">{t('map.confidence')}</div>
            <div className="flex flex-col gap-1">
              <LegendItem color="#0e7490" label={t('map.confidenceHigh')} />
              <LegendItem color="#d97706" label={t('map.confidenceMedium')} />
              <LegendItem color="#64748b" label={t('map.confidenceLow')} />
            </div>
          </div>
        )}
      </div>

      <InterpretationModal
        open={infoOpen}
        onOpenChange={setInfoOpen}
        metadata={metadata}
      />
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
