import { useCallback } from 'react';
import { reverse } from '../urls';
import { getCookie } from '../utils/csrf';

interface ScoreUpdatePayload {
  team: number;
  points: number;
  task?: number; // For task summaries
  task_test?: number; // For test results
}

export const useScoreUpdates = () => {
  const updateContestSummary = useCallback(async (contestId: number, teamId: number, points: number) => {
    const url = reverse('contests-update-contest-summary',contestId);
    const payload: ScoreUpdatePayload = { team: teamId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!,
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
  }, []);

  const updateTaskSummary = useCallback(async (contestId: number, teamId: number, taskId: number, points: number) => {
    const url = reverse('contests-update-task-summary', contestId);
    const payload: ScoreUpdatePayload = { team: teamId, task: taskId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!,
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
  }, []);

  const updateTestResult = useCallback(async (contestId: number, teamId: number, taskTestId: number, points: number) => {
    const url = reverse('contests-update-test-result', contestId);
    const payload: ScoreUpdatePayload = { team: teamId, task_test: taskTestId, points: points };
    try {
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!,
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
  }, []);

  return { updateContestSummary, updateTaskSummary, updateTestResult };
};
