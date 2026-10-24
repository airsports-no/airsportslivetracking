import React from 'react';
import { GateResult, ScoreLogEntry } from '../../types';

interface Props {
    /** The gates the viewer may see, in route order (gate_results). */
    gateResults: GateResult[];
    /** The contestant's log entries with points, for the totals. */
    entries: ScoreLogEntry[];
    timeZone?: string;
    pointsArePenalties: boolean;
    onSelect: (result: GateResult) => void;
    /** Contestants to compare with (others who have flown), the one compared now, and the switch. */
    compareOptions?: { id: number; name: string }[];
    compare?: { id: number; name: string; results: GateResult[] } | null;
    onCompare?: (id: number | null) => void;
}

function clock(iso: string | null, timeZone?: string) {
    return iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone }) : '';
}

/**
 * The debrief's answer to "where did I lose points": one row per gate with its required and actual time, the offset
 * and the points, and above it the totals for gate timing and for everything else (corridor, areas, observations,
 * landing, organizer penalties).
 */
export default function GatesTable({
    gateResults, entries, timeZone, pointsArePenalties, onSelect, compareOptions = [], compare = null, onCompare,
}: Props) {
    if (gateResults.length === 0) return null;
    const timing = gateResults.reduce((sum, r) => sum + r.points, 0);
    const timingEntries = new Set(entries.filter(e => e.planned && e.actual).map(e => e.id));
    // "missing gate" entries are already in the gates' points.
    const other = entries
        .filter(e => !timingEntries.has(e.id) && !e.message.startsWith('missing gate'))
        .reduce((sum, e) => sum + e.points, 0);
    const colour = (points: number) =>
        points === 0 ? 'var(--hud-muted)' : (pointsArePenalties ? points > 0 : points < 0) ? 'var(--hud-red)' : 'var(--hud-ok)';
    const signed = (points: number) => `${points > 0 ? '+' : ''}${points.toFixed(0)}`;
    const offsetText = (r: GateResult | undefined) => r?.missed
        ? <span style={{ color: 'var(--hud-red)' }}>Missed</span>
        : r?.offset_seconds !== null && r?.offset_seconds !== undefined
            ? <span style={{ color: Math.abs(r.offset_seconds) <= 2 ? 'var(--hud-ok)' : 'var(--hud-warn)' }}>{r.offset_seconds > 0 ? '+' : ''}{r.offset_seconds} s</span>
            : null;
    const otherBy = new Map((compare?.results ?? []).map(r => [r.gate, r]));

    return (
        <section className="px-3 pt-2 pb-3 border-b hud-divider" aria-label="Gates">
            <div className="grid grid-cols-2 gap-2 mb-3">
                <div className="rounded-md px-3 py-2" style={{ background: 'var(--hud-raised)' }}>
                    <div className="hud-figure text-2xl" style={{ color: colour(timing) }}>{signed(timing)}</div>
                    <div className="hud-label">Gate timing</div>
                </div>
                <div className="rounded-md px-3 py-2" style={{ background: 'var(--hud-raised)' }}>
                    <div className="hud-figure text-2xl" style={{ color: colour(other) }}>{signed(other)}</div>
                    <div className="hud-label">Other penalties</div>
                </div>
            </div>
            {onCompare && compareOptions.length > 0 && (
                <label className="flex items-center gap-2 mb-2 hud-label">
                    Compare with
                    <select
                        className="flex-1 min-w-0 rounded-md px-1.5 h-8 text-sm"
                        style={{ background: 'var(--hud-raised)', color: 'var(--hud-text)', border: '1px solid var(--hud-line)' }}
                        value={compare?.id ?? ''}
                        onChange={e => onCompare(e.target.value ? Number(e.target.value) : null)}
                    >
                        <option value="">Nobody</option>
                        {compareOptions.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                    </select>
                </label>
            )}
            <table className="w-full text-sm" style={{ borderCollapse: 'collapse' }}>
                <thead>
                    {compare ? (
                        // Side by side: this contestant's offset and points, then the compared one's.
                        <tr className="hud-label text-left">
                            <th scope="col" className="font-normal pb-1">Gate</th>
                            <th scope="col" className="font-normal pb-1 text-right">Offset</th>
                            <th scope="col" className="font-normal pb-1 text-right">Points</th>
                            <th scope="col" className="font-normal pb-1 text-right truncate max-w-[6rem]" title={compare.name}>{compare.name}</th>
                            <th scope="col" className="font-normal pb-1 text-right">Points</th>
                        </tr>
                    ) : (
                        <tr className="hud-label text-left">
                            <th scope="col" className="font-normal pb-1">Gate</th>
                            <th scope="col" className="font-normal pb-1">Required</th>
                            <th scope="col" className="font-normal pb-1">Actual</th>
                            <th scope="col" className="font-normal pb-1 text-right">Offset</th>
                            <th scope="col" className="font-normal pb-1 text-right">Points</th>
                        </tr>
                    )}
                </thead>
                <tbody>
                    {gateResults.map((r, i) => (
                        <tr key={`${r.gate}${i}`} className="hud-row" tabIndex={0} role="button"
                            onClick={() => onSelect(r)}
                            onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(r); } }}>
                            <td className="py-1 pr-2 font-semibold truncate max-w-[5rem]">{r.gate}</td>
                            {compare ? (
                                <>
                                    <td className="py-1 pr-1 hud-figure text-right">{offsetText(r)}</td>
                                    <td className="py-1 pr-2 hud-figure text-right" style={{ color: colour(r.points) }}>{r.points ? signed(r.points) : ''}</td>
                                    <td className="py-1 pr-1 hud-figure text-right">{offsetText(otherBy.get(r.gate))}</td>
                                    <td className="py-1 hud-figure text-right" style={{ color: colour(otherBy.get(r.gate)?.points ?? 0) }}>
                                        {otherBy.get(r.gate)?.points ? signed(otherBy.get(r.gate)!.points) : ''}
                                    </td>
                                </>
                            ) : (
                                <>
                                    <td className="py-1 pr-2 hud-figure hud-muted font-semibold">{r.time_check ? clock(r.planned, timeZone) : ''}</td>
                                    <td className="py-1 pr-2 hud-figure font-semibold">
                                        {r.missed ? <span style={{ color: 'var(--hud-red)' }}>Missed</span> : clock(r.actual, timeZone)}
                                    </td>
                                    <td className="py-1 pr-1 hud-figure text-right">{offsetText(r)}</td>
                                    <td className="py-1 hud-figure text-right" style={{ color: colour(r.points) }}>{r.points ? signed(r.points) : ''}</td>
                                </>
                            )}
                        </tr>
                    ))}
                </tbody>
            </table>
        </section>
    );
}
