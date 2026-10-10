import { describe, expect, it } from 'vitest';
import { directionsUrl, formatWindow, groupByContest, hasLocation, mapUrl, OpenRegistrationTask, registerPath } from './openToday';

const task = (over: Partial<OpenRegistrationTask>): OpenRegistrationTask => ({
    contest_id: 1,
    contest_name: 'Norwegian Cup',
    country: 'NO',
    time_zone: 'Europe/Oslo',
    latitude: 59.9,
    longitude: 10.7,
    navigation_task_id: 10,
    navigation_task_name: 'Day 1',
    start_time: '2026-10-10T08:00:00Z',
    finish_time: '2026-10-10T12:30:00Z',
    is_open_now: false,
    ...over,
});

describe('open today helpers', () => {
    it('groups tasks by contest and keeps the server order', () => {
        const groups = groupByContest([
            task({ navigation_task_id: 10 }),
            task({ navigation_task_id: 11, navigation_task_name: 'Day 2' }),
            task({ contest_id: 2, contest_name: 'Poker Run', navigation_task_id: 20 }),
        ]);
        expect(groups.map((g) => [g.contestName, g.tasks.length])).toEqual([['Norwegian Cup', 2], ['Poker Run', 1]]);
    });

    it('formats the window in the venue time zone, not the viewer\'s', () => {
        // 08:00-12:30 UTC is 10:00-14:30 in Oslo (UTC+2 in October).
        expect(formatWindow(task({}), 'Europe/Oslo')).toBe('10:00 - 14:30');
        expect(formatWindow(task({}), 'UTC')).toBe('08:00 - 12:30');
    });

    it('falls back gracefully on an unknown time zone', () => {
        expect(formatWindow(task({}), 'Not/AZone')).toMatch(/^\d\d:\d\d - \d\d:\d\d$/);
    });

    it('knows when a venue has no location', () => {
        expect(hasLocation({ latitude: 59.9, longitude: 10.7 })).toBe(true);
        expect(hasLocation({ latitude: null, longitude: null })).toBe(false);
        expect(hasLocation({ latitude: 0, longitude: 0 })).toBe(true); // 0 is a real number; the server sends null for "unknown"
    });

    it('builds the maps and registration links', () => {
        expect(directionsUrl(59.9, 10.7)).toBe('https://www.google.com/maps/dir/?api=1&destination=59.9,10.7');
        expect(mapUrl(59.9, 10.7)).toBe('https://www.openstreetmap.org/?mlat=59.9&mlon=10.7#map=13/59.9/10.7');
        expect(registerPath(1, 10)).toBe('/schedule-flight?contestId=1&navigationTaskId=10');
    });
});
