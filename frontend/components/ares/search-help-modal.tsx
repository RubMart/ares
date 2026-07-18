'use client'

import { useTranslation } from 'react-i18next'
import {
  MapPinned,
  Palette,
  Search,
  Sparkles,
} from 'lucide-react'
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
import { SEARCH_CATALOG } from '@/lib/search-catalog'

type SearchHelpModalProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function SearchHelpModal({ open, onOpenChange }: SearchHelpModalProps) {
  const { t } = useTranslation()

  const colors = t('searchHelp.colors', { returnObjects: true })
  const colorList = Array.isArray(colors) ? (colors as string[]) : []
  const limits = t('searchHelp.limits', { returnObjects: true })
  const limitList = Array.isArray(limits) ? (limits as string[]) : []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[min(92vh,42rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-lg"
        showCloseButton
      >
        <DialogHeader className="gap-1 border-b border-border px-5 py-4 pr-12">
          <DialogTitle className="font-display text-lg tracking-tight">
            {t('searchHelp.title')}
          </DialogTitle>
          <DialogDescription>{t('searchHelp.description')}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-4">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('searchHelp.intro')}
          </p>

          <section className="space-y-3">
            <h3 className="text-xs font-semibold tracking-wide text-foreground">
              {t('searchHelp.typesTitle')}
            </h3>
            <div className="grid gap-2.5">
              <HelpCard
                icon={<Search className="size-4" />}
                title={t('searchHelp.typeClassTitle')}
                body={t('searchHelp.typeClassBody')}
              />
              <HelpCard
                icon={<Palette className="size-4" />}
                title={t('searchHelp.typeAttrTitle')}
                body={t('searchHelp.typeAttrBody')}
              />
              <HelpCard
                icon={<MapPinned className="size-4" />}
                title={t('searchHelp.typeSpatialTitle')}
                body={t('searchHelp.typeSpatialBody')}
              />
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-xs font-semibold tracking-wide text-foreground">
              {t('searchHelp.classesTitle')}
            </h3>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {t('searchHelp.classesIntro')}
            </p>
            <div className="grid gap-2">
              {SEARCH_CATALOG.map((entry) => {
                const examples = t(entry.examplesKey, { returnObjects: true })
                const exampleList = Array.isArray(examples)
                  ? (examples as string[])
                  : []
                return (
                  <div
                    key={entry.id}
                    className="rounded-lg border border-border bg-card px-3 py-2.5"
                  >
                    <div className="text-sm font-medium text-foreground">
                      {t(entry.labelKey)}
                    </div>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {exampleList.map((ex) => (
                        <span
                          key={ex}
                          className="rounded-full bg-secondary px-2 py-0.5 text-[0.65rem] text-secondary-foreground"
                        >
                          {ex}
                        </span>
                      ))}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          {colorList.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-xs font-semibold tracking-wide text-foreground">
                {t('searchHelp.colorsTitle')}
              </h3>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t('searchHelp.colorsIntro')}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {colorList.map((c) => (
                  <span
                    key={c}
                    className="rounded-md border border-border bg-muted/50 px-2 py-0.5 text-[0.7rem] text-foreground"
                  >
                    {c}
                  </span>
                ))}
              </div>
            </section>
          )}

          <section className="space-y-2">
            <h3 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-foreground">
              <Sparkles className="size-3.5 text-primary" />
              {t('searchHelp.limitsTitle')}
            </h3>
            <ul className="space-y-2">
              {limitList.map((item) => (
                <li
                  key={item}
                  className="rounded-lg border border-border/80 bg-muted/30 px-3 py-2 text-xs leading-relaxed text-muted-foreground"
                >
                  {item}
                </li>
              ))}
            </ul>
          </section>
        </div>

        <DialogFooter className="mt-0 -mx-0 -mb-0 rounded-b-xl">
          <DialogClose render={<Button variant="outline" />}>
            {t('searchHelp.close')}
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function HelpCard({
  icon,
  title,
  body,
}: {
  icon: React.ReactNode
  title: string
  body: string
}) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-muted/25 px-3 py-2.5">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <p className="mt-0.5 text-xs leading-relaxed text-muted-foreground">{body}</p>
      </div>
    </div>
  )
}
