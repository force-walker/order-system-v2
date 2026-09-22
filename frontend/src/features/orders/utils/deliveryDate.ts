const CLOSED_WEEKDAYS = new Set([0, 3]); // Sunday, Wednesday
const BUSINESS_TIME_ZONE = 'Asia/Hong_Kong';

const toYmd = (date: Date) => {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const isClosedDay = (date: Date) => CLOSED_WEEKDAYS.has(date.getUTCDay());

const inBusinessTimeZone = (base: Date) => {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: BUSINESS_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(base);
  const value = (type: Intl.DateTimeFormatPartTypes) => Number(parts.find((part) => part.type === type)?.value);
  return {
    calendarDate: new Date(Date.UTC(value('year'), value('month') - 1, value('day'))),
    hour: value('hour'),
  };
};

/**
 * Before 13:00 use today when it is a business day. At/after 13:00, or when
 * today is closed, advance to the next business day. Wednesday and Sunday are
 * closed.
 */
export const getDefaultDeliveryDate = (base = new Date()) => {
  const { calendarDate: candidate, hour } = inBusinessTimeZone(base);
  if (hour >= 13 || isClosedDay(candidate)) {
    candidate.setUTCDate(candidate.getUTCDate() + 1);
  }
  while (isClosedDay(candidate)) {
    candidate.setUTCDate(candidate.getUTCDate() + 1);
  }
  return toYmd(candidate);
};
