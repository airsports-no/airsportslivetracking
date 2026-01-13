import React from 'react';
import { NavigationTask } from '../types';

interface TaskScoreDisplayProps {
    task: NavigationTask;
    currentUserEmail: string;
}

const TaskScoreDisplay: React.FC<TaskScoreDisplayProps> = ({ task, currentUserEmail }) => {
    if (!task.contestant_set || task.contestant_set.length === 0) {
        return <p>No scores recorded for this task yet.</p>;
    }

    return (
        <div className="mt-4 pt-2 bg-base-100 p-2 rounded-lg">
            <h5 className="font-semibold text-md mb-2">Scores for {task.name}:</h5>
            {task.contestant_set
                .sort((a, b) => {
                    const scoreA = a.contestanttrack.score;
                    const scoreB = b.contestanttrack.score;

                    if (task.score_sorting_direction === 'desc') {
                        return scoreB - scoreA;
                    } else {
                        return scoreA - scoreB;
                    }
                })
                .map(contestant => {
                    const isCurrentUser =
                        currentUserEmail &&
                        (contestant.team.crew.member1?.email === currentUserEmail ||
                            contestant.team.crew.member2?.email === currentUserEmail);

                    const isStrikethrough =
                        (contestant.contestanttrack.calculator_started === false && contestant.contestanttrack.score === 0) ||
                        (contestant.contestanttrack.current_state === "Waiting...");

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
                            <span>Score: {contestant.contestanttrack.score.toFixed(0)}</span>
                        </div>
                    );
                })}
        </div>
    );
};

export default TaskScoreDisplay;
