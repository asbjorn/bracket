import { format, isSameDay, parseISO } from 'date-fns';
import i18next from 'i18next';
import { useTranslation } from 'react-i18next';

/**
 * The language to format dates in, e.g. `nb` or `en`. Uses the browser's built-in `Intl` support,
 * so no locale data has to be bundled.
 */
function useDateLanguage(): string {
  const { i18n } = useTranslation();
  return intlLanguage(i18n.resolvedLanguage ?? i18n.language);
}

/** A language for Intl: any Norwegian code ("nb-NO", "no", "nn") formats as Bokmål. */
function intlLanguage(language: string | undefined): string {
  // `resolvedLanguage` can be unset; then use the language i18next actually uses
  const code = (language ?? i18next.language ?? 'en').toLowerCase();
  return ['nb', 'no', 'nn'].some((prefix) => code.startsWith(prefix)) ? 'nb' : code;
}

function formatWithIntl(
  datetime: string,
  language: string,
  options: Intl.DateTimeFormatOptions,
): string {
  return new Intl.DateTimeFormat(language, options).format(parseISO(datetime));
}

const timeOptions: Intl.DateTimeFormatOptions = {
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
};

export function DateTime({ datetime }: { datetime: string }) {
  const language = useDateLanguage();
  return (
    <time dateTime={datetime}>
      {formatWithIntl(datetime, language, { dateStyle: 'long' })}{' '}
      {formatWithIntl(datetime, language, timeOptions)}
    </time>
  );
}

export function Time({ datetime }: { datetime: string }) {
  const date = parseISO(datetime);
  return <time dateTime={datetime}>{format(date, 'HH:mm')}</time>;
}

/**
 * Shows the short weekday and date before the time, e.g. "Sat, Jun 13 10:00" in English or
 * "lør. 13. juni 10:00" in Norwegian. Use this when a schedule spans multiple days.
 */
export function DayAndTime({ datetime }: { datetime: string }) {
  const language = useDateLanguage();
  return (
    <time dateTime={datetime}>
      {formatWithIntl(datetime, language, { weekday: 'short', day: 'numeric', month: 'short' })}{' '}
      {formatWithIntl(datetime, language, timeOptions)}
    </time>
  );
}

/**
 * Full date header for a day in a schedule, e.g. "Saturday, June 13, 2026" in English or
 * "lørdag 13. juni 2026" in Norwegian.
 */
export function Day({ datetime }: { datetime: string }) {
  const language = useDateLanguage();
  return (
    <time dateTime={datetime}>{formatWithIntl(datetime, language, { dateStyle: 'full' })}</time>
  );
}

export function formatTime(datetime: string) {
  return format(parseISO(datetime), 'HH:mm');
}

export function isSameDateTimeDay(datetime1: string, datetime2: string) {
  return isSameDay(parseISO(datetime1), parseISO(datetime2));
}

/**
 * Whether the given datetimes are on more than one calendar day (in the browser's timezone).
 */
export function spansMultipleDays(datetimes: string[]) {
  return datetimes.some((datetime) => !isSameDateTimeDay(datetime, datetimes[0]));
}

/**
 * Comparator for sorting datetimes in ascending order.
 */
export function compareDateTime(datetime1: string, datetime2: string) {
  return parseISO(datetime1).getTime() - parseISO(datetime2).getTime();
}

/**
 * Plain-text dates for labels, select options and exports, in the UI language (dayjs would use
 * its global locale, which is English unless set). `language` is e.g. i18n.resolvedLanguage.
 */
export function formatDayTime(
  datetime: string,
  language: string | undefined,
  kind: 'weekday' | 'weekday_time' | 'weekday_date_time' | 'long_day',
): string {
  const lang = intlLanguage(language);
  const date = parseISO(datetime);
  const weekday = new Intl.DateTimeFormat(lang, { weekday: 'short' }).format(date);
  const time = new Intl.DateTimeFormat(lang, timeOptions).format(date);
  switch (kind) {
    case 'weekday':
      return weekday;
    case 'weekday_time':
      return `${weekday} ${time}`;
    case 'weekday_date_time':
      return `${new Intl.DateTimeFormat(lang, { weekday: 'short', day: 'numeric', month: 'short' }).format(date)} ${time}`;
    case 'long_day':
      return new Intl.DateTimeFormat(lang, {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
      }).format(date);
  }
}
