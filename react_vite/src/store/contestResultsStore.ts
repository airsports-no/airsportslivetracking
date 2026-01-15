import { create } from 'zustand';

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
  // Add other properties as identified from reactjs/components/resultsService/contestRankTable.js and backend data
  // Example:
  score: number;
  tests?: Test[]; // Tasks can have nested tests
}

export interface Test {
  id: number;
  name: string;
  score: number;
  // Add other properties
}

export interface ContestTeam {
  id: number;
  name: string;
  // Add other properties
}

export interface ContestResultsState {
  contestId: number | null;
  results: {
    summary_score_sorting_direction: string;
    contestsummary_set: ContestSummary[];
    task_set: Task[];
    contest_teams: ContestTeam[];
    permission_change_contest: boolean;
    // Potentially other top-level properties from the backend results API
  } | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  setContestId: (id: number) => void;
  setResults: (results: ContestResultsState['results']) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useContestResultsStore = create<ContestResultsState>((set) => ({
  contestId: null,
  results: null,
  loading: false,
  error: null,

  setContestId: (id) => set({ contestId: id }),
  setResults: (results) => set({ results }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}));
