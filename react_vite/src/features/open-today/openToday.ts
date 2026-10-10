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

const PART_OPTIONS: Intl.DateTimeFormatOptions = {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
};

/** The pieces of an instant as seen in a time zone ("Sat", "10", "Oct", "10", "00"); falls back to the viewer's zone. */
const parts = (iso: string, timeZone: string) => {
    let formatter: Intl.DateTimeFormat;
    try {
        formatter = new Intl.DateTimeFormat('en-GB', { ...PART_OPTIONS, timeZone });
    } catch {
        formatter = new Intl.DateTimeFormat('en-GB', PART_OPTIONS);
    }
    const out: Record<string, string> = {};
    for (const p of formatter.formatToParts(new Date(iso))) out[p.type] = p.value;
    // Some ICU versions render midnight as "24".
    const hour = out.hour === '24' ? '00' : out.hour;
    return { date: `${out.weekday} ${out.day} ${out.month}`, time: `${hour}:${out.minute}` };
};

/**
 * The task's registration window with dates, in the venue's own time zone (what a pilot standing there needs):
 * "Sat 10 Oct 10:00 - 14:30" within one day, "Fri 9 Oct 08:00 - Sun 11 Oct 18:00" across days.
 */
export const formatWindow = (task: OpenRegistrationTask, timeZone: string): string => {
    const start = parts(task.start_time, timeZone);
    const finish = parts(task.finish_time, timeZone);
    return start.date === finish.date
        ? `${start.date} ${start.time} - ${finish.time}`
        : `${start.date} ${start.time} - ${finish.date} ${finish.time}`;
};

/** The browser's IANA time zone, so the server can decide what "today" means for this pilot. */
export const browserTimeZone = (): string | undefined => {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
        return undefined;
    }
};
