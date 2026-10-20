import React, { forwardRef, useEffect, useState } from 'react';
import { updateNavigationTaskDetails } from '../api';
import { NavigationTaskDetail } from '../types';
import SimulatorPolicyChoice from '../../../components/common/SimulatorPolicyChoice';
import { SimulatorPolicy } from '../../../utils/simulatorPolicy';

interface UpdateTaskDetailsModalProps {
  contestId: number;
  navigationTaskId: number;
  task: NavigationTaskDetail;
  onUpdated: () => void;
}

const toLocalInputValue = (iso: string): string => {
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const UpdateTaskDetailsModal = forwardRef<HTMLDialogElement, UpdateTaskDetailsModalProps>(
  ({ contestId, navigationTaskId, task, onUpdated }, ref) => {
    const [name, setName] = useState(task.name);
    const [startTime, setStartTime] = useState(toLocalInputValue(task.start_time));
    const [finishTime, setFinishTime] = useState(toLocalInputValue(task.finish_time));
    const [windSpeed, setWindSpeed] = useState(String(task.wind_speed));
    const [windDirection, setWindDirection] = useState(String(task.wind_direction));
    const [allowSelfManagement, setAllowSelfManagement] = useState(task.allow_self_management);
    const [allowObservationRegistration, setAllowObservationRegistration] = useState(task.allow_observation_registration);
    const [simulatorPolicy, setSimulatorPolicy] = useState<SimulatorPolicy>(task.simulator_policy ?? 'not_allowed');
  const [showLiveScoreInApp, setShowLiveScoreInApp] = useState(task.show_live_score_in_app);
    const [notifyOnStart, setNotifyOnStart] = useState(task.notify_managers_on_start ?? false);
    const [notifyOnFinish, setNotifyOnFinish] = useState(task.notify_managers_on_finish ?? false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Reset the form's local state to match the task whenever it changes underneath (e.g. after
    // a previous save, or if this modal is reused across a refresh).
    useEffect(() => {
      setName(task.name);
      setStartTime(toLocalInputValue(task.start_time));
      setFinishTime(toLocalInputValue(task.finish_time));
      setWindSpeed(String(task.wind_speed));
      setWindDirection(String(task.wind_direction));
      setAllowSelfManagement(task.allow_self_management);
      setAllowObservationRegistration(task.allow_observation_registration);
      setSimulatorPolicy(task.simulator_policy ?? 'not_allowed');
      setShowLiveScoreInApp(task.show_live_score_in_app);
      setNotifyOnStart(task.notify_managers_on_start ?? false);
      setNotifyOnFinish(task.notify_managers_on_finish ?? false);
    }, [task]);

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      setBusy(true);
      setError(null);
      try {
        await updateNavigationTaskDetails(contestId, navigationTaskId, {
          name,
          start_time: new Date(startTime).toISOString(),
          finish_time: new Date(finishTime).toISOString(),
          wind_speed: Number(windSpeed),
          wind_direction: Number(windDirection),
          allow_self_management: allowSelfManagement,
          allow_observation_registration: allowObservationRegistration,
          simulator_policy: simulatorPolicy,
          show_live_score_in_app: showLiveScoreInApp,
          notify_managers_on_start: notifyOnStart,
          notify_managers_on_finish: notifyOnFinish,
        });
        (ref as React.RefObject<HTMLDialogElement>).current?.close();
        onUpdated();
      } catch (err: any) {
        setError(err.message || 'Failed to update navigation task details');
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
          <h3 className="font-bold text-lg mb-2">Update task details</h3>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <label className="form-control">
              <span className="label-text text-xs">Name</span>
              <input type="text" className="input input-bordered input-sm" value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <div className="flex gap-2">
              <label className="form-control flex-1">
                <span className="label-text text-xs">Start time</span>
                <input
                  type="datetime-local"
                  step={60}
                  className="input input-bordered input-sm w-full"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                />
              </label>
              <label className="form-control flex-1">
                <span className="label-text text-xs">Finish time</span>
                <input
                  type="datetime-local"
                  step={60}
                  className="input input-bordered input-sm w-full"
                  value={finishTime}
                  onChange={(e) => setFinishTime(e.target.value)}
                />
              </label>
            </div>
            <div className="flex gap-2">
              <label className="form-control flex-1">
                <span className="label-text text-xs">Wind speed (kt)</span>
                <input
                  type="number"
                  className="input input-bordered input-sm w-full"
                  value={windSpeed}
                  onChange={(e) => setWindSpeed(e.target.value)}
                />
              </label>
              <label className="form-control flex-1">
                <span className="label-text text-xs">Wind direction (°)</span>
                <input
                  type="number"
                  className="input input-bordered input-sm w-full"
                  value={windDirection}
                  onChange={(e) => setWindDirection(e.target.value)}
                />
              </label>
            </div>
            <label className="label cursor-pointer justify-start gap-2">
              <input
                type="checkbox"
                className="checkbox checkbox-sm"
                checked={allowSelfManagement}
                onChange={(e) => setAllowSelfManagement(e.target.checked)}
              />
              <span className="label-text">Allow self-management</span>
            </label>
            <label className="label cursor-pointer justify-start gap-2">
              <input
                type="checkbox"
                className="checkbox checkbox-sm"
                checked={allowObservationRegistration}
                onChange={(e) => setAllowObservationRegistration(e.target.checked)}
              />
              <span className="label-text">Allow observation registration in the app</span>
            </label>
            <SimulatorPolicyChoice
              name="update_simulator_policy"
              value={simulatorPolicy}
              onChange={setSimulatorPolicy}
              suggestSelfManagement={!allowSelfManagement}
            />
            <label className="label cursor-pointer justify-start gap-2">
              <input
                type="checkbox"
                className="checkbox checkbox-sm"
                checked={showLiveScoreInApp}
                onChange={(e) => setShowLiveScoreInApp(e.target.checked)}
              />
              <span className="label-text">Show live feedback to pilots in the app (running score, training mode)</span>
            </label>
            <fieldset className="border border-base-300 rounded-lg p-3">
              <legend className="text-xs px-1">E-mail the contest managers</legend>
              <p className="text-xs opacity-70 mb-1">
                For tasks flown by each contestant on their own, for example in a cup: everybody who can manage the contest gets an
                e-mail, except when they are flying themselves.
              </p>
              <label className="label cursor-pointer justify-start gap-2">
                <input type="checkbox" className="checkbox checkbox-sm" checked={notifyOnStart} onChange={(e) => setNotifyOnStart(e.target.checked)} />
                <span className="label-text">When a contestant starts the task</span>
              </label>
              <label className="label cursor-pointer justify-start gap-2">
                <input type="checkbox" className="checkbox checkbox-sm" checked={notifyOnFinish} onChange={(e) => setNotifyOnFinish(e.target.checked)} />
                <span className="label-text">When a contestant has finished, with their score</span>
              </label>
            </fieldset>
            {error && <p className="text-error text-sm">{error}</p>}
            <div className="modal-action">
              <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
                {busy ? 'Saving...' : 'Save'}
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

UpdateTaskDetailsModal.displayName = 'UpdateTaskDetailsModal';

export default UpdateTaskDetailsModal;
