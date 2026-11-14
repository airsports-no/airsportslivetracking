import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Download, FlaskConical, Map as MapIcon, Play, RotateCcw, Save, Square, Wand2 } from 'lucide-react';

import { reverse } from '../../urls';
import AreaMap from './AreaMap';
import LayerList from './LayerList';
import { MAX_ATTRIBUTION_LENGTH, fileNameFor, saveGeneratedMap } from './api';
import type { DataCache, GeneratedMap } from './engine/generate';
import { MAX_FILE_BYTES, createDataCache, generateMap } from './engine/generate';
import { preferredSourceId, sourcesCovering } from './engine/sources';
import type { Bounds, MapArea } from './engine/tiles';
import { MAX_DETAIL_TILES, SAMPLE_SIDE_TILES, isValidBounds, sampleBounds, summariseArea } from './engine/tiles';
import type { LogLevel } from './engine/types';
import { CancelledError } from './engine/types';
import { loadSqlJs } from './loadSqlJs';
import type { BuilderSettings } from './settings';
import { DETAIL_ZOOMS, MAX_EXTRA_LEVELS, loadSettings, saveSettings } from './settings';

interface LogLine {
    message: string;
    level: LogLevel;
}

const LOG_CLASS: Record<LogLevel, string> = {
    info: '',
    success: 'text-success',
    warning: 'text-warning',
    error: 'text-error',
};

const megabytes = (bytes: number) => (bytes / 1048576).toFixed(1);

/** The zoom used for printed navigation maps unless the user picks another. */
const PREFERRED_PRINT_ZOOM = 12;

const Section: React.FC<{ step: number; title: string; children: React.ReactNode }> = ({ step, title, children }) => (
    <section className="space-y-2">
        <h2 className="font-semibold flex items-center gap-2">
            <span className="badge badge-primary badge-sm">{step}</span> {title}
        </h2>
        {children}
    </section>
);

