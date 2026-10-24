import React from 'react';
import { Crosshair } from 'lucide-react';
import { ScoreLogEntry } from '../../types';

interface Props {
    entries: ScoreLogEntry[];
    timeZone?: string;
    /** Points count against the contestant (lowest score wins), so they are marked as penalties. */
    pointsArePenalties: boolean;
    /** The entry last jumped to, highlighted. */
    activeId?: number | null;
    /** Entries with a place on the map; clicking one of them moves the map (and the replay) there. */
    locatableIds: Set<number>;
    onSelect: (entry: ScoreLogEntry) => void;
    /** In a replay: entries after this time have not happened yet at the replay's time, and are dimmed. */
    dimAfter?: Date;
}

function clock(iso: string, timeZone?: string): string {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
}

/** The selected contestant's score log, laid out like a navigation log: time, gate, what happened, points. */
export default function NavLog({ entries, timeZone, pointsArePenalties, activeId, locatableIds, onSelect, dimAfter }: Props) {
    if (entries.length === 0) {
        return <p className="hud-muted text-sm px-4 py-6">Nothing has been scored yet. Entries appear here as the flight is scored.</p>;
    }
    return (
        <ol className="flex flex-col" aria-label="Navigation log">
            {entries.map((e) => {
                const locatable = locatableIds.has(e.id);
                const penalty = pointsArePenalties ? e.points > 0 : e.points < 0;
                const ahead = dimAfter !== undefined && new Date(e.time) > dimAfter;
                return (
                    <li
                        key={e.id}
                        role="button"
                        aria-current={activeId === e.id ? 'true' : undefined}
                        tabIndex={0}
                        onClick={() => onSelect(e)}
                        onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); onSelect(e); } }}
                        className={`hud-row grid grid-cols-[3.75rem_1fr_auto] gap-x-2 px-3 py-1.5 items-baseline ${ahead ? 'opacity-45' : ''}`}
                        title={locatable ? 'Show on the map' : undefined}
                    >
                        <span className="hud-figure hud-muted text-sm font-semibold">{clock(e.time, timeZone)}</span>
                        <span className="min-w-0">
                            <span className="flex items-center gap-1.5">
                                <span className="font-semibold text-sm truncate">{e.gate}</span>
                                {locatable && <Crosshair size={12} className="hud-muted flex-none" aria-hidden="true" />}
                            </span>
                            <span className="block text-xs leading-snug hud-muted break-words">{e.message}</span>
                        </span>
                        <span
                            className="hud-figure text-base text-right"
                            style={{ color: e.points === 0 ? 'var(--hud-muted)' : penalty ? 'var(--hud-red)' : 'var(--hud-ok)' }}
                        >
                            {e.points === 0 ? '0' : `${e.points > 0 ? '+' : ''}${e.points.toFixed(0)}`}
                        </span>
                    </li>
                );
            })}
        </ol>
    );
}
