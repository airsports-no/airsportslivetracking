import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { fetchFlightOrderConfiguration, FlightOrderConfiguration, updateFlightOrderConfiguration } from '../api';

export interface FlightOrderConfigurationModalHandle {
  open: () => void;
}

interface FlightOrderConfigurationModalProps {
  contestId: number;
  navigationTaskId: number;
}

const FlightOrderConfigurationModal = forwardRef<FlightOrderConfigurationModalHandle, FlightOrderConfigurationModalProps>(
  ({ contestId, navigationTaskId }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [config, setConfig] = useState<FlightOrderConfiguration | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchFlightOrderConfiguration(contestId, navigationTaskId);
        setConfig(data);
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
        <div className="modal-box max-w-lg">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={() => dialogRef.current?.close()}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">Flight order configuration</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}

          {config && !loading && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
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
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Map zoom level</span>
                  <input
                    type="number"
                    min={1}
                    max={19}
                    className="input input-bordered input-sm w-full"
                    value={config.map_zoom_level}
                    onChange={(e) => set('map_zoom_level', Number(e.target.value))}
                  />
                </label>
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
              <label className="form-control">
                <span className="label-text text-xs">Line colour</span>
                <input
                  type="color"
                  className="input input-bordered input-sm w-20 h-8 p-1"
                  value={config.map_line_colour}
                  onChange={(e) => set('map_line_colour', e.target.value)}
                />
              </label>
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
