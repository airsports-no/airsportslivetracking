import React from 'react';
import { Crosshair } from 'lucide-react';
import { ScoreLogEntry } from '../../types';
import { shortScoreText } from '../../utils/scoreText';
import { isQualityTask, logPointsText, PROVISIONAL_HELP, RAW_POINTS_LEGEND, TaskScoring } from '../../../../utils/taskScore';

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
    /** How the task's score is made: a quality task's log holds raw quality points, not points of the task score. */
    scoring?: TaskScoring | null;
    /** The scores can still change because of other flights. */
    provisional?: boolean;
    /** The contestant's score worked out step by step ("Q 812 of best 930 -> 873; -50% -> 437"). */
    arithmetic?: string | null;
}

function clock(iso: string, timeZone?: string): string {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
}

/** The selected contestant's score log, laid out like a navigation log: time, gate, what happened, points. */
export default function NavLog({ entries, timeZone, pointsArePenalties, activeId, locatableIds, onSelect, dimAfter, scoring, provisional = false, arithmetic = null }: Props) {
    const quality = isQualityTask(scoring);
    // How the score came about, and what the points below are
    const explanation = quality ? (
        <div className="px-3 pt-2 pb-2 border-b hud-divider">
            {arithmetic && <div className="hud-figure text-sm font-semibold" title="Raw quality score Q, scaled to the best flight in the task, less percentage penalties">{arithmetic}</div>}
            <p className="hud-label normal-case mt-1">{RAW_POINTS_LEGEND}</p>
            {provisional && <p className="hud-label normal-case mt-1" style={{ color: 'var(--hud-warn)' }}>{PROVISIONAL_HELP}</p>}
        </div>
    ) : null;
    if (entries.length === 0) {
        return <>{explanation}<p className="hud-muted text-sm px-4 py-6">Nothing has been scored yet. Entries appear here as the flight is scored.</p></>;
    }
    return (
        <>
        {explanation}
        <ol className="flex flex-col" aria-label="Navigation log">
            {entries.map((e) => {
                const locatable = locatableIds.has(e.id);
                const shown = logPointsText(e, scoring, pointsArePenalties);
                const penalty = shown.penalty;
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
                            {/* In a few words; the entry last jumped to shows the whole message. */}
                            <span className="block text-xs leading-snug hud-muted break-words" title={e.message}>
                                {activeId === e.id ? e.message : shortScoreText(e.message)}
                            </span>
                        </span>
                        <span
                            className="hud-figure text-base text-right"
                            style={{ color: e.points === 0 ? 'var(--hud-muted)' : penalty ? 'var(--hud-red)' : 'var(--hud-ok)' }}
                            title={shown.title || undefined}
                        >
                            {shown.text}
                        </span>
                    </li>
                );
            })}
        </ol>
        </>
    );
}
