import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import {
  ContestantEditDetail,
  ContestantFormPayload,
  ContestTeamOption,
  createContestant,
  fetchContestantDetail,
  fetchContestTeams,
  updateContestant,
} from '../api';

export interface ContestantFormModalHandle {
  open: () => void;
}

interface ContestantFormModalProps {
  contestId: number;
  navigationTaskId: number;
  /** When set, edits this contestant. When omitted, creates a new one - the "advanced" alternative
      to Quick Add for power users who need the full field set (tracker id, adaptive start, etc). */
  contestantId?: number;
  /** Create-mode defaults, taken from the navigation task, mirroring quick_add_contestant's own defaults. */
  nextContestantNumber?: number;
  taskWindSpeed?: number;
  taskWindDirection?: number;
  taskMinutesToStartingPoint?: number;
  onSaved: () => void;
}

const TRACKING_SERVICE_OPTIONS = [
  { value: 'traccar', label: 'Airsports' },
  { value: 'flymaster', label: 'Flymaster' },
];

const TRACKING_DEVICE_OPTIONS = [
  { value: 'device', label: 'Hardware GPS tracker' },
  { value: 'pilot_app', label: "Pilot's Air Sports Live Tracking app" },
  { value: 'copilot_app', label: "Copilot's Air Sports Live Tracking app" },
  { value: 'pilot_app_or_copilot_app', label: "Pilot's or copilot's Air Sports Live Tracking app" },
];

const teamLabel = (option: ContestTeamOption): string => {
  const { member1, member2 } = option.team.crew;
  const pilots = member2 ? `${member1.first_name} ${member1.last_name} / ${member2.first_name} ${member2.last_name}` : `${member1.first_name} ${member1.last_name}`;
  return `${pilots} (${option.team.aeroplane.registration})`;
};

