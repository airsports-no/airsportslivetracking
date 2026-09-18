import React, { forwardRef, useState } from 'react';
import { batchUpdateContestants } from '../api';
import { ContestantRow } from '../types';

interface BatchUpdateContestantsModalProps {
  contestId: number;
  navigationTaskId: number;
  contestants: ContestantRow[];
  onUpdated: () => void;
}

const BatchUpdateContestantsModal = forwardRef<HTMLDialogElement, BatchUpdateContestantsModalProps>(
  ({ contestId, navigationTaskId, contestants, onUpdated }, ref) => {
    const [selected, setSelected] = useState<Set<number>>(new Set());
    const [updateWind, setUpdateWind] = useState(false);
    const [windSpeed, setWindSpeed] = useState('8');
    const [windDirection, setWindDirection] = useState('0');
    const [shiftTimes, setShiftTimes] = useState(false);
    const [timeShiftMinutes, setTimeShiftMinutes] = useState('0');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [resultMessage, setResultMessage] = useState<string | null>(null);

    const toggle = (pk: number) => {
      setSelected((prev) => {
        const next = new Set(prev);
        if (next.has(pk)) next.delete(pk);
        else next.add(pk);
        return next;
      });
    };

    const toggleAll = () => {
      setSelected((prev) => (prev.size === contestants.length ? new Set() : new Set(contestants.map((c) => c.pk))));
    };

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (selected.size === 0 || (!updateWind && !shiftTimes)) return;
      setBusy(true);
      setError(null);
      setResultMessage(null);
      try {
        const result = await batchUpdateContestants(contestId, navigationTaskId, {
          contestant_ids: Array.from(selected),
          update_wind: updateWind,
          wind_speed: updateWind ? Number(windSpeed) : undefined,
          wind_direction: updateWind ? Number(windDirection) : undefined,
          shift_times: shiftTimes,
          time_shift_minutes: shiftTimes ? Number(timeShiftMinutes) : undefined,
        });
        setResultMessage(`Updated ${result.updated} of ${selected.size} selected contestant(s).`);
        onUpdated();
      } catch (err: any) {
        setError(err.message || 'Failed to batch-update contestants');
      } finally {
        setBusy(false);
      }
    };

    return (
      <dialog ref={ref} className="modal">
        <div className="modal-box max-w-lg">
          <form method="dialog">
            <button
              type="button"
              className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
              onClick={() => (ref as React.RefObject<HTMLDialogElement>).current?.close()}
            >
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">Batch update contestants</h3>
          <p className="text-xs text-gray-500 mb-2">
            Contestants whose calculator is currently running or about to be dispatched are skipped automatically.
          </p>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="max-h-40 overflow-y-auto border border-base-300 rounded p-2 flex flex-col">
              <label className="label cursor-pointer justify-start gap-2 text-xs font-semibold w-full">
                <input type="checkbox" className="checkbox checkbox-xs" checked={selected.size === contestants.length && contestants.length > 0} onChange={toggleAll} />
                <span>Select all</span>
              </label>
              {contestants.map((contestant) => (
                <label key={contestant.pk} className="label cursor-pointer justify-start gap-2 text-xs w-full">
                  <input
                    type="checkbox"
                    className="checkbox checkbox-xs"
                    checked={selected.has(contestant.pk)}
                    onChange={() => toggle(contestant.pk)}
                  />
                  <span>
                    #{contestant.contestant_number} {contestant.team.crew.member1.first_name} {contestant.team.crew.member1.last_name}
                  </span>
                </label>
              ))}
            </div>

            <div className="border-t border-base-200 pt-2">
              <label className="label cursor-pointer justify-start gap-2">
                <input type="checkbox" className="checkbox checkbox-sm" checked={updateWind} onChange={(e) => setUpdateWind(e.target.checked)} />
                <span className="label-text">Update wind speed/direction</span>
              </label>
              {updateWind && (
                <div className="flex gap-2 ml-6">
                  <input
                    type="number"
                    className="input input-bordered input-sm w-24"
                    placeholder="Speed (kt)"
                    value={windSpeed}
                    onChange={(e) => setWindSpeed(e.target.value)}
                  />
                  <input
                    type="number"
                    className="input input-bordered input-sm w-24"
                    placeholder="Direction (°)"
                    value={windDirection}
                    onChange={(e) => setWindDirection(e.target.value)}
                  />
                </div>
              )}
            </div>

            <div>
              <label className="label cursor-pointer justify-start gap-2">
                <input type="checkbox" className="checkbox checkbox-sm" checked={shiftTimes} onChange={(e) => setShiftTimes(e.target.checked)} />
                <span className="label-text">Shift contestant times</span>
              </label>
              {shiftTimes && (
                <div className="ml-6">
                  <input
                    type="number"
                    className="input input-bordered input-sm w-40"
                    placeholder="Minutes (negative = earlier)"
                    value={timeShiftMinutes}
                    onChange={(e) => setTimeShiftMinutes(e.target.value)}
                  />
                </div>
              )}
            </div>

            {resultMessage && <p className="text-success text-sm">{resultMessage}</p>}
            {error && <p className="text-error text-sm">{error}</p>}
            <div className="modal-action">
              <button type="submit" className="btn btn-primary btn-sm" disabled={selected.size === 0 || (!updateWind && !shiftTimes) || busy}>
                {busy ? 'Updating...' : `Update ${selected.size} contestant(s)`}
              </button>
            </div>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

BatchUpdateContestantsModal.displayName = 'BatchUpdateContestantsModal';

export default BatchUpdateContestantsModal;
