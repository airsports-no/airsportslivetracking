import React, { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { RoutePoint } from '../../../types';
import { metresToNauticalMiles, nauticalMilesToMetres } from '../routeEditorMutations';

const TYPE_LABELS: Record<string, string> = {
  sp: 'Start point',
  tp: 'Turning point',
  secret: 'Secret gate',
  fp: 'Finish point',
  anrtp: 'ANR turning point',
  timed_turnpoint: 'Timed turning point',
  catalogue_turnpoint: 'Catalogue turning point',
  ul: 'Unknown leg',
  unknown_leg: 'Unknown leg',
};

const typeLabel = (type: string) => TYPE_LABELS[type] ?? type;
const formatWidth = (metres: number) => metresToNauticalMiles(metres).toFixed(2);

interface GateWidthModalProps {
  isOpen: boolean;
  /** The gates of the route, in route order */
  points: RoutePoint[];
  /** Gives the chosen gates the width, in metres */
  onApply: (ids: ReadonlySet<string>, widthMetres: number) => void;
  onClose: () => void;
}

/** Sets the width of several gates at once: pick the gates, write the width, apply. */
const GateWidthModal: React.FC<GateWidthModalProps> = ({ isOpen, points, onApply, onClose }) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [widthInput, setWidthInput] = useState('');
  const [applied, setApplied] = useState<string | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);

  const width = parseFloat(widthInput);
  const widthValid = !isNaN(width) && width > 0;
  // Gates that were removed from the route since they were chosen are not applied to
  const chosen = new Set(points.filter((point) => selected.has(point.id)).map((point) => point.id));
  const types = Array.from(new Set(points.map((point) => point.type)));

  const toggle = (id: string) =>
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const apply = () => {
    if (!widthValid || chosen.size === 0) return;
    onApply(chosen, nauticalMilesToMetres(width));
    setApplied(`${chosen.size} ${chosen.size === 1 ? 'gate' : 'gates'} set to ${width.toFixed(2)} NM.`);
  };

  return (
    <dialog ref={dialogRef} className="modal" onClose={onClose}>
      <div className="modal-box max-w-xl">
        <form method="dialog">
          <button type="submit" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" aria-label="Close">
            <X size={16} />
          </button>
        </form>
        <h3 className="font-bold text-lg">Gate widths</h3>
        <p className="text-sm opacity-70">Choose the gates, write the new width and apply it to them all.</p>

        <div className="flex flex-wrap gap-1 mt-3" aria-label="Choose gates">
          <button type="button" className="btn btn-xs" onClick={() => setSelected(new Set(points.map((p) => p.id)))}>
            All
          </button>
          <button type="button" className="btn btn-xs" onClick={() => setSelected(new Set())}>
            None
          </button>
          {types.map((type) => (
            <button
              key={type}
              type="button"
              className="btn btn-xs btn-outline"
              onClick={() => setSelected(new Set(points.filter((p) => p.type === type).map((p) => p.id)))}
            >
              {typeLabel(type)}s only
            </button>
          ))}
        </div>

        <div className="mt-3 max-h-72 overflow-y-auto border border-base-300 rounded-box">
          <table className="table table-xs">
            <thead>
              <tr>
                <th />
                <th>Gate</th>
                <th>Type</th>
                <th className="text-right">Width (NM)</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.id} className="hover cursor-pointer" onClick={() => toggle(point.id)}>
                  <td>
                    <input
                      type="checkbox"
                      className="checkbox checkbox-xs"
                      checked={chosen.has(point.id)}
                      onChange={() => toggle(point.id)}
                      onClick={(event) => event.stopPropagation()}
                      aria-label={`Select ${point.name}`}
                    />
                  </td>
                  <td>{point.name}</td>
                  <td>{typeLabel(point.type)}</td>
                  <td className="text-right">{formatWidth(point.width)}</td>
                </tr>
              ))}
              {points.length === 0 && (
                <tr>
                  <td colSpan={4} className="text-center opacity-70">
                    The route has no gates yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-end gap-2 mt-3">
          <label className="form-control flex-1">
            <span className="label-text text-xs">New width (NM)</span>
            <input
              type="number"
              step="0.01"
              min="0.01"
              className="input input-bordered input-sm w-full"
              value={widthInput}
              onChange={(event) => {
                setWidthInput(event.target.value);
                setApplied(null);
              }}
            />
          </label>
          <button type="button" className="btn btn-primary btn-sm" disabled={!widthValid || chosen.size === 0} onClick={apply}>
            Apply to {chosen.size} {chosen.size === 1 ? 'gate' : 'gates'}
          </button>
        </div>
        {applied && (
          <p className="text-sm text-success mt-2" role="status">
            {applied}
          </p>
        )}
      </div>
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  );
};

export default GateWidthModal;
