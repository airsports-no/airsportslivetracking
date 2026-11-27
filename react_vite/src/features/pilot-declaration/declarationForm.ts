// The logic of the pilot's declaration page without any rendering: what the form asks for is read from the `form` the server
// sends, so nothing here knows a task type. Times are entered as time after the start point (minutes and seconds) and
// always sent as seconds with time_reference "start_point".
import { moveItem } from '../scheduling/declarationSequences';
import { DeclarationForm, DeclarationNeed, DeclarationStatus, FlightOrderStatus, PilotDeclaration } from './types';

export type TimeEntry = { minutes: string; seconds: string };

export type PilotFormState = {
    times: Record<string, TimeEntry>;
    /** The points chosen between the fixed points of the sequence, one list for each gap (see sequenceShape) */
    lanes: string[][];
    period: TimeEntry;
    fuelMinutes: string;
};

export const emptyEntry = (): TimeEntry => ({ minutes: '', seconds: '' });

export const timePointNames = (form: DeclarationForm): string[] =>
    form.declares_times && form.time_key ? form.time_points ?? form.compulsory_points ?? [] : [];

export const asksForSequence = (form: DeclarationForm): boolean => Boolean(form.mandatory_points?.length || form.targets?.length);

/** The points that can be put into the sequence */
export const sequenceOptions = (form: DeclarationForm): string[] => form.turnpoints ?? form.targets ?? [];

/** The text of an entry of minutes and seconds is a whole number of seconds, or null when it is empty or not valid */
export const entrySeconds = (entry: TimeEntry): number | null => {
    const minutes = entry.minutes.trim();
    const seconds = entry.seconds.trim();
    if (minutes === '' && seconds === '') return null;
    if (!/^\d*$/.test(minutes) || !/^\d*$/.test(seconds)) return null;
    const secondsPart = seconds === '' ? 0 : Number(seconds);
    if (secondsPart > 59) return null;
    return (minutes === '' ? 0 : Number(minutes)) * 60 + secondsPart;
};

export const isEntryFilled = (entry: TimeEntry | undefined): boolean => Boolean(entry && (entry.minutes.trim() || entry.seconds.trim()));

export const secondsToEntry = (total: unknown): TimeEntry => {
    const value = typeof total === 'string' ? Number(total) : total;
    if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return emptyEntry();
    const whole = Math.round(value);
    return { minutes: String(Math.floor(whole / 60)), seconds: String(whole % 60) };
};

/** "12:30" */
export const formatEntry = (entry: TimeEntry): string => {
    const total = entrySeconds(entry);
    if (total === null) return '';
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
};

/** The clock time of [offsetSeconds] after the start point in the contest's time zone ("10:12:30"), '' when it cannot be told */
export const clockTime = (startPointTime: string | null | undefined, offsetSeconds: number | null, timeZone: string): string => {
    if (!startPointTime || offsetSeconds === null) return '';
    const start = new Date(startPointTime).getTime();
    if (Number.isNaN(start)) return '';
    try {
        return new Intl.DateTimeFormat('en-GB', {
            timeZone, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
        }).format(new Date(start + offsetSeconds * 1000));
    } catch {
        return '';
    }
};

/** "09:55 on 1 August 2026" in the contest's time zone */
export const clockAndDate = (iso: string, timeZone: string): string => {
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    try {
        const time = new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
        const day = new Intl.DateTimeFormat('en-GB', { timeZone, day: 'numeric', month: 'long', year: 'numeric' }).format(date);
        return `${time} on ${day}`;
    } catch {
        return '';
    }
};

export const cutoffSentence = (status: DeclarationStatus, timeZone: string): string | null => {
    if (!status.edit_until || !status.can_edit) return null;
    const when = clockAndDate(status.edit_until, timeZone);
    return when ? `You can change this until ${when} (${timeZone} time).` : null;
};

// ---- Sequences -------------------------------------------------------------------------------------------------------

export type SequenceShape = {
    /** The fixed points of the sequence, in order */
    anchors: string[];
    /** Whether points can also be flown before the first and after the last fixed point */
    openEnds: boolean;
};

/**
 * The fixed points of the sequence: SP, MP and FP of a contract task (points go between them) or the compulsory points of a
 * hunt, in the order of the times given (points go between them and around them).
 */
