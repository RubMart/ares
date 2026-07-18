'use client'

import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import OlMap from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import VectorLayer from 'ol/layer/Vector'
import WebGLTileLayer from 'ol/layer/WebGLTile'
import XYZ from 'ol/source/XYZ'
import VectorSource from 'ol/source/Vector'
import GeoTIFF from 'ol/source/GeoTIFF'
import GeoJSON from 'ol/format/GeoJSON'
import Feature from 'ol/Feature'
import { transform, transformExtent } from 'ol/proj'
import type { Coordinate } from 'ol/coordinate'
import type { ProjectionLike } from 'ol/proj'
import { Fill, Stroke, Style, Circle as CircleStyle } from 'ol/style'
import { defaults as defaultControls } from 'ol/control'
import { extend, createEmpty, isEmpty } from 'ol/extent'
import type { Extent } from 'ol/extent'
import 'ol/ol.css'

import { isHttpCogUrl, preferIpv4Localhost } from '@/lib/api/catalog'
import type {
  CatalogLayer,
  ReferenceFeatureCollection,
  SearchResult,
} from '@/lib/api/types'
import { confidenceColor, hexToRgba } from '@/lib/map/confidence'
import { olGeometryFromGeoJson } from '@/lib/map/geojson-geometry'
import { ensureProjections } from '@/lib/map/projections'
import { cn } from '@/lib/utils'

type Basemap = 'streets' | 'satellite'

type DisplayCrs = 'EPSG:4326' | 'EPSG:25830' | 'EPSG:3857'

const DISPLAY_CRS_OPTIONS: { crs: DisplayCrs; label: string }[] = [
  { crs: 'EPSG:4326', label: 'Lat Lon' },
  { crs: 'EPSG:25830', label: 'UTM' },
  { crs: 'EPSG:3857', label: 'Web Mercator' },
]
const MAP_CRS = 'EPSG:3857'

type FitCatalogRequest = {
  id: number
  token: number
}

type FitSelectionRequest = {
  id: string
  token: number
}

type MapViewProps = {
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string | null) => void
  /** Show the detection metadata card (map click only). */
  showDetectionDetails?: boolean
  basemap: Basemap
  catalogLayers: CatalogLayer[]
  visibleCatalogIds: Set<number>
  /** When token changes, zoom the map to that catalog layer extent. */
  fitCatalogRequest?: FitCatalogRequest | null
  /** When token changes, zoom to the selected detection (table click or top search hit). */
  fitSelectionRequest?: FitSelectionRequest | null
  referenceFeatures?: ReferenceFeatureCollection | null
}

type GeoTiffViewOptions = {
  extent?: Extent
  projection?: ProjectionLike
}

const STREETS_URL =
  'https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png'
const SATELLITE_URL =
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

const geoJson3857 = new GeoJSON({
  dataProjection: 'EPSG:3857',
  featureProjection: 'EPSG:3857',
})

function boxStyle(score: number, selected: boolean) {
  const color = confidenceColor(score)
  return new Style({
    fill: new Fill({ color: hexToRgba(color, selected ? 0.45 : 0.32) }),
    stroke: new Stroke({
      color: selected ? '#111111' : color,
      width: selected ? 3.5 : 2.5,
    }),
    image: new CircleStyle({
      radius: selected ? 8 : 5,
      fill: new Fill({ color: hexToRgba(color, 0.55) }),
      stroke: new Stroke({
        color: selected ? '#111111' : color,
        width: selected ? 2 : 1.5,
      }),
    }),
  })
}

function projectionCode(projection: ProjectionLike | undefined): string | null {
  if (!projection) return null
  if (typeof projection === 'string') return projection
  if (typeof projection === 'object' && 'getCode' in projection) {
    return projection.getCode()
  }
  return null
}

