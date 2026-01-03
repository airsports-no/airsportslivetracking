import React from 'react';
import { Play, Pause, Rewind } from 'lucide-react';

interface Props {
    currentTime: Date;
    startTime: Date;
    endTime: Date;
    isPlaying: boolean;
    playbackSpeed: number;
    onTimeChange: (newTime: Date) => void;
    onPlayPause: () => void;
    onJumpToStart: () => void;
    onSpeedChange: (speed: number) => void;
}

export default function TimelineControls({
    currentTime,
    startTime,
    endTime,
    isPlaying,
    playbackSpeed,
    onTimeChange,
    onPlayPause,
    onJumpToStart,
    onSpeedChange
}: Props) {
    const min = startTime.getTime();
    const max = endTime.getTime();
    const current = currentTime.getTime();

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        onTimeChange(new Date(Number(e.target.value)));
    };

    return (
        <div className="absolute bottom-0 left-0 right-0 z-[1000] p-4 bg-base-200/80 backdrop-blur-sm">
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <button onClick={onJumpToStart} className="btn btn-sm btn-ghost">
                        <Rewind size={16} />
                    </button>
                    <button onClick={onPlayPause} className="btn btn-sm btn-ghost">
                        {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                    </button>
                </div>
                <span className="text-sm font-mono whitespace-nowrap">{startTime.toLocaleTimeString()}</span>
                <input
                    type="range"
                    min={min}
                    max={max}
                    value={current}
                    onChange={handleSliderChange}
                    className="range range-primary"
                />
                <span className="text-sm font-mono whitespace-nowrap">{endTime.toLocaleTimeString()}</span>
                <div className="flex items-center gap-2">
                    <span className="label-text text-sm">Speed</span>
                    <input 
                        type="range" 
                        min={1} 
                        max={100} 
                        step={1} 
                        value={playbackSpeed} 
                        onChange={e => onSpeedChange(Number(e.target.value))} 
                        className="range range-xs w-32" />
                    <span className="badge badge-sm">{playbackSpeed}x</span>
                </div>
            </div>
            <div className="text-center text-sm font-mono mt-1">
                {currentTime.toLocaleString()}
            </div>
        </div>
    );
}
