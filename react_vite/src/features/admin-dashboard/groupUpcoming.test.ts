import { describe, expect, it } from 'vitest';
import { groupUpcomingContestants } from './groupUpcoming';
import { UpcomingContestant } from './api';

const makeContestant = (id: number, takeoffTime: string): UpcomingContestant => ({
    id,
    contest_id: 1,
    contest_name: 'Contest',
    navigation_task_id: 1,
    navigation_task_name: 'Task',
    team: 'Team',
    aeroplane: 'LN-TEST',
    takeoff_time: takeoffTime,
    contest_time_zone: 'Europe/Oslo',
});

describe('groupUpcomingContestants', () => {
    it('groups by day and sorts groups chronologically', () => {
        const contestants = [
            makeContestant(1, '2026-09-20T10:00:00Z'),
            makeContestant(2, '2026-09-19T08:00:00Z'),
            makeContestant(3, '2026-09-19T14:00:00Z'),
        ];

        const groups = groupUpcomingContestants(contestants, 'day');

        expect(groups).toHaveLength(2);
        expect(groups[0].contestants.map((c) => c.id).sort()).toEqual([2, 3]);
        expect(groups[1].contestants.map((c) => c.id)).toEqual([1]);
    });

    it('groups by week starting Monday', () => {
        // 2026-09-14 is a Monday, 2026-09-21 is the following Monday.
        const contestants = [
            makeContestant(1, '2026-09-14T09:00:00Z'),
            makeContestant(2, '2026-09-20T09:00:00Z'), // Sunday, same week as the 14th
            makeContestant(3, '2026-09-21T09:00:00Z'), // Next week
        ];

        const groups = groupUpcomingContestants(contestants, 'week');

        expect(groups).toHaveLength(2);
        expect(groups[0].contestants.map((c) => c.id).sort()).toEqual([1, 2]);
        expect(groups[1].contestants.map((c) => c.id)).toEqual([3]);
    });

    it('groups by month', () => {
        const contestants = [
            makeContestant(1, '2026-09-01T09:00:00Z'),
            makeContestant(2, '2026-09-30T09:00:00Z'),
            makeContestant(3, '2026-10-01T09:00:00Z'),
        ];

        const groups = groupUpcomingContestants(contestants, 'month');

        expect(groups).toHaveLength(2);
        expect(groups[0].contestants.map((c) => c.id).sort()).toEqual([1, 2]);
        expect(groups[1].contestants.map((c) => c.id)).toEqual([3]);
    });

    it('returns no groups for an empty list', () => {
        expect(groupUpcomingContestants([], 'day')).toEqual([]);
    });
});
