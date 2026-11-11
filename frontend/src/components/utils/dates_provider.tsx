import { DatesProvider } from '@mantine/dates';
import 'dayjs/locale/de';
import 'dayjs/locale/el';
import 'dayjs/locale/es';
import 'dayjs/locale/fa';
import 'dayjs/locale/fr';
import 'dayjs/locale/it';
import 'dayjs/locale/ja';
import 'dayjs/locale/nb';
import 'dayjs/locale/nl';
import 'dayjs/locale/pt';
import 'dayjs/locale/sv';
import 'dayjs/locale/zh-cn';
import { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

// Maps base language codes used by i18next (see `public/locales`) to dayjs locale names.
// Norwegian browsers may report `no` or `nn`, both are shown in Bokmål.
const dayjsLocales: Record<string, string> = {
  de: 'de',
  el: 'el',
  en: 'en',
  es: 'es',
  fa: 'fa',
  fr: 'fr',
  it: 'it',
  ja: 'ja',
  nb: 'nb',
  nl: 'nl',
  nn: 'nb',
  no: 'nb',
  pt: 'pt',
  sv: 'sv',
  zh: 'zh-cn',
};

export function getDayjsLocale(language: string | undefined): string {
  const baseLanguage = (language ?? 'en').toLowerCase().split('-')[0];
  return dayjsLocales[baseLanguage] ?? 'en';
}

/**
 * Makes Mantine date pickers use the month and weekday names of the selected language.
 */
export function LocalizedDatesProvider({ children }: { children: ReactNode }) {
  const { i18n } = useTranslation();
  const locale = getDayjsLocale(i18n.resolvedLanguage ?? i18n.language);
  return <DatesProvider settings={{ locale }}>{children}</DatesProvider>;
}
