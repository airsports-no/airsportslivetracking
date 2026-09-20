import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import {
  AdministrativePenaltyCategory,
  applyQuarantinePenalty,
  fetchGateTimes,
  GateTimesResponse,
  removeScoreLogEntry,
} from '../api';
import { formatTimeInZone } from '../utils';

export interface GateTimesModalHandle {
  open: () => void;
}

interface GateTimesModalProps {
  contestId: number;
  navigationTaskId: number;
  contestantId: number;
  contestantNumber: number;
  canManage: boolean;
  timeZone: string;
  onChanged: () => void;
}

const DEFAULT_CATEGORY = 'quarantine';

const GateTimesModal = forwardRef<GateTimesModalHandle, GateTimesModalProps>(
  ({ contestId, navigationTaskId, contestantId, contestantNumber, canManage, timeZone, onChanged }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [data, setData] = useState<GateTimesResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busyEntryPk, setBusyEntryPk] = useState<number | null>(null);

    const [category, setCategory] = useState(DEFAULT_CATEGORY);
    const [points, setPoints] = useState('100');
    const [reason, setReason] = useState('');
    const [applyingPenalty, setApplyingPenalty] = useState(false);

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchGateTimes(contestId, navigationTaskId, contestantId);
        setData(response);
      } catch (err: any) {
        setError(err.message || 'Failed to load gate times');
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

    const handleRemoveEntry = async (entryPk: number) => {
      if (busyEntryPk !== null || !window.confirm('Remove this score log entry?')) return;
      setBusyEntryPk(entryPk);
      try {
        await removeScoreLogEntry(contestId, navigationTaskId, contestantId, entryPk);
        await load();
        onChanged();
      } catch (err: any) {
        window.alert(err.message || 'Failed to remove score log entry');
      } finally {
        setBusyEntryPk(null);
      }
    };

    const handleApplyPenalty = async (event: React.FormEvent) => {
      event.preventDefault();
      const pointsValue = Number(points);
      if (Number.isNaN(pointsValue)) return;
      setApplyingPenalty(true);
      try {
        await applyQuarantinePenalty(contestId, navigationTaskId, contestantId, { points: pointsValue, reason, category });
        setReason('');
        await load();
        onChanged();
      } catch (err: any) {
        window.alert(err.message || 'Failed to apply penalty');
      } finally {
        setApplyingPenalty(false);
      }
    };

    const categories: [string, AdministrativePenaltyCategory][] = data
      ? Object.entries(data.administrative_penalty_categories)
      : [];

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-2xl">
          <form method="dialog">
            <button
              type="button"
              className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
              onClick={() => dialogRef.current?.close()}
            >
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg">Gate times &amp; penalties - contestant #{contestantNumber}</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}
          {error && <p className="py-4 text-error text-sm">{error}</p>}

          {data && !loading && (
            <div className="py-2">
              <p className="text-sm text-gray-500 mb-3">
                Total distance: {data.total_distance.toFixed(1)} NM
              </p>
              <div className="overflow-x-auto">
                <table className="table table-xs w-full">
                  <thead>
                    <tr>
                      <th>Gate</th>
                      <th>Distance</th>
                      <th>Actual time</th>
                      <th>Score log</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.rendered_waypoints.map((gate) => (
                      <tr key={gate}>
                        <td className="font-medium whitespace-nowrap">{gate}</td>
                        <td className="whitespace-nowrap">{data.distances[gate]?.toFixed(1) ?? '-'}</td>
                        <td className="whitespace-nowrap">
                          {data.actual_times[gate] ? formatTimeInZone(data.actual_times[gate], timeZone) : '-'}
                        </td>
                        <td>
                          {(data.log[gate] || []).map((entry) => (
                            <div key={entry.pk} className="flex items-center gap-2 text-xs mb-1 last:mb-0">
                              <span>{entry.text}</span>
                              {canManage && (
                                <button
                                  type="button"
                                  disabled={busyEntryPk === entry.pk}
                                  onClick={() => handleRemoveEntry(entry.pk)}
                                  className="btn btn-ghost btn-xs text-error px-1"
                                >
                                  Remove
                                </button>
                              )}
                            </div>
                          ))}
                        </td>
                      </tr>
                    ))}
                    {Object.keys(data.log)
                      .filter((gate) => !data.rendered_waypoints.includes(gate))
                      .map((gate) => (
                        <tr key={gate}>
                          <td className="font-medium whitespace-nowrap">{gate}</td>
                          <td>-</td>
                          <td>-</td>
                          <td>
                            {data.log[gate].map((entry) => (
                              <div key={entry.pk} className="flex items-center gap-2 text-xs mb-1 last:mb-0">
                                <span>{entry.text}</span>
                                {canManage && (
                                  <button
                                    type="button"
                                    disabled={busyEntryPk === entry.pk}
                                    onClick={() => handleRemoveEntry(entry.pk)}
                                    className="btn btn-ghost btn-xs text-error px-1"
                                  >
                                    Remove
                                  </button>
                                )}
                              </div>
                            ))}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {canManage && data.can_apply_quarantine_penalty && categories.length > 0 && (
                <form onSubmit={handleApplyPenalty} className="mt-4 border-t border-base-200 pt-4 flex flex-wrap items-end gap-2">
                  <div className="form-control">
                    <label className="label label-text text-xs">Category</label>
                    <select
                      className="select select-bordered select-sm"
                      value={category}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      {categories.map(([key, config]) => (
                        <option key={key} value={key}>
                          {config.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-control">
                    <label className="label label-text text-xs">Points</label>
                    <input
                      type="number"
                      className="input input-bordered input-sm w-24"
                      value={points}
                      onChange={(e) => setPoints(e.target.value)}
                    />
                  </div>
                  <div className="form-control flex-1 min-w-[160px]">
                    <label className="label label-text text-xs">Reason</label>
                    <input
                      type="text"
                      className="input input-bordered input-sm w-full"
                      placeholder={categories.find(([key]) => key === category)?.[1].default_reason}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={applyingPenalty}>
                    {applyingPenalty ? 'Applying...' : 'Apply penalty'}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

GateTimesModal.displayName = 'GateTimesModal';

export default GateTimesModal;
