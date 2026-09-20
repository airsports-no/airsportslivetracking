import React, { useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { restartCalculator, terminateCalculator } from '../api';
import { ContestantRow, TeamDisplay } from '../types';
import { formatDateHeadingInZone, formatDateKeyInZone, formatTimeInZone, formatWholeNumber, formatWindDirection } from '../utils';
import ContestantActionsMenu from './ContestantActionsMenu';
import ContestantFormModal, { ContestantFormModalHandle } from './ContestantFormModal';

const TeamDisplayLabel: React.FC<{ team: TeamDisplay; missingDeclaration?: boolean; declarationErrors?: string[]; onClick: () => void }> = ({
  team,
  missingDeclaration,
  declarationErrors,
  onClick,
}) => (
  <button
    type="button"
    onClick={onClick}
    className="leading-tight text-left hover:underline decoration-dotted"
    title="Edit contestant"
  >
    {missingDeclaration && (
      // Prefer the actual validation error(s) - e.g. a route that structurally can't satisfy
      // this task subtype (wrong waypoint count for contract navigation, etc.) - over the
      // generic message, so a declaration that was saved but is still invalid doesn't look
      // identical to one that was never entered at all.
      <span
        className="tooltip"
        data-tip={declarationErrors && declarationErrors.length > 0 ? declarationErrors.join('; ') : 'Missing required declaration'}
      >
        <AlertTriangle size={12} className="inline text-warning align-text-top mr-1" />
      </span>
    )}
    {team.crew.member1.first_name} {team.crew.member1.last_name}
    {team.crew.member2 && (
      <>
        <br />
        {team.crew.member2.first_name} {team.crew.member2.last_name}
      </>
    )}
    <br />
    <span className="text-[10px] opacity-70">{team.aeroplane.registration}</span>
  </button>
);

interface ContestantListProps {
  contestants: ContestantRow[];
  contestId: number;
  navigationTaskId: number;
  taskSubtype?: string | null;
  isPokerRun?: boolean;
  canManage: boolean;
  timeZone: string;
  runningStatus: Record<number, boolean>;
  onRefresh: () => void;
}

interface LiveDotProps {
  contestant: ContestantRow;
  isRunning: boolean;
  contestId: number;
  navigationTaskId: number;
  canManage: boolean;
  onRefresh: () => void;
}

const LiveDot: React.FC<LiveDotProps> = ({ contestant, isRunning, contestId, navigationTaskId, canManage, onRefresh }) => {
  const [busy, setBusy] = useState(false);

  const handleClick = async (action: 'terminate' | 'restart', confirmMessage: string) => {
    if (busy || !window.confirm(confirmMessage)) return;
    setBusy(true);
    try {
      if (action === 'terminate') {
        await terminateCalculator(contestId, navigationTaskId, contestant.pk);
      } else {
        await restartCalculator(contestId, navigationTaskId, contestant.pk);
      }
      onRefresh();
    } catch (err: any) {
      window.alert(err.message || `Failed to ${action} the calculator`);
    } finally {
      setBusy(false);
    }
  };

  if (isRunning) {
    if (!canManage) {
      return (
        <div className="tooltip tooltip-right" data-tip="Calculator is running.">
          <div className="w-3 h-3 rounded-full bg-success animate-pulse" />
        </div>
      );
    }
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => handleClick('terminate', 'Stop calculator?')}
        className="tooltip tooltip-right p-0 border-0 bg-transparent"
        data-tip="Calculator is running."
      >
        <div className="w-3 h-3 rounded-full bg-success animate-pulse" />
      </button>
    );
  }
  if (contestant.contestanttrack.calculator_finished) {
    if (!canManage) {
      return (
        <div className="tooltip tooltip-right" data-tip="Finished.">
          <div className="w-3 h-3 rounded-full bg-error/50" />
        </div>
      );
    }
    return (
      <button
        type="button"
        disabled={busy}
        onClick={() => handleClick('restart', 'Restart calculator?')}
        className="tooltip tooltip-right p-0 border-0 bg-transparent"
        data-tip="Restart calculator."
      >
        <div className="w-3 h-3 rounded-full bg-error/50" />
      </button>
    );
  }
  return (
    <div className="tooltip tooltip-right" data-tip="Not running.">
      <div className="w-3 h-3 rounded-full bg-error" />
    </div>
  );
};

