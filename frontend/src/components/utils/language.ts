import { i18n as I18n } from 'i18next';

/**
 * 'nb' or 'en' for texts made outside i18next (CSV headers, dates in plain text). The browser
 * language is often a regional code such as 'nb-NO', 'no' or 'nn', which all mean Norwegian.
 */
export function contentLanguage(i18n: I18n): 'nb' | 'en' {
  const language = (i18n.resolvedLanguage ?? i18n.language ?? 'en').toLowerCase();
  return ['nb', 'no', 'nn'].some((code) => language.startsWith(code)) ? 'nb' : 'en';
}
