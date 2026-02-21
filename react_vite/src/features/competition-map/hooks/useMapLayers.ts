import { useEffect, useRef, useState, useMemo } from 'react';
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
    contestants: Contestant[]; // Sorted dynamic contestants
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
    contestants, // Sorted dynamic contestants
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
    const annotationMarkersRef = useRef<Map<number, L.Marker>>(new Map());
    const annotationStatesRef = useRef<Map<number, { content: string, type: string, lat: number, lng: number, isExpanded: boolean }>>(new Map());
    const prevPermanentAnnotationsRef = useRef(permanentAnnotations);
    
    const [clickedAnnotationId, setClickedAnnotationId] = useState<number | null>(null);

    // Memoize the list of contestant IDs to stabilize effect dependencies
    const contestantIds = useMemo(() => contestants.map(c => c.id).join(','), [contestants]);

    // Cleanup effect for when mode changes
    useEffect(() => {
        return () => {
            Object.values(layersRef.current).forEach(l => {
                l.marker.remove();
                l.recentTrail.remove();
                l.fullTrail.remove();
            });
            layersRef.current = {};
            
            annotationMarkersRef.current.forEach(m => m.remove());
            annotationMarkersRef.current.clear();
            annotationStatesRef.current.clear();
        }
    }, [mode]);

    // Handle map clicks to deselect annotation
    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        const onMapClick = () => {
            setClickedAnnotationId(null);
        };

        map.on('click', onMapClick);
        return () => {
            map.off('click', onMapClick);
        };
    }, [mapRef]);

    // Effect 1: Layer synchronization. Creates/destroys layers to match 'contestants' list.
    useEffect(() => {
        const map = mapRef.current;
        if (!map) return;

        const total = contestants.length;
        const currentIds = new Set(contestants.map(c => c.id));

        // 1. Remove layers for contestants no longer present
        Object.keys(layersRef.current).forEach(idStr => {
            const id = Number(idStr);
            if (!currentIds.has(id)) {
                const l = layersRef.current[id];
                l.marker.remove();
                l.recentTrail.remove();
                l.fullTrail.remove();
                delete layersRef.current[id];
            }
        });

        // 2. Add or update layers for current contestants
        contestants.forEach((c, index) => {
            const color = hslColor(index, total);
            
            if (!layersRef.current[c.id]) {
                const marker = L.marker([0, 0], {
                    icon: planeIcon(c.contestant_number, color, 0),
                    opacity: 0,
                }).addTo(map);

                marker.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    onContestantSelect(c.id, false);
                });

                const recentTrail = L.polyline([], { color, weight: 5, opacity: 0 }).addTo(map);
                const fullTrail = L.polyline([], { color, weight: 4, opacity: 0 }).addTo(map);

                layersRef.current[c.id] = { marker, recentTrail, fullTrail };
            } else {
                // Update color if it changed due to re-indexing
                const l = layersRef.current[c.id];
                l.recentTrail.setStyle({ color });
                l.fullTrail.setStyle({ color });
                // Marker icon will be updated in Effect 2
            }
        });

    }, [mapRef, contestantIds, onContestantSelect]); // Run when map or list of contestants changes

    // Effect 2: Layer updates. Runs frequently to update positions/styles.
    useEffect(() => {
        const map = mapRef.current;
        if (!map || !navTask) return;

        // Iterate over ALL current layers to ensure correct visibility state
        // even if some contestants are filtered out in this specific update cycle.
        Object.keys(layersRef.current).forEach(idStr => {
            const id = Number(idStr);
            const layers = layersRef.current[id];
            const contestant = contestants.find(c => c.id === id);
            
            if (!contestant) return; // Should have been handled by Effect 1 cleanup

            const positions = currentPositions[id] ?? [];
            const isSelected = selectedContestantId === id;
            const isAnySelected = selectedContestantId !== null;
            const shouldBeVisible = !(isAnySelected && !isSelected);

            // Handle visibility based on positions.length
            if (positions.length === 0 || !shouldBeVisible) {
                layers.marker.setOpacity(0);
                layers.recentTrail.setStyle({ opacity: 0 });
                layers.fullTrail.setStyle({ opacity: 0 });
                return;
            }

            // Update marker position and icon
            const latest = positions[positions.length - 1];
            if (latest) {
                layers.marker.setLatLng([latest.latitude, latest.longitude]);
                layers.marker.setIcon(planeIcon(contestant.contestant_number, layers.recentTrail.options.color as string, latest.course ?? 0));
                layers.marker.setOpacity(1);
            } else {
                layers.marker.setOpacity(0);
            }

            // Update trails
            if (showFullTrails || isSelected) {
                const fullLatLngs = positions.map(p => [p.latitude, p.longitude] as [number, number]);
                layers.fullTrail.setLatLngs(fullLatLngs);
                layers.fullTrail.setStyle({ opacity: 0.7 });
                layers.recentTrail.setStyle({ opacity: 0 });
            } else {
                const recentPositions = lastMinutesPositions(positions, 5, currentTime);
                const recentLatLngs = recentPositions.map(p => [p.latitude, p.longitude] as [number, number]);
                layers.recentTrail.setLatLngs(recentLatLngs);
                layers.recentTrail.setStyle({ opacity: 0.9 });
                layers.fullTrail.setStyle({ opacity: 0 });
            }
        });

        // Annotations cleanup and rendering
        if (prevPermanentAnnotationsRef.current !== permanentAnnotations) {
             prevPermanentAnnotationsRef.current = permanentAnnotations;
        }

        const visibleAnnotationIds = new Set<number>();

        if (selectedContestantId) {
            const allAnnotations = annotationsByContestant[selectedContestantId] ?? [];
            const allLogs = scoreLogByContestant[selectedContestantId] ?? [];

            const visibleAnnotations = allAnnotations.filter(ann =>
                new Date(ann.time) <= currentTime &&
                (ann.type !== 'secret' || (navTask.display_secrets && userShowSecrets))
            );

            visibleAnnotations.forEach(ann => {
                visibleAnnotationIds.add(ann.id);
                
                const scoreLog = ann.score_log_entry ? allLogs.find(l => l.id === ann.score_log_entry) : null;
                const content = `
                    <b>${ann.gate} (${ann.type})</b><br/>
                    ${ann.message.replace(/\n/g, '<br/>')}<br/>
                    <small>${new Date(ann.time).toLocaleString()}</small>
                    ${scoreLog ? `<br/><b>Score: ${scoreLog.points}</b>` : ''}
                `;

                const shouldExpand = permanentAnnotations || (clickedAnnotationId === ann.id);

                let marker = annotationMarkersRef.current.get(ann.id);
                let lastState = annotationStatesRef.current.get(ann.id);

                if (!marker) {
                    marker = L.marker([ann.latitude, ann.longitude], { icon: getAnnotationIcon(ann.type) });
                    
                    marker.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        setClickedAnnotationId(ann.id);
                    });
                    
                    marker.bindTooltip(content, { permanent: shouldExpand, direction: 'top' });
                    if (shouldExpand) {
                        marker.openTooltip();
                    }
                    
                    marker.addTo(map);
                    annotationMarkersRef.current.set(ann.id, marker);
                    
                    annotationStatesRef.current.set(ann.id, {
                        content,
                        type: ann.type,
                        lat: ann.latitude,
                        lng: ann.longitude,
                        isExpanded: shouldExpand
                    });
                } else {
                    let stateChanged = false;

                    if (lastState?.isExpanded !== shouldExpand) {
                        marker.unbindTooltip();
                        marker.bindTooltip(content, { permanent: shouldExpand, direction: 'top' });
                        if (shouldExpand) {
                            marker.openTooltip();
                        }
                        stateChanged = true;
                    } 
                    else if (lastState?.content !== content) {
                         marker.setTooltipContent(content);
                         stateChanged = true;
                    }
                    
                    if (lastState?.lat !== ann.latitude || lastState?.lng !== ann.longitude) {
                        marker.setLatLng([ann.latitude, ann.longitude]);
                        stateChanged = true;
                    }

                    if (lastState?.type !== ann.type) {
                        marker.setIcon(getAnnotationIcon(ann.type));
                        stateChanged = true;
                    }

                    if (stateChanged) {
                        annotationStatesRef.current.set(ann.id, {
                            content,
                            type: ann.type,
                            lat: ann.latitude,
                            lng: ann.longitude,
                            isExpanded: shouldExpand
                        });
                    }
                }
            });
        }
        
        for (const [id, marker] of annotationMarkersRef.current.entries()) {
            if (!visibleAnnotationIds.has(id)) {
                marker.remove();
                annotationMarkersRef.current.delete(id);
                annotationStatesRef.current.delete(id);
            }
        }

    }, [mapRef, navTask, contestants, currentPositions, showFullTrails, currentTime, mode, selectedContestantId, annotationsByContestant, scoreLogByContestant, userShowSecrets, permanentAnnotations, clickedAnnotationId]);
}