/** Confidence color thresholds shared by map, table, legend and filters. */

export type ConfidenceLevel = 'low' | 'medium' | 'high'

export const CONFIDENCE_LEVELS: readonly ConfidenceLevel[] = [
  'low',
  'medium',
  'high',
] as const

export const CONFIDENCE_LEVEL_COLOR: Record<ConfidenceLevel, string> = {
  high: '#0e7490',
  medium: '#d97706',
  low: '#64748b',
}

/** High >75%, medium 50–75%, low <50%. */
export function confidenceLevel(score: number): ConfidenceLevel {
  if (score > 0.75) return 'high'
  if (score >= 0.5) return 'medium'
  return 'low'
}

export function confidenceColor(score: number): string {
  return CONFIDENCE_LEVEL_COLOR[confidenceLevel(score)]
}

export function hexToRgba(hex: string, alpha: number): string {
  const raw = hex.replace('#', '')
  const r = Number.parseInt(raw.slice(0, 2), 16)
  const g = Number.parseInt(raw.slice(2, 4), 16)
  const b = Number.parseInt(raw.slice(4, 6), 16)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}
