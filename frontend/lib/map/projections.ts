import proj4 from 'proj4'
import { register } from 'ol/proj/proj4'

let ready = false

/** Register Spanish UTM zones used by PNOA/COG orthophotos. */
export function ensureProjections() {
  if (ready) return
  ready = true

  const defs: Record<string, string> = {
    'EPSG:25830': '+proj=utm +zone=30 +ellps=GRS80 +units=m +no_defs +type=crs',
    'EPSG:25831': '+proj=utm +zone=31 +ellps=GRS80 +units=m +no_defs +type=crs',
  }

  for (const [code, definition] of Object.entries(defs)) {
    if (!proj4.defs(code)) {
      proj4.defs(code, definition)
    }
  }

  register(proj4)
}
