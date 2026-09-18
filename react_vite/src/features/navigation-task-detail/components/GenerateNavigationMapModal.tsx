import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import {
  fetchFlightOrderConfiguration,
  fetchMapSourceOptions,
  fetchMapGenerationStatus,
  generateNavigationTaskMap,
  GenerateMapPayload,
  MapSourceOption,
} from '../api';

export interface GenerateNavigationMapModalHandle {
  open: () => void;
}

interface GenerateNavigationMapModalProps {
  contestId: number;
  navigationTaskId: number;
}

// Mirrors display/flight_order_and_maps/map_constants.py's SCALES - SCALE_TO_FIT (0) means "fit
// the route to the page" rather than a fixed printed scale. Same list as
// FlightOrderConfigurationModal.tsx's MAP_SCALE_OPTIONS.
const MAP_SCALE_OPTIONS = [
  { value: 0, label: 'Fit page' },
  { value: 25, label: '1:25,000' },
  { value: 50, label: '1:50,000' },
  { value: 100, label: '1:100,000' },
  { value: 150, label: '1:150,000' },
  { value: 200, label: '1:200,000' },
  { value: 250, label: '1:250,000' },
  { value: 300, label: '1:300,000' },
];

const POLL_INTERVAL_MS = 2000;
const POLL_RETRY_AFTER_ERROR_MS = 5000;

