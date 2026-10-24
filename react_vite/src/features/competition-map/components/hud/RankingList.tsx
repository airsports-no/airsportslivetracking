import React, { useEffect, useRef } from 'react';

export interface RankingRow {
    id: number;
    name: string;
    score: number | string;
    state?: string;
    color?: string;
    countdown?: number | null;
    expectedBy?: string | null;
    is_active_flight?: boolean;
    is_receiving_data?: boolean;
    progress?: number;
}

interface Props {
    rows: RankingRow[];
    selectedId?: number | null;
    onSelect: (id: number) => void;
    /** Index of the first contestant still waiting to fly; -1 when none is. */
    dividerIndex?: number;
    /** Only rank, name and score: used while following one contestant, so the map stays in view. */
    compact?: boolean;
}

function formatStartsIn(totalSeconds: number): string {
    const s = Math.max(0, Math.floor(totalSeconds));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const pad = (n: number) => String(n).padStart(2, '0');
    return h > 0 ? `${h}:${pad(m)}:${pad(s % 60)}` : `${m}:${pad(s % 60)}`;
}

/** What the contestant is doing, in a few words, under their name. */
function statusLine(r: RankingRow): string | null {
    if (r.countdown && r.countdown > 0) return `Starts in ${formatStartsIn(r.countdown)}`;
    if (r.expectedBy) return `Adaptive start, by ${r.expectedBy}`;
    if (r.state && r.state !== 'Waiting...') return r.state;
    return null;
}

/**
 * The standings as a rack of flight strips, the same way the apps list flights. On a phone each contestant takes one
 * line (rank, colour, name, score), so twice as many fit; the status line shows from tablet width up.
 */
export default function RankingList({ rows, selectedId, onSelect, dividerIndex = -1, compact = false }: Props) {
    // Opening the list while following someone shows their row, however long the list is.
    const selectedRef = useRef<HTMLLIElement>(null);
    useEffect(() => {
        selectedRef.current?.scrollIntoView({ block: 'nearest' });
    }, [selectedId]);

    if (rows.length === 0) {
        return <p className="hud-muted text-sm px-4 py-6">No contestants have been added to this task yet.</p>;
    }
    return (
        <ol className="flex flex-col" aria-label="Ranking">
            {rows.map((r, idx) => {
                const waiting = r.state === 'Waiting...';
                const status = compact ? null : statusLine(r);
                return (
                    <React.Fragment key={r.id}>
                        {idx === dividerIndex && idx !== 0 && (
                            <li className="hud-label px-4 pt-3 pb-1 border-t hud-divider" aria-hidden="true">Not started yet</li>
                        )}
                        <li
                            ref={selectedId === r.id ? selectedRef : undefined}
                            role="option"
                            aria-selected={selectedId === r.id}
                            tabIndex={0}
                            onClick={() => onSelect(r.id)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(r.id); } }}
                            className={`hud-row grid grid-cols-[1.75rem_0.625rem_1fr_auto] items-center gap-x-2 px-3 py-1.5 ${compact ? '' : 'sm:py-2'} ${waiting ? 'opacity-60' : ''}`}
                        >
                            <span className="hud-figure hud-muted text-base text-right">{waiting ? '' : idx + 1}</span>
                            {/* The contestant's colour on the map. */}
                            <span className="w-2.5 h-2.5 rounded-full" style={{ background: r.color }} aria-hidden="true" />
                            <span className="min-w-0">
                                <span className="flex items-center gap-1.5">
                                    <span className="truncate font-semibold text-sm">{r.name}</span>
                                    {r.is_receiving_data && (
                                        <span className="w-1.5 h-1.5 rounded-full flex-none" style={{ background: 'var(--hud-ok)' }} title="Receiving positions now" />
                                    )}
                                </span>
                                {status && <span className="hidden sm:block hud-label truncate">{status}</span>}
                                {!compact && r.is_active_flight && r.progress !== undefined && (
                                    <span className="hidden sm:block h-0.5 mt-1 rounded-full overflow-hidden" style={{ background: 'var(--hud-line)' }} title={`${Math.round(r.progress)}% of the route`}>
                                        <span className="block h-full" style={{ width: `${Math.max(0, Math.min(100, r.progress))}%`, background: 'var(--hud-accent)' }} />
                                    </span>
                                )}
                            </span>
                            <span className={`hud-figure text-lg ${compact ? '' : 'sm:text-xl'} text-right`}>
                                {typeof r.score === 'number' ? r.score.toFixed(0) : <span className="hud-label">{r.score}</span>}
                            </span>
                        </li>
                    </React.Fragment>
                );
            })}
        </ol>
    );
}
