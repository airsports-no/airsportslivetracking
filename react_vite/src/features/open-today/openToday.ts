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
    simulator_policy?: 'not_allowed' | 'allowed' | 'simulator_only';
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

/** Where the user is, when the mobile app told the page (see userLocationFromUrl). */
export interface Coordinates {
    latitude: number;
    longitude: number;
}

const toCoordinates = (lat: string | null, lon: string | null): Coordinates | null => {
    if (lat === null || lon === null || lat.trim() === '' || lon.trim() === '') return null;
    const latitude = Number(lat);
    const longitude = Number(lon);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    if (Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
    return { latitude, longitude };
};

/**
 * The user's position as passed by the mobile app: `#lat=59.9&lon=10.7` in the address (a fragment is never sent to the
 * server, so the location stays on the phone), or the same as query parameters. Null when absent or not valid.
 */
export const userLocationFromUrl = (search: string, hash: string): Coordinates | null => {
    const fromHash = new URLSearchParams(hash.replace(/^#/, ''));
    const fromQuery = new URLSearchParams(search);
    return (
        toCoordinates(fromHash.get('lat'), fromHash.get('lon')) ?? toCoordinates(fromQuery.get('lat'), fromQuery.get('lon'))
    );
};

const EARTH_RADIUS_KM = 6371.0088;

/** Great-circle distance in kilometres (haversine). */
export const distanceKm = (a: Coordinates, b: Coordinates): number => {
    const rad = (degrees: number) => (degrees * Math.PI) / 180;
    const dLat = rad(b.latitude - a.latitude);
    const dLon = rad(b.longitude - a.longitude);
    const h =
        Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
};

/** A group with its distance from the user, or null when the venue has no published location. */
export type GroupWithDistance = ContestGroup & { distanceKm: number | null };

/**
 * The groups nearest to the user first. Venues without a location go last, in the order the server sent them; so do all
 * groups when the user's location is not known (then the distance is null everywhere and the order is unchanged).
 */
export const sortByDistance = (groups: ContestGroup[], here: Coordinates | null): GroupWithDistance[] => {
    const withDistance = groups.map((group, index) => ({
        group: {
            ...group,
            distanceKm:
                here && group.latitude !== null && group.longitude !== null
                    ? distanceKm(here, { latitude: group.latitude, longitude: group.longitude })
                    : null,
        } as GroupWithDistance,
        index,
    }));
    if (!here) return withDistance.map((item) => item.group);
    return withDistance
        .sort((x, y) => {
            const dx = x.group.distanceKm;
            const dy = y.group.distanceKm;
            if (dx === null && dy === null) return x.index - y.index;
            if (dx === null) return 1;
            if (dy === null) return -1;
            return dx - dy || x.index - y.index;
        })
        .map((item) => item.group);
};

/** "850 m", "4.2 km", "126 km". */
export const formatDistance = (km: number): string => {
    if (km < 1) return `${Math.max(10, Math.round((km * 1000) / 10) * 10)} m`;
    if (km < 10) return `${km.toFixed(1)} km`;
    return `${Math.round(km)} km`;
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
