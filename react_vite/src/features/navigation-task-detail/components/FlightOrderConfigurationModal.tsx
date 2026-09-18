import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import {
  fetchFlightOrderConfiguration,
  fetchMapSourceOptions,
  FlightOrderConfiguration,
  MapSourceOption,
  updateFlightOrderConfiguration,
} from '../api';

export interface FlightOrderConfigurationModalHandle {
  open: () => void;
}

interface FlightOrderConfigurationModalProps {
  contestId: number;
  navigationTaskId: number;
}

// Mirrors display/flight_order_and_maps/map_constants.py's SCALES - SCALE_TO_FIT (0) means "fit
// the route to the page" rather than a fixed printed scale.
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

const FlightOrderConfigurationModal = forwardRef<FlightOrderConfigurationModalHandle, FlightOrderConfigurationModalProps>(
  ({ contestId, navigationTaskId }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [config, setConfig] = useState<FlightOrderConfiguration | null>(null);
    const [mapSourceOptions, setMapSourceOptions] = useState<MapSourceOption[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, sources] = await Promise.all([
          fetchFlightOrderConfiguration(contestId, navigationTaskId),
          fetchMapSourceOptions(contestId, navigationTaskId),
        ]);
        setConfig(data);
        setMapSourceOptions(sources);
      } catch (err: any) {
        setError(err.message || 'Failed to load flight order configuration');
      } finally {
        setLoading(false);
      }
    };

    useImperativeHandle(ref, () => ({
      open: () => {
        dialogRef.current?.showModal();
        load();
      },
    }));

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (!config) return;
      setSaving(true);
      setError(null);
      try {
        const updated = await updateFlightOrderConfiguration(contestId, navigationTaskId, config);
        setConfig(updated);
      } catch (err: any) {
        setError(err.message || 'Failed to save flight order configuration');
      } finally {
        setSaving(false);
      }
    };

    const set = <K extends keyof FlightOrderConfiguration>(key: K, value: FlightOrderConfiguration[K]) =>
      setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-2xl max-h-[85vh]">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={() => dialogRef.current?.close()}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">Flight order configuration</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}

          {config && !loading && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="divider my-0 text-xs">Document</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Document size</span>
                  <select
                    className="select select-bordered select-sm"
                    value={config.document_size}
                    onChange={(e) => set('document_size', e.target.value)}
                  >
                    <option value="A4">A4</option>
                    <option value="A3">A3</option>
                  </select>
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Orientation</span>
                  <select
                    className="select select-bordered select-sm"
                    value={config.map_orientation}
                    onChange={(e) => set('map_orientation', e.target.value)}
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
                  value={config.map_source}
                  onChange={(e) => {
                    const source = mapSourceOptions.find((option) => option.key === e.target.value);
                    set('map_source', e.target.value);
                    if (source) set('map_zoom_level', source.default_zoom);
                  }}
                >
                  {!mapSourceOptions.some((option) => option.key === config.map_source) && (
                    <option value={config.map_source}>{config.map_source}</option>
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
                  const selectedSource = mapSourceOptions.find((option) => option.key === config.map_source);
                  const minZoom = selectedSource?.min_zoom ?? 1;
                  const maxZoom = selectedSource?.max_zoom ?? 19;
                  return (
                    <label className="form-control flex-1">
                      <span className="label-text text-xs">
                        Map zoom level ({minZoom}-{maxZoom})
                      </span>
                      <input
                        type="number"
                        min={minZoom}
                        max={maxZoom}
                        className="input input-bordered input-sm w-full"
                        value={config.map_zoom_level}
                        onChange={(e) => set('map_zoom_level', Number(e.target.value))}
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
                    value={config.map_dpi}
                    onChange={(e) => set('map_dpi', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Map style</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Scale</span>
                  <select
                    className="select select-bordered select-sm"
                    value={config.map_scale}
                    onChange={(e) => set('map_scale', Number(e.target.value))}
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
                    value={config.map_line_colour}
                    onChange={(e) => set('map_line_colour', e.target.value)}
                  />
                </label>
              </div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Line width</span>
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    className="input input-bordered input-sm w-full"
                    value={config.map_line_width}
                    onChange={(e) => set('map_line_width', Number(e.target.value))}
                  />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Minute mark line width</span>
                  <input
                    type="number"
                    min={0.1}
                    max={10}
                    step={0.1}
                    className="input input-bordered input-sm w-full"
                    value={config.map_minute_mark_line_width}
                    onChange={(e) => set('map_minute_mark_line_width', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Map content</div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={config.map_include_annotations}
                    onChange={(e) => set('map_include_annotations', e.target.checked)}
                  />
                  <span className="label-text">Include annotations</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={config.map_include_contestant_declarations}
                    onChange={(e) => set('map_include_contestant_declarations', e.target.checked)}
                  />
                  <span className="label-text">Include contestant declarations</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={config.map_plot_track_between_waypoints}
                    onChange={(e) => set('map_plot_track_between_waypoints', e.target.checked)}
                  />
                  <span className="label-text">Plot track between waypoints</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={config.map_include_meridians_and_parallels_lines}
                    onChange={(e) => set('map_include_meridians_and_parallels_lines', e.target.checked)}
                  />
                  <span className="label-text">Include meridians/parallels</span>
                </label>
                <label className="label cursor-pointer justify-start gap-2">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-sm"
                    checked={config.map_include_openaip_overlay}
                    onChange={(e) => set('map_include_openaip_overlay', e.target.checked)}
                  />
                  <span className="label-text">Include OpenAIP overlay</span>
                </label>
              </div>

              <div className="divider my-0 text-xs">Turning point photos</div>
              <label className="label cursor-pointer justify-start gap-2">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={config.include_turning_point_images}
                  onChange={(e) => set('include_turning_point_images', e.target.checked)}
                />
                <span className="label-text">Include turning point photo pages</span>
              </label>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Meters across</span>
                  <input
                    type="number"
                    min={1}
                    className="input input-bordered input-sm w-full"
                    value={config.turning_point_photos_meters_across}
                    onChange={(e) => set('turning_point_photos_meters_across', Number(e.target.value))}
                  />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Zoom level</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="input input-bordered input-sm w-full"
                    value={config.turning_point_photos_zoom_level}
                    onChange={(e) => set('turning_point_photos_zoom_level', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Unknown leg photos</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Meters across</span>
                  <input
                    type="number"
                    min={1}
                    className="input input-bordered input-sm w-full"
                    value={config.unknown_leg_photos_meters_across}
                    onChange={(e) => set('unknown_leg_photos_meters_across', Number(e.target.value))}
                  />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Zoom level</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="input input-bordered input-sm w-full"
                    value={config.unknown_leg_photos_zoom_level}
                    onChange={(e) => set('unknown_leg_photos_zoom_level', Number(e.target.value))}
                  />
                </label>
              </div>

              <div className="divider my-0 text-xs">Observation photos</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Meters across</span>
                  <input
                    type="number"
                    min={1}
                    className="input input-bordered input-sm w-full"
                    value={config.photos_meters_across}
                    onChange={(e) => set('photos_meters_across', Number(e.target.value))}
                  />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Zoom level</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    className="input input-bordered input-sm w-full"
                    value={config.photos_zoom_level}
                    onChange={(e) => set('photos_zoom_level', Number(e.target.value))}
                  />
                </label>
              </div>

              {error && <p className="text-error text-sm">{error}</p>}
              <div className="modal-action">
                <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          )}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

FlightOrderConfigurationModal.displayName = 'FlightOrderConfigurationModal';

export default FlightOrderConfigurationModal;