const GenerateNavigationMapModal = forwardRef<GenerateNavigationMapModalHandle, GenerateNavigationMapModalProps>(
  ({ contestId, navigationTaskId }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [payload, setPayload] = useState<GenerateMapPayload | null>(null);
    const [mapSourceOptions, setMapSourceOptions] = useState<MapSourceOption[]>([]);
    const [loading, setLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [generationState, setGenerationState] = useState<'idle' | 'pending' | 'complete' | 'error'>('idle');
    const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
    const [warning, setWarning] = useState<string | null>(null);

    const stopPolling = () => {
      if (pollTimeoutRef.current) {
        clearTimeout(pollTimeoutRef.current);
        pollTimeoutRef.current = null;
      }
    };

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [sources, config] = await Promise.all([
          fetchMapSourceOptions(contestId, navigationTaskId),
          fetchFlightOrderConfiguration(contestId, navigationTaskId),
        ]);
        setMapSourceOptions(sources);
        setPayload({
          size: config.document_size,
          orientation: config.map_orientation,
          plot_track_between_waypoints: config.map_plot_track_between_waypoints,
          include_meridians_and_parallels_lines: config.map_include_meridians_and_parallels_lines,
          scale: config.map_scale,
          map_source: config.map_source,
          include_openaip_overlay: config.map_include_openaip_overlay,
          zoom_level: config.map_zoom_level,
          dpi: config.map_dpi,
          line_width: config.map_line_width,
          colour: config.map_line_colour,
        });
      } catch (err: any) {
        setError(err.message || 'Failed to load map generation options');
      } finally {
        setLoading(false);
      }
    };

    useImperativeHandle(ref, () => ({
      open: () => {
        stopPolling();
        setGenerationState('idle');
        setDownloadUrl(null);
        setWarning(null);
        dialogRef.current?.showModal();
        load();
      },
    }));

    const pollStatus = (statusCheckUrl: string) => {
      fetchMapGenerationStatus(statusCheckUrl)
        .then((data) => {
          if (data.status === 'complete') {
            setGenerationState('complete');
            setWarning(data.warning || null);
            setDownloadUrl(data.url || null);
            if (data.url) {
              // Matches the classic map_generation_status.html page's behaviour: the download
              // starts automatically, the link is just a fallback if the browser blocks it.
              window.location.href = data.url;
            }
          } else if (data.status === 'error') {
            setGenerationState('error');
            setError(data.message || 'Map generation failed');
          } else {
            pollTimeoutRef.current = setTimeout(() => pollStatus(statusCheckUrl), POLL_INTERVAL_MS);
          }
        })
        .catch(() => {
          pollTimeoutRef.current = setTimeout(() => pollStatus(statusCheckUrl), POLL_RETRY_AFTER_ERROR_MS);
        });
    };

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (!payload) return;
      setSubmitting(true);
      setError(null);
      try {
        const { status_check_url } = await generateNavigationTaskMap(contestId, navigationTaskId, payload);
        setGenerationState('pending');
        pollStatus(status_check_url);
      } catch (err: any) {
        setError(err.message || 'Failed to start map generation');
      } finally {
        setSubmitting(false);
      }
    };

    const set = <K extends keyof GenerateMapPayload>(key: K, value: GenerateMapPayload[K]) =>
      setPayload((prev) => (prev ? { ...prev, [key]: value } : prev));

    const handleClose = () => {
      stopPolling();
      dialogRef.current?.close();
    };

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-2xl">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={handleClose}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">Generate navigation map</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}

          {payload && !loading && generationState === 'idle' && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="divider my-0 text-xs">Document</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Document size</span>
                  <select className="select select-bordered select-sm" value={payload.size} onChange={(e) => set('size', e.target.value)}>
                    <option value="A4">A4</option>
                    <option value="A3">A3</option>
                  </select>
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Orientation</span>
                  <select
                    className="select select-bordered select-sm"
                    value={payload.orientation}
                    onChange={(e) => set('orientation', e.target.value)}
                  >
                    <option value="portrait">Portrait</option>
                    <option value="landscape">Landscape</option>
                  </select>
                </label>
              </div>

              <div className="divider my-0 text-xs">Map source</div>
              <label className="form-control">
                <span className="label-text text-xs">Map source</span>
                <select
                  className="select select-bordered select-sm"
                  value={payload.map_source}
                  onChange={(e) => {
                    const source = mapSourceOptions.find((option) => option.key === e.target.value);
                    set('map_source', e.target.value);
                    if (source) set('zoom_level', source.default_zoom);
                  }}
                >
                  {!mapSourceOptions.some((option) => option.key === payload.map_source) && (
                    <option value={payload.map_source}>{payload.map_source}</option>
                  )}
                  {mapSourceOptions.some((option) => option.origin === 'builtin') && (
                    <optgroup label="Built-in">
                      {mapSourceOptions
                        .filter((option) => option.origin === 'builtin')
                        .map((option) => (
                          <option key={option.key} value={option.key}>
                            {option.label}
                          </option>
                        ))}
                    </optgroup>
                  )}
                  {mapSourceOptions.some((option) => option.origin === 'user_upload') && (
                    <optgroup label="Your uploaded maps">
                      {mapSourceOptions
                        .filter((option) => option.origin === 'user_upload')
                        .map((option) => (
                          <option key={option.key} value={option.key}>
                            {option.label}
                          </option>
                        ))}
                    </optgroup>
                  )}
                </select>
              </label>
              <div className="flex gap-2">
                {(() => {
                  const selectedSource = mapSourceOptions.find((option) => option.key === payload.map_source);
                  const minZoom = selectedSource?.min_zoom ?? 1;
                  const maxZoom = selectedSource?.max_zoom ?? 19;
                  return (
                    <label className="form-control flex-1">
                      <span className="label-text text-xs">
                        Zoom level ({minZoom}-{maxZoom})
                      </span>
                      <input
                        type="number"
                        min={minZoom}
                        max={maxZoom}
                        className="input input-bordered input-sm w-full"
                        value={payload.zoom_level}
                        onChange={(e) => set('zoom_level', Number(e.target.value))}
                      />
                    </label>
                  );
                })()}
                <label className="form-control flex-1">
                  <span className="label-text text-xs">DPI</span>
                  <input
                    type="number"
                    min={100}
                    max={300}
                    className="input input-bordered input-sm w-full"
                    value={payload.dpi}
                    onChange={(e) => set('dpi', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Map style</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Scale</span>
                  <select
                    className="select select-bordered select-sm"
                    value={payload.scale}
                    onChange={(e) => set('scale', Number(e.target.value))}
                  >
                    {MAP_SCALE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Line colour</span>
                  <input
                    type="color"
                    className="input input-bordered input-sm w-20 h-8 p-1"
                    value={payload.colour}
                    onChange={(e) => set('colour', e.target.value)}
                  />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Line width</span>
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    className="input input-bordered input-sm w-full"
                    value={payload.line_width}
                    onChange={(e) => set('line_width', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Map content</div>
              <div className="grid grid-cols-1 gap-1">
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={payload.plot_track_between_waypoints}
                    onChange={(e) => set('plot_track_between_waypoints', e.target.checked)}
                  />
                  <span className="label-text">Plot track between waypoints</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={payload.include_meridians_and_parallels_lines}
                    onChange={(e) => set('include_meridians_and_parallels_lines', e.target.checked)}
                  />
                  <span className="label-text">Include meridians/parallels</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={payload.include_openaip_overlay}
                    onChange={(e) => set('include_openaip_overlay', e.target.checked)}
                  />
                  <span className="label-text">Include OpenAIP overlay</span>
                </label>
              </div>

              <div role="alert" className="alert alert-warning text-sm mt-2">
                <span>
                  <b>Caution:</b> Map generation may require several minutes. Using large zoom levels (above 12) with
                  significant scales (1:200,000 or higher) could result in an out of memory error - if this happens,
                  decrease the zoom level.
                </span>
              </div>

              {error && <p className="text-error text-sm">{error}</p>}
              <div className="modal-action">
                <button type="submit" className="btn btn-primary btn-sm" disabled={submitting}>
                  {submitting ? 'Starting...' : 'Generate map'}
                </button>
              </div>
            </form>
          )}

          {generationState === 'pending' && (
            <div className="flex flex-col items-center py-8 gap-4">
              <span className="loading loading-spinner loading-lg text-primary" />
              <p className="text-sm text-gray-500">Generating your map - this may take a minute.</p>
            </div>
          )}

          {generationState === 'complete' && (
            <div className="flex flex-col items-center py-8 gap-4 text-center">
              <p className="text-success font-bold">Map generation complete!</p>
              {warning && <p className="text-warning text-sm">{warning}</p>}
              {downloadUrl && (
                <a href={downloadUrl} className="btn btn-primary">
                  Download map
                </a>
              )}
            </div>
          )}

          {generationState === 'error' && (
            <div className="flex flex-col items-center py-8 gap-4 text-center">
              <p className="text-error font-bold">Map generation failed</p>
              {error && <p className="text-error text-sm">{error}</p>}
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setGenerationState('idle')}>
                Try again
              </button>
            </div>
          )}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button onClick={handleClose}>close</button>
        </form>
      </dialog>
    );
  }
);

GenerateNavigationMapModal.displayName = 'GenerateNavigationMapModal';

export default GenerateNavigationMapModal;
