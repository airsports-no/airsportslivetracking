import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { planeIcon, getAnnotationIcon } from '../components/icons';
import { TrackPosition, NavigationTask, Contestant } from '../types';
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
    navTask: NavigationTask | null; // Stable navTask data
    contestants: Contestant[]; // Dynamic contestants
    currentPositions: Record<number, TrackPosition[]>;
    showFullTrails: boolean;
    currentTime: Date;
    mode: 'realtime' | 'playback';
    selectedContestantId: number | null;
    onContestantSelect: (id: number | null, showLog: boolean) => void;
    annotationsByContestant: Record<number, any[]>;
    scoreLogByContestant: Record<number, any[]>;
    userShowSecrets: boolean;
    permanentAnnotations: boolean;
}
export function useMapLayers({
    mapRef,
    navTask,
    contestants, // Destructure new prop
    currentPositions,
    showFullTrails,
    currentTime,
    mode,
    selectedContestantId,
    onContestantSelect,
    annotationsByContestant,
    scoreLogByContestant,
    userShowSecrets,
    permanentAnnotations
}: MapLayersProps) {
    const layersRef = useRef<Record<number, ContestantLayers>>({});
    const annotationLayersRef = useRef<L.Marker[]>([]);
    // Cleanup effect for when mode changes (existing, fine)
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
    // Effect 1: Layer creation/destruction. Runs when fundamental map data changes.
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !navTask) return;
        // Clear all layers from previous run of this effect (e.g., if task changes)
        Object.values(layersRef.current).forEach(l => {
            l.marker.remove();
            l.recentTrail.remove();
            l.fullTrail.remove();
        });
        layersRef.current = {}; // Clear the ref
        // Create initial layers for each contestant from the stable navTask.contestant_set
        navTask.contestant_set.forEach((c, index) => {
            const color = hslColor(index, navTask.contestant_set.length);
            const marker = L.marker([0, 0], { // Create at 0,0 initially, hidden
                icon: planeIcon(c.contestant_number, color, 0),
                opacity: 0,
            }).addTo(map);
            marker.on('click', (e) => {
                L.DomEvent.stopPropagation(e);
                onContestantSelect(c.id, false);
            });
            const recentTrail = L.polyline([], { color, weight: 5, opacity: 0 }).addTo(map); // Initially hidden
            const fullTrail = L.polyline([], { color, weight: 4, opacity: 0 }).addTo(map); // Initially hidden
            layersRef.current[c.id] = { marker, recentTrail, fullTrail };
        });
        // This cleanup runs only when mapRef, navTask, or onContestantSelect change
        return () => {
            Object.values(layersRef.current).forEach(l => {
                l.marker.remove();
                l.recentTrail.remove();
                l.fullTrail.remove();
            });
            layersRef.current = {};
            annotationLayersRef.current.forEach(m => m.remove());
            annotationLayersRef.current = [];
        };
    }, [mapRef, navTask, onContestantSelect]); // Dependencies for creation/destruction
    // Effect 2: Layer updates. Runs frequently to update positions/styles.
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !navTask) return;
        contestants.forEach((c) => {
            const layers = layersRef.current[c.id];
            if (!layers) return; // Layers might not be initialized yet by Effect 1
            const positions = currentPositions[c.id] ?? [];
            const isSelected = selectedContestantId === c.id;
            const isAnySelected = selectedContestantId !== null;
            const shouldBeVisible = !(isAnySelected && !isSelected);
            // Handle visibility based on positions.length
            if (positions.length === 0) {
                layers.marker.setOpacity(0);
                layers.recentTrail.setStyle({ opacity: 0 });
                layers.fullTrail.setStyle({ opacity: 0 });
                return;
            }
            // Update marker position and icon
            const latest = positions[positions.length - 1];
            if (latest && shouldBeVisible) {
                layers.marker.setLatLng([latest.latitude, latest.longitude]);
                layers.marker.setIcon(planeIcon(c.contestant_number, layers.recentTrail.options.color as string, latest.course ?? 0));
                layers.marker.setOpacity(1);
            } else {
                layers.marker.setOpacity(0);
            }
            // Update trails
            if (shouldBeVisible && (showFullTrails || isSelected)) {
                const fullLatLngs = positions.map(p => [p.latitude, p.longitude] as [number, number]);
                layers.fullTrail.setLatLngs(fullLatLngs);
                layers.fullTrail.setStyle({ opacity: 0.7 });
                layers.recentTrail.setStyle({ opacity: 0 });
            } else if (shouldBeVisible) {
                const recentPositions = lastMinutesPositions(positions, 5, currentTime);
                const recentLatLngs = recentPositions.map(p => [p.latitude, p.longitude] as [number, number]);
                layers.recentTrail.setLatLngs(recentLatLngs);
                layers.recentTrail.setStyle({ opacity: 0.9 });
                layers.fullTrail.setStyle({ opacity: 0 });
            } else {
                layers.recentTrail.setStyle({ opacity: 0 });
                layers.fullTrail.setStyle({ opacity: 0 });
            }
        });
        // Annotations cleanup and rendering (can be in a separate effect or here)
        annotationLayersRef.current.forEach(m => m.remove());
        annotationLayersRef.current = [];
        if (selectedContestantId) {
            const allAnnotations = annotationsByContestant[selectedContestantId] ?? [];
            const allLogs = scoreLogByContestant[selectedContestantId] ?? [];
            const visibleAnnotations = allAnnotations.filter(ann =>
                new Date(ann.time) <= currentTime &&
                (ann.type !== 'secret' || (navTask.display_secrets && userShowSecrets))
            );
            visibleAnnotations.forEach(ann => {
                const scoreLog = ann.score_log_entry ? allLogs.find(l => l.id === ann.score_log_entry) : null;
                const marker = L.marker([ann.latitude, ann.longitude], { icon: getAnnotationIcon(ann.type) });
                const content = `
                                                                                                        <b>${ann.gate} (${ann.type})</b><br/>
                                                                                                        ${ann.message.replace(/\n/g, '<br/>')}<br/>
                                                                                                        <small>${new Date(ann.time).toLocaleString()}</small>
                                                                                                        ${scoreLog ? `<br/><b>Score: ${scoreLog.points}</b>` : ''}
                                                                                                    `;
                if (permanentAnnotations) {
                    marker.bindTooltip(content, { permanent: true, direction: 'top' });
                } else {
                    marker.bindPopup(content);
                }
                marker.addTo(map);
                annotationLayersRef.current.push(marker);
            });
        }
    }, [mapRef, navTask, contestants, currentPositions, showFullTrails, currentTime, mode, selectedContestantId, annotationsByContestant, scoreLogByContestant, userShowSecrets, permanentAnnotations]);
}
