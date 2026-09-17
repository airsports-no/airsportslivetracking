import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapPin } from 'lucide-react';
import { Loading } from '../route-editor/components/basicComponents';
import { fetchNavigationTask } from '../competition-map/api';
import { shareNavigationTask, NavigationTaskVisibility } from './api';
import { generatePath } from '../../urls';
import { formatDateInterval } from '../../utils';

// The competition-map and mission-dashboard features each keep their own (incomplete, mutually
// inconsistent) NavigationTask type - see the "Deferred lint & verification backlog" note in
// project memory. Rather than fight that pre-existing duplication, this page declares the
// narrow slice of the real REST payload (navigationtasks-detail) it actually reads.
interface NavigationTaskDetail {
  name: string;
  start_time: string;
  finish_time: string;
  tracking_link: string;
  is_public: boolean;
  is_featured: boolean;
  user_has_change_permission: boolean;
  contestant_set: unknown[];
}

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

      <div className="flex flex-wrap gap-2 mb-6">
        <Link to={generatePath('SCORECARD_EDITOR', { contestId: contestId!, navigationTaskId: navigationTaskId! })} className="btn btn-sm">
          Scorecard
        </Link>
        <Link to={generatePath('CONTEST_RESULTS_TABLE', { contestId: contestId! })} className="btn btn-sm">
          Results
        </Link>
        <Link
          to={generatePath('MISSION_DASHBOARD_PHOTOS', { contestId: contestId!, navigationTaskId: navigationTaskId! })}
          className="btn btn-sm"
        >
          Photos
        </Link>
        {canManage && (
          <Link
            to={generatePath('CONTESTANT_SCHEDULING', { contestId: contestId!, navigationTaskId: navigationTaskId! })}
            className="btn btn-sm"
          >
            Scheduling
          </Link>
        )}
      </div>

      {canManage && (
        <div className="mb-6">
          <span className="font-semibold mr-2">Visibility:</span>
          <div className="join">
            {VISIBILITY_OPTIONS.map((option) => (
              <button
                key={option.value}
                disabled={sharingBusy}
                onClick={() => handleShare(option.value)}
                className={`btn btn-sm join-item ${visibility === option.value ? 'btn-active' : ''}`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="divider" />

      <h2 className="text-xl font-bold mb-2">Contestants ({task.contestant_set.length})</h2>
      <p className="text-sm text-gray-500">Contestant management is coming in the next slice.</p>

      <Link to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: contestId! })} className="btn btn-secondary mt-6">
        Back to contest
      </Link>
    </div>
  );
};

export default NavigationTaskDetailPage;
