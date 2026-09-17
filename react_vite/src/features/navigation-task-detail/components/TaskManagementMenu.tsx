import React, { useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Settings } from 'lucide-react';
import { generatePath, reverse } from '../../../urls';
import { deleteNavigationTask, refreshEditableRoute, removeAllContestants } from '../api';
import { NavigationTaskDetail } from '../types';
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
      <label tabIndex={0} className="btn btn-sm btn-square btn-ghost" title="Management">
        <Settings size={16} />
      </label>
      <ul tabIndex={0} className="dropdown-content z-[1] menu p-2 shadow bg-base-100 rounded-box w-64">
        <li>
          <button type="button" disabled={removingContestants} onClick={handleRemoveContestants} className="text-error w-full text-left">
            Remove contestants
          </button>
        </li>
        {task.editable_route && (
          <>
            <li>
              <hr className="my-1 border-base-200" />
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
        <li>
          <hr className="my-1 border-base-200" />
        </li>
        <li>
          <a href={reverse('navigationtask_flightordersprogress', navigationTaskId)}>Generate flight orders</a>
        </li>
        <li>
          <a href={reverse('navigationtask_qr', navigationTaskId)}>QR Code</a>
        </li>
        {task.allow_self_management && (
          <li>
            <a href={reverse('hangar_flyer', navigationTaskId)}>Hangar flyer</a>
          </li>
        )}
        <li>
          <a href={reverse('navigationtask_map', navigationTaskId)}>Navigation Map</a>
        </li>
        <li>
          <hr className="my-1 border-base-200" />
        </li>
        <li>
          <button type="button" onClick={() => flightOrderConfigModalRef.current?.open()} className="w-full text-left">
            Flight order configuration
          </button>
        </li>
        <li>
          {/* TODO: still the classic Django form - it scopes map_source choices to this
              specific navigation task's available maps (get_available_map_source_definitions_for_navigation_task),
              which the REST action above doesn't replicate yet. See project memory. */}
          <a href={reverse('navigationtask_flightorderconfiguration', navigationTaskId)}>
            Flight order configuration (advanced)
          </a>
        </li>
        <li>
          <hr className="my-1 border-base-200" />
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
    </div>
  );
};

export default TaskManagementMenu;
