import { useCallback } from 'react';
import { useFrontendContext } from './useFrontendContext';

interface ScoreUpdatePayload {
  team: number;
  points: number;
  task?: number; // For task summaries
  task_test?: number; // For test results
}

export const useScoreUpdates = () => {
  const { context } = useFrontendContext();

  const updateContestSummary = useCallback(async (contestId: number, teamId: number, points: number) => {
    if (!context || !context.urls.contests_update_contest_summary) {
      console.error('Frontend context or contestUpdateContestSummaryUrl not available.');
      return;
    }
    const url = context.urls.contests_update_contest_summary(contestId);
    const payload: ScoreUpdatePayload = { team: teamId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          // You might need to include a CSRF token here depending on your Django setup
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      console.log('Contest summary updated successfully.');
    } catch (error) {
      console.error('Failed to update contest summary:', error);
      throw error;
    }
  }, [context]);

  const updateTaskSummary = useCallback(async (contestId: number, teamId: number, taskId: number, points: number) => {
    if (!context || !context.urls.contests_update_task_summary) {
      console.error('Frontend context or contestUpdateTaskSummaryUrl not available.');
      return;
    }
    const url = context.urls.contests_update_task_summary(contestId);
    const payload: ScoreUpdatePayload = { team: teamId, task: taskId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      console.log('Task summary updated successfully.');
    } catch (error) {
      console.error('Failed to update task summary:', error);
      throw error;
    }
  }, [context]);

  const updateTestResult = useCallback(async (contestId: number, teamId: number, taskTestId: number, points: number) => {
    if (!context || !context.urls.contests_update_test_result) {
      console.error('Frontend context or contestUpdateTestResultUrl not available.');
      return;
    }
    const url = context.urls.contests_update_test_result(contestId);
    const payload: ScoreUpdatePayload = { team: teamId, task_test: taskTestId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      console.log('Test result updated successfully.');
    } catch (error) {
      console.error('Failed to update test result:', error);
      throw error;
    }
  }, [context]);

  return { updateContestSummary, updateTaskSummary, updateTestResult };
};
