'use client'

import { Filter } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Slider } from '@/components/ui/slider'
import {
  CONFIDENCE_LEVELS,
  CONFIDENCE_LEVEL_COLOR,
  type ConfidenceLevel,
} from '@/lib/map/confidence'
import { cn } from '@/lib/utils'

export type MetricRange = { min: number; max: number }

export type ResultFilterState = {
  enabledClasses: Set<string>
  confidenceLevels: Set<ConfidenceLevel>
  similarity: MetricRange
}

export type ResultFilterBounds = {
  similarity: MetricRange
}

type ClassCount = { name: string; count: number }

type ResultFiltersControlProps = {
  classCounts: ClassCount[]
  bounds: ResultFilterBounds
  filters: ResultFilterState
  visibleCount: number
  totalCount: number
  onToggleClass: (className: string) => void
  onEnableAllClasses: () => void
  onDisableAllClasses: () => void
  onToggleConfidenceLevel: (level: ConfidenceLevel) => void
  onSimilarityChange: (range: MetricRange) => void
}

function formatMetric(value: number) {
  return value.toFixed(2)
}

const LEVEL_LABEL_KEY: Record<ConfidenceLevel, string> = {
  low: 'map.confidenceLevelLow',
  medium: 'map.confidenceLevelMedium',
  high: 'map.confidenceLevelHigh',
}

export function ResultFiltersControl({
  classCounts,
  bounds,
  filters,
  visibleCount,
  totalCount,
  onToggleClass,
  onEnableAllClasses,
  onDisableAllClasses,
  onToggleConfidenceLevel,
  onSimilarityChange,
}: ResultFiltersControlProps) {
  const { t } = useTranslation()

  return (
    <div className="w-72 overflow-hidden rounded-lg border border-border bg-card shadow-md">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
          <Filter className="size-4 shrink-0 text-primary" />
          {t('map.resultFilters')}
        </div>
        <span className="text-[0.65rem] tabular-nums text-muted-foreground">
          {t('map.visibleOfTotal', { visible: visibleCount, total: totalCount })}
        </span>
      </div>

      <div className="flex max-h-[min(50vh,28rem)] flex-col gap-3 overflow-y-auto px-3 py-3">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-foreground">{t('map.filterClasses')}</span>
            <div className="flex gap-1">
              <button
                type="button"
                onClick={onEnableAllClasses}
                className="rounded px-1.5 py-0.5 text-[0.65rem] text-primary hover:bg-secondary"
              >
                {t('map.filterAll')}
              </button>
              <button
                type="button"
                onClick={onDisableAllClasses}
                className="rounded px-1.5 py-0.5 text-[0.65rem] text-muted-foreground hover:bg-secondary hover:text-foreground"
              >
                {t('map.filterNone')}
              </button>
            </div>
          </div>

          {classCounts.length === 0 ? (
            <p className="text-xs text-muted-foreground">{t('map.filterClassesEmpty')}</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {classCounts.map(({ name, count }) => {
                const active = filters.enabledClasses.has(name)
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => onToggleClass(name)}
                    aria-pressed={active}
                    className={cn(
                      'inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 text-[0.7rem] transition-colors',
                      active
                        ? 'border-primary/40 bg-primary/10 text-primary'
                        : 'border-border bg-background text-muted-foreground hover:bg-secondary',
                    )}
                  >
                    <span className="truncate">{name}</span>
                    <span className="shrink-0 tabular-nums opacity-70">{count}</span>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <span className="text-xs font-medium text-foreground">{t('map.filterConfidence')}</span>
          <div
            role="group"
            aria-label={t('map.filterConfidence')}
            className="grid grid-cols-3 gap-1 rounded-lg bg-muted/80 p-1"
          >
            {CONFIDENCE_LEVELS.map((level) => {
              const active = filters.confidenceLevels.has(level)
              const color = CONFIDENCE_LEVEL_COLOR[level]
              return (
                <button
                  key={level}
                  type="button"
                  aria-pressed={active}
                  onClick={() => onToggleConfidenceLevel(level)}
                  className={cn(
                    'relative flex items-center justify-center gap-1.5 rounded-md px-1.5 py-1.5 text-[0.7rem] font-medium transition-all',
                    active
                      ? 'bg-card text-foreground shadow-sm'
                      : 'text-muted-foreground hover:text-foreground',
                  )}
                >
                  <span
                    className={cn(
                      'size-2 shrink-0 rounded-full transition-opacity',
                      active ? 'opacity-100' : 'opacity-35',
                    )}
                    style={{ backgroundColor: color }}
                    aria-hidden
                  />
                  {t(LEVEL_LABEL_KEY[level])}
                </button>
              )
            })}
          </div>
        </div>

        <DualRangeField
          label={t('map.filterSimilarity')}
          bounds={bounds.similarity}
          value={filters.similarity}
          onChange={onSimilarityChange}
        />
      </div>
    </div>
  )
}

function DualRangeField({
  label,
  bounds,
  value,
  onChange,
}: {
  label: string
  bounds: MetricRange
  value: MetricRange
  onChange: (range: MetricRange) => void
}) {
  const min = bounds.min
  const max = Math.max(bounds.max, bounds.min + 0.01)
  const lo = Math.min(Math.max(value.min, min), max)
  const hi = Math.min(Math.max(value.max, lo), max)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-foreground">{label}</span>
        <div className="flex items-center gap-1">
          <span className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[0.65rem] tabular-nums text-foreground">
            {formatMetric(lo)}
          </span>
          <span className="text-[0.65rem] text-muted-foreground">–</span>
          <span className="rounded-md bg-secondary px-1.5 py-0.5 font-mono text-[0.65rem] tabular-nums text-foreground">
            {formatMetric(hi)}
          </span>
        </div>
      </div>

      <Slider
        min={min}
        max={max}
        step={0.01}
        minStepsBetweenValues={1}
        value={[lo, hi]}
        onValueChange={(next) => {
          if (!Array.isArray(next) || next.length < 2) return
          onChange({ min: next[0], max: next[1] })
        }}
      />

      <div className="flex justify-between text-[0.65rem] tabular-nums text-muted-foreground">
        <span>{formatMetric(min)}</span>
        <span>{formatMetric(max)}</span>
      </div>
    </div>
  )
}