/** Prefer the COG native extent (reprojected to map CRS); catalog bbox can drift. */
function extentFromGeoTiffView(viewOptions: GeoTiffViewOptions | null | undefined): Extent | null {
  if (!viewOptions) return null
  const extent = viewOptions.extent
  if (!extent?.every(Number.isFinite)) return null

  const code = projectionCode(viewOptions.projection)
  if (code && code !== 'EPSG:3857' && viewOptions.projection) {
    return transformExtent(extent, viewOptions.projection, 'EPSG:3857')
  }
  return extent
}

function catalogLayerExtent(layer: CatalogLayer): Extent | null {
  if (!layer.bbox) return null
  try {
    const geometry = geoJson3857.readGeometry(layer.bbox)
    if (!geometry) return null
    const extent = geometry.getExtent()
    return isEmpty(extent) ? null : extent
  } catch {
    return null
  }
}

function catalogUnionExtent(layers: CatalogLayer[]): Extent | null {
  const extent = createEmpty()
  for (const layer of layers) {
    const layerExtent = catalogLayerExtent(layer)
    if (layerExtent) extend(extent, layerExtent)
  }
  return isEmpty(extent) ? null : extent
}

function fitViewToExtent(map: OlMap, extent: Extent) {
  map.getView().fit(extent, {
    padding: [48, 48, 48, 48],
    maxZoom: 18,
    duration: 400,
  })
}

const referenceStyle = new Style({
  fill: new Fill({ color: 'rgba(14, 116, 144, 0.15)' }),
  stroke: new Stroke({ color: '#0e7490', width: 2, lineDash: [6, 4] }),
  image: new CircleStyle({
    radius: 7,
    fill: new Fill({ color: 'rgba(14, 116, 144, 0.3)' }),
    stroke: new Stroke({ color: '#0e7490', width: 2, lineDash: [4, 3] }),
  }),
})

function formatDisplayCoordinate(coord: Coordinate | null, crs: DisplayCrs): string {
  if (!coord) return '—'
  try {
    const [x, y] = transform(coord, MAP_CRS, crs)
    if (!Number.isFinite(x) || !Number.isFinite(y)) return '—'
    if (crs === 'EPSG:4326') {
      // Lat, Lon
      return `${y.toFixed(6)}°, ${x.toFixed(6)}°`
    }
    return `${x.toFixed(2)}, ${y.toFixed(2)}`
  } catch {
    return '—'
  }
}

type MapHandles = {
  map: OlMap
  streetsLayer: TileLayer<XYZ>
  satelliteLayer: TileLayer<XYZ>
  resultsSource: VectorSource
  referenceSource: VectorSource
  cogLayers: Map<number, WebGLTileLayer>
  fittedCatalogKey: string | null
}

