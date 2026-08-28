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
        <div className="absolute bottom-0 left-0 right-0 z-[1100] p-2 sm:p-4 bg-base-200/80 backdrop-blur-sm">
            <div className="flex flex-wrap items-center gap-2 sm:gap-4">
                <div className="flex items-center gap-1 sm:gap-2 order-1">
                    <button onClick={onJumpToStart} className="btn btn-xs sm:btn-sm btn-ghost">
                        <Rewind size={16} />
                    </button>
                    <button onClick={onPlayPause} className="btn btn-xs sm:btn-sm btn-ghost">
                        {isPlaying ? <Pause size={16} /> : <Play size={16} />}
                    </button>
                </div>
                
                <div className="flex-1 flex items-center gap-2 order-3 sm:order-2 min-w-full sm:min-w-0">
                    <span className="text-xs sm:text-sm font-mono whitespace-nowrap">{startTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                    <input
                        type="range"
                        min={min}
                        max={max}
                        value={current}
                        onChange={handleSliderChange}
                        className="range range-primary range-xs sm:range-sm flex-1"
                    />
                    <span className="text-xs sm:text-sm font-mono whitespace-nowrap">{endTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                </div>

                <div className="flex items-center gap-2 order-2 sm:order-3 ml-auto sm:ml-0">
                    <span className="label-text text-xs sm:text-sm">Speed</span>
                    <input 
                        type="range" 
                        min={1} 
                        max={100} 
                        step={1} 
                        value={playbackSpeed} 
                        onChange={e => onSpeedChange(Number(e.target.value))} 
                        className="range range-xs w-24 sm:w-32" />
                    <span className="badge badge-xs sm:badge-sm">{playbackSpeed}x</span>
                </div>
            </div>
            <div className="text-center text-[10px] sm:text-sm font-mono mt-1">
                {currentTime.toLocaleString()}
            </div>
        </div>
    );
}
