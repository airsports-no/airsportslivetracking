import { formatDateKeyInZone, formatTimeInZone, formatWholeNumber, formatWindDirection, joinTmax, splitTmax } from './utils';

describe('formatTimeInZone', () => {
  it('formats an ISO time in the given time zone as HH:MM:SS', () => {
    expect(formatTimeInZone('2026-08-01T08:05:00Z', 'UTC')).toBe('08:05:00');
  });

  it('converts across time zones', () => {
    expect(formatTimeInZone('2026-08-01T08:05:00Z', 'Europe/Oslo')).toBe('10:05:00');
  });

  it('returns a dash for a missing or invalid value', () => {
    expect(formatTimeInZone(null, 'UTC')).toBe('-');
    expect(formatTimeInZone(undefined, 'UTC')).toBe('-');
    expect(formatTimeInZone('not-a-date', 'UTC')).toBe('-');
  });
});

describe('formatDateKeyInZone', () => {
  it('returns a stable YYYY-MM-DD key in the given time zone', () => {
    expect(formatDateKeyInZone('2026-08-01T23:30:00Z', 'UTC')).toBe('2026-08-01');
  });

  it('rolls over to the next day in a later time zone', () => {
    expect(formatDateKeyInZone('2026-08-01T23:30:00Z', 'Europe/Oslo')).toBe('2026-08-02');
  });
});

describe('formatWindDirection', () => {
  it('rounds and zero-pads to 3 digits', () => {
    expect(formatWindDirection(8)).toBe('008');
    expect(formatWindDirection(165.4)).toBe('165');
    expect(formatWindDirection(359.6)).toBe('360');
  });
});

describe('formatWholeNumber', () => {
  it('rounds to the nearest whole number', () => {
    expect(formatWholeNumber(74.6)).toBe('75');
    expect(formatWholeNumber(74.4)).toBe('74');
  });
});

describe('Tmax of 2.A1', () => {
  it('splits the stored seconds into minutes and seconds', () => {
    expect(splitTmax(754)).toEqual({ minutes: '12', seconds: '34' });
    expect(splitTmax(600)).toEqual({ minutes: '10', seconds: '0' });
  });

  it('shows no limit as empty fields', () => {
    expect(splitTmax(undefined)).toEqual({ minutes: '', seconds: '' });
    expect(splitTmax(0)).toEqual({ minutes: '', seconds: '' });
  });

  it('joins minutes and seconds into seconds, empty meaning no limit', () => {
    expect(joinTmax('12', '34')).toBe(754);
    expect(joinTmax('', '90')).toBe(90);
    expect(joinTmax('', '')).toBeNull();
    expect(joinTmax('0', '0')).toBeNull();
  });
});
