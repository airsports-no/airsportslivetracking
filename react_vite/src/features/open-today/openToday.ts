/** Tasks that can be registered for (self registration) today, as returned by contests/open_registration_today/. */
export interface OpenRegistrationTask {
    contest_id: number;
    contest_name: string;
    country: string;
    time_zone: string;
    latitude: number | null;
    longitude: number | null;
    navigation_task_id: number;
    navigation_task_name: string;
    start_time: string;
    finish_time: string;
    is_open_now: boolean;
}

export interface ContestGroup {
    contestId: number;
    contestName: string;
    country: string;
    timeZone: string;
    latitude: number | null;
    longitude: number | null;
    tasks: OpenRegistrationTask[];
}

/** One card per contest, in the order the server sent them (contest name, then start time). */
export const groupByContest = (tasks: OpenRegistrationTask[]): ContestGroup[] => {
    const groups = new Map<number, ContestGroup>();
    for (const task of tasks) {
        let group = groups.get(task.contest_id);
        if (!group) {
            group = {
                contestId: task.contest_id,
                contestName: task.contest_name,
                country: task.country,
                timeZone: task.time_zone,
                latitude: task.latitude,
                longitude: task.longitude,
                tasks: [],
            };
            groups.set(task.contest_id, group);
        }
        group.tasks.push(task);
    }
    return Array.from(groups.values());
};

/**
 * Case-insensitive search on contest name or task name. A matching contest keeps all its tasks; otherwise only the
 * matching tasks are kept, and contests left without tasks are dropped.
 */
export const filterGroups = (groups: ContestGroup[], query: string): ContestGroup[] => {
    const q = query.trim().toLowerCase();
    if (!q) return groups;
    const result: ContestGroup[] = [];
    for (const group of groups) {
        if (group.contestName.toLowerCase().includes(q)) {
            result.push(group);
            continue;
        }
        const tasks = group.tasks.filter((t) => t.navigation_task_name.toLowerCase().includes(q));
        if (tasks.length > 0) result.push({ ...group, tasks });
    }
    return result;
};

export const hasLocation = (g: { latitude: number | null; longitude: number | null }): boolean =>
    g.latitude !== null && g.longitude !== null;

/** Opens turn-by-turn directions in the device's maps app or the browser. */
export const directionsUrl = (latitude: number, longitude: number): string =>
    `https://www.google.com/maps/dir/?api=1&destination=${latitude},${longitude}`;

export const mapUrl = (latitude: number, longitude: number): string =>
    `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=13/${latitude}/${longitude}`;

/** The page where the pilot registers a flight for this task. */
export const registerPath = (contestId: number, navigationTaskId: number): string =>
    `/schedule-flight?contestId=${contestId}&navigationTaskId=${navigationTaskId}`;

const time = (iso: string, timeZone: string): string => {
    try {
        return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone }).format(new Date(iso));
    } catch {
        return new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(iso));
    }
};

/** "10:00 - 14:30" in the venue's own time zone, which is what a pilot standing there needs. */
export const formatWindow = (task: OpenRegistrationTask, timeZone: string): string =>
    `${time(task.start_time, timeZone)} - ${time(task.finish_time, timeZone)}`;

/** The browser's IANA time zone, so the server can decide what "today" means for this pilot. */
export const browserTimeZone = (): string | undefined => {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
        return undefined;
    }
};
