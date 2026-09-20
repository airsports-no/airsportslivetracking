import { UpcomingContestant } from './api';

export type UpcomingGrouping = 'day' | 'week' | 'month';

export interface UpcomingGroup {
    key: string;
    label: string;
    sortDate: Date;
    contestants: UpcomingContestant[];
}

const startOfWeek = (date: Date): Date => {
    const result = new Date(date);
    const day = result.getDay(); // 0 = Sunday
    const diffToMonday = (day + 6) % 7;
    result.setDate(result.getDate() - diffToMonday);
    result.setHours(0, 0, 0, 0);
    return result;
};

const dayFormatter = new Intl.DateTimeFormat(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
const monthFormatter = new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' });

const groupKeyAndLabel = (takeoffTime: Date, grouping: UpcomingGrouping): { key: string; label: string; sortDate: Date } => {
    if (grouping === 'day') {
        const start = new Date(takeoffTime);
        start.setHours(0, 0, 0, 0);
        return { key: start.toISOString(), label: dayFormatter.format(start), sortDate: start };
    }
    if (grouping === 'week') {
        const start = startOfWeek(takeoffTime);
        const end = new Date(start);
        end.setDate(end.getDate() + 6);
        const label = `Week of ${dayFormatter.format(start)} – ${dayFormatter.format(end)}`;
        return { key: start.toISOString(), label, sortDate: start };
    }
    const start = new Date(takeoffTime.getFullYear(), takeoffTime.getMonth(), 1);
    return { key: start.toISOString(), label: monthFormatter.format(start), sortDate: start };
};

export const groupUpcomingContestants = (
    contestants: UpcomingContestant[],
    grouping: UpcomingGrouping,
): UpcomingGroup[] => {
    const groups = new Map<string, UpcomingGroup>();
    for (const contestant of contestants) {
        const takeoffTime = new Date(contestant.takeoff_time);
        const { key, label, sortDate } = groupKeyAndLabel(takeoffTime, grouping);
        let group = groups.get(key);
        if (!group) {
            group = { key, label, sortDate, contestants: [] };
            groups.set(key, group);
        }
        group.contestants.push(contestant);
    }
    return Array.from(groups.values()).sort((a, b) => a.sortDate.getTime() - b.sortDate.getTime());
};
