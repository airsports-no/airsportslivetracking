import React, { useEffect, useMemo, useRef } from 'react';
import { Check, X } from 'lucide-react';
import { GateResult, ScoreAnnotation, ScoreLogEntry, Waypoint } from '../../types';
import { shortScoreText } from '../../utils/scoreText';
import { gateStates, inCrossingOrder } from '../../utils/gateStates';

interface Props {
    /** Each gate of the route and how it went (the score data's gate_results). */
    gateResults: GateResult[];
    waypoints: Waypoint[];
    /** With an adaptive start the required times are only known once the starting point is crossed. */
    timesKnown: boolean;
    /** The selected contestant's log (the entries with points), without the gates the viewer may not see. */
    entries: ScoreLogEntry[];
    /** Their annotations: a crossed gate's click shows its note on the map. */
    annotations: ScoreAnnotation[];
    /** Secret and unknown-leg gates may be listed (the task shows secrets and the viewer has them on). */
    showSecrets: boolean;
    /** The map's time (live: now, held back by any calculation delay; replay: the replay's time). */
    now: Date;
    /** Misses count as soon as the server reports them: live, and at the end of a replay (see gateStates). */
    missesKnown: boolean;
    /** The pilot chooses the order (turnpoint hunt): gates in the order crossed, none marked next. */
    crossingOrder?: boolean;
    timeZone?: string;
    pointsArePenalties: boolean;
    onSelectEntry: (entry: ScoreLogEntry) => void;
    onSelectAnnotation: (annotation: ScoreAnnotation) => void;
    onSelectGate: (waypoint: Waypoint) => void;
}

function clock(t: Date, timeZone?: string) {
    return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
}

function inMinutes(seconds: number) {
    const s = Math.max(0, Math.ceil(seconds));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

/**
 * The followed contestant's flight down the side panel: the gates in order with their required times, how each passed
 * gate went, the penalties in between, and the next gate highlighted, so the panel shows the flight as it unfolds next to
 * the ranking. Clicking a passed gate or a penalty shows it on the map (and in the replay); an upcoming gate centres the
 * map on it.
 */
export default function FlightTimeline({
    gateResults, waypoints, timesKnown, entries, annotations, showSecrets, now, missesKnown, crossingOrder = false, timeZone, pointsArePenalties,
    onSelectEntry, onSelectAnnotation, onSelectGate,
}: Props) {
    const rows = useMemo(() => {
        const visible = gateResults.filter(r => showSecrets || !r.hidden);
        const ordered = crossingOrder
            ? inCrossingOrder(visible, now, missesKnown)
            : gateStates(visible, now, missesKnown).map((state, i) => ({ result: visible[i], state }));
        // Penalties that are not a gate's own timing result (corridor, prohibited areas, ...) under the gate they belong to.
        const penaltiesBy = new Map<string, ScoreLogEntry[]>();
        for (const e of entries) {
            // A gate's own timing result and its miss show on the gate's row.
            if (e.points === 0 || (e.planned && e.actual) || e.message.startsWith('missing gate')) continue;
            const list = penaltiesBy.get(e.gate) ?? [];
            list.push(e);
            penaltiesBy.set(e.gate, list);
        }
        return ordered.map(({ result, state }) => ({ result, state, penalties: penaltiesBy.get(result.gate) ?? [] }));
    }, [gateResults, entries, showSecrets, now, missesKnown, crossingOrder]);

    // Keep the next gate in view as the flight moves on.
    const nextRef = useRef<HTMLLIElement>(null);
    const nextName = rows.find(r => r.state === 'next')?.result.gate ?? null;
    useEffect(() => {
        nextRef.current?.scrollIntoView({ block: 'nearest' });
    }, [nextName]);

    if (rows.length === 0) return null;

    return (
        <ol className="flex flex-col pb-2" aria-label="Flight">
            {!timesKnown && (
                <li className="hud-label px-4 pb-2">Gate times are set when the contestant crosses the starting point.</li>
            )}
            {rows.map(({ result, state, penalties }, i) => {
                const crossed = state === 'crossed';
                const missed = state === 'missed';
                const next = state === 'next';
                const required = timesKnown && result.time_check && result.planned ? new Date(result.planned) : null;
                const offset = crossed ? result.offset_seconds : null;
                const timing = entries.find(e => e.gate === result.gate && e.planned && e.actual);
                const note = annotations.find(a => a.gate === result.gate);
                const waypoint = waypoints.find(w => w.name === result.gate);
                const select = () => {
                    if ((crossed || missed) && timing) onSelectEntry(timing);
                    else if ((crossed || missed) && note) onSelectAnnotation(note);
                    else if (waypoint) onSelectGate(waypoint);
                };
                return (
                    <React.Fragment key={`${result.gate}${i}`}>
                        <li ref={next ? nextRef : undefined} tabIndex={0} role="button" aria-current={next ? 'step' : undefined}
                            title={crossed || missed ? `Show ${result.gate} on the map and in the replay` : `Show ${result.gate} on the map`}
                            onClick={select}
                            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); select(); } }}
                            className={`hud-row grid grid-cols-[1.25rem_1fr_auto] gap-x-2 px-3 py-1.5 items-center ${state === 'ahead' ? 'opacity-70' : ''}`}>
                            <span className="flex justify-center" aria-hidden="true">
                                {crossed ? <Check size={14} style={{ color: 'var(--hud-ok)' }} />
                                    : missed ? <X size={14} style={{ color: 'var(--hud-red)' }} />
                                    : <span className="w-2 h-2 rounded-full" style={{ background: next ? 'var(--hud-accent)' : 'var(--hud-line)' }} />}
                            </span>
                            <span className="min-w-0 flex items-baseline gap-2">
                                <span className="font-semibold text-sm truncate">{result.gate}</span>
                                {required && <span className="hud-figure hud-muted text-sm font-semibold">{clock(required, timeZone)}</span>}
                            </span>
                            <span className="hud-figure text-sm text-right">
                                {missed ? <span style={{ color: 'var(--hud-red)' }}>Missed{result.points ? ` +${result.points.toFixed(0)}` : ''}</span>
                                    // Green within 2 s, the apps' "on time"; the points, if any, are in the log.
                                    : offset !== null ? <span style={{ color: Math.abs(offset) <= 2 ? 'var(--hud-ok)' : 'var(--hud-warn)' }}>{offset > 0 ? '+' : ''}{offset} s</span>
                                    : next && required ? <span style={{ color: 'var(--hud-accent)' }}>{required > now ? `in ${inMinutes((required.getTime() - now.getTime()) / 1000)}` : 'now'}</span>
                                    : null}
                            </span>
                        </li>
                        {penalties.map(e => {
                            const penalty = pointsArePenalties ? e.points > 0 : e.points < 0;
                            return (
                                <li key={`e${e.id}`} tabIndex={0} role="button"
                                    onClick={() => onSelectEntry(e)}
                                    onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelectEntry(e); } }}
                                    className="hud-row grid grid-cols-[1.25rem_1fr_auto] gap-x-2 pl-9 pr-3 py-1 items-baseline">
                                    <span aria-hidden="true" />
                                    <span className="text-xs hud-muted truncate" title={e.message}>{shortScoreText(e.message)}</span>
                                    <span className="hud-figure text-sm" style={{ color: penalty ? 'var(--hud-red)' : 'var(--hud-ok)' }}>
                                        {e.points > 0 ? '+' : ''}{e.points.toFixed(0)}
                                    </span>
                                </li>
                            );
                        })}
                    </React.Fragment>
                );
            })}
        </ol>
    );
}
