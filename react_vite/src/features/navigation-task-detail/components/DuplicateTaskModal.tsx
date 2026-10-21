import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { generatePath } from '../../../urls';
import { useMissionDashboardStore } from '../../mission-dashboard/store';
import { DuplicateTaskOptions, duplicateNavigationTask, fetchDuplicateTaskOptions } from '../api';

export interface DuplicateTaskModalHandle {
  open: () => void;
}

interface DuplicateTaskModalProps {
  contestId: number;
  navigationTaskId: number;
}

const toLocalInputValue = (iso: string): string => {
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

/**
 * Make a new task like this one, for the next round of a cup or another contest: a new name, route and time window, and
 * everything else (task type and settings, the scorecard with its changes, flight order configuration) copied.
 */
const DuplicateTaskModal = forwardRef<DuplicateTaskModalHandle, DuplicateTaskModalProps>(({ contestId, navigationTaskId }, ref) => {
  const navigate = useNavigate();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [options, setOptions] = useState<DuplicateTaskOptions | null>(null);
  const [targetContest, setTargetContest] = useState('');
  const [name, setName] = useState('');
  const [route, setRoute] = useState('');
  const [startTime, setStartTime] = useState('');
  const [finishTime, setFinishTime] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useImperativeHandle(ref, () => ({
    open: () => {
      setError(null);
      setOptions(null);
      dialogRef.current?.showModal();
      fetchDuplicateTaskOptions(contestId, navigationTaskId)
        .then((loaded) => {
          setOptions(loaded);
          setTargetContest(String(loaded.contest));
          setName(loaded.name);
          // No route is chosen for the organiser: the point of a copy is usually a new route
          setRoute('');
          setStartTime(toLocalInputValue(loaded.start_time));
          setFinishTime(toLocalInputValue(loaded.finish_time));
        })
        .catch((err: Error) => setError(err.message));
    },
  }));

  const close = () => dialogRef.current?.close();

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await duplicateNavigationTask(contestId, navigationTaskId, {
        contest: Number(targetContest),
        name,
        editable_route: Number(route),
        start_time: new Date(startTime).toISOString(),
        finish_time: new Date(finishTime).toISOString(),
      });
      close();
      // The contest page caches its task list, so make it show the new task
      await useMissionDashboardStore.getState().fetchContest(created.contest, true);
      navigate(generatePath('NAVIGATION_TASK_DETAIL', { contestId: String(created.contest), navigationTaskId: String(created.id) }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const fitting = options?.routes.filter((item) => item.compatible) ?? [];
  const notFitting = options?.routes.filter((item) => !item.compatible) ?? [];
  const sameRoute = options && Number(route) === options.editable_route;

  return (
    <dialog ref={dialogRef} className="modal">
      <div className="modal-box max-w-lg">
        <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={close}>
          ✕
        </button>
        <h3 className="font-bold text-lg">Duplicate task</h3>
        <p className="text-sm opacity-70 mt-1">
          Makes a new task with the same task type and settings, the same scorecard including your changes to it, and the same
          flight order configuration. Choose its name, route and time window. Contestants are not copied, and the new task
          starts private.
        </p>
        {!options && !error && <span className="loading loading-spinner loading-sm mt-4"></span>}
        {options && (
          <form onSubmit={submit} className="flex flex-col gap-3 mt-4">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold">Contest</span>
              <select className="select select-bordered select-sm w-full" value={targetContest} onChange={(e) => setTargetContest(e.target.value)}>
                {options.contests.map((contest) => (
                  <option key={contest.id} value={contest.id}>
                    {contest.name}
                    {contest.id === contestId ? ' (this contest)' : ''}
                  </option>
                ))}
              </select>
              <span className="text-xs opacity-60">The contests you manage.</span>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold">Name</span>
              <input className="input input-bordered input-sm w-full" maxLength={200} value={name} onChange={(e) => setName(e.target.value)} required />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs font-semibold">Route</span>
              <select className="select select-bordered select-sm w-full" value={route} onChange={(e) => setRoute(e.target.value)} required>
                <option value="" disabled>
                  Choose a route…
                </option>
                {fitting.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                    {item.id === options.editable_route ? ' (the route of this task)' : ''}
                  </option>
                ))}
                {notFitting.length > 0 && (
                  <optgroup label="Do not fit this task type">
                    {notFitting.map((item) => (
                      <option key={item.id} value={item.id} disabled title={item.reasons.join('; ')}>
                        {item.name}
                      </option>
                    ))}
                  </optgroup>
                )}
              </select>
              <span className="text-xs opacity-60">
                {fitting.length === 0
                  ? 'None of your routes fits this task type. Draw one in the route editor first.'
                  : 'Your routes that fit this task type.'}
                {sameRoute ? ' This is the route the task already flies.' : ''}
              </span>
            </label>
            <div className="flex gap-2">
              <label className="flex flex-col gap-1 flex-1">
                <span className="text-xs font-semibold">Start time</span>
                <input type="datetime-local" step={60} className="input input-bordered input-sm w-full" value={startTime} onChange={(e) => setStartTime(e.target.value)} required />
              </label>
              <label className="flex flex-col gap-1 flex-1">
                <span className="text-xs font-semibold">Finish time</span>
                <input type="datetime-local" step={60} className="input input-bordered input-sm w-full" value={finishTime} onChange={(e) => setFinishTime(e.target.value)} required />
              </label>
            </div>
            <span className="text-xs opacity-60 -mt-1">Filled in from this task; change them for the new occurrence.</span>
            {error && <p className="text-error text-sm">{error}</p>}
            <div className="modal-action">
              <button type="button" className="btn btn-ghost btn-sm" onClick={close}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !route || !name.trim()}>
                {busy ? 'Duplicating…' : 'Duplicate'}
              </button>
            </div>
          </form>
        )}
        {!options && error && <p className="text-error text-sm mt-4">{error}</p>}
      </div>
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  );
});

DuplicateTaskModal.displayName = 'DuplicateTaskModal';

export default DuplicateTaskModal;