export default function MapView({
  results,
  selectedId,
  onSelect,
  showDetectionDetails = false,
  basemap,
  catalogLayers,
  visibleCatalogIds,
  fitCatalogRequest = null,
  fitSelectionRequest = null,
  referenceFeatures = null,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const handlesRef = useRef<MapHandles | null>(null)
  const onSelectRef = useRef(onSelect)
  const selectedIdRef = useRef(selectedId)
  const displayCrsRef = useRef<DisplayCrs>('EPSG:4326')
  const pointerCoordRef = useRef<Coordinate | null>(null)
  const coordTextRef = useRef<HTMLSpanElement>(null)
  const [mapReady, setMapReady] = useState(false)
  const [displayCrs, setDisplayCrs] = useState<DisplayCrs>('EPSG:4326')
  onSelectRef.current = onSelect
  selectedIdRef.current = selectedId
  displayCrsRef.current = displayCrs

  function paintCoordinateText() {
    const el = coordTextRef.current
    if (!el) return
    const text = formatDisplayCoordinate(pointerCoordRef.current, displayCrsRef.current)
    el.textContent = text
    el.classList.toggle('text-muted-foreground', text === '—')
  }

  // Create map once
  useEffect(() => {
    if (!containerRef.current) return

    ensureProjections()

    const streetsLayer = new TileLayer({
      source: new XYZ({
        url: STREETS_URL,
        attributions: '© OpenStreetMap contributors © CARTO',
      }),
      visible: true,
      zIndex: 0,
    })

    const satelliteLayer = new TileLayer({
      source: new XYZ({
        url: SATELLITE_URL,
        attributions: 'Tiles © Esri, Maxar, Earthstar Geographics',
      }),
      visible: false,
      zIndex: 0,
    })

    const resultsSource = new VectorSource()
    const resultsLayer = new VectorLayer({
      source: resultsSource,
      zIndex: 100,
      style: (feature) => {
        const score = Number(feature.get('score') ?? 0)
        const selected = Boolean(feature.get('selected'))
        return boxStyle(score, selected)
      },
    })

    const referenceSource = new VectorSource()
    const referenceLayer = new VectorLayer({
      source: referenceSource,
      zIndex: 15,
      style: referenceStyle,
    })

    const map = new OlMap({
      target: containerRef.current,
      layers: [streetsLayer, satelliteLayer, referenceLayer, resultsLayer],
      controls: defaultControls({ zoom: false, rotate: false, attribution: true }),
      view: new View({
        center: [0, 0],
        zoom: 2,
        minZoom: 2,
        projection: MAP_CRS,
      }),
    })

    map.on('click', (event) => {
      const feature = map.forEachFeatureAtPixel(
        event.pixel,
        (f) => f,
        { layerFilter: (layer) => layer === resultsLayer },
      )
      if (feature) {
        const id = feature.get('resultId')
        if (typeof id === 'string') onSelectRef.current(id)
      } else {
        onSelectRef.current(null)
      }
    })

    map.on('pointermove', (event) => {
      if (event.dragging) return
      if (event.coordinate) {
        pointerCoordRef.current = [...event.coordinate]
        paintCoordinateText()
      }
      const hit = map.hasFeatureAtPixel(event.pixel, {
        layerFilter: (layer) => layer === resultsLayer,
      })
      map.getTargetElement().style.cursor = hit ? 'pointer' : ''
    })

    handlesRef.current = {
      map,
      streetsLayer,
      satelliteLayer,
      resultsSource,
      referenceSource,
      cogLayers: new Map(),
      fittedCatalogKey: null,
    }
    setMapReady(true)
    paintCoordinateText()

    const ro = new ResizeObserver(() => {
      map.updateSize()
    })
    ro.observe(containerRef.current)

    return () => {
      ro.disconnect()
      map.setTarget(undefined)
      handlesRef.current = null
      setMapReady(false)
    }
  }, [])

  // Reproject readout when the user switches CRS
  useEffect(() => {
    paintCoordinateText()
  }, [displayCrs])

  // Basemap visibility
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return
    h.streetsLayer.setVisible(basemap === 'streets')
    h.satelliteLayer.setVisible(basemap === 'satellite')
  }, [basemap, mapReady])

  // Catalog COG layers + fit to GeoTIFF extent once per catalog snapshot
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    const { map, cogLayers } = h
    const nextIds = new Set(catalogLayers.map((l) => l.id))

    for (const [id, layer] of cogLayers) {
      if (!nextIds.has(id)) {
        map.removeLayer(layer)
        cogLayers.delete(id)
      }
    }

    for (const catalogLayer of catalogLayers) {
      let tileLayer = cogLayers.get(catalogLayer.id)
      if (!tileLayer && isHttpCogUrl(catalogLayer.cog_url)) {
        // Chrome can fail concurrent COG Range requests with
        // net::ERR_CACHE_OPERATION_NOT_SUPPORTED → TypeError: Failed to fetch.
        // Bypass HTTP cache for geotiff.js fetches (geotiffjs/geotiff.js#67).
        const source = new GeoTIFF({
          sources: [{ url: preferIpv4Localhost(catalogLayer.cog_url) }],
          convertToRGB: true,
          interpolate: true,
          sourceOptions: {
            headers: {
              'Cache-Control': 'no-cache, no-store',
              Pragma: 'no-cache',
            },
          },
        })
        tileLayer = new WebGLTileLayer({
          source,
          opacity: 1,
          zIndex: 10,
        })
        cogLayers.set(catalogLayer.id, tileLayer)
        map.addLayer(tileLayer)
      }
      if (tileLayer) {
        tileLayer.setVisible(visibleCatalogIds.has(catalogLayer.id))
      }
    }

    const catalogKey = catalogLayers.map((l) => l.id).join(',')
    if (!catalogKey || catalogKey === h.fittedCatalogKey) return

    let cancelled = false

    void (async () => {
      const union = createEmpty()

      await Promise.all(
        catalogLayers.map(async (catalogLayer) => {
          const tileLayer = cogLayers.get(catalogLayer.id)
          const source = tileLayer?.getSource()
          if (!(source instanceof GeoTIFF)) return
          try {
            const cogExtent = extentFromGeoTiffView(await source.getView())
            if (cogExtent) extend(union, cogExtent)
          } catch {
            // Range/CORS failures: fall back to catalog bbox below
          }
        }),
      )

      if (cancelled || handlesRef.current !== h) return

      const extent = !isEmpty(union) ? union : catalogUnionExtent(catalogLayers)
      if (!extent) return

      fitViewToExtent(map, extent)
      h.fittedCatalogKey = catalogKey
    })()

    return () => {
      cancelled = true
    }
  }, [catalogLayers, visibleCatalogIds, mapReady])

  // Zoom to a single catalog layer (double-click in layer control)
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady || !fitCatalogRequest) return

    const catalogLayer = catalogLayers.find((l) => l.id === fitCatalogRequest.id)
    if (!catalogLayer) return

    let cancelled = false

    void (async () => {
      const tileLayer = h.cogLayers.get(catalogLayer.id)
      const source = tileLayer?.getSource()
      let extent: Extent | null = null

      if (source instanceof GeoTIFF) {
        try {
          extent = extentFromGeoTiffView(await source.getView())
        } catch {
          // fall back to catalog bbox
        }
      }

      if (!extent) extent = catalogLayerExtent(catalogLayer)
      if (cancelled || handlesRef.current !== h || !extent) return

      fitViewToExtent(h.map, extent)
    })()

    return () => {
      cancelled = true
    }
  }, [fitCatalogRequest, catalogLayers, mapReady])

  // Search result boxes — update geometries only (no camera move on filter changes)
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    h.resultsSource.clear()
    const features: Feature[] = []
    for (const r of results) {
      const geometry = olGeometryFromGeoJson(r.geometry)
      if (!geometry) continue
      const feature = new Feature({
        resultId: r.id,
        score: r.confianza,
        selected: r.id === selectedIdRef.current,
        title: r.claseYolo,
      })
      feature.setGeometry(geometry)
      features.push(feature)
    }
    h.resultsSource.addFeatures(features)
  }, [results, mapReady])

  // Zoom to a detection (table click or top hit after search).
  // Depends on `results` so it runs after geometries are loaded into the source.
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady || !fitSelectionRequest) return

    const feature = h.resultsSource
      .getFeatures()
      .find((f) => f.get('resultId') === fitSelectionRequest.id)
    const geometry = feature?.getGeometry()
    if (geometry) {
      h.map.getView().fit(geometry.getExtent(), {
        padding: [80, 80, 80, 80],
        maxZoom: 19,
        duration: 800,
      })
      return
    }

    const target = results.find((r) => r.id === fitSelectionRequest.id)
    if (!target) return
    const view = h.map.getView()
    view.animate({
      center: [target.x, target.y],
      zoom: Math.max(view.getZoom() ?? 2, 17),
      duration: 800,
    })
  }, [fitSelectionRequest, mapReady, results])

  // Spatial reference geometries
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    h.referenceSource.clear()
    const refs = referenceFeatures?.features
    if (!refs?.length) return

    try {
      const features = geoJson3857.readFeatures({
        type: 'FeatureCollection',
        features: refs,
      })
      h.referenceSource.addFeatures(features)
    } catch {
      // Ignore malformed reference geometries
    }
  }, [referenceFeatures, mapReady])

  // Selection highlight only — no camera move on map click
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    h.resultsSource.getFeatures().forEach((feature) => {
      feature.set('selected', feature.get('resultId') === selectedId)
    })
    h.resultsSource.changed()
  }, [selectedId, mapReady])

  const selectedResult =
    showDetectionDetails && selectedId
      ? (results.find((r) => r.id === selectedId) ?? null)
      : null

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full bg-muted" />

      {selectedResult && (
        <DetectionDetailsCard
          result={selectedResult}
          onClose={() => onSelect(null)}
        />
      )}

      <div
        className="pointer-events-auto absolute bottom-4 left-4 z-[1000] flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs shadow-md"
        aria-live="polite"
      >
        <label className="sr-only" htmlFor="map-display-crs">
          Coordinate system
        </label>
        <select
          id="map-display-crs"
          value={displayCrs}
          onChange={(event) => setDisplayCrs(event.target.value as DisplayCrs)}
          className="rounded-md border border-border bg-background px-1.5 py-1 font-medium text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title="Coordinate system"
        >
          {DISPLAY_CRS_OPTIONS.map(({ crs, label }) => (
            <option key={crs} value={crs}>
              {label}
            </option>
          ))}
        </select>
        <span
          ref={coordTextRef}
          className="min-w-[11rem] font-mono tabular-nums text-muted-foreground"
        >
          —
        </span>
      </div>
    </div>
  )
}

