import i18n from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import Backend from 'i18next-http-backend';
import { initReactI18next } from 'react-i18next';

i18n
  .use(Backend)
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    // Norwegian browsers may report `no` (Norwegian) or `nn` (Nynorsk), show those in Bokmål.
    fallbackLng: { no: ['nb'], nn: ['nb'], default: ['en'] },
    // The languages in public/locales; "nb-NO" uses "nb" (no requests for region files)
    supportedLngs: [
      'de',
      'el',
      'en',
      'es',
      'fa',
      'fr',
      'it',
      'ja',
      'nb',
      'nl',
      'pt',
      'sv',
      'zh',
      'no',
      'nn',
    ],
    nonExplicitSupportedLngs: true,
    // The build version in the URL: after a deploy browsers load the new texts, not a cached copy
    backend: { loadPath: `/locales/{{lng}}/{{ns}}.json?v=${__BUILD_VERSION__}` },
    load: 'languageOnly',
    defaultNS: 'common',
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
