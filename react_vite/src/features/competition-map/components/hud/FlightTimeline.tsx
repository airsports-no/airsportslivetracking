import React, { useEffect, useMemo, useRef } from 'react';
import { Check, X } from 'lucide-react';
import { ScoreAnnotation, ScoreLogEntry, Waypoint } from '../../types';
import { shortScoreText } from '../../utils/scoreText';

interface Props {
    waypoints: Waypoint[];
    /** Required time per gate name (ISO); with an adaptive start only meaningful once the starting point is crossed. */
    gateTimes?: Record<string, string>;
    timesKnown: boolean;
    /** The selected contestant's log (the entries with points), without the gates the viewer may not see. */
    entries: ScoreLogEntry[];
    /**
     * Their annotations, which unlike the log the map receives also note every crossing without a time check
     * ("passing gate") and every miss; already limited to what has happened by the map's time and may be seen.
     */
    annotations: ScoreAnnotation[];
    /** Secret and unknown-leg gates may be listed (the task shows secrets and the viewer has them on). */
    showSecrets: boolean;
    /** The map's time (live: now, held back by any calculation delay; replay: the replay's time). */
    now: Date;
    timeZone?: string;
    pointsArePenalties: boolean;
    onSelectEntry: (entry: ScoreLogEntry) => void;
    onSelectAnnotation: (annotation: ScoreAnnotation) => void;
    onSelectGate: (waypoint: Waypoint) => void;
}

const NOT_GATES = new Set(['dummy', 'circle_center', 'route_to_sp', 'route_from_fp']);
const SECRET = new Set(['secret', 'ul']);

function clock(t: Date, timeZone?: string) {
    return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
}

