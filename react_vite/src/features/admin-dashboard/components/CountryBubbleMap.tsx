import React, { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import useLeafletMap from '../../../hooks/useLeafletMap';
import { Loading } from '../../route-editor/components/basicComponents';
import { CountryStatsRow } from '../api';

type Metric = 'contestants' | 'tasks' | 'contests';

const METRIC_OPTIONS: { value: Metric; label: string }[] = [
    { value: 'contestants', label: 'Contestants' },
    { value: 'tasks', label: 'Tasks' },
    { value: 'contests', label: 'Contests' },
];

const MIN_RADIUS = 6;
const MAX_RADIUS = 40;

interface Props {
    rows: CountryStatsRow[] | null;
    loading: boolean;
}

export default function CountryBubbleMap({ rows, loading }: Props) {
    const containerRef = useRef<HTMLDivElement>(null);
    const map = useLeafletMap(containerRef, { initialCenter: [20, 0], initialZoom: 2, minZoom: 2 });
    const layerGroupRef = useRef<L.LayerGroup | null>(null);
    const [metric, setMetric] = useState<Metric>('contestants');

    const plottable = useMemo(
        () => (rows ?? []).filter((row) => row.latitude !== null && row.longitude !== null && row[metric] > 0),
        [rows, metric],
    );

    const maxValue = useMemo(() => Math.max(1, ...plottable.map((row) => row[metric])), [plottable, metric]);

    useEffect(() => {
        if (!map) return;
        if (!layerGroupRef.current) {
            layerGroupRef.current = L.layerGroup().addTo(map);
        }
        const layerGroup = layerGroupRef.current;
        layerGroup.clearLayers();

        for (const row of plottable) {
            // Circle AREA (not radius) should be proportional to value, or the visual size
            // difference between e.g. 10 and 40 contestants reads as far bigger than 4x.
            const fraction = row[metric] / maxValue;
            const radius = MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * Math.sqrt(fraction);
            const marker = L.circleMarker([row.latitude as number, row.longitude as number], {
                radius,
                color: 'var(--color-primary)',
                weight: 1,
                fillColor: 'var(--color-primary)',
                fillOpacity: 0.45,
            });
            marker.bindTooltip(
                `<strong>${row.country_name}</strong><br/>` +
                    `Contests: ${row.contests}<br/>Tasks: ${row.tasks}<br/>Contestants: ${row.contestants}`,
            );
            marker.addTo(layerGroup);
        }
    }, [map, plottable, maxValue, metric]);

    return (
        <div className="card bg-base-100 shadow-xl">
            <div className="card-body">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
                    <div>
                        <h2 className="card-title">Reach map</h2>
                        <p className="text-sm text-base-content/70">
                            One bubble per country with at least one resolved task location, sized by the selected
                            metric. Position is the average of that country's task locations, not a fixed centroid.
                        </p>
                    </div>
                    <div className="join">
                        {METRIC_OPTIONS.map((option) => (
                            <button
                                key={option.value}
                                className={`btn btn-sm join-item ${metric === option.value ? 'btn-primary' : 'btn-ghost'}`}
                                onClick={() => setMetric(option.value)}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>

                {loading ? (
                    <Loading />
                ) : (
                    <div ref={containerRef} className="rounded-lg border border-base-300" style={{ height: '420px', width: '100%' }} />
                )}
                {!loading && plottable.length === 0 && (
                    <div className="text-sm text-base-content/60 py-2 text-center">
                        No countries with both a resolved location and this metric yet.
                    </div>
                )}
            </div>
        </div>
    );
}
