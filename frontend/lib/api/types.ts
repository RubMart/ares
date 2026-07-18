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
