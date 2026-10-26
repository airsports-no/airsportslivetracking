import React from 'react';
import { Pause, Play, SkipBack } from 'lucide-react';

export interface ReplayEvent {
    id: number;
    time: Date;
    label: string;
    penalty: boolean;
}

interface Props {
    currentTime: Date;
    startTime: Date;
    endTime: Date;
    timeZone?: string;
    isPlaying: boolean;
    playbackSpeed: number;
    onTimeChange: (time: Date) => void;
    onPlayPause: () => void;
    onJumpToStart: () => void;
    onSpeedChange: (speed: number) => void;
    /** The selected contestant's scored events, marked on the timeline; clicking one jumps there. */
    events?: ReplayEvent[];
    onEventSelect?: (id: number) => void;
    /** With one contestant selected: whether the replay spans the whole day or only their flight, and the switch. */
    spanChoice?: { wholeDay: boolean; onToggle: () => void };
}

const SPEEDS = [1, 2, 5, 10, 25, 50, 100];

function clock(t: Date, timeZone?: string) {
    return t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone });
}

/** Replay along the bottom edge of the map: play, the timeline with the selected contestant's events, and the speed. */
export default function ReplayBar({
    currentTime, startTime, endTime, timeZone, isPlaying, playbackSpeed,
    onTimeChange, onPlayPause, onJumpToStart, onSpeedChange, events = [], onEventSelect, spanChoice,
}: Props) {
    const min = startTime.getTime();
    const max = Math.max(endTime.getTime(), min + 1);
    const at = (t: Date) => `${((t.getTime() - min) / (max - min)) * 100}%`;

    return (
        <section className="hud border-t hud-divider px-3 sm:px-4 py-2 z-[1100]" aria-label="Replay">
            <div className="flex items-center gap-2 sm:gap-3">
                <button className="hud-button" onClick={onJumpToStart} aria-label="Back to the start" title="Back to the start"><SkipBack size={16} /></button>
                <button className="hud-button" onClick={onPlayPause} aria-label={isPlaying ? 'Pause' : 'Play'} title={isPlaying ? 'Pause' : 'Play'}
                    style={{ background: 'var(--hud-accent)', color: '#fff' }}>
                    {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                </button>

                <div className="relative flex-1 min-w-0 h-8 flex items-center">
                    {/* Event ticks sit behind the slider's track; penalties in red. */}
                    <div className="absolute inset-x-0 top-0 h-2 pointer-events-none" aria-hidden="true">
                        {events.map(e => (
                            <span key={e.id} className="absolute top-0 w-0.5 h-2 -translate-x-1/2 rounded-full"
                                style={{ left: at(e.time), background: e.penalty ? 'var(--hud-red)' : 'var(--hud-muted)' }} />
                        ))}
                    </div>
                    <input
                        title="Drag to any moment of the replay; the red marks are penalties" type="range" min={min} max={max} value={Math.min(max, Math.max(min, currentTime.getTime()))}
                        onChange={e => onTimeChange(new Date(Number(e.target.value)))}
                        className="w-full" aria-label="Replay time"
                    />
                    {onEventSelect && events.length > 0 && (
                        // Wider click targets over the penalty ticks, above the slider.
                        <div className="absolute inset-x-0 top-0 h-3">
                            {events.filter(e => e.penalty).map(e => (
                                <button key={e.id} className="absolute top-0 w-3 h-3 -translate-x-1/2" style={{ left: at(e.time) }}
                                    onClick={() => onEventSelect(e.id)} title={`${clock(e.time, timeZone)} ${e.label}`} aria-label={`Jump to ${e.label}`} />
                            ))}
                        </div>
                    )}
                </div>

                <span className="hud-label hidden md:inline">{clock(startTime, timeZone)} to {clock(endTime, timeZone)}</span>
                {spanChoice && (
                    <button className="hud-button flex-none" aria-pressed={spanChoice.wholeDay} onClick={spanChoice.onToggle}
                        title={spanChoice.wholeDay ? 'Replay only this flight' : 'Replay the whole day, all contestants'}>
                        Whole day
                    </button>
                )}
                <label className="flex items-center gap-1.5 flex-none">
                    <span className="hud-label hidden sm:inline">Speed</span>
                    <select
                        value={playbackSpeed}
                        onChange={e => onSpeedChange(Number(e.target.value))}
                        className="hud-figure text-base rounded-md px-1.5 h-8"
                        title="How fast the replay plays: 1× is real time" aria-label="Replay speed"
                        style={{ background: 'var(--hud-raised)', color: 'var(--hud-text)', border: '1px solid var(--hud-line)' }}
                    >
                        {(SPEEDS.includes(playbackSpeed) ? SPEEDS : [...SPEEDS, playbackSpeed].sort((a, b) => a - b)).map(s => (
                            <option key={s} value={s}>{s}×</option>
                        ))}
                    </select>
                </label>
            </div>
        </section>
    );
}
