import React, { useState } from 'react';
import { ArrowDown, ArrowUp, Plus, X } from 'lucide-react';
import { SequenceShape, TimeEntry, addToLane, clockTime, entrySeconds, isEntryFilled, laneCount, laneLabel, moveInLane, removeFromLane } from './declarationForm';

interface TimeRowProps {
    name: string;
    entry: TimeEntry;
    onChange: (entry: TimeEntry) => void;
    /** When the start point is crossed (ISO), null when that is not known before the flight (adaptive start) */
    startPointTime: string | null | undefined;
    timeZone: string;
    disabled?: boolean;
    /** What the time is for, shown in the label: "Time at TP1" */
    label?: string;
}

/** A time after the start point as minutes and seconds, with the clock time it comes to */
export const TimeRow: React.FC<TimeRowProps> = ({ name, entry, onChange, startPointTime, timeZone, disabled, label }) => {
    const seconds = entrySeconds(entry);
    const filled = isEntryFilled(entry);
    const invalid = filled && seconds === null;
    const clock = clockTime(startPointTime, seconds, timeZone);
    return (
        <fieldset className="py-2" disabled={disabled}>
            <legend className="font-semibold text-base mb-1">{label ?? name}</legend>
            <div className="flex items-end gap-2">
                <label className="flex-1">
                    <span className="text-xs opacity-70">Minutes</span>
                    <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        autoComplete="off"
                        aria-label={`${name}, minutes after the start point`}
                        className={`input input-bordered w-full min-h-11 text-lg ${invalid ? 'input-error' : ''}`}
                        value={entry.minutes}
                        disabled={disabled}
                        onChange={(event) => onChange({ ...entry, minutes: event.target.value })}
                    />
                </label>
                <span className="pb-3 text-lg" aria-hidden="true">:</span>
                <label className="flex-1">
                    <span className="text-xs opacity-70">Seconds</span>
                    <input
                        type="text"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        autoComplete="off"
                        aria-label={`${name}, seconds`}
                        className={`input input-bordered w-full min-h-11 text-lg ${invalid ? 'input-error' : ''}`}
                        value={entry.seconds}
                        disabled={disabled}
                        onChange={(event) => onChange({ ...entry, seconds: event.target.value })}
                    />
                </label>
            </div>
            {invalid && <p className="text-sm text-error mt-1">Use whole minutes and seconds from 0 to 59.</p>}
            {!invalid && clock && <p className="text-sm opacity-80 mt-1" data-testid={`clock-${name}`}>That is {clock} on the clock.</p>}
        </fieldset>
    );
};

interface SequenceLanesProps {
    shape: SequenceShape;
    lanes: string[][];
    options: string[];
    onChange: (lanes: string[][]) => void;
    disabled?: boolean;
}

const Anchor: React.FC<{ name: string }> = ({ name }) => (
    <div className="flex items-center gap-2 my-1">
        <span className="badge badge-neutral badge-lg" data-testid={`anchor-${name}`}>{name}</span>
        <span className="text-xs opacity-70">fixed</span>
    </div>
);

/**
 * The points a pilot chooses to fly, in order, between fixed points. Tapping a point adds it; each chosen point has buttons
 * to move it up or down and to take it out (no dragging needed).
 */
export const SequenceLanes: React.FC<SequenceLanesProps> = ({ shape, lanes, options, onChange, disabled }) => {
    const [openLane, setOpenLane] = useState<number | null>(null);
    const chosen = new Set(lanes.flat());
    const available = options.filter((name) => !chosen.has(name));

    const lane = (index: number) => {
        const points = lanes[index] ?? [];
        return (
            <div key={`lane-${index}`} className="rounded-box border border-base-300 p-3 my-1" data-testid={`lane-${index}`}>
                <h3 className="text-sm font-semibold mb-1">{laneLabel(shape, index)}</h3>
                {points.length === 0 && <p className="text-sm opacity-70">No points chosen.</p>}
                <ol className="space-y-2">
                    {points.map((point, position) => (
                        <li key={point} className="flex items-center gap-2" data-testid={`lane-${index}-item`}>
                            <span className="flex-1 font-medium text-lg">{point}</span>
                            <button
                                type="button"
                                className="btn btn-square btn-outline min-h-11 min-w-11"
                                aria-label={`Move ${point} up`}
                                disabled={disabled || position === 0}
                                onClick={() => onChange(moveInLane(lanes, index, position, -1))}
                            >
                                <ArrowUp size={18} />
                            </button>
                            <button
                                type="button"
                                className="btn btn-square btn-outline min-h-11 min-w-11"
                                aria-label={`Move ${point} down`}
                                disabled={disabled || position === points.length - 1}
                                onClick={() => onChange(moveInLane(lanes, index, position, 1))}
                            >
                                <ArrowDown size={18} />
                            </button>
                            <button
                                type="button"
                                className="btn btn-square btn-outline btn-error min-h-11 min-w-11"
                                aria-label={`Take ${point} out`}
                                disabled={disabled}
                                onClick={() => onChange(removeFromLane(lanes, index, point))}
                            >
                                <X size={18} />
                            </button>
                        </li>
                    ))}
                </ol>
                {!disabled && (
                    <div className="mt-2">
                        <button
                            type="button"
                            className="btn btn-sm btn-ghost min-h-11 gap-1"
                            aria-expanded={openLane === index}
                            onClick={() => setOpenLane(openLane === index ? null : index)}
                        >
                            <Plus size={16} />
                            Add a point
                        </button>
                        {openLane === index && (
                            <div className="flex flex-wrap gap-2 mt-2" role="group" aria-label={`Points to add: ${laneLabel(shape, index)}`}>
                                {available.length === 0 && <p className="text-sm opacity-70">All points are chosen.</p>}
                                {available.map((name) => (
                                    <button
                                        key={name}
                                        type="button"
                                        className="btn btn-outline min-h-11"
                                        onClick={() => onChange(addToLane(lanes, index, name))}
                                    >
                                        {name}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        );
    };

    const blocks: React.ReactNode[] = [];
    const count = laneCount(shape);
    if (shape.openEnds) {
        for (let index = 0; index < count; index += 1) {
            blocks.push(lane(index));
            if (index < shape.anchors.length) blocks.push(<Anchor key={`anchor-${index}`} name={shape.anchors[index]} />);
        }
    } else {
        shape.anchors.forEach((name, index) => {
            blocks.push(<Anchor key={`anchor-${index}`} name={name} />);
            if (index < count) blocks.push(lane(index));
        });
    }
    return <div>{blocks}</div>;
};
