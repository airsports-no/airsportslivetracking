import { create } from 'zustand';
import { reverse } from '../urls';
import { getCookie } from '../utils/csrf';

export interface ContestSummary {
  id: number;
  team_name: string;
  total_score: number;
  rank: number;
  [key: string]: any;
}

export interface TeamTestScore {
  id: number;
  team: number;
  task_test: number;
  points: number;
  [key: string]: any;
}

export interface TaskSummaryEntry {
  id: number;
  team: number;
  task: number;
  points: number;
  [key: string]: any;
}

export interface Task {
  id: number;
  name: string;
  heading: string;
  weight: number;
  autosum_scores: boolean;
  summary_score_sorting_direction: string;
  index: number;
  tasksummary_set: TaskSummaryEntry[];
  tasktest_set: Test[];
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
  teamtestscore_set: TeamTestScore[];
}

export interface ContestTeam {
  id: number;
  name: string;
}

export interface ContestResults {
  summary_score_sorting_direction: string;
  autosum_scores?: boolean;
  contestsummary_set: ContestSummary[];
  task_set: Task[];
  contest_teams: ContestTeam[];
  permission_change_contest: boolean;
  name: string;
  [key: string]: any;
}

export interface ScoreUpdateMessage {
  type: 'score.update';
  test_score: TeamTestScore | null;
  task_summary: TaskSummaryEntry | null;
  contest_summary: ContestSummary | null;
  task_test_id?: number;
  team_id?: number;
}

export interface ContestResultsState {
  contestId: number | null;
  results: ContestResults | null;
  loading: boolean;
  error: string | null;

  fetchResults: (id: number) => Promise<void>;
  setContestId: (id: number) => void;
  setResults: (results: ContestResultsState['results']) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  applyRealtimeMessage: (message: any) => void;
  createOrUpdateTask: (contestId: number, task: Task) => Promise<void>;
  createOrUpdateTest: (contestId: number, taskId: number, test: Test) => Promise<void>;
  deleteTask: (contestId: number, taskId: number) => Promise<void>;
  deleteTest: (contestId: number, testId: number) => Promise<void>;
  deleteTeamResults: (contestId: number, teamId: number) => Promise<void>;
}

const upsertById = <T extends { id: number }>(items: T[], item: T): T[] => {
  const index = items.findIndex((entry) => entry.id === item.id);
  if (index === -1) {
    return [...items, item];
  }

  const next = [...items];
  next[index] = item;
  return next;
};

const mergeTaskWithExistingCollections = (incomingTask: any, existingTask?: Task): Task => ({
  ...(existingTask || {}),
  ...incomingTask,
  tasksummary_set: existingTask?.tasksummary_set || [],
  tasktest_set: existingTask?.tasktest_set || [],
});

const mergeContestSummaryUpdate = (
  existingSummaries: ContestSummary[],
  incomingSummary: ContestSummary,
): ContestSummary[] => {
  const existingSummary = existingSummaries.find((summary) => summary.id === incomingSummary.id);

  if (!existingSummary) {
    return upsertById(existingSummaries, incomingSummary);
  }

  return upsertById(existingSummaries, {
    ...existingSummary,
    ...incomingSummary,
    team: typeof incomingSummary.team === 'object' ? incomingSummary.team : existingSummary.team,
  });
};

const applyTasksUpdate = (results: ContestResults, tasks: any[]): ContestResults => {
  const existingTasks = new Map((results.task_set || []).map((task) => [task.id, task]));
  return {
    ...results,
    task_set: tasks
      .map((task) => mergeTaskWithExistingCollections(task, existingTasks.get(task.id)))
      .sort((a, b) => (a.index || 0) - (b.index || 0)),
  };
};

const applyTestsUpdate = (results: ContestResults, tests: any[]): ContestResults => {
  const testsByTask = new Map<number, any[]>();
  tests.forEach((test) => {
    const taskTests = testsByTask.get(test.task) || [];
    taskTests.push(test);
    testsByTask.set(test.task, taskTests);
  });

  return {
    ...results,
    task_set: (results.task_set || []).map((task) => {
      if (!testsByTask.has(task.id)) {
        return task;
      }

      const existingTests = new Map((task.tasktest_set || []).map((test) => [test.id, test]));
      const nextTests = (testsByTask.get(task.id) || [])
        .map((test) => ({
          ...(existingTests.get(test.id) || {}),
          ...test,
          teamtestscore_set: existingTests.get(test.id)?.teamtestscore_set || [],
        }))
        .sort((a, b) => (a.index || 0) - (b.index || 0));

      return {
        ...task,
        tasktest_set: nextTests,
      };
    }),
  };
};

