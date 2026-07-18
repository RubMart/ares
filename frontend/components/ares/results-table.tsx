'use client'

import { MapPin } from 'lucide-react'
import type { SearchResult } from '@/lib/search'
import { cn } from '@/lib/utils'

type ResultsTableProps = {
  results: SearchResult[]
  selectedId: string | null
  onSelect: (id: string) => void
  query: string
}

function scoreClasses(score: number) {
  if (score >= 0.85) return 'bg-primary/15 text-primary'
  if (score >= 0.7) return 'bg-amber-500/15 text-amber-700'
  return 'bg-slate-500/15 text-slate-600'
}

export function ResultsTable({ results, selectedId, onSelect, query }: ResultsTableProps) {
  return (
    <section className="mt-6" aria-label="Search results">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Results</h2>
        <span className="text-xs text-muted-foreground">
          {results.length} matches{query ? ` for “${query}”` : ''}
        </span>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <div className="max-h-[calc(100vh-30rem)] overflow-y-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="sticky top-0 z-10 bg-secondary text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 font-medium">
                  Feature
                </th>
                <th scope="col" className="px-3 py-2 font-medium">
                  Score
                </th>
                <th scope="col" className="px-3 py-2 text-right font-medium">
                  Coordinates
                </th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => {
                const isSelected = r.id === selectedId
                return (
                  <tr
                    key={r.id}
                    onClick={() => onSelect(r.id)}
                    className={cn(
                      'cursor-pointer border-t border-border transition-colors',
                      isSelected ? 'bg-accent' : 'hover:bg-secondary',
                    )}
                  >
                    <td className="px-3 py-2">
                      <div className="flex items-start gap-2">
                        <MapPin
                          className={cn(
                            'mt-0.5 size-4 shrink-0',
                            isSelected ? 'text-primary' : 'text-muted-foreground',
                          )}
                        />
                        <div className="min-w-0">
                          <div className="truncate font-medium text-foreground">{r.title}</div>
                          <div className="font-mono text-xs text-muted-foreground">
                            {r.id} · {r.source}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={cn(
                          'inline-block rounded-full px-2 py-0.5 text-xs font-semibold',
                          scoreClasses(r.score),
                        )}
                      >
                        {(r.score * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-xs text-muted-foreground">
                      {r.lat.toFixed(3)}, {r.lng.toFixed(3)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
