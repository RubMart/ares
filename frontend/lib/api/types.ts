/** GeoJSON geometry as returned by GET /catalog (EPSG:3857 coordinates). */
export type CatalogBbox = {
  type: string
  coordinates: unknown
}

export type CatalogLayer = {
  id: number
  nombre_capa: string
  cog_url: string
  bbox: CatalogBbox | null
  metadata: Record<string, unknown>
}

export type HealthResponse = {
  status: string
  database: string
  llm_model: string
  llm_status: string
  clip_model: string
  embedding_dim: number
}

export type SearchRequest = {
  query: string
  top_k?: number
  per_layer_limit?: number
  min_confidence?: number
  spatial_relation?: 'near' | null
  target?: string | null
  reference?: string | null
  spatial_distance_m?: number | null
}

export type GeoJsonGeometry = {
  type: string
  coordinates: unknown
}

export type SearchFeatureProperties = {
  layer: string
  similarity: number
  clase_yolo: string
  modelo_deteccion: string
  confianza: number
  tile_id: string
  query: string
  distance_to_reference_m?: number
  reference_id?: number
}

export type SearchFeature = {
  type: 'Feature'
  id: string
  geometry: GeoJsonGeometry | null
  properties: SearchFeatureProperties
}

export type CatalogEntityRef = {
  label: string | null
  canonical: string | null
  clase_yolo: string[]
}

export type Interpretation = {
  summary_es?: string
  summary_en?: string
  intent: string
  target: CatalogEntityRef
  relation: 'near' | 'inside' | null
  distance_m: number | null
  embedding_text: string
  source: string
  reference?: CatalogEntityRef
}

export type SearchTimings = {
  llm_ms: number
  clip_ms: number
  database_ms: number
  total_ms: number
}

export type ReferenceFeatureProperties = {
  layer: string
  role: 'reference'
  clase_yolo: string | null
  reference_id: number
}

export type ReferenceFeature = {
  type: 'Feature'
  id: string
  geometry: GeoJsonGeometry | null
  properties: ReferenceFeatureProperties
}

export type ReferenceFeatureCollection = {
  type: 'FeatureCollection'
  features: ReferenceFeature[]
}

export type SearchMetadata = {
  query: string
  detected_language: 'es' | 'en' | 'unknown'
  interpretation: Interpretation
  structured_query?: Record<string, unknown>
  total_features: number
  layers_searched: string[]
  warnings: string[]
  timings?: SearchTimings
  reference_features?: ReferenceFeatureCollection
}

export type SearchFeatureCollection = {
  type: 'FeatureCollection'
  crs?: {
    type: string
    properties: { name: string }
  }
  features: SearchFeature[]
  metadata: SearchMetadata
}

/** UI row derived from a search GeoJSON feature (coords in EPSG:3857). */
export type SearchResult = {
  id: string
  claseYolo: string
  confianza: number
  layer: string
  similarity: number
  /** Detection geometry (typically a Polygon bbox) in EPSG:3857. */
  geometry: GeoJsonGeometry
  /** Map X in EPSG:3857 (centroid / representative point) */
  x: number
  /** Map Y in EPSG:3857 */
  y: number
  distanceToReferenceM?: number
}