export const sequenceShape = (form: DeclarationForm, times: Record<string, TimeEntry>): SequenceShape => {
    if (form.mandatory_points?.length) return { anchors: form.mandatory_points, openEnds: false };
    const names = form.compulsory_points ?? [];
    const timed = names
        .map((name, index) => ({ name, index, seconds: entrySeconds(times[name] ?? emptyEntry()) }))
        .sort((a, b) => {
            if (a.seconds === null && b.seconds === null) return a.index - b.index;
            if (a.seconds === null) return 1;
            if (b.seconds === null) return -1;
            return a.seconds - b.seconds || a.index - b.index;
        });
    return { anchors: timed.map((item) => item.name), openEnds: true };
};

export const laneCount = (shape: SequenceShape): number => (shape.openEnds ? shape.anchors.length + 1 : Math.max(shape.anchors.length - 1, 0));

/** The label of lane [index]: where in the flight its points are flown */
export const laneLabel = (shape: SequenceShape, index: number): string => {
    const { anchors, openEnds } = shape;
    if (openEnds) {
        if (anchors.length === 0) return 'Your points, in order';
        if (index === 0) return `Before ${anchors[0]}`;
        if (index === anchors.length) return `After ${anchors[anchors.length - 1]}`;
        return `Between ${anchors[index - 1]} and ${anchors[index]}`;
    }
    return index === 0 && anchors.length === 3 ? `Before ${anchors[1]}` : `Between ${anchors[index]} and ${anchors[index + 1]}`;
};

/** The declared sequence as the lists between the fixed points */
export const splitSequence = (sequence: unknown, shape: SequenceShape, options: string[]): string[][] => {
    const lanes: string[][] = Array.from({ length: laneCount(shape) }, () => []);
    if (!Array.isArray(sequence)) return lanes;
    const optionSet = new Set(options);
    const anchorSet = new Set(shape.anchors);
    let seen = 0;
    for (const item of sequence) {
        if (typeof item !== 'string') continue;
        if (anchorSet.has(item)) {
            seen += 1;
        } else if (optionSet.has(item)) {
            const lane = shape.openEnds ? seen : seen - 1;
            if (lane >= 0 && lane < lanes.length && !lanes.some((points) => points.includes(item))) lanes[lane].push(item);
        }
    }
    return lanes;
};

export const buildSequence = (shape: SequenceShape, lanes: string[][]): string[] => {
    const result: string[] = [];
    const { anchors, openEnds } = shape;
    if (openEnds) {
        result.push(...(lanes[0] ?? []));
        anchors.forEach((anchor, index) => result.push(anchor, ...(lanes[index + 1] ?? [])));
    } else {
        anchors.forEach((anchor, index) => {
            result.push(anchor);
            if (index < anchors.length - 1) result.push(...(lanes[index] ?? []));
        });
    }
    return result;
};

/** Up and down by one place within a lane; the first cannot go up and the last cannot go down */
export const moveInLane = (lanes: string[][], lane: number, from: number, direction: -1 | 1): string[][] => {
    const to = from + direction;
    if (!lanes[lane] || to < 0 || to >= lanes[lane].length) return lanes;
    return lanes.map((points, index) => (index === lane ? moveItem(points, from, to) : points));
};

export const addToLane = (lanes: string[][], lane: number, point: string): string[][] =>
    lanes.some((points) => points.includes(point)) ? lanes : lanes.map((points, index) => (index === lane ? [...points, point] : points));

export const removeFromLane = (lanes: string[][], lane: number, point: string): string[][] =>
    lanes.map((points, index) => (index === lane ? points.filter((item) => item !== point) : points));

/** Keeps the lanes valid when the number of lanes changes (the times of a hunt do not change it, but a new form might) */
export const fitLanes = (lanes: string[][], count: number): string[][] =>
    Array.from({ length: count }, (_, index) => lanes[index] ?? []);

// ---- From the server's declaration to the form and back --------------------------------------------------------------

/** The times of the stored declaration as minutes and seconds after the start point */
const storedOffsets = (form: DeclarationForm, payload: Record<string, any>): Record<string, number> => {
    const key = form.time_key;
    const result: Record<string, number> = {};
    if (!key) return result;
    if (payload.time_reference === 'start_point' && payload.relative_times && typeof payload.relative_times === 'object') {
        for (const [name, seconds] of Object.entries(payload.relative_times as Record<string, unknown>)) {
            if (typeof seconds === 'number') result[name] = seconds;
        }
        return result;
    }
    // A declaration in clock times (an organiser's): its distance from the start point, when that is known
    const start = form.start_point_time ? new Date(form.start_point_time).getTime() : NaN;
    const stored = payload[key];
    if (Number.isNaN(start) || !stored || typeof stored !== 'object') return result;
    for (const [name, value] of Object.entries(stored as Record<string, unknown>)) {
        const time = typeof value === 'string' ? new Date(value).getTime() : NaN;
        if (!Number.isNaN(time) && time >= start) result[name] = Math.round((time - start) / 1000);
    }
    return result;
};

