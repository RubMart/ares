import { apiPost } from '@/lib/api/client'
import type {
  GeoJsonGeometry,
  SearchFeature,
  SearchFeatureCollection,
  SearchRequest,
  SearchResult,
} from '@/lib/api/types'

export const SEARCH_TIMEOUT_MS = 60_000

export type SearchDetectionsParams = Pick<
  SearchRequest,
  'query' | 'top_k' | 'min_confidence' | 'per_layer_limit'
> & {
  signal?: AbortSignal
}

export async function searchDetections(
  params: SearchDetectionsParams,
): Promise<SearchFeatureCollection> {
  const { signal, ...body } = params
  return apiPost<SearchFeatureCollection>('/search', body, {
    signal,
    timeoutMs: SEARCH_TIMEOUT_MS,
  })
}

/** Extract a representative [x, y] in EPSG:3857 from GeoJSON geometry. */
export function geometryPoint3857(
  geometry: GeoJsonGeometry | null | undefined,
): [number, number] | null {
  if (!geometry?.coordinates) return null
  const coords = geometry.coordinates

  if (geometry.type === 'Point' && isPair(coords)) {
    return [coords[0], coords[1]]
  }

  if (geometry.type === 'MultiPoint' && Array.isArray(coords) && isPair(coords[0])) {
    return [coords[0][0], coords[0][1]]
  }

  if (geometry.type === 'LineString' && Array.isArray(coords)) {
    return averagePairs(coords.filter(isPair))
  }

  if (geometry.type === 'MultiLineString' && Array.isArray(coords)) {
    const pairs = coords.flatMap((line) =>
      Array.isArray(line) ? line.filter(isPair) : [],
    )
    return averagePairs(pairs)
  }

  if (geometry.type === 'Polygon' && Array.isArray(coords) && Array.isArray(coords[0])) {
    return averagePairs((coords[0] as unknown[]).filter(isPair))
  }

  if (geometry.type === 'MultiPolygon' && Array.isArray(coords)) {
    const pairs: [number, number][] = []
    for (const polygon of coords) {
      if (!Array.isArray(polygon) || !Array.isArray(polygon[0])) continue
      for (const ring of polygon[0] as unknown[]) {
        if (isPair(ring)) pairs.push(ring)
      }
    }
    return averagePairs(pairs)
  }

  return null
}

function isPair(value: unknown): value is [number, number] {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    typeof value[0] === 'number' &&
    typeof value[1] === 'number' &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1])
  )
}

function averagePairs(pairs: [number, number][]): [number, number] | null {
  if (pairs.length === 0) return null
  let sx = 0
  let sy = 0
  for (const [x, y] of pairs) {
    sx += x
    sy += y
  }
  return [sx / pairs.length, sy / pairs.length]
}

export function featureToSearchResult(feature: SearchFeature): SearchResult | null {
  if (!feature.geometry) return null
  const point = geometryPoint3857(feature.geometry)
  if (!point) return null
  const props = feature.properties
  const id =
    typeof feature.id === 'string' || typeof feature.id === 'number'
      ? String(feature.id)
      : `${props.layer}/${props.tile_id}`

  return {
    id,
    claseYolo: props.clase_yolo ?? '—',
    confianza: typeof props.confianza === 'number' ? props.confianza : 0,
    layer: props.layer ?? '—',
    similarity: typeof props.similarity === 'number' ? props.similarity : 0,
    // Drop PostGIS legacy `crs` member; FeatureCollection already declares EPSG:3857.
    geometry: {
      type: feature.geometry.type,
      coordinates: feature.geometry.coordinates,
    },
    x: point[0],
    y: point[1],
    distanceToReferenceM: props.distance_to_reference_m,
  }
}

export function featuresToSearchResults(features: SearchFeature[]): SearchResult[] {
  const results: SearchResult[] = []
  for (const feature of features) {
    const row = featureToSearchResult(feature)
    if (row) results.push(row)
  }
  return results
}
