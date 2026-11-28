export const formatTimeInZone = (iso: string | null | undefined, timeZone: string): string => {
  if (!iso) return '-';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
};

export const formatDateKeyInZone = (iso: string, timeZone: string): string => {
  const date = new Date(iso);
  return new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).format(date);
};

export const formatDateHeadingInZone = (iso: string, timeZone: string): string =>
  new Intl.DateTimeFormat('en-US', { timeZone, weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).format(new Date(iso));

export const formatWindDirection = (degrees: number): string => String(Math.round(degrees)).padStart(3, '0');

export const formatWholeNumber = (value: number): string => String(Math.round(value));

/** Tmax (2.A1, the longest time allowed from SP to FP) is stored in seconds in task_config; the form takes minutes and seconds. */
export const CURVE_NAVIGATION_SUBTYPE = 'curve_navigation_time_estimation';

export const splitTmax = (seconds: unknown): { minutes: string; seconds: string } => {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total <= 0) return { minutes: '', seconds: '' };
  return { minutes: String(Math.floor(total / 60)), seconds: String(Math.round(total % 60)) };
};

/** The Tmax in seconds from the two form fields, null (no limit) when both are empty or zero. */
export const joinTmax = (minutes: string, seconds: string): number | null => {
  const total = (Number(minutes) || 0) * 60 + (Number(seconds) || 0);
  return total > 0 ? Math.round(total) : null;
};
