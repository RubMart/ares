'use client'

import { useTranslation } from 'react-i18next'
import type { ApiStatus } from '@/hooks/use-api-status'
import { cn } from '@/lib/utils'

type ApiStatusBadgeProps = {
  status: ApiStatus
  detail?: string | null
  onRecheck?: () => void
  className?: string
}

const DOT: Record<ApiStatus, string> = {
  checking: 'bg-muted-foreground/50',
  online: 'bg-emerald-500',
  degraded: 'bg-amber-500',
  offline: 'bg-red-500',
}

export function ApiStatusBadge({
  status,
  detail,
  onRecheck,
  className,
}: ApiStatusBadgeProps) {
  const { t } = useTranslation()
  const label = t(`api.status.${status}`)
  const title = detail ? `${label} — ${detail}` : t('api.recheckHint')

  return (
    <button
      type="button"
      onClick={onRecheck}
      title={title}
      aria-label={title}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
        className,
      )}
    >
      <span className="relative flex size-2 shrink-0">
        {(status === 'online' || status === 'checking') && (
          <span
            className={cn(
              'absolute inline-flex size-full rounded-full opacity-60',
              status === 'online' ? 'animate-ping bg-emerald-400' : 'animate-pulse bg-muted-foreground/40',
            )}
          />
        )}
        <span className={cn('relative inline-flex size-2 rounded-full', DOT[status])} />
      </span>
      <span>{label}</span>
    </button>
  )
}