const MapBuilderPage: React.FC = () => {
    const [settings, setSettings] = useState<BuilderSettings>(loadSettings);
    const [running, setRunning] = useState(false);
    const [progress, setProgress] = useState<number | null>(null);
    const [status, setStatus] = useState('');
    const [log, setLog] = useState<LogLine[]>([]);
    const [result, setResult] = useState<GeneratedMap | null>(null);
    const [showPreview, setShowPreview] = useState(false);
    const [fullBounds, setFullBounds] = useState<Bounds | null>(null);
    const [printZoom, setPrintZoom] = useState(PREFERRED_PRINT_ZOOM);
    const [saveState, setSaveState] = useState<{ kind: 'idle' | 'saving' | 'saved' | 'error'; message?: string }>({ kind: 'idle' });
    const abortRef = useRef<AbortController | null>(null);
    const cacheRef = useRef<DataCache>(createDataCache());
    const previewRef = useRef<HTMLCanvasElement>(null);
    const logRef = useRef<HTMLDivElement>(null);

    useEffect(() => saveSettings(settings), [settings]);
    useEffect(() => {
        logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
    }, [log]);
    // Stop a running job when leaving the page.
    useEffect(() => () => abortRef.current?.abort(), []);

    const update = (changes: Partial<BuilderSettings>) => setSettings(current => ({ ...current, ...changes }));

    const bounds: Bounds | null = useMemo(() => {
        const candidate = {
            west: parseFloat(settings.west),
            south: parseFloat(settings.south),
            east: parseFloat(settings.east),
            north: parseFloat(settings.north),
        };
        return isValidBounds(candidate) ? candidate : null;
    }, [settings.west, settings.south, settings.east, settings.north]);

    const area: MapArea | null = bounds ? { bounds, minZoom: settings.minZoom, maxZoom: settings.maxZoom } : null;
    const summary = area ? summariseArea(area) : null;
    const availableSources = bounds ? sourcesCovering(bounds) : [];
    const sourceId = bounds ? preferredSourceId(bounds, settings.sourcePreference) : 'osm';
    const selectedSource = availableSources.find(source => source.id === sourceId);
    const name = settings.name.trim();

    const setBounds = (value: Bounds) =>
        update({ west: String(value.west), south: String(value.south), east: String(value.east), north: String(value.north) });

    const handleDrawBounds = (value: Bounds) => {
        setFullBounds(null);
        setBounds(value);
    };

    const shrinkToTestArea = () => {
        if (!bounds) return;
        const sample = sampleBounds(bounds, settings.maxZoom);
        if (sample === bounds) return;
        if (!fullBounds) setFullBounds(bounds);
        setBounds(sample);
    };

    const restoreFullArea = () => {
        if (!fullBounds) return;
        setBounds(fullBounds);
        setFullBounds(null);
    };

    const fullAreaSummary = useMemo(
        () => (fullBounds ? summariseArea({ bounds: fullBounds, minZoom: settings.minZoom, maxZoom: settings.maxZoom }) : null),
        [fullBounds, settings.minZoom, settings.maxZoom],
    );
    const canShrinkToSample = !!bounds && !!summary && summary.detailGrid.tileCount > SAMPLE_SIDE_TILES * SAMPLE_SIDE_TILES;

    const setDetailZoom = (maxZoom: number) => {
        const levels = settings.maxZoom - settings.minZoom;
        update({ maxZoom, minZoom: maxZoom - levels });
    };

    const generateForArea = async (targetArea: MapArea) => {
        const targetSummary = summariseArea(targetArea);
        if (targetSummary.tooLarge || !name) return;
        const controller = new AbortController();
        abortRef.current = controller;
        setRunning(true);
        setResult(null);
        setShowPreview(false);
        setSaveState({ kind: 'idle' });
        setLog([]);
        setProgress(0);
        const reporter = {
            log: (message: string, level: LogLevel = 'info') => setLog(lines => [...lines, { message, level }]),
            progress: (fraction: number) => setProgress(fraction),
            status: (message: string) => setStatus(message),
        };
        try {
            const SQL = await loadSqlJs();
            setShowPreview(true);
            const generated = await generateMap(
                {
                    name,
                    area: targetArea,
                    featureBounds: fullBounds,
                    sourceId: preferredSourceId(targetArea.bounds, settings.sourcePreference),
                    layers: settings.layers,
                    terrain: settings.terrain,
                    lowerLevels: settings.lowerLevels,
                    lineScale: settings.lineScale,
                },
                SQL,
                cacheRef.current,
                { signal: controller.signal, reporter },
                previewRef.current,
            );
            setResult(generated);
            setPrintZoom(Math.min(targetArea.maxZoom, Math.max(targetArea.minZoom, PREFERRED_PRINT_ZOOM)));
            reporter.log(
                `Finished: ${generated.tileCount} tiles, ${megabytes(generated.file.length)} MB, in ${generated.seconds.toFixed(0)} s.`,
                'success',
            );
        } catch (error) {
            setShowPreview(false);
            if (error instanceof CancelledError || controller.signal.aborted) reporter.log('Cancelled.', 'warning');
            else {
                console.error(error);
                reporter.log(`Error: ${(error as Error).message}`, 'error');
            }
        } finally {
            setRunning(false);
            setStatus('');
            setProgress(null);
            abortRef.current = null;
        }
    };

    const generate = () => {
        if (!area) return;
        void generateForArea(area);
    };

    const restoreAndGenerateFull = () => {
        if (!fullBounds || !name || running) return;
        const targetBounds = fullBounds;
        setBounds(targetBounds);
        setFullBounds(null);
        void generateForArea({ bounds: targetBounds, minZoom: settings.minZoom, maxZoom: settings.maxZoom });
    };

    const download = () => {
        if (!result) return;
        const url = URL.createObjectURL(new Blob([result.file as BlobPart], { type: 'application/vnd.sqlite3' }));
        const link = document.createElement('a');
        link.href = url;
        link.download = fileNameFor(result.name);
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
    };

    const save = async () => {
        if (!result) return;
        setSaveState({ kind: 'saving' });
        try {
            await saveGeneratedMap({ name: result.name, file: result.file, defaultZoom: printZoom, attribution: result.attribution });
            setSaveState({ kind: 'saved' });
        } catch (error) {
            setSaveState({ kind: 'error', message: (error as Error).message });
        }
    };

    const tooBigToSave = !!result && result.file.length > MAX_FILE_BYTES;
    const canGenerate = !!summary && !summary.tooLarge && !!name && !running;
    const zoomRange = (zoom: number) => (zoom === settings.maxZoom ? `${zoom}` : `${zoom}–${settings.maxZoom}`);

    return (
        <div className="flex-1 min-h-0 flex flex-col lg:flex-row bg-base-200 text-base-content">
            <aside className="lg:w-[26rem] shrink-0 overflow-y-auto bg-base-100 border-r border-base-300 p-4 space-y-6 order-2 lg:order-1">
                <div className="space-y-2">
                    <a href={reverse('useruploadedmap_list')} className="link link-hover text-sm inline-flex items-center gap-1 opacity-70">
                        <ArrowLeft size={14} /> My maps
                    </a>
                    <h1 className="text-xl font-bold flex items-center gap-2 mt-1">
                        <Wand2 size={22} /> Map builder
                    </h1>
                    <p className="text-sm opacity-70">
                        Compose a map background from open map data and terrain, and save it to My maps to use in
                        the route editor and on navigation maps. Your browser downloads the data directly from the
                        map data providers and draws the map itself.
                    </p>
                    <div className="bg-base-200 rounded-lg p-3 text-xs space-y-1">
                        <div className="font-semibold">Recommended workflow</div>
                        <ol className="list-decimal list-inside space-y-0.5 opacity-80">
                            <li>
                                <strong>Draw your full competition area</strong> on the map, then click{' '}
                                <strong>Shrink to small test area</strong>.
                            </li>
                            <li>
                                <strong>Preview &amp; tune on the test area:</strong> generate the small sample in seconds, pan/zoom the
                                result on the map, and tweak layers or terrain (re-renders use cached data).
                            </li>
                            <li>
                                <strong>Restore full area, generate &amp; save:</strong> expand back to the full competition extent,
                                generate the final file, and save it to <strong>My maps</strong>.
                            </li>
                        </ol>
                    </div>
                </div>

                <Section step={1} title="Area and zoom levels">
                    <p className="text-sm opacity-70">Draw a rectangle on the map, or type the coordinates in decimal degrees.</p>
                    <div className="grid grid-cols-2 gap-2">
                        {(['north', 'south', 'west', 'east'] as const).map(side => (
                            <label key={side} className="form-control">
                                <span className="label-text text-xs capitalize">{side}</span>
                                <input
                                    type="number"
                                    step="any"
                                    className="input input-bordered input-sm w-full"
                                    value={settings[side]}
                                    disabled={running}
                                    onChange={event => update({ [side]: event.target.value })}
                                />
                            </label>
                        ))}
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                        <label className="form-control">
                            <span className="label-text text-xs">Most detailed zoom</span>
                            <select
                                className="select select-bordered select-sm w-full"
                                value={settings.maxZoom}
                                disabled={running}
                                onChange={event => setDetailZoom(Number(event.target.value))}
                            >
                                {DETAIL_ZOOMS.map(zoom => (
                                    <option key={zoom} value={zoom}>
                                        {zoom}
                                        {zoom === 13 ? ' (recommended)' : ''}
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label className="form-control">
                            <span className="label-text text-xs">Zoom levels in the file</span>
                            <select
                                className="select select-bordered select-sm w-full"
                                value={settings.minZoom}
                                disabled={running}
                                onChange={event => update({ minZoom: Number(event.target.value) })}
                            >
                                {Array.from({ length: MAX_EXTRA_LEVELS + 1 }, (_, levels) => settings.maxZoom - levels).map(zoom => (
                                    <option key={zoom} value={zoom}>
                                        {zoomRange(zoom)}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                    {settings.minZoom < settings.maxZoom && (
                        <label className="form-control">
                            <span className="label-text text-xs">Lower zoom levels</span>
                            <select
                                className="select select-bordered select-sm w-full"
                                value={settings.lowerLevels}
                                disabled={running}
                                onChange={event => update({ lowerLevels: event.target.value as BuilderSettings['lowerLevels'] })}
                            >
                                <option value="redrawn">Redrawn: same line weights, clearer when printed (recommended)</option>
                                <option value="scaled">Shrunk from zoom {settings.maxZoom}: finer lines, less crowded</option>
                            </select>
                        </label>
                    )}
                    <p className="text-xs opacity-70">
                        Navigation maps are usually printed at zoom 12. Redrawing zoom 12 keeps full road and railway
                        widths so they stay visible when printed at 1:200,000–1:250,000; shrinking from zoom 13 gives
                        finer lines if the area is dense. Each extra level adds about a third to the file size.
                    </p>
                    {!bounds && <div className="text-sm text-warning">Draw an area or enter valid coordinates (west &lt; east, south &lt; north).</div>}
                    {summary && (
                        <div className="text-sm">
                            {summary.widthKm.toFixed(0)} × {summary.heightKm.toFixed(0)} km · {summary.detailGrid.tileCount} tiles at zoom{' '}
                            {settings.maxZoom} ({summary.totalTiles} in total) · {summary.metresPerPixel.toFixed(1)} m per pixel
                            {summary.tooLarge ? (
                                <div role="alert" className="alert alert-error py-2 mt-2 text-sm">
                                    Too large for zoom {settings.maxZoom}: at most {MAX_DETAIL_TILES} tiles. Make the area smaller or lower the zoom.
                                </div>
                            ) : (
                                summary.detailGrid.tileCount > 600 && (
                                    <div className="text-warning mt-1">Large area: downloading the data may take several minutes.</div>
                                )
                            )}
                        </div>
                    )}
                    <div className="bg-base-200 rounded-lg p-2.5 space-y-2 text-xs">
                        <p className="opacity-80">
                            <strong>Tip:</strong> Experiment on a small test section first (a few tiles) to preview layers, terrain shading, and
                            zoom levels interactively. Downloaded data for the test section is cached while you tweak settings; once happy,
                            restore the full area and generate the final map.
                        </p>
                        {(canShrinkToSample || fullBounds) && (
                            <div className="flex flex-wrap gap-2">
                                {canShrinkToSample && (
                                    <button
                                        type="button"
                                        className="btn btn-xs btn-outline"
                                        disabled={running}
                                        onClick={shrinkToTestArea}
                                    >
                                        <FlaskConical size={13} /> Shrink to small test area ({SAMPLE_SIDE_TILES}×{SAMPLE_SIDE_TILES} tiles)
                                    </button>
                                )}
                                {fullBounds && (
                                    <button
                                        type="button"
                                        className="btn btn-xs btn-secondary"
                                        disabled={running}
                                        onClick={restoreFullArea}
                                    >
                                        <RotateCcw size={13} /> Restore full area
                                        {fullAreaSummary ? ` (${fullAreaSummary.widthKm.toFixed(0)} × ${fullAreaSummary.heightKm.toFixed(0)} km)` : ''}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                </Section>

                <Section step={2} title="Map data">
                    <label className="form-control">
                        <span className="label-text text-xs">Data source</span>
                        <select
                            className="select select-bordered select-sm w-full"
                            value={sourceId}
                            disabled={running || availableSources.length < 2}
                            onChange={event => update({ sourcePreference: event.target.value })}
                        >
                            {availableSources.map(source => (
                                <option key={source.id} value={source.id}>
                                    {source.name}
                                </option>
                            ))}
                        </select>
                    </label>
                    {selectedSource && <p className="text-xs opacity-70">{selectedSource.description}</p>}
                    <label className="block">
                        <span className="text-xs flex justify-between">
                            Line thickness <span>{settings.lineScale.toFixed(1)}×</span>
                        </span>
                        <input
                            type="range"
                            className="range range-xs"
                            min={0.5}
                            max={2.5}
                            step={0.1}
                            value={settings.lineScale}
                            disabled={running}
                            onChange={event => update({ lineScale: Number(event.target.value) })}
                        />
                    </label>
                    <LayerList
                        selection={settings.layers}
                        sourceId={sourceId}
                        lineScale={settings.lineScale}
                        disabled={running}
                        onChange={layers => update({ layers })}
                    />
                </Section>

                <Section step={3} title="Terrain">
                    <label className="flex items-center gap-2 cursor-pointer">
                        <input
                            type="checkbox"
                            className="checkbox checkbox-sm"
                            checked={settings.terrain.hillshade}
                            disabled={running}
                            onChange={event => update({ terrain: { ...settings.terrain, hillshade: event.target.checked } })}
                        />
                        <span className="text-sm">Shaded relief</span>
                    </label>
                    {settings.terrain.hillshade && (
                        <div className="space-y-1 pl-7">
                            <label className="block">
                                <span className="text-xs flex justify-between">
                                    Vertical exaggeration <span>{settings.terrain.exaggeration.toFixed(1)}×</span>
                                </span>
                                <input
                                    type="range"
                                    className="range range-xs"
                                    min={0.8}
                                    max={3}
                                    step={0.1}
                                    value={settings.terrain.exaggeration}
                                    disabled={running}
                                    onChange={event => update({ terrain: { ...settings.terrain, exaggeration: Number(event.target.value) } })}
                                />
                            </label>
                            <label className="block">
                                <span className="text-xs flex justify-between">
                                    Shading strength <span>{Math.round(settings.terrain.intensity * 100)}%</span>
                                </span>
                                <input
                                    type="range"
                                    className="range range-xs"
                                    min={0.3}
                                    max={1}
                                    step={0.02}
                                    value={settings.terrain.intensity}
                                    disabled={running}
                                    onChange={event => update({ terrain: { ...settings.terrain, intensity: Number(event.target.value) } })}
                                />
                            </label>
                        </div>
                    )}
                    <div className="flex items-center gap-2">
                        <label className="flex items-center gap-2 cursor-pointer">
                            <input
                                type="checkbox"
                                className="checkbox checkbox-sm"
                                checked={settings.terrain.contours}
                                disabled={running}
                                onChange={event => update({ terrain: { ...settings.terrain, contours: event.target.checked } })}
                            />
                            <span className="text-sm">Contour lines every</span>
                        </label>
                        <select
                            className="select select-bordered select-xs"
                            value={settings.terrain.contourInterval}
                            disabled={running || !settings.terrain.contours}
                            onChange={event => update({ terrain: { ...settings.terrain, contourInterval: Number(event.target.value) } })}
                        >
                            <option value={50}>50 m</option>
                            <option value={10}>10 m (50 m bold)</option>
                        </select>
                    </div>
                </Section>

                <Section step={4} title="Generate">
                    <label className="form-control">
                        <span className="label-text text-xs">Map name</span>
                        <input
                            type="text"
                            className="input input-bordered input-sm w-full"
                            maxLength={200}
                            placeholder="For example: Nationals 2027 practice area"
                            value={settings.name}
                            disabled={running}
                            onChange={event => update({ name: event.target.value })}
                        />
                    </label>
                    <div className="flex flex-wrap gap-2">
                        <button type="button" className="btn btn-primary btn-sm" disabled={!canGenerate} onClick={generate}>
                            <Play size={16} />{' '}
                            {fullBounds && summary ? `Generate test preview (${summary.totalTiles} tiles)` : 'Generate map'}
                        </button>
                        {fullBounds && !running && (
                            <button
                                type="button"
                                className="btn btn-secondary btn-sm"
                                disabled={!name || (fullAreaSummary?.tooLarge ?? false)}
                                onClick={restoreAndGenerateFull}
                                title="Restore the full competition area and generate the final map"
                            >
                                <RotateCcw size={15} /> Restore &amp; generate full map
                            </button>
                        )}
                        {running && (
                            <button type="button" className="btn btn-sm" onClick={() => abortRef.current?.abort()}>
                                <Square size={16} /> Cancel
                            </button>
                        )}
                    </div>
                    {progress !== null && <progress className="progress progress-primary w-full" value={progress * 100} max={100} />}
                    {status && <div className="text-xs opacity-70">{status}</div>}
                    {log.length > 0 && (
                        <div ref={logRef} className="bg-base-200 rounded p-2 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5">
                            {log.map((line, index) => (
                                <div key={index} className={`whitespace-pre-wrap ${LOG_CLASS[line.level]}`}>
                                    {line.message}
                                </div>
                            ))}
                        </div>
                    )}
                </Section>

                {result && (
                    <Section step={5} title="Preview and save">
                        <div className="text-sm">
                            {result.name} · zoom {result.area.minZoom === result.area.maxZoom ? result.area.maxZoom : `${result.area.minZoom}–${result.area.maxZoom}`} ·{' '}
                            {megabytes(result.file.length)} MB
                        </div>
                        <p className="text-xs opacity-70">
                            Pan and zoom the map on the right to inspect the generated tiles at 1:1 resolution. Use the zoom buttons at the top
                            of the map to compare each generated zoom level before saving.
                        </p>
                        {fullBounds && (
                            <div role="alert" className="alert alert-info py-2 text-xs flex flex-col items-start gap-1.5">
                                <span>
                                    You are currently previewing the small test area (the dashed outline on the map shows your full competition
                                    area). Once you are satisfied with the look, generate the full area before saving.
                                </span>
                                <div className="flex flex-wrap gap-1.5">
                                    <button
                                        type="button"
                                        className="btn btn-xs btn-secondary"
                                        disabled={running || !name || (fullAreaSummary?.tooLarge ?? false)}
                                        onClick={restoreAndGenerateFull}
                                    >
                                        <Play size={13} /> Restore &amp; generate full area
                                        {fullAreaSummary ? ` (${fullAreaSummary.widthKm.toFixed(0)} × ${fullAreaSummary.heightKm.toFixed(0)} km)` : ''}
                                    </button>
                                    <button type="button" className="btn btn-xs btn-ghost" disabled={running} onClick={restoreFullArea}>
                                        <RotateCcw size={13} /> Restore full area only
                                    </button>
                                </div>
                            </div>
                        )}
                        {result.area.minZoom < result.area.maxZoom && (
                            <label className="form-control">
                                <span className="label-text text-xs">Zoom for navigation maps</span>
                                <select
                                    className="select select-bordered select-sm w-full"
                                    value={printZoom}
                                    onChange={event => setPrintZoom(Number(event.target.value))}
                                >
                                    {Array.from({ length: result.area.maxZoom - result.area.minZoom + 1 }, (_, i) => result.area.minZoom + i).map(zoom => (
                                        <option key={zoom} value={zoom}>
                                            {zoom}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}
                        {tooBigToSave && (
                            <div role="alert" className="alert alert-warning py-2 text-sm">
                                The file is larger than the {megabytes(MAX_FILE_BYTES)} MB limit for My maps. Make the area smaller or drop a zoom level.
                            </div>
                        )}
                        {result.attribution.length > MAX_ATTRIBUTION_LENGTH && (
                            <div className="text-xs text-warning">The attribution will be shortened to {MAX_ATTRIBUTION_LENGTH} characters.</div>
                        )}
                        <div className="flex flex-wrap gap-2">
                            <button
                                type="button"
                                className="btn btn-primary btn-sm"
                                disabled={tooBigToSave || saveState.kind === 'saving' || saveState.kind === 'saved' || !document.configuration.isOrganizer}
                                onClick={save}
                            >
                                {saveState.kind === 'saving' ? <span className="loading loading-spinner loading-xs" /> : <Save size={16} />} Save to My maps
                            </button>
                            <button type="button" className="btn btn-sm" onClick={download}>
                                <Download size={16} /> Download .mbtiles
                            </button>
                            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowPreview(value => !value)}>
                                <MapIcon size={16} /> {showPreview ? 'Hide preview on map' : 'Show preview on map'}
                            </button>
                        </div>
                        {!document.configuration.isOrganizer && (
                            <div className="text-xs opacity-70">Saving to My maps needs an organiser account. You can download the file.</div>
                        )}
                        {saveState.kind === 'saved' && (
                            <div role="alert" className="alert alert-success py-2 text-sm">
                                <span>
                                    Saved. The map is being processed and shows up in{' '}
                                    <a className="link" href={reverse('useruploadedmap_list')}>
                                        My maps
                                    </a>{' '}
                                    in a minute.
                                </span>
                            </div>
                        )}
                        {saveState.kind === 'error' && (
                            <div role="alert" className="alert alert-error py-2 text-sm">
                                {saveState.message}
                            </div>
                        )}
                    </Section>
                )}

                <p className="text-xs opacity-60">
                    Data: © OpenStreetMap contributors (ODbL), distributed by the Overture Maps Foundation · Terrain:
                    Mapterhorn (Copernicus GLO-30 © ESA and national elevation models) · Spain: National Topographic Base
                    © IGN-CNIG (CC BY 4.0). Airspace is added by Air Sports Live Tracking when maps are printed. Not for
                    real-world air navigation.
                </p>
            </aside>

            <div className="flex-1 min-h-[50vh] lg:min-h-0 relative order-1 lg:order-2">
                <AreaMap
                    bounds={bounds}
                    fullBounds={fullBounds}
                    onDraw={handleDrawBounds}
                    preview={result}
                    showPreview={showPreview}
                    onTogglePreview={() => setShowPreview(value => !value)}
                />
                <div className={`absolute inset-0 z-[1100] bg-base-300 overflow-auto ${running && showPreview ? '' : 'hidden'}`}>
                    <canvas ref={previewRef} className="block mx-auto max-w-full h-auto" />
                </div>
            </div>
        </div>
    );
};

export default MapBuilderPage;
