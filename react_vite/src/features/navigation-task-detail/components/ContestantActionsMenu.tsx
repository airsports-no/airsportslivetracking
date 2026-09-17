import React from 'react';
import { Link } from 'react-router-dom';
import { EllipsisVertical } from 'lucide-react';
import { reverse, generatePath } from '../../../urls';
import { ContestantRow, supportsDeclarationEditing } from '../types';

interface ContestantActionsMenuProps {
  contestant: ContestantRow;
  contestId: number;
  navigationTaskId: number;
  taskSubtype?: string | null;
  canManage: boolean;
  /** Renders the trigger as a vertical-ellipsis icon button (mobile) instead of the text "Actions" button (desktop). */
  iconTrigger?: boolean;
}

// Read-only/navigation items only for now - the calculator lifecycle, GPX/recalculate, penalty/
// card, and delete actions still link out to the classic Django pages; they get wired to the
// Slice 0 REST actions incrementally in follow-up commits (see project memory).
const ContestantActionsMenu: React.FC<ContestantActionsMenuProps> = ({
  contestant,
  contestId,
  navigationTaskId,
  taskSubtype,
  canManage,
  iconTrigger,
}) => {
  return (
    <div className="dropdown dropdown-end dropdown-left">
      <label tabIndex={0} className={iconTrigger ? 'btn btn-square btn-ghost btn-sm' : 'btn btn-ghost btn-xs px-1'}>
        {iconTrigger ? <EllipsisVertical size={20} /> : 'Actions'}
      </label>
      <ul tabIndex={0} className="dropdown-content menu p-2 shadow bg-base-100 rounded-box w-52 z-50">
        <li>
          <a href={reverse('contestant_gate_times', contestant.pk)}>View / remove penalties</a>
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
              <a href={`${reverse('navigationtask_flightordersprogress', navigationTaskId)}?contestant_pk=${contestant.pk}`}>
                Generate flight order
              </a>
            </li>
            <li>
              <a href={reverse('contestant_uploadgpxtrack', contestant.pk)}>Upload GPX</a>
            </li>
            <li>
              <a href={reverse('contestant_downloadgpxtrack', contestant.pk)}>Download GPX</a>
            </li>
            <li>
              <a href={reverse('contestant_recalculatelivetrack', contestant.pk)}>Recalculate live track</a>
            </li>
            <li>
              <a href={reverse('contestant_recalculate_start_time', contestant.pk)}>Recalculate with new start time</a>
            </li>
            <li>
              <a href={reverse('processingstatistics', contestant.pk)}>Processing statistics</a>
            </li>
            <li>
              <hr className="my-1 border-base-200" />
            </li>
            <li>
              <a href={reverse('contestant_delete', contestant.pk)} className="text-error">
                Delete
              </a>
            </li>
          </>
        )}
      </ul>
    </div>
  );
};

export default ContestantActionsMenu;
