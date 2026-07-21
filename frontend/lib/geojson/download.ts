import type { GeoJsonGeometry, SearchResult } from '@/lib/api/types'

export type ExportFeatureProperties = {
  clase_yolo: string
  confianza: number
  layer: string
  similarity: number
  distance_to_reference_m?: number
}

export type ExportFeature = {
  type: 'Feature'
  id: string
  geometry: GeoJsonGeometry
  properties: ExportFeatureProperties
}

/** FeatureCollection rebuilt from UI rows (coordinates in EPSG:3857). */
export type ExportFeatureCollection = {
  type: 'FeatureCollection'
  crs: {
    type: 'name'
    properties: { name: 'EPSG:3857' }
  }
  features: ExportFeature[]
}

export function searchResultsToGeoJson(
  results: SearchResult[],
): ExportFeatureCollection {
  return {
    type: 'FeatureCollection',
    crs: {
      type: 'name',
      properties: { name: 'EPSG:3857' },
    },
    features: results.map((row) => {
      const properties: ExportFeatureProperties = {
        clase_yolo: row.claseYolo,
        confianza: row.confianza,
        layer: row.layer,
        similarity: row.similarity,
      }
      if (row.distanceToReferenceM != null) {
        properties.distance_to_reference_m = row.distanceToReferenceM
      }
      return {
        type: 'Feature',
        id: row.id,
        geometry: row.geometry,
        properties,
      }
    }),
  }
}

function slugifyQuery(query: string): string {
  const slug = query
    .trim()
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40)
  return slug || 'results'
}

export function downloadGeoJsonFilename(
  query: string,
  scope: 'all' | 'filtered',
): string {
  return `ares-${slugifyQuery(query)}-${scope}.geojson`
}

/** Trigger a browser download of a GeoJSON FeatureCollection. */
export function downloadSearchResultsGeoJson(
  results: SearchResult[],
  query: string,
  scope: 'all' | 'filtered',
): void {
  if (results.length === 0) return

  const collection = searchResultsToGeoJson(results)
  const blob = new Blob([JSON.stringify(collection, null, 2)], {
    type: 'application/geo+json;charset=utf-8',
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = downloadGeoJsonFilename(query, scope)
  anchor.rel = 'noopener'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
