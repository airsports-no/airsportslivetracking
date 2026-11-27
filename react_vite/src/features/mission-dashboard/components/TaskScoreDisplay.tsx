import React from 'react';
import { NavigationTask } from '../types';
import { generatePath } from '../../../urls';
import { FlightSummaryButton } from '../../../components/common/FlightSummaryModal';
import { hasSummaryButton, useSummarisableFlights } from '../../../components/common/flightSummaryApi';
import { DNF_LABEL, DNF_TITLE, didNotFly, formatScoreOutOf, isQualityTask, PROVISIONAL_HELP, scoreArithmetic, scoresAreProvisional, sortByScore, trimmedNumber } from '../../../utils/taskScore';

interface TaskScoreDisplayProps {
    task: NavigationTask;
    myContestantIds: Set<number>;
    contestId?: number;
}

const TaskScoreDisplay: React.FC<TaskScoreDisplayProps> = ({ task, myContestantIds, contestId }) => {
    // The task detail endpoint used to send only "id": fall back to it so the replay link works against an older backend as well
    const navigationTaskId: number | undefined = task.pk ?? (task as { id?: number }).id;
    // Every flight with an AI summary gets its button (a superuser's, any flight, to have one written)
    const summarisable = useSummarisableFlights(navigationTaskId);

    if (!task.contestant_set || task.contestant_set.length === 0) {
        return <p>No scores recorded for this task yet.</p>;
    }

    const isStruckThrough = (contestant: any) =>
        (contestant.contestanttrack.calculator_started === false && contestant.contestanttrack.score === 0) ||
        contestant.contestanttrack.current_state === 'Waiting...';

    // Highest first for a quality task, the scorecard's direction otherwise
    const sorted = sortByScore(task.contestant_set as any[], contestant => contestant.contestanttrack.score, task, task.score_sorting_direction);
    const tracks = (task.contestant_set as any[]).map(contestant => contestant.contestanttrack);
    const quality = isQualityTask(task);
    const provisional = scoresAreProvisional(task, tracks);
    // Rank only among entries that actually flew; struck-through rows are shown but do not count
    const ranked = sorted.filter(contestant => !isStruckThrough(contestant));

    return (
        <div className="mt-4 pt-2 bg-base-100 p-2 rounded-lg">
            <h5 className="font-semibold text-md mb-2">
                Scores for {task.name}{quality && task.task_value ? ` (out of ${trimmedNumber(task.task_value)})` : ''}:
                {provisional && (
                    <span className="badge badge-warning badge-sm ml-2 align-middle" title={PROVISIONAL_HELP} data-testid="provisional-badge">Provisional</span>
                )}
            </h5>
            {provisional && <p className="text-xs opacity-70 mb-2">{PROVISIONAL_HELP}</p>}
            {sorted
                .map(contestant => {
                    const isCurrentUser = myContestantIds.has(contestant.id);

                    const isStrikethrough = isStruckThrough(contestant);

                    return (
                        <div
                            key={contestant.id}
                            className={`flex flex-col items-start sm:flex-row sm:justify-between sm:items-center text-sm p-2 rounded mb-1 ${
                                isCurrentUser ? 'bg-info text-info-content font-bold' : 'bg-base-100'
                            } ${isStrikethrough ? 'line-through opacity-30' : ''}`}
                        >
                            <span>
                                {contestant.team.crew.member1.first_name} {contestant.team.crew.member1.last_name}
                                {contestant.team.crew.member2 && ` & ${contestant.team.crew.member2.first_name} ${contestant.team.crew.member2.last_name}`}
                                ({contestant.team.aeroplane.registration})
                            </span>
                            <span className="flex items-center gap-3">
                                {isCurrentUser && !isStrikethrough && (
                                    <span>Rank {ranked.findIndex(entry => entry.id === contestant.id) + 1} of {ranked.length}</span>
                                )}
                                {isCurrentUser && contestId !== undefined && navigationTaskId !== undefined && (
                                    <a
                                        href={generatePath('COMPETITION_MAP_DETAIL', { contestId, navigationTaskId })}
                                        className="link"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                    >
                                        Replay track
                                    </a>
                                )}
                                {!isStrikethrough && hasSummaryButton(summarisable, contestant.id) && (
                                    <FlightSummaryButton contestantId={contestant.id} />
                                )}
                                {didNotFly(task, contestant.contestanttrack) ? (
                                    <span title={DNF_TITLE}>Score: {DNF_LABEL} (0)</span>
                                ) : (
                                    <span title={scoreArithmetic(task, contestant.contestanttrack, tracks)?.text}>
                                        Score: {formatScoreOutOf(contestant.contestanttrack.score, task)}
                                    </span>
                                )}
                            </span>
                        </div>
                    );
                })}
        </div>
    );
};

export default TaskScoreDisplay;