function inMinutes(seconds: number) {
    const s = Math.max(0, Math.ceil(seconds));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

type Row =
    | { kind: 'gate'; waypoint: Waypoint; required?: Date; passed?: ScoreAnnotation; timing?: ScoreLogEntry; missed?: ScoreAnnotation; next: boolean }
    | { kind: 'event'; entry: ScoreLogEntry };

/**
 * The followed contestant's flight down the side panel: the gates in order with their required times, how each passed
 * gate went, the penalties in between, and the next gate highlighted, so the panel shows the flight as it unfolds next to
 * the ranking. Clicking a passed gate or a penalty shows it on the map (and in the replay); an upcoming gate centres the
 * map on it.
 */
export default function FlightTimeline({
    waypoints, gateTimes, timesKnown, entries, annotations, showSecrets, now, timeZone, pointsArePenalties,
    onSelectEntry, onSelectAnnotation, onSelectGate,
}: Props) {
    const rows = useMemo<Row[]>(() => {
        const gates = waypoints.filter(w => !NOT_GATES.has(w.type) && !(w as { on_curved_segment?: boolean }).on_curved_segment
            && (showSecrets || !SECRET.has(w.type)));
        const gateNames = new Set(gates.map(g => g.name));
        // Crossings and misses from the annotations ("passing gate ...", "adaptive start set ...", "missed ...").
        const passedBy = new Map<string, ScoreAnnotation>();
        const missedBy = new Map<string, ScoreAnnotation>();
        for (const a of annotations) {
            if (!gateNames.has(a.gate)) continue;
            if (/passing gate|adaptive start set/i.test(a.message) && !passedBy.has(a.gate)) passedBy.set(a.gate, a);
            else if (/\bmissed\b/i.test(a.message) && !missedBy.has(a.gate)) missedBy.set(a.gate, a);
        }
        // A timed gate's result in the log: its planned and actual time.
        const timingBy = new Map<string, ScoreLogEntry>();
        for (const e of entries) {
            if (gateNames.has(e.gate) && e.planned && e.actual && !timingBy.has(e.gate)) timingBy.set(e.gate, e);
        }
        // Penalties that are not a gate's own timing result (corridor, prohibited areas, ...) under the gate they belong to.
        const penaltiesBy = new Map<string, ScoreLogEntry[]>();
        for (const e of entries) {
            if (e.points === 0 || timingBy.get(e.gate) === e) continue;
            const list = penaltiesBy.get(e.gate) ?? [];
            list.push(e);
            penaltiesBy.set(e.gate, list);
        }
        let nextFound = false;
        const out: Row[] = [];
        for (const g of gates) {
            const timing = timingBy.get(g.name);
            const missed = missedBy.get(g.name);
            const passed = passedBy.get(g.name) ?? (timing ? annotations.find(a => a.score_log_entry === timing.id) : undefined);
            const done = !!passed || !!timing || !!missed;
            const next = !done && !nextFound;
            if (next) nextFound = true;
            const iso = timesKnown && g.time_check ? gateTimes?.[g.name] : undefined;
            out.push({ kind: 'gate', waypoint: g, required: iso ? new Date(iso) : undefined, passed, timing, missed, next });
            for (const e of penaltiesBy.get(g.name) ?? []) out.push({ kind: 'event', entry: e });
        }
        return out;
    }, [waypoints, gateTimes, timesKnown, entries, annotations, showSecrets]);

    // Keep the next gate in view as the flight moves on.
    const nextRef = useRef<HTMLLIElement>(null);
    const nextGate = rows.find((r): r is Extract<Row, { kind: 'gate' }> => r.kind === 'gate' && r.next);
    const nextName = nextGate?.waypoint.name ?? null;
    useEffect(() => {
        nextRef.current?.scrollIntoView({ block: 'nearest' });
    }, [nextName]);

    if (rows.length === 0) return null;

    return (
        <ol className="flex flex-col pb-2" aria-label="Flight">
            {!timesKnown && (
                <li className="hud-label px-4 pb-2">Gate times are set when the contestant crosses the starting point.</li>
            )}
            {rows.map((r, i) => {
                if (r.kind === 'event') {
                    const penalty = pointsArePenalties ? r.entry.points > 0 : r.entry.points < 0;
                    return (
                        <li key={`e${r.entry.id}`} tabIndex={0} role="button"
                            onClick={() => onSelectEntry(r.entry)}
                            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelectEntry(r.entry); } }}
                            className="hud-row grid grid-cols-[1.25rem_1fr_auto] gap-x-2 pl-9 pr-3 py-1 items-baseline">
                            <span aria-hidden="true" />
                            <span className="text-xs hud-muted truncate" title={r.entry.message}>{shortScoreText(r.entry.message)}</span>
                            <span className="hud-figure text-sm" style={{ color: penalty ? 'var(--hud-red)' : 'var(--hud-ok)' }}>
                                {r.entry.points > 0 ? '+' : ''}{r.entry.points.toFixed(0)}
                            </span>
                        </li>
                    );
                }
                const { waypoint, required, passed, timing, missed, next } = r;
                const crossed = !!passed || !!timing;
                const offset = timing && waypoint.time_check && timing.planned && timing.actual
                    ? Math.round((new Date(timing.actual).getTime() - new Date(timing.planned).getTime()) / 1000) : null;
                const select = () => (timing ? onSelectEntry(timing) : passed ? onSelectAnnotation(passed)
                    : missed ? onSelectAnnotation(missed) : onSelectGate(waypoint));
                return (
                    <li key={`g${waypoint.name}${i}`} ref={next ? nextRef : undefined} tabIndex={0} role="button" aria-current={next ? 'step' : undefined}
                        onClick={select}
                        onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(); } }}
                        className={`hud-row grid grid-cols-[1.25rem_1fr_auto] gap-x-2 px-3 py-1.5 items-center ${!crossed && !missed && !next ? 'opacity-70' : ''}`}>
                        <span className="flex justify-center" aria-hidden="true">
                            {crossed ? <Check size={14} style={{ color: 'var(--hud-ok)' }} />
                                : missed ? <X size={14} style={{ color: 'var(--hud-red)' }} />
                                : <span className="w-2 h-2 rounded-full" style={{ background: next ? 'var(--hud-accent)' : 'var(--hud-line)' }} />}
                        </span>
                        <span className="min-w-0 flex items-baseline gap-2">
                            <span className="font-semibold text-sm truncate">{waypoint.name}</span>
                            {required && <span className="hud-figure hud-muted text-sm font-semibold">{clock(required, timeZone)}</span>}
                        </span>
                        <span className="hud-figure text-sm text-right">
                            {missed ? <span style={{ color: 'var(--hud-red)' }}>Missed</span>
                                // Green within 2 s, the apps' "on time"; the points, if any, are in the log.
                                : offset !== null ? <span style={{ color: Math.abs(offset) <= 2 ? 'var(--hud-ok)' : 'var(--hud-warn)' }}>{offset > 0 ? '+' : ''}{offset} s</span>
                                : next && required ? <span style={{ color: 'var(--hud-accent)' }}>{required > now ? `in ${inMinutes((required.getTime() - now.getTime()) / 1000)}` : 'now'}</span>
                                : null}
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}