export const initialFormState = (declaration: PilotDeclaration): PilotFormState => {
    const { form } = declaration;
    const payload = declaration.declaration_payload || {};
    const offsets = storedOffsets(form, payload);
    const times: Record<string, TimeEntry> = {};
    for (const name of timePointNames(form)) {
        times[name] = name in offsets ? secondsToEntry(offsets[name]) : emptyEntry();
    }
    const shape = sequenceShape(form, times);
    const lanes = asksForSequence(form)
        ? splitSequence(payload.declared_sequence, shape, sequenceOptions(form))
        : [];
    const endurance = payload.fuel_metadata?.declared_endurance_minutes;
    return {
        times,
        lanes,
        period: form.asks_for_period ? secondsToEntry(payload.declared_t_seconds) : emptyEntry(),
        fuelMinutes: endurance != null ? String(endurance) : '',
    };
};

export type BuiltDeclaration = { payload: Record<string, unknown>; problems: string[] };

/** The declaration to send, or what is wrong with the entries (nothing is sent then, and nothing is lost) */
export const buildDeclarationPayload = (form: DeclarationForm, state: PilotFormState): BuiltDeclaration => {
    const payload: Record<string, unknown> = {};
    const problems: string[] = [];
    const names = timePointNames(form);
    if (names.length > 0 && form.time_key) {
        const given: Record<string, number> = {};
        for (const name of names) {
            const entry = state.times[name];
            if (!isEntryFilled(entry)) continue;
            const seconds = entrySeconds(entry);
            if (seconds === null) problems.push(`The time for ${name} must be minutes and seconds, with seconds from 0 to 59.`);
            else given[name] = seconds;
        }
        if (Object.keys(given).length > 0) {
            payload[form.time_key] = given;
            payload.time_reference = 'start_point';
        }
    }
    if (asksForSequence(form)) {
        const shape = sequenceShape(form, state.times);
        const sequence = buildSequence(shape, fitLanes(state.lanes, laneCount(shape)));
        // A hunt without chosen targets declares no sequence at all; a contract task always has SP, MP and FP
        if (form.mandatory_points?.length || state.lanes.some((points) => points.length > 0)) payload.declared_sequence = sequence;
    }
    if (form.asks_for_period && isEntryFilled(state.period)) {
        const seconds = entrySeconds(state.period);
        if (seconds === null || seconds <= 0) problems.push('Your period T must be minutes and seconds, longer than zero.');
        else payload.declared_t_seconds = seconds;
    }
    if (form.asks_for_fuel_endurance && state.fuelMinutes.trim()) {
        const minutes = Number(state.fuelMinutes);
        if (!Number.isFinite(minutes) || minutes <= 0) problems.push('Your fuel endurance must be a number of minutes.');
        else payload.fuel_metadata = { declared_endurance_minutes: minutes };
    }
    return { payload, problems };
};

// ---- Words for the status --------------------------------------------------------------------------------------------

/** What the own-flights list says about the declaration of a flight: null when there is nothing to declare */
export const declarationLabel = (status: Pick<DeclarationStatus, 'need' | 'state' | 'can_edit'> | null | undefined): { text: string; tone: 'warning' | 'success' | 'neutral' | 'info' } | null => {
    if (!status || status.need === 'not_needed') return null;
    if (!status.can_edit) return { text: 'Declaration closed', tone: 'neutral' };
    if (status.state === 'complete') return { text: 'Declaration complete', tone: 'success' };
    if (status.state === 'incomplete') return { text: 'Declaration saved, not finished', tone: 'warning' };
    return status.need === 'required' ? { text: 'Declaration needed', tone: 'warning' } : { text: 'Declaration optional', tone: 'info' };
};

export const declarationActionText = (status: Pick<DeclarationStatus, 'need' | 'state' | 'can_edit'>): string => {
    if (!status.can_edit) return 'View declaration';
    return status.state === 'missing' ? 'Make declaration' : 'Edit declaration';
};

export const needsDeclarationStep = (need: DeclarationNeed | undefined | null): boolean => need === 'required' || need === 'optional';

/** Whether the page asks the server again: only while the flight order is being made */
export const shouldPoll = (status: FlightOrderStatus | null | undefined): boolean => status?.state === 'being_made';