const applyTeamsUpdate = (results: ContestResults, teams: ContestTeam[]): ContestResults => ({
  ...results,
  contest_teams: teams,
});

const applyScoreUpdate = (results: ContestResults, message: ScoreUpdateMessage): ContestResults => {
  const nextResults: ContestResults = {
    ...results,
    contestsummary_set: [...(results.contestsummary_set || [])],
    task_set: (results.task_set || []).map((task) => ({
      ...task,
      tasksummary_set: [...(task.tasksummary_set || [])],
      tasktest_set: (task.tasktest_set || []).map((test) => ({
        ...test,
        teamtestscore_set: [...(test.teamtestscore_set || [])],
      })),
    })),
  };

  if (message.contest_summary) {
    nextResults.contestsummary_set = mergeContestSummaryUpdate(nextResults.contestsummary_set, message.contest_summary);
  }

  if (message.task_summary) {
    nextResults.task_set = nextResults.task_set.map((task) => {
      if (task.id !== message.task_summary?.task) {
        return task;
      }
      return {
        ...task,
        tasksummary_set: upsertById(task.tasksummary_set || [], message.task_summary),
      };
    });
  }

  if (message.test_score) {
    nextResults.task_set = nextResults.task_set.map((task) => ({
      ...task,
      tasktest_set: (task.tasktest_set || []).map((test) => {
        if (test.id !== message.test_score?.task_test) {
          return test;
        }
        return {
          ...test,
          teamtestscore_set: upsertById(test.teamtestscore_set || [], message.test_score),
        };
      }),
    }));
  }

  return nextResults;
};

export const useContestResultsStore = create<ContestResultsState>((set, get) => ({
  contestId: null,
  results: null,
  loading: false,
  error: null,

  setContestId: (id) => set({ contestId: id }),
  setResults: (results) => set({ results }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  applyRealtimeMessage: (message) => {
    if (!message || typeof message !== 'object') {
      return;
    }

    if (message.type === 'contest.results' && message.results) {
      const currentResults = get().results;
      set({
        results: {
          ...message.results,
          permission_change_contest: currentResults?.permission_change_contest ?? message.results.permission_change_contest,
        },
      });
      return;
    }

    const currentResults = get().results;
    if (!currentResults) {
      return;
    }

    if (message.type === 'contest.tasks' && Array.isArray(message.tasks)) {
      set({ results: applyTasksUpdate(currentResults, message.tasks) });
      return;
    }

    if (message.type === 'contest.tests' && Array.isArray(message.tests)) {
      set({ results: applyTestsUpdate(currentResults, message.tests) });
      return;
    }

    if (message.type === 'contest.teams' && Array.isArray(message.teams)) {
      set({ results: applyTeamsUpdate(currentResults, message.teams) });
      return;
    }

    if (message.type === 'score.update') {
      set({ results: applyScoreUpdate(currentResults, message as ScoreUpdateMessage) });
    }
  },

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
      console.error('Error fetching results:', error);
      set({ error: error.message, loading: false });
    }
  },

  createOrUpdateTask: async (contestId: number, task: Task) => {
    const url = task.id ? reverse('tasks-detail', contestId, task.id) : reverse('tasks-list', contestId);
    const method = task.id ? 'PUT' : 'POST';
    const payload: Partial<Task> = { ...task };
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
    } catch (error: any) {
      console.error('Error creating/updating task:', error);
      set({ error: error.message });
    }
  },

  createOrUpdateTest: async (contestId: number, taskId: number, test: Test) => {
    const url = test.id ? reverse('tasktests-detail', contestId, test.id) : reverse('tasktests-list', contestId);
    const method = test.id ? 'PUT' : 'POST';
    const payload: Partial<Test> = { ...test };
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
    } catch (error: any) {
      console.error('Error creating/updating test:', error);
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
    } catch (error: any) {
      console.error('Error deleting task:', error);
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
    } catch (error: any) {
      console.error('Error deleting test:', error);
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
    } catch (error: any) {
      console.error('Error deleting team results:', error);
      set({ error: error.message });
    }
  },
}));
