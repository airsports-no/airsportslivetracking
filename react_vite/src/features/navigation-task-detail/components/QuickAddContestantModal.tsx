import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { ContestTeamOption, fetchContestTeams, quickAddContestant } from '../api';

export interface QuickAddContestantModalHandle {
  open: () => void;
}

interface QuickAddContestantModalProps {
  contestId: number;
  navigationTaskId: number;
  onAdded: () => void;
}

const teamLabel = (option: ContestTeamOption): string => {
  const { member1, member2 } = option.team.crew;
  const pilots = member2 ? `${member1.first_name} ${member1.last_name} / ${member2.first_name} ${member2.last_name}` : `${member1.first_name} ${member1.last_name}`;
  return `${pilots} (${option.team.aeroplane.registration})`;
};

const QuickAddContestantModal = forwardRef<QuickAddContestantModalHandle, QuickAddContestantModalProps>(
  ({ contestId, navigationTaskId, onAdded }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [teams, setTeams] = useState<ContestTeamOption[]>([]);
    const [loading, setLoading] = useState(false);
    const [contestTeamId, setContestTeamId] = useState<string>('');
    const [startingPointTime, setStartingPointTime] = useState('');
    const [adaptiveStart, setAdaptiveStart] = useState(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const options = await fetchContestTeams(contestId);
        setTeams(options);
        if (options.length > 0) setContestTeamId(String(options[0].id));
      } catch (err: any) {
        setError(err.message || 'Failed to load registered teams');
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
      if (!contestTeamId || !startingPointTime) return;
      setBusy(true);
      setError(null);
      try {
        await quickAddContestant(contestId, navigationTaskId, {
          contest_team: Number(contestTeamId),
          starting_point_time: new Date(startingPointTime).toISOString(),
          adaptive_start: adaptiveStart,
        });
        dialogRef.current?.close();
        setStartingPointTime('');
        onAdded();
      } catch (err: any) {
        setError(err.message || 'Failed to add contestant');
      } finally {
        setBusy(false);
      }
    };

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={() => dialogRef.current?.close()}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg mb-2">Quick add contestant</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading registered teams...</p>}

          {!loading && teams.length === 0 && !error && (
            <p className="py-4 text-sm text-gray-500">No teams are registered for this contest yet.</p>
          )}

          {!loading && teams.length > 0 && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <label className="form-control">
                <span className="label-text text-xs">Team</span>
                <select
                  className="select select-bordered select-sm"
                  value={contestTeamId}
                  onChange={(e) => setContestTeamId(e.target.value)}
                >
                  {teams.map((option) => (
                    <option key={option.id} value={option.id}>
                      {teamLabel(option)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-control">
                <span className="label-text text-xs">Time at starting point</span>
                <input
                  type="datetime-local"
                  step={60}
                  className="input input-bordered input-sm w-full"
                  value={startingPointTime}
                  onChange={(e) => setStartingPointTime(e.target.value)}
                />
              </label>
              <label className="label cursor-pointer justify-start gap-2">
                <input
                  type="checkbox"
                  className="checkbox checkbox-sm"
                  checked={adaptiveStart}
                  onChange={(e) => setAdaptiveStart(e.target.checked)}
                />
                <span className="label-text">Adaptive start</span>
              </label>
              {error && <p className="text-error text-sm">{error}</p>}
              <div className="modal-action">
                <button type="submit" className="btn btn-primary btn-sm" disabled={!contestTeamId || !startingPointTime || busy}>
                  {busy ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          )}
          {error && teams.length === 0 && <p className="text-error text-sm mt-2">{error}</p>}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

QuickAddContestantModal.displayName = 'QuickAddContestantModal';

export default QuickAddContestantModal;