const groupByDay = (contestants: ContestantRow[], timeZone: string) => {
  const sorted = [...contestants].sort((a, b) => a.contestant_number - b.contestant_number);
  const groups: { dayKey: string; heading: string; contestants: ContestantRow[] }[] = [];
  for (const contestant of sorted) {
    const dayKey = formatDateKeyInZone(contestant.takeoff_time, timeZone);
    let group = groups.find((g) => g.dayKey === dayKey);
    if (!group) {
      group = { dayKey, heading: formatDateHeadingInZone(contestant.takeoff_time, timeZone), contestants: [] };
      groups.push(group);
    }
    group.contestants.push(contestant);
  }
  return groups;
};

const ContestantList: React.FC<ContestantListProps> = ({
  contestants,
  contestId,
  navigationTaskId,
  taskSubtype,
  isPokerRun,
  canManage,
  timeZone,
  runningStatus,
  onRefresh,
}) => {
  const groups = groupByDay(contestants, timeZone);
  const editModalRef = useRef<ContestantFormModalHandle>(null);
  const handleTeamNameClick = (contestantPk: number) => {
    if (canManage) editModalRef.current?.open(contestantPk);
  };

  if (contestants.length === 0) {
    return <p className="text-sm text-gray-500">No contestants yet.</p>;
  }

  return (
    <div>
      {/* Mobile card view */}
      <div className="block md:hidden space-y-4">
        {groups.map((group) => (
          <React.Fragment key={group.dayKey}>
            <div className="divider font-bold text-base-content/60">{group.heading}</div>
            {group.contestants.map((contestant) => (
              <div key={contestant.pk} className="card bg-base-200/50 shadow-sm border border-base-300">
                <div className="card-body p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="badge badge-neutral font-mono font-bold shrink-0">#{contestant.contestant_number}</span>
                        <span className="font-bold text-lg break-words leading-tight">
                          <TeamDisplayLabel
                            team={contestant.team}
                            missingDeclaration={contestant.declaration_status.required && !contestant.declaration_status.complete}
                            declarationErrors={contestant.declaration_status.errors}
                            onClick={() => handleTeamNameClick(contestant.pk)}
                          />
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <LiveDot
                          contestant={contestant}
                          isRunning={!!runningStatus[contestant.pk]}
                          contestId={contestId}
                          navigationTaskId={navigationTaskId}
                          canManage={canManage}
                          onRefresh={onRefresh}
                        />
                        <span className="badge badge-outline badge-sm">{contestant.contestanttrack.current_state}</span>
                      </div>
                    </div>
                    <ContestantActionsMenu
                      contestant={contestant}
                      contestId={contestId}
                      navigationTaskId={navigationTaskId}
                      taskSubtype={taskSubtype}
                      isPokerRun={isPokerRun}
                      canManage={canManage}
                      timeZone={timeZone}
                      onRefresh={onRefresh}
                      iconTrigger
                    />
                  </div>

                  {contestant.tracker_id_display.length > 0 && (
                    <div className="mt-3 text-xs bg-base-100 rounded p-2">
                      <div className="font-semibold mb-1 opacity-70">Trackers:</div>
                      {contestant.tracker_id_display.map((tracker) => (
                        <div key={tracker.tracker} className="flex items-center gap-2 mb-1 last:mb-0 min-w-0">
                          <span className="truncate">{tracker.tracker}</span>
                          {!tracker.has_user && <span className="text-error">*</span>}
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-2 mt-3 text-xs">
                    <div className="bg-base-100 p-2 rounded">
                      <div className="opacity-70 mb-0.5">Tracking Start</div>
                      <div className="font-mono">{formatTimeInZone(contestant.tracker_start_time, timeZone)}</div>
                    </div>
                    <div className="bg-base-100 p-2 rounded">
                      <div className="opacity-70 mb-0.5">Takeoff</div>
                      <div className="font-mono">
                        {contestant.adaptive_start ? 'Adaptive' : formatTimeInZone(contestant.takeoff_time, timeZone)}
                      </div>
                    </div>
                    <div className="bg-base-100 p-2 rounded">
                      <div className="opacity-70 mb-0.5">Finished</div>
                      <div className="font-mono">{formatTimeInZone(contestant.finished_by_time, timeZone)}</div>
                    </div>
                    <div className="bg-base-100 p-2 rounded">
                      <div className="opacity-70 mb-0.5">Airspeed</div>
                      <div className="font-mono">{formatWholeNumber(contestant.air_speed)}</div>
                    </div>
                    <div className="bg-base-100 p-2 rounded">
                      <div className="opacity-70 mb-0.5">Wind</div>
                      <div className="font-mono">
                        {formatWindDirection(contestant.wind_direction)}/{contestant.wind_speed}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </React.Fragment>
        ))}
      </div>

      {/* Desktop table view */}
      <div className="hidden md:block overflow-visible">
        <table className="table table-zebra table-xs w-full">
          <thead>
            <tr>
              <th className="w-8">#</th>
              <th>Team</th>
              <th className="w-8">Live</th>
              <th>Tracking</th>
              <th>Timing</th>
              <th className="w-8">AS</th>
              <th className="w-8">Wind</th>
              <th>State</th>
              <th className="w-16">Actions</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <React.Fragment key={group.dayKey}>
                <tr className="bg-base-200 font-bold">
                  <td colSpan={9} className="text-center py-2 text-base-content/80">
                    {group.heading}
                  </td>
                </tr>
                {group.contestants.map((contestant) => (
                  <tr key={contestant.pk} className="hover">
                    <td className="font-bold text-base-content/70">{contestant.contestant_number}</td>
                    <td className="whitespace-nowrap font-medium">
                      <TeamDisplayLabel
                        team={contestant.team}
                        missingDeclaration={contestant.declaration_status.required && !contestant.declaration_status.complete}
                        declarationErrors={contestant.declaration_status.errors}
                        onClick={() => handleTeamNameClick(contestant.pk)}
                      />
                    </td>
                    <td>
                      <LiveDot
                        contestant={contestant}
                        isRunning={!!runningStatus[contestant.pk]}
                        contestId={contestId}
                        navigationTaskId={navigationTaskId}
                        canManage={canManage}
                        onRefresh={onRefresh}
                      />
                    </td>
                    <td>
                      {contestant.tracker_id_display.map((tracker) => (
                        <div
                          key={tracker.tracker}
                          className="flex items-center gap-1 whitespace-nowrap overflow-hidden text-[10px] opacity-80"
                          title={tracker.tracker}
                        >
                          <span className="truncate max-w-[120px]">{tracker.tracker}</span>
                          {!tracker.has_user && (
                            <span className="text-error font-bold" title="User not registered">
                              *
                            </span>
                          )}
                        </div>
                      ))}
                    </td>
                    <td>
                      <div className="text-[10px] leading-tight space-y-0.5 whitespace-nowrap">
                        <div>
                          <span className="opacity-50">Trk:</span> {formatTimeInZone(contestant.tracker_start_time, timeZone)}
                        </div>
                        <div>
                          <span className="opacity-50">T/O:</span>{' '}
                          {contestant.adaptive_start
                            ? contestant.has_crossed_starting_line
                              ? formatTimeInZone(contestant.takeoff_time, timeZone)
                              : 'Adap.'
                            : formatTimeInZone(contestant.takeoff_time, timeZone)}
                        </div>
                        <div>
                          <span className="opacity-50">Fin:</span> {formatTimeInZone(contestant.finished_by_time, timeZone)}
                        </div>
                      </div>
                    </td>
                    <td className="font-mono">{formatWholeNumber(contestant.air_speed)}</td>
                    <td>
                      <div className="font-mono text-[10px]">
                        {formatWindDirection(contestant.wind_direction)}/{contestant.wind_speed}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-outline badge-xs whitespace-nowrap">{contestant.contestanttrack.current_state}</span>
                    </td>
                    <td>
                      <ContestantActionsMenu
                        contestant={contestant}
                        contestId={contestId}
                        navigationTaskId={navigationTaskId}
                        taskSubtype={taskSubtype}
                        isPokerRun={isPokerRun}
                        canManage={canManage}
                        timeZone={timeZone}
                        onRefresh={onRefresh}
                      />
                    </td>
                  </tr>
                ))}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {canManage && (
        <ContestantFormModal ref={editModalRef} contestId={contestId} navigationTaskId={navigationTaskId} onSaved={onRefresh} />
      )}
    </div>
  );
};

export default ContestantList;
