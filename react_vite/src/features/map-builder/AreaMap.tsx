import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Crop, Eye, EyeOff, Layers, Maximize2 } from 'lucide-react';

import useLeafletMap from '../../hooks/useLeafletMap';
import type { GeneratedMap } from './engine/generate';
import { tileKey } from './engine/generate';
import type { Bounds } from './engine/tiles';
import { gridBounds, tileGridForBounds } from './engine/tiles';

interface Props {
    bounds: Bounds | null;
    fullBounds?: Bounds | null;
    onDraw(bounds: Bounds): void;
    preview?: GeneratedMap | null;
    showPreview?: boolean;
    onTogglePreview?: () => void;
}

const round = (value: number) => Math.round(value * 100000) / 100000;

/** World map for picking the area and interactively previewing the generated MBTiles levels. */
const AreaMap: React.FC<Props> = ({ bounds, fullBounds = null, onDraw, preview = null, showPreview = false, onTogglePreview }) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const map = useLeafletMap(containerRef, { initialCenter: [50, 10], initialZoom: 4 });
    const rectangleRef = useRef<L.Rectangle | null>(null);
    const fullRectangleRef = useRef<L.Rectangle | null>(null);
    const previewLayerRef = useRef<L.GridLayer | null>(null);
    const lastFocusedPreviewRef = useRef<GeneratedMap | null>(null);
    const [drawing, setDrawing] = useState(false);
    const [currentZoom, setCurrentZoom] = useState<number>(4);
    const [translucent, setTranslucent] = useState(false);
    const zoomedToInitialArea = useRef(false);
    const onDrawRef = useRef(onDraw);
    useEffect(() => {
        onDrawRef.current = onDraw;
    }, [onDraw]);

    // Track current map zoom level so the preview toolbar highlights the active level.
    useEffect(() => {
        if (!map) return;
        const updateZoom = () => setCurrentZoom(Math.round(map.getZoom()));
        updateZoom();
        map.on('zoomend', updateZoom);
        return () => {
            map.off('zoomend', updateZoom);
        };
    }, [map]);

    // Show the current area rectangle.
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

    // Show the dashed outline of the full competition area while experimenting on a shrunk 3×3 test section.
    useEffect(() => {
        if (!map) return;
        if (!fullBounds) {
            fullRectangleRef.current?.remove();
            fullRectangleRef.current = null;
            return;
        }
        const latLngBounds = L.latLngBounds([fullBounds.south, fullBounds.west], [fullBounds.north, fullBounds.east]);
        if (fullRectangleRef.current) fullRectangleRef.current.setBounds(latLngBounds);
        else {
            fullRectangleRef.current = L.rectangle(latLngBounds, {
                color: '#64748b',
                weight: 2,
                dashArray: '6 6',
                fillOpacity: 0.02,
                interactive: false,
            }).addTo(map);
        }
    }, [map, fullBounds]);

    // Render generated tiles directly on the Leaflet map so all zoom levels can be explored at 1:1 scale.
    useEffect(() => {
        if (!map) return;
        previewLayerRef.current?.remove();
        previewLayerRef.current = null;
        if (!preview || !showPreview) return;

        const coarsestBounds = gridBounds(tileGridForBounds(preview.area.bounds, preview.area.minZoom));
        const tileBounds = L.latLngBounds([coarsestBounds.south, coarsestBounds.west], [coarsestBounds.north, coarsestBounds.east]);

        const PreviewGridLayer = L.GridLayer.extend({
            createTile(coords: L.Coords, done: L.DoneCallback) {
                const tile = document.createElement('img');
                tile.alt = '';
                tile.setAttribute('role', 'presentation');
                const data = preview.tiles.get(tileKey(coords.z, coords.x, coords.y));
                if (!data) {
                    setTimeout(() => done(undefined, tile), 0);
                    return tile;
                }
                const url = URL.createObjectURL(new Blob([data as BlobPart], { type: 'image/png' }));
                tile.onload = () => {
                    URL.revokeObjectURL(url);
                    done(undefined, tile);
                };
                tile.onerror = error => {
                    URL.revokeObjectURL(url);
                    done(error as unknown as Error, tile);
                };
                tile.src = url;
                return tile;
            },
        });

        const layer: L.GridLayer = new (PreviewGridLayer as unknown as new (options: L.GridLayerOptions) => L.GridLayer)({
            tileSize: 256,
            minZoom: Math.max(2, preview.area.minZoom - 3),
            maxZoom: Math.min(18, preview.area.maxZoom + 2),
            minNativeZoom: preview.area.minZoom,
            maxNativeZoom: preview.area.maxZoom,
            bounds: tileBounds,
            opacity: translucent ? 0.65 : 1,
            zIndex: 400,
        });
        layer.addTo(map);
        previewLayerRef.current = layer;

        // When a newly generated map finishes, center on its area at the detail zoom level for immediate 1:1 inspection.
        if (lastFocusedPreviewRef.current !== preview) {
            lastFocusedPreviewRef.current = preview;
            const areaLatLng = L.latLngBounds(
                [preview.area.bounds.south, preview.area.bounds.west],
                [preview.area.bounds.north, preview.area.bounds.east],
            );
            const center = areaLatLng.contains(map.getCenter()) ? map.getCenter() : areaLatLng.getCenter();
            map.setView(center, preview.area.maxZoom);
        }

        return () => {
            layer.remove();
            if (previewLayerRef.current === layer) previewLayerRef.current = null;
        };
    }, [map, preview, showPreview, translucent]);

    // Update opacity dynamically without recreating tiles.
    useEffect(() => {
        previewLayerRef.current?.setOpacity(translucent ? 0.65 : 1);
    }, [translucent]);

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

    const fitPreviewArea = () => {
        if (!map || !preview) return;
        const box = L.latLngBounds(
            [preview.area.bounds.south, preview.area.bounds.west],
            [preview.area.bounds.north, preview.area.bounds.east],
        );
        map.fitBounds(box, { padding: [30, 30], maxZoom: preview.area.maxZoom });
    };

    const previewZooms = preview
        ? Array.from({ length: preview.area.maxZoom - preview.area.minZoom + 1 }, (_, i) => preview.area.minZoom + i)
        : [];

    return (
        <div className="relative w-full h-full">
            <div ref={containerRef} className="w-full h-full" />
            {preview && (
                <div className="absolute top-3 left-14 z-[1000] flex flex-wrap items-center gap-1.5 bg-base-100/95 backdrop-blur px-2.5 py-1.5 rounded-lg shadow border border-base-300">
                    {onTogglePreview && (
                        <button
                            type="button"
                            className={`btn btn-xs ${showPreview ? 'btn-primary' : 'btn-ghost'}`}
                            onClick={onTogglePreview}
                            title={showPreview ? 'Hide the generated tiles to see the base map underneath' : 'Show the generated map tiles on the map'}
                        >
                            {showPreview ? <Eye size={14} /> : <EyeOff size={14} />}
                            {showPreview ? 'Previewing result' : 'Preview hidden'}
                        </button>
                    )}
                    {showPreview && (
                        <>
                            <span className="text-xs opacity-70 ml-1">Zoom:</span>
                            {previewZooms.map(zoom => (
                                <button
                                    key={zoom}
                                    type="button"
                                    className={`btn btn-xs ${currentZoom === zoom ? 'btn-secondary' : 'btn-ghost'}`}
                                    onClick={() => map?.setZoom(zoom)}
                                    title={`Inspect generated zoom level ${zoom} at 1:1 resolution`}
                                >
                                    {zoom}
                                </button>
                            ))}
                            {(currentZoom < preview.area.minZoom || currentZoom > preview.area.maxZoom) && (
                                <span className="badge badge-ghost badge-xs" title="Current map zoom (scaled from nearest generated level)">
                                    now {currentZoom}
                                </span>
                            )}
                            <button
                                type="button"
                                className={`btn btn-xs ${translucent ? 'btn-accent' : 'btn-ghost'}`}
                                onClick={() => setTranslucent(value => !value)}
                                title="Make generated tiles semi-transparent to compare with the OpenStreetMap base map"
                            >
                                <Layers size={14} /> {translucent ? '65%' : '100%'}
                            </button>
                            <button
                                type="button"
                                className="btn btn-xs btn-ghost"
                                onClick={fitPreviewArea}
                                title="Fit the generated map area in view"
                            >
                                <Maximize2 size={14} /> Fit
                            </button>
                        </>
                    )}
                </div>
            )}
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
