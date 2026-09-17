import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { EllipsisVertical } from 'lucide-react';
import { reverse, generatePath } from '../../../urls';
import { deleteContestant, recalculateTrack } from '../api';
import { ContestantRow, supportsDeclarationEditing } from '../types';
import GateTimesModal, { GateTimesModalHandle } from './GateTimesModal';
import RecalculateStartTimeModal from './RecalculateStartTimeModal';
import UploadGpxModal from './UploadGpxModal';

interface ContestantActionsMenuProps {
  contestant: ContestantRow;
  contestId: number;
  navigationTaskId: number;
  taskSubtype?: string | null;
  canManage: boolean;
  timeZone: string;
  onRefresh: () => void;
  /** Renders the trigger as a vertical-ellipsis icon button (mobile) instead of the text "Actions" button (desktop). */
  iconTrigger?: boolean;
}

// GPX download, "processing statistics", and playing-card actions still link out to the classic
// Django pages - see project memory for what's still pending.
const ContestantActionsMenu: React.FC<ContestantActionsMenuProps> = ({
  contestant,
  contestId,
  navigationTaskId,
  taskSubtype,
  canManage,
  timeZone,
  onRefresh,
  iconTrigger,
}) => {
  const [recalculating, setRecalculating] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const startTimeModalRef = useRef<HTMLDialogElement>(null);
  const gpxModalRef = useRef<HTMLDialogElement>(null);
  const gateTimesModalRef = useRef<GateTimesModalHandle>(null);

  const handleRecalculateTrack = async () => {
    if (recalculating || !window.confirm('Reset the track/score and reload it from the tracker?')) return;
    setRecalculating(true);
    try {
      await recalculateTrack(contestId, navigationTaskId, contestant.pk);
      onRefresh();
    } catch (err: any) {
      window.alert(err.message || 'Failed to recalculate the live track');
    } finally {
      setRecalculating(false);
    }
  };

  const handleDelete = async () => {
    if (deleting || !window.confirm(`Delete contestant #${contestant.contestant_number}? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteContestant(contestId, navigationTaskId, contestant.pk);
      onRefresh();
    } catch (err: any) {
      window.alert(err.message || 'Failed to delete contestant');
      setDeleting(false);
    }
  };

  return (
    <div className="dropdown dropdown-end dropdown-left">
      <label tabIndex={0} className={iconTrigger ? 'btn btn-square btn-ghost btn-sm' : 'btn btn-ghost btn-xs px-1'}>
        {iconTrigger ? <EllipsisVertical size={20} /> : 'Actions'}
      </label>
      <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-100 rounded-box w-52 z-50">
        <li>
          <button type="button" onClick={() => gateTimesModalRef.current?.open()} className="w-full text-left">
            View / remove penalties
          </button>
        </li>
        <li>
          <a href={reverse('contestant_map', contestant.pk)}>Map</a>
        </li>
        {supportsDeclarationEditing(taskSubtype) && (
          <li>
            <Link
              to={generatePath('CONTESTANT_DECLARATION', {
                contestId: String(contestId),
                navigationTaskId: String(navigationTaskId),
                contestantId: String(contestant.pk),
              })}
            >
              Edit declaration
            </Link>
          </li>
        )}
        {canManage && (
          <>
            <li>
              <hr className="my-1 border-base-200" />
            </li>
            <li>
              {/* TODO: still the classic Django form (team/aircraft/tracker/wind fields) - no
                  React equivalent has been built yet. See project memory. */}
              <a href={reverse('contestant_update', contestant.pk)}>Edit team assignment</a>
            </li>
            <li>
              <a href={`${reverse('navigationtask_flightordersprogress', navigationTaskId)}?contestant_pk=${contestant.pk}`}>
                Generate flight order
              </a>
            </li>
            <li>
              <button type="button" onClick={() => gpxModalRef.current?.showModal()} className="w-full text-left">
                Upload GPX
              </button>
            </li>
            <li>
              <a href={reverse('contestant_downloadgpxtrack', contestant.pk)}>Download GPX</a>
            </li>
            <li>
              <button type="button" disabled={recalculating} onClick={handleRecalculateTrack} className="w-full text-left">
                Recalculate live track
              </button>
            </li>
            <li>
              <button type="button" onClick={() => startTimeModalRef.current?.showModal()} className="w-full text-left">
                Recalculate with new start time
              </button>
            </li>
            <li>
              <a href={reverse('processingstatistics', contestant.pk)}>Processing statistics</a>
            </li>
            <li>
              {/* TODO: poker-run playing cards - still the classic Django page, no React
                  equivalent yet. Shown unconditionally since the REST payload doesn't expose
                  is_poker_run to gate it on. See project memory. */}
              <a href={reverse('contestant_cards_list', contestant.pk)}>Playing cards</a>
            </li>
            <li>
              <hr className="my-1 border-base-200" />
            </li>
            <li>
              <button type="button" disabled={deleting} onClick={handleDelete} className="w-full text-left text-error">
                Delete
              </button>
            </li>
          </>
        )}
      </ul>
      <GateTimesModal
        ref={gateTimesModalRef}
        contestId={contestId}
        navigationTaskId={navigationTaskId}
        contestantId={contestant.pk}
        contestantNumber={contestant.contestant_number}
        canManage={canManage}
        timeZone={timeZone}
        onChanged={onRefresh}
      />
      {canManage && (
        <>
          <UploadGpxModal
            ref={gpxModalRef}
            contestId={contestId}
            navigationTaskId={navigationTaskId}
            contestantId={contestant.pk}
            onUploaded={onRefresh}
          />
          <RecalculateStartTimeModal
            ref={startTimeModalRef}
            contestId={contestId}
            navigationTaskId={navigationTaskId}
            contestantId={contestant.pk}
            onRecalculated={onRefresh}
          />
        </>
      )}
    </div>
  );
};

export default ContestantActionsMenu;
