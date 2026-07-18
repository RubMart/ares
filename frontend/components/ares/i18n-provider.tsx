'use client'

import { useEffect, useState } from 'react'
import { I18nextProvider } from 'react-i18next'
import i18n from '@/lib/i18n/config'

function syncHtmlLang() {
  document.documentElement.lang = i18n.resolvedLanguage ?? i18n.language
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  // Wait until client-side language detection has run to avoid SSR/hydration mismatch.
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const markReady = () => {
      syncHtmlLang()
      setReady(true)
    }

    if (i18n.isInitialized) {
      markReady()
    } else {
      i18n.on('initialized', markReady)
    }

    i18n.on('languageChanged', syncHtmlLang)

    return () => {
      i18n.off('initialized', markReady)
      i18n.off('languageChanged', syncHtmlLang)
    }
  }, [])

  if (!ready) {
    return null
  }

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
}
