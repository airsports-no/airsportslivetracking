import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin, Plus } from 'lucide-react';
import { Loading } from '../route-editor/components/basicComponents';
import { fetchNavigationTask } from '../competition-map/api';
import { fetchRunningCalculators, shareNavigationTask, NavigationTaskVisibility } from './api';
import { NavigationTaskDetail } from './types';
import ContestantList from './components/ContestantList';
import QuickAddContestantModal, { QuickAddContestantModalHandle } from './components/QuickAddContestantModal';
import TaskManagementMenu from './components/TaskManagementMenu';
import { generatePath } from '../../urls';
import { formatDateInterval } from '../../utils';

const visibilityOf = (task: NavigationTaskDetail): NavigationTaskVisibility => {
  if (task.is_public && task.is_featured) return 'public';
  if (task.is_public && !task.is_featured) return 'unlisted';
  return 'private';
};

const VISIBILITY_OPTIONS: { value: NavigationTaskVisibility; label: string }[] = [
  { value: 'private', label: 'Private' },
  { value: 'unlisted', label: 'Unlisted' },
  { value: 'public', label: 'Public' },
];

const NavigationTaskDetailPage: React.FC = () => {
  const { contestId, navigationTaskId } = useParams<{ contestId: string; navigationTaskId: string }>();
  const [task, setTask] = useState<NavigationTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sharingBusy, setSharingBusy] = useState(false);
  const [runningStatus, setRunningStatus] = useState<Record<number, boolean>>({});
  const quickAddModalRef = useRef<QuickAddContestantModalHandle>(null);

  const load = useCallback(async () => {
    if (!contestId || !navigationTaskId) return;
    try {
      setLoading(true);
      const data = await fetchNavigationTask(Number(contestId), Number(navigationTaskId));
      setTask(data as unknown as NavigationTaskDetail);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load navigation task');
    } finally {
      setLoading(false);
    }
  }, [contestId, navigationTaskId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!navigationTaskId) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const statuses = await fetchRunningCalculators(Number(navigationTaskId));
        if (!cancelled) {
          setRunningStatus(Object.fromEntries(statuses));
        }
      } catch {
        // Transient polling failures aren't worth surfacing as a page-level error.
      }
    };
    poll();
    const interval = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [navigationTaskId]);

  const handleShare = async (visibility: NavigationTaskVisibility) => {
    if (!contestId || !navigationTaskId) return;
    setSharingBusy(true);
    try {
      await shareNavigationTask(Number(contestId), Number(navigationTaskId), visibility);
      await load();
    } catch (err: any) {
      setError(err.message || 'Failed to update sharing');
    } finally {
      setSharingBusy(false);
    }
  };

  if (loading && !task) return <Loading />;
  if (error && !task) return <div className="alert alert-error m-4">{error}</div>;
  if (!task) return null;

  const canManage = task.user_has_change_permission;
  const visibility = visibilityOf(task);

  return (
    <div className="p-4 max-w-5xl mx-auto">
      {error && <div className="alert alert-error mb-4">{error}</div>}

      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
        <h1 className="text-2xl font-bold">{task.name}</h1>
        <a
          href={task.tracking_link}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-sm btn-outline btn-info gap-1"
        >
          <MapPin size={14} />
          Live Map
        </a>
      </div>
      <p className="text-sm text-gray-500 mb-4">{formatDateInterval(task.start_time, task.finish_time)}</p>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        {/* Navigation: destinations that just show data about this task. */}
        <div className="join">
          <Link
            to={generatePath('SCORECARD_EDITOR', { contestId: contestId!, navigationTaskId: navigationTaskId! })}
            className="btn btn-sm btn-outline join-item"
          >
            Scorecard
          </Link>
          <Link to={generatePath('CONTEST_RESULTS_TABLE', { contestId: contestId! })} className="btn btn-sm btn-outline join-item">
            Results
          </Link>
          <Link
            to={generatePath('MISSION_DASHBOARD_PHOTOS', { contestId: contestId!, navigationTaskId: navigationTaskId! })}
            className="btn btn-sm btn-outline join-item"
          >
            Photos
          </Link>
          {canManage && (
            <Link
              to={generatePath('CONTESTANT_SCHEDULING', { contestId: contestId!, navigationTaskId: navigationTaskId! })}
              className="btn btn-sm btn-outline join-item"
            >
              Scheduling
            </Link>
          )}
        </div>

        {canManage && (
          <>
            <div className="divider divider-horizontal mx-0 hidden sm:flex" />
            {/* Actions: the primary "do something" affordance stays a plain button; anything
                less frequent lives behind the management dropdown instead of crowding the bar. */}
            <button type="button" className="btn btn-sm btn-primary gap-1" onClick={() => quickAddModalRef.current?.open()}>
              <Plus size={14} />
              Quick Add
            </button>
            <TaskManagementMenu contestId={Number(contestId)} navigationTaskId={Number(navigationTaskId)} task={task} onRefresh={load} />
          </>
        )}
      </div>

      {canManage && (
        <div className="mb-6 flex items-center gap-2">
          <span className="font-semibold text-sm">Visibility:</span>
          <div className="join">
            {VISIBILITY_OPTIONS.map((option) => (
              <button
                key={option.value}
                disabled={sharingBusy}
                onClick={() => handleShare(option.value)}
                className={`btn btn-sm join-item ${visibility === option.value ? 'btn-primary' : 'btn-outline'}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {canManage && task.guest_capacity_status.show_guest_capacity_warning && (
        <div
          className={`alert ${task.guest_capacity_status.guest_capacity_full ? 'alert-warning' : 'alert-info'} shadow-sm mb-6 text-sm`}
        >
          <div>
            <div className="font-bold">Pilot capacity status</div>
            {task.guest_capacity_status.guest_capacity_full ? (
              <div>
                {task.guest_capacity_status.guest_created_contestants} / {task.guest_capacity_status.guest_capacity_limit} guest
                pilot slots are now reserved on this task. The contest owner is exempt. To enable more slots, remove an
                unstarted contestant that is holding a reservation, reuse an already-counted pilot, or apply a larger token
                or club pass.
              </div>
            ) : (
              <div>
                {task.guest_capacity_status.guest_created_contestants} / {task.guest_capacity_status.guest_capacity_limit} guest
                pilot slots are reserved on this task. The contest owner is exempt.
              </div>
            )}
          </div>
        </div>
      )}

      <div className="divider" />

      <h2 className="text-xl font-bold mb-4">Contestants ({task.contestant_set.length})</h2>
      <ContestantList
        contestants={task.contestant_set}
        contestId={Number(contestId)}
        navigationTaskId={Number(navigationTaskId)}
        taskSubtype={task.task_subtype}
        isPokerRun={task.is_poker_run}
        canManage={canManage}
        timeZone={task.time_zone}
        runningStatus={runningStatus}
        onRefresh={load}
      />

      <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contestId! })} className="btn btn-secondary mt-6">
        Back to contest
      </Link>

      {canManage && (
        <QuickAddContestantModal
          ref={quickAddModalRef}
          contestId={Number(contestId)}
          navigationTaskId={Number(navigationTaskId)}
          onAdded={load}
        />
      )}
    </div>
  );
};

export default NavigationTaskDetailPage;
