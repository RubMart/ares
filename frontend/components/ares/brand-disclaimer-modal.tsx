'use client'

import { useTranslation } from 'react-i18next'
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

type BrandDisclaimerModalProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function BrandDisclaimerModal({
  open,
  onOpenChange,
}: BrandDisclaimerModalProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[min(92vh,32rem)] flex-col gap-0 overflow-hidden p-0 sm:max-w-md"
        showCloseButton
      >
        <DialogHeader className="gap-1 border-b border-border px-5 py-4 pr-12">
          <DialogTitle className="font-display text-lg tracking-tight">
            {t('brand.disclaimer.title')}
          </DialogTitle>
          <DialogDescription>
            {t('brand.disclaimer.description')}
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
          <p className="text-sm leading-relaxed text-foreground">
            {t('brand.disclaimer.purpose')}
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('brand.disclaimer.demo')}
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('brand.disclaimer.responsibility')}
          </p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            {t('brand.disclaimer.humanReview')}
          </p>
        </div>

        <DialogFooter className="mt-0 -mx-0 -mb-0 rounded-b-xl">
          <DialogClose render={<Button variant="outline" />}>
            {t('brand.disclaimer.close')}
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
