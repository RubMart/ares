'use client'

import { useTranslation } from 'react-i18next'
import { supportedLngs, type AppLanguage } from '@/lib/i18n/config'
import { cn } from '@/lib/utils'

const LABELS: Record<AppLanguage, string> = {
  en: 'EN',
  es: 'ES',
}

export function LanguageSwitcher({ className }: { className?: string }) {
  const { t, i18n } = useTranslation()
  const current = (i18n.resolvedLanguage ?? i18n.language).slice(0, 2) as AppLanguage

  return (
    <div
      role="group"
      aria-label={t('language.switch')}
      className={cn(
        'inline-flex overflow-hidden rounded-md border border-border bg-card text-xs font-semibold',
        className,
      )}
    >
      {supportedLngs.map((lng) => {
        const active = current === lng
        return (
          <button
            key={lng}
            type="button"
            aria-pressed={active}
            onClick={() => void i18n.changeLanguage(lng)}
            className={cn(
              'px-2 py-1 transition-colors',
              active
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
            )}
          >
            {LABELS[lng]}
          </button>
        )
      })}
    </div>
  )
}
