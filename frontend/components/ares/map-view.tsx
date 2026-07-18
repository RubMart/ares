'use client'

import { useEffect, useRef, useState } from 'react'
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
import Point from 'ol/geom/Point'
import { fromLonLat, transform, transformExtent } from 'ol/proj'
import type { Coordinate } from 'ol/coordinate'
import type { ProjectionLike } from 'ol/proj'
import { Fill, Stroke, Style, Circle as CircleStyle } from 'ol/style'
import { defaults as defaultControls } from 'ol/control'
import { extend, createEmpty, isEmpty } from 'ol/extent'
import type { Extent } from 'ol/extent'
import 'ol/ol.css'

import { isHttpCogUrl, preferIpv4Localhost } from '@/lib/api/catalog'
import type { CatalogLayer } from '@/lib/api/types'
import { ensureProjections } from '@/lib/map/projections'
import type { SearchResult } from '@/lib/search'

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

type MapViewProps = {
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string) => void
  basemap: Basemap
  catalogLayers: CatalogLayer[]
  visibleCatalogIds: Set<number>
  /** When token changes, zoom the map to that catalog layer extent. */
  fitCatalogRequest?: FitCatalogRequest | null
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

function scoreColor(score: number) {
  if (score >= 0.85) return '#0e7490'
  if (score >= 0.7) return '#d97706'
  return '#64748b'
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

function markerStyle(score: number, selected: boolean) {
  const color = scoreColor(score)
  return new Style({
    image: new CircleStyle({
      radius: selected ? 10 : 6,
      fill: new Fill({ color }),
      stroke: new Stroke({
        color: selected ? '#111111' : color,
        width: selected ? 2 : 1,
      }),
    }),
  })
}

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
  cogLayers: Map<number, WebGLTileLayer>
  fittedCatalogKey: string | null
}

export default function MapView({
  results,
  selectedId,
  onSelect,
  basemap,
  catalogLayers,
  visibleCatalogIds,
  fitCatalogRequest = null,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const handlesRef = useRef<MapHandles | null>(null)
  const onSelectRef = useRef(onSelect)
  const displayCrsRef = useRef<DisplayCrs>('EPSG:4326')
  const pointerCoordRef = useRef<Coordinate | null>(null)
  const coordTextRef = useRef<HTMLSpanElement>(null)
  const [mapReady, setMapReady] = useState(false)
  const [displayCrs, setDisplayCrs] = useState<DisplayCrs>('EPSG:4326')
  onSelectRef.current = onSelect
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
      zIndex: 20,
      style: (feature) => {
        const score = Number(feature.get('score') ?? 0)
        const selected = Boolean(feature.get('selected'))
        return markerStyle(score, selected)
      },
    })

    const map = new OlMap({
      target: containerRef.current,
      layers: [streetsLayer, satelliteLayer, resultsLayer],
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

  // Search result markers (mock data still in lon/lat)
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    h.resultsSource.clear()
    const features = results.map((r) => {
      const feature = new Feature({
        geometry: new Point(fromLonLat([r.lng, r.lat])),
        resultId: r.id,
        score: r.score,
        selected: r.id === selectedId,
        title: r.title,
      })
      return feature
    })
    h.resultsSource.addFeatures(features)

    if (results.length > 0) {
      const extent = createEmpty()
      for (const f of features) {
        const g = f.getGeometry()
        if (g) extend(extent, g.getExtent())
      }
      if (!isEmpty(extent)) {
        const pad = 500
        extent[0] -= pad
        extent[1] -= pad
        extent[2] += pad
        extent[3] += pad
        h.map.getView().fit(extent, {
          padding: [60, 60, 60, 60],
          maxZoom: 6,
          duration: 350,
        })
      }
    }
  }, [results, mapReady])

  // Selection highlight + fly
  useEffect(() => {
    const h = handlesRef.current
    if (!h || !mapReady) return

    h.resultsSource.getFeatures().forEach((feature) => {
      feature.set('selected', feature.get('resultId') === selectedId)
    })
    h.resultsSource.changed()

    if (!selectedId) return
    const target = results.find((r) => r.id === selectedId)
    if (!target) return
    const view = h.map.getView()
    view.animate({
      center: fromLonLat([target.lng, target.lat]),
      zoom: Math.max(view.getZoom() ?? 2, 7),
      duration: 800,
    })
  }, [selectedId, results, mapReady])

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full bg-muted" />

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
