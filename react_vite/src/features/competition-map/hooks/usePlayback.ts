import { useState, useEffect, useRef } from 'react';
import { TrackPosition } from '../types';

export function usePlayback(
    mode: 'realtime' | 'playback',
    positionsByContestant: Record<number, TrackPosition[]>
) {
    const [playbackSpeed, setPlaybackSpeed] = useState(1);
    const [isPlaying, setIsPlaying] = useState(false);
    const [playbackTime, setPlaybackTime] = useState<Date>(new Date());
    const [playbackTimeInfo, setPlaybackTimeInfo] = useState<{start: Date, end: Date} | null>(null);
    const playbackTimerRef = useRef<number | null>(null);

    // Playback mode setup
    useEffect(() => {
        if (mode === 'playback') {
            setIsPlaying(false);
            
            const allPositions = Object.values(positionsByContestant).flat();
            if (allPositions.length > 0) {
                const start = new Date(Math.min(...allPositions.map(p => new Date(p.time).getTime())));
                const end = new Date(Math.max(...allPositions.map(p => new Date(p.time).getTime())));
                setPlaybackTimeInfo({start, end});
                setPlaybackTime(start);
            }
        }
    }, [mode, positionsByContestant]);

    // Playback timer
    useEffect(() => {
        if (mode !== 'playback' || !playbackTimeInfo || !isPlaying) {
            if (playbackTimerRef.current) {
                window.clearInterval(playbackTimerRef.current);
                playbackTimerRef.current = null;
            }
            return;
        }

        const SCREEN_UPDATE_INTERVAL_MS = 50;
        const timeStepMs = playbackSpeed * SCREEN_UPDATE_INTERVAL_MS;

        playbackTimerRef.current = window.setInterval(() => {
            setPlaybackTime(prevTime => {
                const newTime = new Date(prevTime.getTime() + timeStepMs);
                if (newTime >= playbackTimeInfo.end) {
                    if(playbackTimerRef.current) clearInterval(playbackTimerRef.current);
                    setIsPlaying(false);
                    return playbackTimeInfo.end;
                }
                return newTime;
            });
        }, SCREEN_UPDATE_INTERVAL_MS);
        
        return () => {
            if (playbackTimerRef.current) {
                window.clearInterval(playbackTimerRef.current);
                playbackTimerRef.current = null;
            }
        };
    }, [mode, playbackSpeed, playbackTimeInfo, isPlaying]);

    const handleTimeChange = (time: Date) => {
        setIsPlaying(false);
        setPlaybackTime(time);
    };

    return {
        playbackSpeed,
        setPlaybackSpeed,
        isPlaying,
        setIsPlaying,
        playbackTime,
        setPlaybackTime: handleTimeChange,
        playbackTimeInfo
    };
}
