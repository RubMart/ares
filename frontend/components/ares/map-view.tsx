'use client'

import { useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import type { SearchResult } from '@/lib/search'

type MapViewProps = {
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string) => void
  basemap: 'streets' | 'satellite'
}

const TILE_CONFIG = {
  streets: {
    url: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: 'Tiles &copy; Esri, Maxar, Earthstar Geographics',
  },
}

function scoreColor(score: number) {
  if (score >= 0.85) return '#0e7490'
  if (score >= 0.7) return '#d97706'
  return '#64748b'
}

function FitBounds({ results }: { results: SearchResult[] }) {
  const map = useMap()
  useEffect(() => {
    if (results.length === 0) return
    const bounds = L.latLngBounds(results.map((r) => [r.lat, r.lng] as [number, number]))
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 6 })
  }, [results, map])
  return null
}

function FlyToSelected({
  results,
  selectedId,
}: {
  results: SearchResult[]
  selectedId: string | null
}) {
  const map = useMap()
  useEffect(() => {
    if (!selectedId) return
    const target = results.find((r) => r.id === selectedId)
    if (target) {
      map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), 7), { duration: 0.8 })
    }
  }, [selectedId, results, map])
  return null
}

export default function MapView({ results, selectedId, onSelect, basemap }: MapViewProps) {
  const tiles = TILE_CONFIG[basemap]

  const markers = useMemo(
    () =>
      results.map((r) => {
        const isSelected = r.id === selectedId
        const color = scoreColor(r.score)
        return (
          <CircleMarker
            key={r.id}
            center={[r.lat, r.lng]}
            radius={isSelected ? 10 : 6}
            pathOptions={{
              color: isSelected ? '#111' : color,
              weight: isSelected ? 2 : 1,
              fillColor: color,
              fillOpacity: isSelected ? 1 : 0.75,
            }}
            eventHandlers={{ click: () => onSelect(r.id) }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              <div className="text-xs">
                <div className="font-semibold">{r.title}</div>
                <div className="font-mono">
                  {r.lat.toFixed(3)}, {r.lng.toFixed(3)} · {(r.score * 100).toFixed(0)}%
                </div>
              </div>
            </Tooltip>
          </CircleMarker>
        )
      }),
    [results, selectedId, onSelect],
  )

  return (
    <MapContainer
      center={[25, 10]}
      zoom={2}
      minZoom={2}
      worldCopyJump
      className="h-full w-full bg-muted"
      zoomControl={false}
    >
      <TileLayer key={basemap} url={tiles.url} attribution={tiles.attribution} />
      {markers}
      <FitBounds results={results} />
      <FlyToSelected results={results} selectedId={selectedId} />
    </MapContainer>
  )
}
