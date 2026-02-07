import { create } from 'zustand';
import { reverse } from '../urls';
import { getCookie } from '../utils/csrf';

export interface ContestSummary {
  id: number;
  // Example:
  team_name: string;
  total_score: number;
  rank: number;
  [key: string]: any; // Allow for other dynamic properties
}

export interface Task {
  id: number;
  name: string;
  heading: string;
  weight: number;
  autosum_scores: boolean;
  summary_score_sorting_direction: string;
  index: number;
  tasksummary_set: any[]; // Define further if needed
  tasktest_set: Test[]; // This was task_set before
  contest: number;
}

export interface Test {
  id: number;
  name: string;
  heading: string;
  weight: number;
  sorting: string;
  index: number;
  task: number;
  navigation_task: number | null;
  navigation_task_link: string | null;
  teamtestscore_set: any[]; // Define further if needed
}

export interface ContestTeam {
  id: number;
  name: string;
  // Add other properties
}

export interface ContestResults {
  summary_score_sorting_direction: string;
  contestsummary_set: ContestSummary[];
  task_set: Task[];
  contest_teams: ContestTeam[];
  permission_change_contest: boolean;
  name: string;
  // Potentially other top-level properties from the backend results API
}

export interface ContestResultsState {
  contestId: number | null;
  results: ContestResults | null;
  loading: boolean;
  error: string | null;

  // Actions
  fetchResults: (id: number) => Promise<void>;
  setContestId: (id: number) => void;
  setResults: (results: ContestResultsState['results']) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  createOrUpdateTask: (contestId: number, task: Task) => Promise<void>;
  createOrUpdateTest: (contestId: number, taskId: number, test: Test) => Promise<void>;
  deleteTask: (contestId: number, taskId: number) => Promise<void>;
  deleteTest: (contestId: number, testId: number) => Promise<void>;
  deleteTeamResults: (contestId: number, teamId: number) => Promise<void>;
}

export const useContestResultsStore = create<ContestResultsState>((set, get) => ({
  contestId: null,
  results: null,
  loading: false,
  error: null,

  setContestId: (id) => set({ contestId: id }),
  setResults: (results) => set({ results }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  fetchResults: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const response = await fetch(reverse('contests-results-details', id));
      if (!response.ok) {
        throw new Error('Failed to fetch contest results');
      }
      const data = await response.json();
      set({ results: data, loading: false });
    } catch (error: any) {
      console.error("Error fetching results:", error);
      set({ error: error.message, loading: false });
    }
  },

  createOrUpdateTask: async (contestId: number, task: Task) => {
    const url = task.id
      ? reverse('tasks-detail', contestId, task.id)
      : reverse('tasks-list', contestId);
    const method = task.id ? 'PUT' : 'POST';
    const payload = { ...task };
    if (method === 'POST') {
      delete payload.id;
    }
    payload.contest = contestId;

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to save task');
      }
      // Refresh results to get the latest state
      await get().fetchResults(contestId);
    } catch (error: any) {
      console.error("Error creating/updating task:", error);
      set({ error: error.message });
    }
  },

  createOrUpdateTest: async (contestId: number, taskId: number, test: Test) => {
    const url = test.id
      ? reverse('tasktests-detail', contestId, test.id)
      : reverse('tasktests-list', contestId);
    const method = test.id ? 'PUT' : 'POST';
    const payload = { ...test };
    if (method === 'POST') {
      delete payload.id;
    }
    payload.task = taskId;

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCookie('csrftoken')!,
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Failed to save test');
      }
      // Refresh results to get the latest state
      await get().fetchResults(contestId);
    } catch (error: any) {
      console.error("Error creating/updating test:", error);
      set({ error: error.message });
    }
  },

  deleteTask: async (contestId: number, taskId: number) => {
    const url = reverse('tasks-detail', contestId, taskId);
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')!,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete task');
      }
      // Refresh results to get the latest state
      await get().fetchResults(contestId);
    } catch (error: any) {
      console.error("Error deleting task:", error);
      set({ error: error.message });
    }
  },

  deleteTest: async (contestId: number, testId: number) => {
    const url = reverse('tasktests-detail', contestId, testId);
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')!,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete test');
      }
      // Refresh results to get the latest state
      await get().fetchResults(contestId);
    } catch (error: any) {
      console.error("Error deleting test:", error);
      set({ error: error.message });
    }
  },

  deleteTeamResults: async (contestId: number, teamId: number) => {
    const url = reverse('contestteams-detail', contestId, teamId);
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCookie('csrftoken')!,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to delete team results');
      }
      // Refresh results to get the latest state
      await get().fetchResults(contestId);
    } catch (error: any) {
      console.error("Error deleting team results:", error);
      set({ error: error.message });
    }
  },
}));