const toLocalInputValue = (iso: string): string => {
  const date = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const ContestantFormModal = forwardRef<ContestantFormModalHandle, ContestantFormModalProps>(
  (
    { contestId, navigationTaskId, contestantId, nextContestantNumber, taskWindSpeed, taskWindDirection, taskMinutesToStartingPoint, onSaved },
    ref
  ) => {
    const isEditMode = contestantId !== undefined;
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [teams, setTeams] = useState<ContestTeamOption[]>([]);
    const [loading, setLoading] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [contestantNumber, setContestantNumber] = useState('');
    const [teamId, setTeamId] = useState('');
    const [takeoffTime, setTakeoffTime] = useState('');
    const [adaptiveStart, setAdaptiveStart] = useState(false);
    const [minutesToStartingPoint, setMinutesToStartingPoint] = useState('5');
    const [airSpeed, setAirSpeed] = useState('70');
    const [windDirection, setWindDirection] = useState('0');
    const [windSpeed, setWindSpeed] = useState('0');
    const [trackingService, setTrackingService] = useState('traccar');
    const [trackingDevice, setTrackingDevice] = useState('pilot_app_or_copilot_app');
    const [trackerDeviceId, setTrackerDeviceId] = useState('');
    const [trackerStartTime, setTrackerStartTime] = useState('');
    const [finishedByTime, setFinishedByTime] = useState('');

    const applyTeamDefaults = (option: ContestTeamOption) => {
      setTeamId(String(option.team.id));
      setTrackingService(option.tracking_service);
      setTrackingDevice(option.tracking_device);
      setTrackerDeviceId(option.tracker_device_id || '');
      setAirSpeed(String(option.air_speed));
    };

    const populateFromDetail = (detail: ContestantEditDetail) => {
      setContestantNumber(String(detail.contestant_number));
      setTeamId(String(detail.team.id));
      setTakeoffTime(toLocalInputValue(detail.takeoff_time));
      setAdaptiveStart(detail.adaptive_start);
      setMinutesToStartingPoint(String(detail.minutes_to_starting_point));
      setAirSpeed(String(detail.air_speed));
      setWindDirection(String(detail.wind_direction));
      setWindSpeed(String(detail.wind_speed));
      setTrackingService(detail.tracking_service);
      setTrackingDevice(detail.tracking_device);
      setTrackerDeviceId(detail.tracker_device_id || '');
      setTrackerStartTime(toLocalInputValue(detail.tracker_start_time));
      setFinishedByTime(toLocalInputValue(detail.finished_by_time));
    };

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const teamOptions = await fetchContestTeams(contestId);
        setTeams(teamOptions);
        if (contestantId !== undefined) {
          const detail = await fetchContestantDetail(contestId, navigationTaskId, contestantId);
          populateFromDetail(detail);
        } else {
          setContestantNumber(String(nextContestantNumber ?? 1));
          setWindDirection(String(taskWindDirection ?? 0));
          setWindSpeed(String(taskWindSpeed ?? 0));
          setMinutesToStartingPoint(String(taskMinutesToStartingPoint ?? 5));
          setAdaptiveStart(false);
          setTakeoffTime('');
          setTrackerStartTime('');
          setFinishedByTime('');
          if (teamOptions.length > 0) applyTeamDefaults(teamOptions[0]);
        }
      } catch (err: any) {
        setError(err.message || 'Failed to load contestant data');
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

    const handleTeamChange = (value: string) => {
      setTeamId(value);
      if (!isEditMode) {
        const option = teams.find((t) => String(t.team.id) === value);
        if (option) applyTeamDefaults(option);
      }
    };

    const requiredFieldsFilled = teamId && takeoffTime && trackerStartTime && finishedByTime && contestantNumber;

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (!requiredFieldsFilled) return;
      setBusy(true);
      setError(null);
      const payload: ContestantFormPayload = {
        contestant_number: Number(contestantNumber),
        team: Number(teamId),
        tracking_service: trackingService,
        tracking_device: trackingDevice,
        tracker_device_id: trackerDeviceId,
        takeoff_time: new Date(takeoffTime).toISOString(),
        adaptive_start: adaptiveStart,
        tracker_start_time: new Date(trackerStartTime).toISOString(),
        finished_by_time: new Date(finishedByTime).toISOString(),
        minutes_to_starting_point: Number(minutesToStartingPoint),
        air_speed: Number(airSpeed),
        wind_direction: Number(windDirection),
        wind_speed: Number(windSpeed),
      };
      try {
        const result = isEditMode
          ? await updateContestant(contestId, navigationTaskId, contestantId!, payload)
          : await createContestant(contestId, navigationTaskId, payload);
        dialogRef.current?.close();
        if (result.overlap_warnings && result.overlap_warnings.length > 0) {
          window.alert(result.overlap_warnings.join('\n'));
        }
        onSaved();
      } catch (err: any) {
        setError(err.message || `Failed to ${isEditMode ? 'update' : 'create'} contestant`);
      } finally {
        setBusy(false);
      }
    };

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-2xl">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={() => dialogRef.current?.close()}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">{isEditMode ? 'Edit contestant' : 'Add contestant (advanced)'}</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}

          {!loading && !isEditMode && teams.length === 0 && !error && (
            <p className="py-4 text-sm text-gray-500">No teams are registered for this contest yet.</p>
          )}

          {!loading && (isEditMode || teams.length > 0) && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-2">
                <label className="form-control">
                  <span className="label-text text-xs">Contestant number</span>
                  <input
                    type="number"
                    className="input input-bordered input-sm w-full"
                    value={contestantNumber}
                    onChange={(e) => setContestantNumber(e.target.value)}
                  />
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Team</span>
                  <select className="select select-bordered select-sm" value={teamId} onChange={(e) => handleTeamChange(e.target.value)}>
                    {teams.map((option) => (
                      <option key={option.id} value={option.team.id}>
                        {teamLabel(option)}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <label className="form-control">
                  <span className="label-text text-xs">Takeoff time</span>
                  <input
                    type="datetime-local"
                    step={60}
                    className="input input-bordered input-sm w-full"
                    value={takeoffTime}
                    onChange={(e) => setTakeoffTime(e.target.value)}
                  />
                </label>
                <label className="label cursor-pointer justify-start gap-2 self-end pb-1">
                  <input type="checkbox" className="checkbox checkbox-sm" checked={adaptiveStart} onChange={(e) => setAdaptiveStart(e.target.checked)} />
                  <span className="label-text">Adaptive start</span>
                </label>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <label className="form-control">
                  <span className="label-text text-xs">Minutes to starting point</span>
                  <input
                    type="number"
                    className="input input-bordered input-sm w-full"
                    value={minutesToStartingPoint}
                    onChange={(e) => setMinutesToStartingPoint(e.target.value)}
                  />
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Air speed</span>
                  <input type="number" className="input input-bordered input-sm w-full" value={airSpeed} onChange={(e) => setAirSpeed(e.target.value)} />
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Wind direction (°)</span>
                  <input
                    type="number"
                    className="input input-bordered input-sm w-full"
                    value={windDirection}
                    onChange={(e) => setWindDirection(e.target.value)}
                  />
                </label>
              </div>
              <label className="form-control w-1/3">
                <span className="label-text text-xs">Wind speed</span>
                <input type="number" className="input input-bordered input-sm w-full" value={windSpeed} onChange={(e) => setWindSpeed(e.target.value)} />
              </label>

              <div className="divider my-0 text-xs">Tracking</div>
              <p className="text-xs text-gray-500 -mt-2">
                Tracker start time and finished-by time can mostly be left alone - they only matter for defining the
                window in which the tracker is considered active for this contestant.
              </p>

              <div className="grid grid-cols-2 gap-2">
                <label className="form-control">
                  <span className="label-text text-xs">Tracking service</span>
                  <select className="select select-bordered select-sm" value={trackingService} onChange={(e) => setTrackingService(e.target.value)}>
                    {TRACKING_SERVICE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Tracking device</span>
                  <select className="select select-bordered select-sm" value={trackingDevice} onChange={(e) => setTrackingDevice(e.target.value)}>
                    {TRACKING_DEVICE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="form-control">
                <span className="label-text text-xs">Tracker device ID</span>
                <input
                  type="text"
                  className="input input-bordered input-sm w-full"
                  value={trackerDeviceId}
                  onChange={(e) => setTrackerDeviceId(e.target.value)}
                  placeholder="Leave blank if using the Air Sports Live Tracking app"
                />
              </label>
              <div className="grid grid-cols-2 gap-2">
                <label className="form-control">
                  <span className="label-text text-xs">Tracker start time</span>
                  <input
                    type="datetime-local"
                    step={60}
                    className="input input-bordered input-sm w-full"
                    value={trackerStartTime}
                    onChange={(e) => setTrackerStartTime(e.target.value)}
                  />
                </label>
                <label className="form-control">
                  <span className="label-text text-xs">Finished by time</span>
                  <input
                    type="datetime-local"
                    step={60}
                    className="input input-bordered input-sm w-full"
                    value={finishedByTime}
                    onChange={(e) => setFinishedByTime(e.target.value)}
                  />
                </label>
              </div>
              <p className="text-xs text-gray-500">Times are in your browser's local time zone.</p>

              {error && <p className="text-error text-sm">{error}</p>}
              <div className="modal-action">
                <button type="submit" className="btn btn-primary btn-sm" disabled={!requiredFieldsFilled || busy}>
                  {busy ? 'Saving...' : isEditMode ? 'Save' : 'Create'}
                </button>
              </div>
            </form>
          )}
          {error && loading === false && teams.length === 0 && !isEditMode && <p className="text-error text-sm mt-2">{error}</p>}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

ContestantFormModal.displayName = 'ContestantFormModal';

export default ContestantFormModal;
