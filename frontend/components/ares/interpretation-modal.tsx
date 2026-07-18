'use client'

import { useTranslation } from 'react-i18next'
import { AlertTriangle, Layers, Sparkles, Target } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { Interpretation, SearchMetadata } from '@/lib/api/types'
import { cn } from '@/lib/utils'

type InterpretationModalProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  metadata: SearchMetadata | null
}

function entityLabel(entity: { label: string | null; canonical: string | null } | undefined) {
  if (!entity) return null
  return entity.label || entity.canonical || null
}

function intentKey(intent: string) {
  if (intent === 'search_spatial') return 'interpretation.intentSpatial'
  if (intent === 'search_class') return 'interpretation.intentClass'
  return 'interpretation.intentOther'
}

function sourceKey(source: string) {
  if (source === 'parser') return 'interpretation.sourceParser'
  if (source === 'llm') return 'interpretation.sourceLlm'
  if (source === 'override') return 'interpretation.sourceOverride'
  return 'interpretation.sourceOther'
}

function languageKey(lang: string) {
  if (lang === 'es') return 'interpretation.langEs'
  if (lang === 'en') return 'interpretation.langEn'
  return 'interpretation.langUnknown'
}

export function InterpretationModal({
  open,
  onOpenChange,
  metadata,
}: InterpretationModalProps) {
  const { t, i18n } = useTranslation()
  const interp = metadata?.interpretation
  const summary = summaryForLocale(interp, i18n.language, t('interpretation.none'))
  const isSpatial = interp?.intent === 'search_spatial'
  const timings = metadata?.timings

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[min(90vh,36rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
        showCloseButton
      >
        <DialogHeader className="gap-1 border-b border-border px-5 py-4 pr-12">
          <DialogTitle className="font-display text-lg tracking-tight">
            {t('interpretation.title')}
          </DialogTitle>
          <DialogDescription>{t('interpretation.description')}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          {!metadata || !interp ? (
            <p className="text-sm text-muted-foreground">{t('interpretation.none')}</p>
          ) : (
            <div className="flex flex-col gap-5">
              <blockquote className="rounded-lg border border-primary/15 bg-primary/5 px-3.5 py-3 text-sm leading-relaxed text-foreground">
                {summary}
              </blockquote>

              <div className="flex flex-wrap gap-1.5">
                <MetaChip>{t(intentKey(interp.intent))}</MetaChip>
                <MetaChip>{t(sourceKey(interp.source))}</MetaChip>
                <MetaChip>{t(languageKey(metadata.detected_language))}</MetaChip>
              </div>

              <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5">
                <div className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
                  {t('interpretation.query')}
                </div>
                <p className="mt-1 font-mono text-sm text-foreground">“{metadata.query}”</p>
              </div>

              <Section
                icon={<Target className="size-3.5" />}
                title={t('interpretation.sectionSearch')}
              >
                <div className="flex flex-col gap-3">
                  <EntityBlock
                    label={t('interpretation.target')}
                    name={entityLabel(interp.target) ?? t('interpretation.none')}
                    classes={interp.target.clase_yolo}
                  />

                  {isSpatial && (
                    <>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span className="rounded-md bg-secondary px-2 py-0.5 font-medium text-foreground">
                          {interp.relation ?? t('interpretation.none')}
                        </span>
                        {interp.distance_m != null && (
                          <span>
                            {t('interpretation.meters', { value: interp.distance_m })}
                          </span>
                        )}
                      </div>
                      <EntityBlock
                        label={t('interpretation.reference')}
                        name={entityLabel(interp.reference) ?? t('interpretation.none')}
                        classes={interp.reference?.clase_yolo}
                      />
                    </>
                  )}

                  {interp.embedding_text ? (
                    <div>
                      <div className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
                        {t('interpretation.embeddingText')}
                      </div>
                      <p className="mt-1 font-mono text-xs leading-relaxed text-muted-foreground">
                        {interp.embedding_text}
                      </p>
                    </div>
                  ) : null}
                </div>
              </Section>

              <Section
                icon={<Layers className="size-3.5" />}
                title={t('interpretation.sectionResults')}
              >
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-sm">
                  <span className="font-semibold tabular-nums text-primary">
                    {metadata.total_features}
                  </span>
                  <span className="text-muted-foreground">
                    {t('interpretation.featuresReturned')}
                  </span>
                </div>
                {metadata.layers_searched?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {metadata.layers_searched.map((layer) => (
                      <span
                        key={layer}
                        className="rounded-md border border-border bg-background px-2 py-0.5 font-mono text-[0.65rem] text-muted-foreground"
                      >
                        {layer}
                      </span>
                    ))}
                  </div>
                )}
              </Section>

              {timings && (
                <Section
                  icon={<Sparkles className="size-3.5" />}
                  title={t('interpretation.timings')}
                >
                  <div className="grid grid-cols-4 gap-2">
                    <TimingStat
                      label={t('interpretation.llmMs')}
                      value={Math.round(timings.llm_ms)}
                    />
                    <TimingStat
                      label={t('interpretation.clipMs')}
                      value={Math.round(timings.clip_ms)}
                    />
                    <TimingStat
                      label={t('interpretation.databaseMs')}
                      value={Math.round(timings.database_ms)}
                    />
                    <TimingStat
                      label={t('interpretation.totalMs')}
                      value={Math.round(timings.total_ms)}
                      emphasize
                    />
                  </div>
                </Section>
              )}

              {metadata.warnings?.length > 0 && (
                <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2.5">
                  <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                    <AlertTriangle className="size-3.5" />
                    {t('interpretation.warnings')}
                  </div>
                  <ul className="space-y-1 text-xs leading-relaxed text-amber-900/90">
                    {metadata.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter className="mt-0 -mx-0 -mb-0 rounded-b-xl">
          <DialogClose render={<Button variant="outline" />}>
            {t('interpretation.close')}
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function summaryForLocale(
  interp: Interpretation | undefined,
  language: string,
  fallback: string,
) {
  if (!interp) return fallback
  const preferEs = language.toLowerCase().startsWith('es')
  if (preferEs) return interp.summary_es || interp.summary_en || fallback
  return interp.summary_en || interp.summary_es || fallback
}

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border bg-secondary/80 px-2.5 py-0.5 text-[0.7rem] font-medium text-secondary-foreground">
      {children}
    </span>
  )
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="flex flex-col gap-2">
      <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-foreground">
        <span className="text-primary">{icon}</span>
        {title}
      </h3>
      <div>{children}</div>
    </section>
  )
}

function EntityBlock({
  label,
  name,
  classes,
}: {
  label: string
  name: string
  classes?: string[] | null
}) {
  return (
    <div>
      <div className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <p className="mt-0.5 text-sm font-medium text-foreground">{name}</p>
      {classes && classes.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {classes.map((c) => (
            <span
              key={c}
              className="rounded-md bg-primary/10 px-1.5 py-0.5 font-mono text-[0.65rem] text-primary"
            >
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function TimingStat({
  label,
  value,
  emphasize,
}: {
  label: string
  value: number
  emphasize?: boolean
}) {
  const { t } = useTranslation()
  return (
    <div
      className={cn(
        'rounded-md px-2 py-1.5 text-center',
        emphasize ? 'bg-primary/10' : 'bg-muted/60',
      )}
    >
      <div className="text-[0.6rem] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div
        className={cn(
          'mt-0.5 font-mono text-xs tabular-nums',
          emphasize ? 'font-semibold text-primary' : 'text-foreground',
        )}
      >
        {t('interpretation.ms', { value })}
      </div>
    </div>
  )
}
