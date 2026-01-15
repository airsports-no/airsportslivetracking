import { create } from 'zustand';
import { reverse } from '../urls';

// Define the interfaces for the data structures based on the reactjs analysis
export interface ContestSummary {
  id: number;
  // Add other properties as identified from reactjs/components/resultsService/contestRankTable.js and backend data
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
  deleteTask: (contestId: number, taskId: number) => Promise<void>;
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
      ? reverse('contests-tasks-update', contestId, task.id)
      : reverse('contests-tasks-create', contestId);
    const method = task.id ? 'PUT' : 'POST';

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          // You may need to add authentication headers (e.g., CSRF token) here
        },
        body: JSON.stringify(task),
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

  deleteTask: async (contestId: number, taskId: number) => {
    const url = reverse('contests-tasks-delete', contestId, taskId);
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          // You may need to add authentication headers (e.g., CSRF token) here
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

  deleteTeamResults: async (contestId: number, teamId: number) => {
    const url = reverse('contests-contestteams-delete', contestId, teamId);
    try {
      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          // You may need to add authentication headers (e.g., CSRF token) here
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