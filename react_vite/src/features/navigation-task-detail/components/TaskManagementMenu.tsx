import React, { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Settings } from 'lucide-react';
import { generatePath, reverse } from '../../../urls';
import { deleteNavigationTask, refreshEditableRoute, removeAllContestants } from '../api';
import { NavigationTaskDetail } from '../types';
import BatchUpdateContestantsModal from './BatchUpdateContestantsModal';
import ContestantFormModal, { ContestantFormModalHandle } from './ContestantFormModal';
import FlightOrderConfigurationModal, { FlightOrderConfigurationModalHandle } from './FlightOrderConfigurationModal';
import UpdateTaskDetailsModal from './UpdateTaskDetailsModal';

interface TaskManagementMenuProps {
  contestId: number;
  navigationTaskId: number;
  task: NavigationTaskDetail;
  onRefresh: () => void;
}

const TaskManagementMenu: React.FC<TaskManagementMenuProps> = ({ contestId, navigationTaskId, task, onRefresh }) => {
  const navigate = useNavigate();
  const [removingContestants, setRemovingContestants] = useState(false);
  const [reloadingRoute, setReloadingRoute] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const updateDetailsModalRef = useRef<HTMLDialogElement>(null);
  const flightOrderConfigModalRef = useRef<FlightOrderConfigurationModalHandle>(null);
  const addContestantModalRef = useRef<ContestantFormModalHandle>(null);
  const batchUpdateModalRef = useRef<HTMLDialogElement>(null);

  const nextContestantNumber =
    task.contestant_set.length > 0 ? Math.max(...task.contestant_set.map((c) => c.contestant_number)) + 1 : 1;

  const handleRemoveContestants = async () => {
    if (removingContestants || !window.confirm('Remove all contestants from this navigation task?')) return;
    setRemovingContestants(true);
    try {
      await removeAllContestants(contestId, navigationTaskId);
      onRefresh();
    } catch (err: any) {
      window.alert(err.message || 'Failed to remove contestants');
    } finally {
      setRemovingContestants(false);
    }
  };

  const handleReloadRoute = async () => {
    if (reloadingRoute || !window.confirm('Reload the route from the linked editable route?')) return;
    setReloadingRoute(true);
    try {
      await refreshEditableRoute(contestId, navigationTaskId);
      onRefresh();
    } catch (err: any) {
      window.alert(err.message || 'Failed to reload the route');
    } finally {
      setReloadingRoute(false);
    }
  };

  const handleDelete = async () => {
    if (deleting || !window.confirm(`Delete navigation task "${task.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await deleteNavigationTask(contestId, navigationTaskId);
      navigate(generatePath('MISSION_DASHBOARD_DETAIL', { contestId: String(contestId) }));
    } catch (err: any) {
      window.alert(err.message || 'Failed to delete navigation task');
      setDeleting(false);
    }
  };

  return (
    <div className="dropdown dropdown-end">
      <label tabIndex={0} className="btn btn-sm btn-ghost gap-1" title="Management">
        <Settings size={16} />
        Manage
      </label>
      <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-72">
        <li className="menu-title">
          <span>Contestants</span>
        </li>
        <li>
          {/* Advanced path for power users - Quick Add, scheduling, and contestant self-registration
              cover the common cases; this exposes the full field set (tracker id, adaptive start,
              wind/air-speed overrides, etc). */}
          <button type="button" onClick={() => addContestantModalRef.current?.open()} className="w-full text-left">
            Add contestant (advanced)
          </button>
        </li>
        <li>
          <button type="button" onClick={() => batchUpdateModalRef.current?.showModal()} className="w-full text-left">
            Batch update contestants
          </button>
        </li>
        <li>
          <button type="button" disabled={removingContestants} onClick={handleRemoveContestants} className="text-error w-full text-left">
            Clear contestants
          </button>
        </li>
        {task.editable_route && (
          <>
            <li className="menu-title">
              <span>Route</span>
            </li>
            <li>
              <Link to={generatePath('ROUTE_EDITOR_EDIT', { routeId: String(task.editable_route) })}>Edit route</Link>
            </li>
            <li>
              <button type="button" disabled={reloadingRoute} onClick={handleReloadRoute} className="w-full text-left">
                Reload route
              </button>
            </li>
          </>
        )}
        <li className="menu-title">
          <span>Flight orders &amp; documents</span>
        </li>
        <li>
          <Link to={generatePath('MISSION_DASHBOARD_PHOTOS', { contestId: String(contestId), navigationTaskId: String(navigationTaskId) })}>
            Manage photos
          </Link>
        </li>
        <li>
          <a href={reverse('navigationtask_flightordersprogress', navigationTaskId)}>Generate flight orders</a>
        </li>
        <li>
          <button type="button" onClick={() => flightOrderConfigModalRef.current?.open()} className="w-full text-left">
            Flight order configuration
          </button>
        </li>
        <li>
          <a href={reverse('navigationtask_qr', navigationTaskId)}>QR Code</a>
        </li>
        {task.allow_self_management && (
          <li>
            <a href={reverse('hangar_flyer', navigationTaskId)}>Hangar flyer</a>
          </li>
        )}
        <li className="menu-title">
          <span>Task</span>
        </li>
        <li>
          <button type="button" onClick={() => updateDetailsModalRef.current?.showModal()} className="w-full text-left">
            Update
          </button>
        </li>
        <li>
          <button type="button" disabled={deleting} onClick={handleDelete} className="w-full text-left text-error">
            Delete
          </button>
        </li>
      </ul>
      <UpdateTaskDetailsModal ref={updateDetailsModalRef} contestId={contestId} navigationTaskId={navigationTaskId} task={task} onUpdated={onRefresh} />
      <FlightOrderConfigurationModal ref={flightOrderConfigModalRef} contestId={contestId} navigationTaskId={navigationTaskId} />
      <ContestantFormModal
        ref={addContestantModalRef}
        contestId={contestId}
        navigationTaskId={navigationTaskId}
        nextContestantNumber={nextContestantNumber}
        taskWindSpeed={task.wind_speed}
        taskWindDirection={task.wind_direction}
        taskMinutesToStartingPoint={task.minutes_to_starting_point}
        onSaved={onRefresh}
      />
      <BatchUpdateContestantsModal
        ref={batchUpdateModalRef}
        contestId={contestId}
        navigationTaskId={navigationTaskId}
        contestants={task.contestant_set}
        onUpdated={onRefresh}
      />
    </div>
  );
};

export default TaskManagementMenu;
