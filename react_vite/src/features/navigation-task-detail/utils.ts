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
