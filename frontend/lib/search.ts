export type SearchResult = {
  id: string
  title: string
  category: string
  score: number
  lat: number
  lng: number
  source: string
  captured: string
}

const CATEGORIES = [
  'Airfield',
  'Port Facility',
  'Solar Farm',
  'Stadium',
  'Rail Yard',
  'Storage Depot',
  'Bridge',
  'Refinery',
  'Vessel Cluster',
  'Runway Marking',
]

const SOURCES = ['Sentinel-2', 'Landsat-9', 'Planet SkySat', 'Maxar WV-3', 'Airbus Pléiades']

// Anchor regions to scatter realistic-looking hits around the globe.
const ANCHORS: Array<{ name: string; lat: number; lng: number }> = [
  { name: 'San Francisco Bay', lat: 37.77, lng: -122.42 },
  { name: 'Rotterdam', lat: 51.92, lng: 4.48 },
  { name: 'Suez', lat: 30.02, lng: 32.55 },
  { name: 'Singapore Strait', lat: 1.29, lng: 103.85 },
  { name: 'Persian Gulf', lat: 26.5, lng: 51.5 },
  { name: 'Los Angeles', lat: 34.05, lng: -118.24 },
  { name: 'Tokyo Bay', lat: 35.5, lng: 139.8 },
  { name: 'Panama Canal', lat: 9.08, lng: -79.68 },
  { name: 'Gibraltar', lat: 36.14, lng: -5.35 },
  { name: 'Cape Town', lat: -33.92, lng: 18.42 },
]

function seededRandom(seed: number) {
  let s = seed % 2147483647
  if (s <= 0) s += 2147483646
  return () => {
    s = (s * 16807) % 2147483647
    return (s - 1) / 2147483646
  }
}

function hashString(str: string) {
  let h = 0
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i)
    h |= 0
  }
  return Math.abs(h) || 1
}

export function runSemanticSearch(query: string, count: number): SearchResult[] {
  const rand = seededRandom(hashString(query || 'ares') + count)
  const results: SearchResult[] = []

  for (let i = 0; i < count; i++) {
    const anchor = ANCHORS[Math.floor(rand() * ANCHORS.length)]
    const lat = clamp(anchor.lat + (rand() - 0.5) * 6, -85, 85)
    const lng = clamp(anchor.lng + (rand() - 0.5) * 8, -179, 179)
    const category = CATEGORIES[Math.floor(rand() * CATEGORIES.length)]
    const score = Number((0.55 + rand() * 0.44).toFixed(3))
    const source = SOURCES[Math.floor(rand() * SOURCES.length)]
    const daysAgo = Math.floor(rand() * 120)
    const captured = new Date(Date.now() - daysAgo * 86400000).toISOString().slice(0, 10)

    results.push({
      id: `AR-${(hashString(query) % 1000).toString().padStart(3, '0')}-${(i + 1)
        .toString()
        .padStart(3, '0')}`,
      title: `${category} · ${anchor.name}`,
      category,
      score,
      lat: Number(lat.toFixed(4)),
      lng: Number(lng.toFixed(4)),
      source,
      captured,
    })
  }

  return results.sort((a, b) => b.score - a.score)
}

function clamp(v: number, min: number, max: number) {
  return Math.max(min, Math.min(max, v))
}