function DetectionDetailsCard({
  result,
  onClose,
}: {
  result: SearchResult
  onClose: () => void
}) {
  const { t } = useTranslation()
  const shortId = result.id.includes('/') ? result.id.split('/').pop()! : result.id
  const color = confidenceColor(result.confianza)

  return (
    <div
      className="pointer-events-auto absolute right-4 bottom-20 z-[1000] w-72 rounded-lg border border-border bg-card p-3 shadow-lg"
      role="dialog"
      aria-label={t('detection.title')}
    >
      <div className="mb-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span
              className="size-2.5 shrink-0 rounded-full"
              style={{ backgroundColor: color }}
              aria-hidden
            />
            <h3 className="truncate text-sm font-semibold text-foreground">
              {result.claseYolo}
            </h3>
          </div>
          <p className="mt-0.5 font-mono text-[0.65rem] text-muted-foreground">{shortId}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          aria-label={t('detection.close')}
        >
          <X className="size-3.5" />
        </button>
      </div>

      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-xs">
        <DetailRow label={t('detection.confidence')}>
          <span className="font-semibold tabular-nums" style={{ color }}>
            {(result.confianza * 100).toFixed(1)}%
          </span>
        </DetailRow>
        <DetailRow label={t('detection.similarity')}>
          <span className="tabular-nums">{result.similarity.toFixed(4)}</span>
        </DetailRow>
        <DetailRow label={t('detection.layer')}>
          <span className="truncate" title={result.layer}>
            {result.layer}
          </span>
        </DetailRow>
        {result.distanceToReferenceM != null && (
          <DetailRow label={t('detection.distance')}>
            <span className="tabular-nums">
              {t('detection.meters', { value: result.distanceToReferenceM.toFixed(1) })}
            </span>
          </DetailRow>
        )}
      </dl>
    </div>
  )
}

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className={cn('min-w-0 text-right font-medium text-foreground')}>{children}</dd>
    </>
  )
}
