import { describe, expect, it } from 'vitest';
import { directionsUrl, filterGroups, formatWindow, groupByContest, hasLocation, mapUrl, OpenRegistrationTask, registerPath } from './openToday';

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

    it('filters by contest name or task name, case-insensitively', () => {
        const groups = groupByContest([
            task({ navigation_task_id: 10 }),
            task({ navigation_task_id: 11, navigation_task_name: 'Day 2' }),
            task({ contest_id: 2, contest_name: 'Poker Run', navigation_task_id: 20, navigation_task_name: 'Morning' }),
        ]);
        expect(filterGroups(groups, '  ')).toBe(groups);
        expect(filterGroups(groups, 'norweg').map((g) => g.tasks.length)).toEqual([2]); // contest match keeps all tasks
        const byTask = filterGroups(groups, 'DAY 2');
        expect(byTask.map((g) => g.tasks.map((x) => x.navigation_task_name))).toEqual([['Day 2']]);
        expect(filterGroups(groups, 'morning').map((g) => g.contestName)).toEqual(['Poker Run']);
        expect(filterGroups(groups, 'nothing')).toEqual([]);
    });

    it('shows the date once for a window inside one day, in the venue time zone', () => {
        // 08:00-12:30 UTC on Sat 10 Oct is 10:00-14:30 in Oslo (UTC+2 in October).
        expect(formatWindow(task({}), 'Europe/Oslo')).toBe('Sat 10 Oct 10:00 - 14:30');
        expect(formatWindow(task({}), 'UTC')).toBe('Sat 10 Oct 08:00 - 12:30');
    });

    it('shows both dates when the window spans several days', () => {
        const multi = task({ start_time: '2026-10-09T06:00:00Z', finish_time: '2026-10-11T16:00:00Z' });
        expect(formatWindow(multi, 'Europe/Oslo')).toBe('Fri 9 Oct 08:00 - Sun 11 Oct 18:00');
    });

    it('uses the venue day, not the UTC day, when deciding whether it is one day', () => {
        // 22:30 UTC Sat and 01:30 UTC Sun are 00:30 and 03:30 on Sunday in Oslo: one day there, two in UTC.
        const night = task({ start_time: '2026-10-10T22:30:00Z', finish_time: '2026-10-11T01:30:00Z' });
        expect(formatWindow(night, 'Europe/Oslo')).toBe('Sun 11 Oct 00:30 - 03:30');
        expect(formatWindow(night, 'UTC')).toBe('Sat 10 Oct 22:30 - Sun 11 Oct 01:30');
    });

    it('falls back gracefully on an unknown time zone', () => {
        expect(formatWindow(task({}), 'Not/AZone')).toMatch(/^\w{3} \d{1,2} \w{3} \d\d:\d\d - \d\d:\d\d$/);
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
