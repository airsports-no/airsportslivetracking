import React, { forwardRef, useState } from 'react';
import { recalculateWithStartTime } from '../api';

interface RecalculateStartTimeModalProps {
  contestId: number;
  navigationTaskId: number;
  contestantId: number;
  onRecalculated: () => void;
}

// Local-time input, converted to an absolute instant via the browser's own time zone - the
// datetime-local input type carries no time zone of its own, so `new Date(value)` interprets it
// against the browser's local zone, which may differ from the contest's own time zone.
const RecalculateStartTimeModal = forwardRef<HTMLDialogElement, RecalculateStartTimeModalProps>(
  ({ contestId, navigationTaskId, contestantId, onRecalculated }, ref) => {
    const [value, setValue] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (!value) return;
      const startingPointTime = new Date(value);
      if (Number.isNaN(startingPointTime.getTime())) {
        setError('Enter a valid date and time');
        return;
      }
      setBusy(true);
      setError(null);
      try {
        await recalculateWithStartTime(contestId, navigationTaskId, contestantId, startingPointTime.toISOString());
        (ref as React.RefObject<HTMLDialogElement>).current?.close();
        // The contestant is replaced with a new one (new pk) sharing the same schedule slot -
        // onRefresh() re-fetches the whole navigation task, whose contestant_set will already
        // reflect the replacement.
        onRecalculated();
      } catch (err: any) {
        setError(err.message || 'Failed to recalculate with a new start time');
      } finally {
        setBusy(false);
      }
    };

    return (
      <dialog ref={ref} className="modal">
        <div className="modal-box">
          <form method="dialog">
            <button
              type="button"
              className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
              onClick={() => (ref as React.RefObject<HTMLDialogElement>).current?.close()}
            >
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg">Recalculate with new start time</h3>
          <p className="py-2 text-sm text-gray-500">
            Replaces this contestant with a new one sharing the same team and uploaded track, using this new starting-point
            time to derive the takeoff/tracker-start/finish times. All current scores are discarded.
          </p>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="datetime-local"
              step={1}
              className="input input-bordered input-sm w-full"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <p className="text-xs text-gray-500">Time is in your browser's local time zone.</p>
            {error && <p className="text-error text-sm">{error}</p>}
            <div className="modal-action">
              <button type="submit" className="btn btn-primary btn-sm" disabled={!value || busy}>
                {busy ? 'Recalculating...' : 'Recalculate'}
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

RecalculateStartTimeModal.displayName = 'RecalculateStartTimeModal';

export default RecalculateStartTimeModal;
