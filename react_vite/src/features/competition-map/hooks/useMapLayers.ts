import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { planeIcon, getAnnotationIcon } from '../components/icons';
import { TrackPosition, NavigationTask } from '../types';

function hslColor(index: number, total: number): string {
    const hue = Math.round((index / Math.max(1, total)) * 360);
    return `hsl(${hue}, 70%, 50%)`;
}

function lastMinutesPositions(all: TrackPosition[], minutes: number, currentTime: Date): TrackPosition[] {
    const cutoff = new Date(currentTime.getTime() - minutes * 60_000);
    return all.filter(p => new Date(p.time) >= cutoff);
}

interface ContestantLayers {
    marker: L.Marker;
    recentTrail: L.Polyline;
    fullTrail: L.Polyline;
}

interface MapLayersProps {
    mapRef: React.MutableRefObject<L.Map | null>;
    navTask: NavigationTask | null;
    currentPositions: Record<number, TrackPosition[]>;
    showFullTrails: boolean;
    currentTime: Date;
    mode: 'realtime' | 'playback';
    selectedContestantId: number | null;
    onContestantSelect: (id: number | null, showLog: boolean) => void;
    annotationsByContestant: Record<number, any[]>;
    scoreLogByContestant: Record<number, any[]>;
    userShowSecrets: boolean;
}

export function useMapLayers({
    mapRef,
    navTask,
    currentPositions,
    showFullTrails,
    currentTime,
    mode,
    selectedContestantId,
    onContestantSelect,
    annotationsByContestant,
    scoreLogByContestant,
    userShowSecrets
}: MapLayersProps) {
    const layersRef = useRef<Record<number, ContestantLayers>>({});
    const annotationLayersRef = useRef<L.Marker[]>([]);

    // Cleanup effect for when mode changes
    useEffect(() => {
        return () => {
            Object.values(layersRef.current).forEach(l => {
                l.marker.remove();
                l.recentTrail.remove();
                l.fullTrail.remove();
            });
            layersRef.current = {};
            annotationLayersRef.current.forEach(m => m.remove());
            annotationLayersRef.current = [];
        }
    }, [mode]);
    
    // Main layer rendering effect
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !navTask) return;
        
        const total = navTask.contestant_set.length;
        for (const [index, c] of navTask.contestant_set.entries()) {
            const color = hslColor(index, total);
            const positions = currentPositions[c.id] ?? [];
            
            const isSelected = selectedContestantId === c.id;
            const isAnySelected = selectedContestantId !== null;

            if (!layersRef.current[c.id]) {
                const marker = L.marker([positions[0]?.latitude ?? 0, positions[0]?.longitude ?? 0], {
                    icon: planeIcon(c.contestant_number, color, positions[positions.length - 1]?.course ?? 0),
                }).addTo(map);
                marker.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    onContestantSelect(c.id, false);
                });
                const recentTrail = L.polyline([], { color, weight: 5, opacity: 0.9 }).addTo(map);
                const fullTrail = L.polyline([], { color, weight: 4, opacity: 0.5 }).addTo(map);
                layersRef.current[c.id] = { marker, recentTrail, fullTrail };
            }
            const { marker, recentTrail, fullTrail } = layersRef.current[c.id];

            const shouldBeVisible = !(isAnySelected && !isSelected);

            const latest = positions[positions.length - 1];
            if (latest && shouldBeVisible) {
                marker.setLatLng([latest.latitude, latest.longitude]);
                marker.setIcon(planeIcon(c.contestant_number, color, latest.course ?? 0));
                marker.setOpacity(1);
            } else {
                marker.setOpacity(0);
            }

            if (shouldBeVisible && (showFullTrails || isSelected)) {
                const fullLatLngs = positions.map(p => [p.latitude, p.longitude] as [number, number]);
                fullTrail.setLatLngs(fullLatLngs);
                fullTrail.setStyle({opacity: 0.7});
                recentTrail.setLatLngs([]);
                recentTrail.setStyle({opacity: 0});
            } else if (shouldBeVisible) {
                const recentPositions = lastMinutesPositions(positions, 5, currentTime);
                const recentLatLngs = recentPositions.map(p => [p.latitude, p.longitude] as [number, number]);
                recentTrail.setLatLngs(recentLatLngs);
                recentTrail.setStyle({opacity: 0.9});
                fullTrail.setLatLngs([]);
                fullTrail.setStyle({opacity: 0});
            } else {
                recentTrail.setLatLngs([]);
                recentTrail.setStyle({opacity: 0});
                fullTrail.setLatLngs([]);
                fullTrail.setStyle({opacity: 0});
            }
        }
        
        annotationLayersRef.current.forEach(m => m.remove());
        annotationLayersRef.current = [];
        if(selectedContestantId) {
            const allAnnotations = annotationsByContestant[selectedContestantId] ?? [];
            const allLogs = scoreLogByContestant[selectedContestantId] ?? [];
            
            const visibleAnnotations = allAnnotations.filter(ann => 
                new Date(ann.time) <= currentTime && 
                (ann.type !== 'secret' || (navTask.display_secrets && userShowSecrets))
            );

            visibleAnnotations.forEach(ann => {
                const scoreLog = ann.score_log_entry ? allLogs.find(l => l.id === ann.score_log_entry) : null;
                const marker = L.marker([ann.latitude, ann.longitude], {icon: getAnnotationIcon(ann.type)})
                    .bindTooltip(`
                        <b>${ann.gate} (${ann.type})</b><br/>
                        ${ann.message}<br/>
                        <small>${new Date(ann.time).toLocaleString()}</small>
                        ${scoreLog ? `<br/><b>Score: ${scoreLog.points}</b>` : ''}
                    `)
                    .addTo(map);
                annotationLayersRef.current.push(marker);
            });
        }

    }, [mapRef, navTask, currentPositions, showFullTrails, currentTime, mode, selectedContestantId, annotationsByContestant, scoreLogByContestant, userShowSecrets]);
}
