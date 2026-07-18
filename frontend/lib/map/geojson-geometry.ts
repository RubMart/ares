import type { Coordinate } from 'ol/coordinate'
import type Geometry from 'ol/geom/Geometry'
import MultiPolygon from 'ol/geom/MultiPolygon'
import Point from 'ol/geom/Point'
import Polygon from 'ol/geom/Polygon'
import type { GeoJsonGeometry } from '@/lib/api/types'

/**
 * Build an OpenLayers geometry from API GeoJSON.
 * PostGIS `ST_AsGeoJSON` may embed a legacy `crs` member; we ignore it and
 * treat coordinates as EPSG:3857 (as declared by the search FeatureCollection).
 */
export function olGeometryFromGeoJson(
  geometry: GeoJsonGeometry | null | undefined,
): Geometry | null {
  if (!geometry?.type || geometry.coordinates == null) return null

  try {
    switch (geometry.type) {
      case 'Polygon': {
        const rings = geometry.coordinates as Coordinate[][]
        if (!Array.isArray(rings) || rings.length === 0) return null
        return new Polygon(rings)
      }
      case 'MultiPolygon': {
        const polys = geometry.coordinates as Coordinate[][][]
        if (!Array.isArray(polys) || polys.length === 0) return null
        return new MultiPolygon(polys)
      }
      case 'Point': {
        const coord = geometry.coordinates as Coordinate
        if (!Array.isArray(coord) || coord.length < 2) return null
        return new Point(coord)
      }
      default:
        return null
    }
  } catch {
    return null
  }
}
