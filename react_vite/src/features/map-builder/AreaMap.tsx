import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Crop } from 'lucide-react';

import useLeafletMap from '../../hooks/useLeafletMap';
import type { Bounds } from './engine/tiles';

interface Props {
    bounds: Bounds | null;
    onDraw(bounds: Bounds): void;
}

const round = (value: number) => Math.round(value * 100000) / 100000;

/** World map for picking the area: drag a rectangle while drawing mode is on. */
const AreaMap: React.FC<Props> = ({ bounds, onDraw }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const map = useLeafletMap(containerRef, { initialCenter: [50, 10], initialZoom: 4 });
    const rectangleRef = useRef<L.Rectangle | null>(null);
    const [drawing, setDrawing] = useState(false);
    const zoomedToInitialArea = useRef(false);
    const onDrawRef = useRef(onDraw);
    useEffect(() => {
        onDrawRef.current = onDraw;
    }, [onDraw]);

    // Show the current area.
    useEffect(() => {
        if (!map) return;
        if (!bounds) {
            rectangleRef.current?.remove();
            rectangleRef.current = null;
            return;
        }
        const latLngBounds = L.latLngBounds([bounds.south, bounds.west], [bounds.north, bounds.east]);
        if (rectangleRef.current) rectangleRef.current.setBounds(latLngBounds);
        else rectangleRef.current = L.rectangle(latLngBounds, { color: '#d7301f', weight: 2, fillOpacity: 0.05, interactive: false }).addTo(map);
        if (!zoomedToInitialArea.current) {
            zoomedToInitialArea.current = true;
            map.fitBounds(latLngBounds, { padding: [30, 30] });
        }
    }, [map, bounds]);

    // Rectangle drawing.
    useEffect(() => {
        if (!map || !drawing) return;
        const container = map.getContainer();
        container.style.cursor = 'crosshair';
        map.dragging.disable();
        let start: L.LatLng | null = null;
        let preview: L.Rectangle | null = null;
        const down = (event: L.LeafletMouseEvent) => {
            start = event.latlng;
        };
        const move = (event: L.LeafletMouseEvent) => {
            if (!start) return;
            const box = L.latLngBounds(start, event.latlng);
            if (preview) preview.setBounds(box);
            else preview = L.rectangle(box, { color: '#d7301f', weight: 2, dashArray: '6 4', fillOpacity: 0.05, interactive: false }).addTo(map);
        };
        const up = (event: L.LeafletMouseEvent) => {
            if (!start) return;
            const box = L.latLngBounds(start, event.latlng);
            start = null;
            preview?.remove();
            preview = null;
            if (box.getNorth() - box.getSouth() > 1e-4 && box.getEast() - box.getWest() > 1e-4) {
                onDrawRef.current({
                    west: round(box.getWest()),
                    south: round(box.getSouth()),
                    east: round(box.getEast()),
                    north: round(box.getNorth()),
                });
                setDrawing(false);
            }
        };
        map.on('mousedown', down);
        map.on('mousemove', move);
        map.on('mouseup', up);
        return () => {
            map.off('mousedown', down);
            map.off('mousemove', move);
            map.off('mouseup', up);
            preview?.remove();
            map.dragging.enable();
            container.style.cursor = '';
        };
    }, [map, drawing]);

    const useView = () => {
        if (!map) return;
        const view = map.getBounds().pad(-0.1);
        onDraw({
            west: round(view.getWest()),
            south: round(view.getSouth()),
            east: round(view.getEast()),
            north: round(view.getNorth()),
        });
    };

    return (
        <div className="relative w-full h-full">
            <div ref={containerRef} className="w-full h-full" />
            <div className="absolute top-3 right-3 z-[1000] flex flex-col sm:flex-row gap-2">
                <button
                    type="button"
                    className={`btn btn-sm shadow ${drawing ? 'btn-warning' : 'btn-primary'}`}
                    onClick={() => setDrawing(value => !value)}
                >
                    <Crop size={16} /> {drawing ? 'Drag on the map… (click to stop)' : 'Draw area'}
                </button>
                <button type="button" className="btn btn-sm shadow" onClick={useView}>
                    Use current view
                </button>
            </div>
        </div>
    );
};

export default AreaMap;
