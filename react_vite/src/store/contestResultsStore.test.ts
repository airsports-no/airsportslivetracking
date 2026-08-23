import {
  upsertById,
  mergeTaskWithExistingCollections,
  mergeContestSummaryUpdate,
  applyTasksUpdate,
  applyTestsUpdate,
  applyTeamsUpdate,
  applyScoreUpdate,
  useContestResultsStore,
  type ContestResults,
  type ContestSummary,
  type Task,
  type Test,
} from './contestResultsStore';

describe('upsertById', () => {
  it('appends a new item when no existing item shares its id', () => {
    const items = [{ id: 1, value: 'a' }];
    expect(upsertById(items, { id: 2, value: 'b' })).toEqual([{ id: 1, value: 'a' }, { id: 2, value: 'b' }]);
  });

  it('replaces the matching item in place, preserving order', () => {
    const items = [{ id: 1, value: 'a' }, { id: 2, value: 'b' }];
    expect(upsertById(items, { id: 1, value: 'z' })).toEqual([{ id: 1, value: 'z' }, { id: 2, value: 'b' }]);
  });
});

describe('mergeTaskWithExistingCollections', () => {
  it('keeps the existing tasksummary_set/tasktest_set when merging in an incoming task update', () => {
    const existingTask = { id: 1, name: 'Old', tasksummary_set: [{ id: 9 }], tasktest_set: [{ id: 8 }] } as unknown as Task;
    const incomingTask = { id: 1, name: 'New' };
    const result = mergeTaskWithExistingCollections(incomingTask, existingTask);
    expect(result.name).toBe('New');
    expect(result.tasksummary_set).toEqual([{ id: 9 }]);
    expect(result.tasktest_set).toEqual([{ id: 8 }]);
  });

  it('defaults to empty collections when there is no existing task', () => {
    const result = mergeTaskWithExistingCollections({ id: 1, name: 'New' }, undefined);
    expect(result.tasksummary_set).toEqual([]);
    expect(result.tasktest_set).toEqual([]);
  });
});

describe('mergeContestSummaryUpdate', () => {
  it('inserts a summary that has no existing counterpart', () => {
    const result = mergeContestSummaryUpdate([], { id: 1, team_name: 'A', total_score: 10, rank: 1 });
    expect(result).toEqual([{ id: 1, team_name: 'A', total_score: 10, rank: 1 }]);
  });

  it('merges fields onto the existing summary, keeping the existing team object when the incoming team is not an object', () => {
    const existing: ContestSummary = { id: 1, team_name: 'A', total_score: 10, rank: 2, team: { id: 5, name: 'Team A' } };
    const incoming = { id: 1, team_name: 'A', total_score: 20, rank: 1, team: 5 } as unknown as ContestSummary;
    const result = mergeContestSummaryUpdate([existing], incoming);
    expect(result[0].total_score).toBe(20);
    expect(result[0].rank).toBe(1);
    expect(result[0].team).toEqual({ id: 5, name: 'Team A' });
  });

  it('takes the incoming team object when it is provided as an object', () => {
    const existing: ContestSummary = { id: 1, team_name: 'A', total_score: 10, rank: 2, team: { id: 5, name: 'Old' } };
    const incoming = { id: 1, team_name: 'A', total_score: 20, rank: 1, team: { id: 5, name: 'New' } };
    const result = mergeContestSummaryUpdate([existing], incoming);
    expect(result[0].team).toEqual({ id: 5, name: 'New' });
  });
});

describe('applyTasksUpdate', () => {
  it('sorts incoming tasks by index and preserves each task\'s existing summary/test collections', () => {
    const results = {
      task_set: [{ id: 1, tasksummary_set: [{ id: 100 }], tasktest_set: [] }],
    } as unknown as ContestResults;
    const incoming = [
      { id: 2, name: 'Second', index: 1 },
      { id: 1, name: 'First', index: 0 },
    ];
    const updated = applyTasksUpdate(results, incoming);
    expect(updated.task_set.map((t) => t.id)).toEqual([1, 2]);
    expect(updated.task_set[0].tasksummary_set).toEqual([{ id: 100 }]);
  });
});

describe('applyTestsUpdate', () => {
  it('attaches incoming tests to the matching task, sorted by index, preserving each test\'s teamtestscore_set', () => {
    const results = {
      task_set: [
        { id: 1, tasktest_set: [{ id: 10, teamtestscore_set: [{ id: 500 }] }] },
        { id: 2, tasktest_set: [] },
      ],
    } as unknown as ContestResults;
    const incoming = [
      { id: 11, task: 1, index: 1 },
      { id: 10, task: 1, index: 0 },
    ];
    const updated = applyTestsUpdate(results, incoming);
    const task1 = updated.task_set.find((t) => t.id === 1)!;
    expect(task1.tasktest_set.map((t: Test) => t.id)).toEqual([10, 11]);
    expect(task1.tasktest_set[0].teamtestscore_set).toEqual([{ id: 500 }]);
    // Task 2 has no incoming tests, so it is left untouched.
    const task2 = updated.task_set.find((t) => t.id === 2)!;
    expect(task2.tasktest_set).toEqual([]);
  });
});

describe('applyTeamsUpdate', () => {
  it('replaces contest_teams wholesale', () => {
    const results = { contest_teams: [{ id: 1, name: 'Old' }] } as unknown as ContestResults;
    const updated = applyTeamsUpdate(results, [{ id: 2, name: 'New' }]);
    expect(updated.contest_teams).toEqual([{ id: 2, name: 'New' }]);
  });
});

describe('applyScoreUpdate', () => {
  const baseResults = (): ContestResults => ({
    summary_score_sorting_direction: 'ascending',
    contestsummary_set: [{ id: 1, team_name: 'A', total_score: 0, rank: 1 }],
    task_set: [
      {
        id: 1,
        name: 'Task',
        heading: 'H',
        weight: 1,
        autosum_scores: true,
        summary_score_sorting_direction: 'ascending',
        index: 0,
        contest: 1,
        tasksummary_set: [{ id: 5, team: 1, task: 1, points: 0 }],
        tasktest_set: [
          { id: 10, name: 'Test', heading: 'H', weight: 1, sorting: 'ascending', index: 0, task: 1, navigation_task: null, navigation_task_link: null, teamtestscore_set: [{ id: 20, team: 1, task_test: 10, points: 0 }] },
        ],
      },
    ],
    contest_teams: [],
    permission_change_contest: false,
    name: 'Contest',
  });

  it('upserts a contest_summary update', () => {
    const updated = applyScoreUpdate(baseResults(), {
      type: 'score.update',
      contest_summary: { id: 1, team_name: 'A', total_score: 42, rank: 1 },
      test_score: null,
      task_summary: null,
    });
    expect(updated.contestsummary_set[0].total_score).toBe(42);
  });

  it('upserts a task_summary update into the matching task', () => {
    const updated = applyScoreUpdate(baseResults(), {
      type: 'score.update',
      contest_summary: null,
      test_score: null,
      task_summary: { id: 5, team: 1, task: 1, points: 77 },
    });
    expect(updated.task_set[0].tasksummary_set[0].points).toBe(77);
  });

  it('leaves other tasks\' tasksummary_set untouched when the task_summary targets a different task', () => {
    const results = baseResults();
    results.task_set.push({ ...results.task_set[0], id: 2, tasksummary_set: [{ id: 6, team: 1, task: 2, points: 0 }] });
    const updated = applyScoreUpdate(results, {
      type: 'score.update',
      contest_summary: null,
      test_score: null,
      task_summary: { id: 5, team: 1, task: 1, points: 77 },
    });
    const task2 = updated.task_set.find((t) => t.id === 2)!;
    expect(task2.tasksummary_set[0].points).toBe(0);
  });

  it('upserts a test_score update into the matching test across all tasks', () => {
    const updated = applyScoreUpdate(baseResults(), {
      type: 'score.update',
      contest_summary: null,
      task_summary: null,
      test_score: { id: 20, team: 1, task_test: 10, points: 99 },
    });
    expect(updated.task_set[0].tasktest_set[0].teamtestscore_set[0].points).toBe(99);
  });

  it('does not mutate the original results object (returns new nested arrays)', () => {
    const original = baseResults();
    const updated = applyScoreUpdate(original, {
      type: 'score.update',
      contest_summary: { id: 1, team_name: 'A', total_score: 42, rank: 1 },
      test_score: null,
      task_summary: null,
    });
    expect(original.contestsummary_set[0].total_score).toBe(0);
    expect(updated).not.toBe(original);
    expect(updated.task_set).not.toBe(original.task_set);
  });
});

describe('useContestResultsStore.applyRealtimeMessage', () => {
  beforeEach(() => {
    useContestResultsStore.setState({ contestId: null, results: null, loading: false, error: null });
  });

  it('ignores non-object messages', () => {
    const before = useContestResultsStore.getState().results;
    useContestResultsStore.getState().applyRealtimeMessage(null);
    useContestResultsStore.getState().applyRealtimeMessage('a string');
    expect(useContestResultsStore.getState().results).toBe(before);
  });

  it('sets results wholesale on contest.results, preserving the existing permission_change_contest when the incoming payload omits it', () => {
    useContestResultsStore.setState({
      results: { permission_change_contest: true } as unknown as ContestResults,
    });
    useContestResultsStore.getState().applyRealtimeMessage({
      type: 'contest.results',
      results: { name: 'Fresh', contestsummary_set: [], task_set: [], contest_teams: [] },
    });
    expect(useContestResultsStore.getState().results?.permission_change_contest).toBe(true);
    expect(useContestResultsStore.getState().results?.name).toBe('Fresh');
  });

  it('uses the incoming permission_change_contest only when there are no existing results to preserve it from', () => {
    // The `??` fallback only kicks in when currentResults is null/undefined
    // (e.g. first load) - once a value exists it always wins over the
    // incoming payload, even an explicit `false`, because `??` doesn't
    // fall through on a defined `false`.
    useContestResultsStore.setState({ results: null });
    useContestResultsStore.getState().applyRealtimeMessage({
      type: 'contest.results',
      results: { name: 'Fresh', permission_change_contest: false, contestsummary_set: [], task_set: [], contest_teams: [] },
    });
    expect(useContestResultsStore.getState().results?.permission_change_contest).toBe(false);
  });

  it('an existing permission_change_contest of true always wins over an incoming false (only null/undefined existing falls through)', () => {
    useContestResultsStore.setState({
      results: { permission_change_contest: true } as unknown as ContestResults,
    });
    useContestResultsStore.getState().applyRealtimeMessage({
      type: 'contest.results',
      results: { name: 'Fresh', permission_change_contest: false, contestsummary_set: [], task_set: [], contest_teams: [] },
    });
    expect(useContestResultsStore.getState().results?.permission_change_contest).toBe(true);
  });

  it('ignores contest.tasks/contest.tests/contest.teams/score.update messages when there are no results loaded yet', () => {
    useContestResultsStore.getState().applyRealtimeMessage({ type: 'contest.tasks', tasks: [{ id: 1 }] });
    expect(useContestResultsStore.getState().results).toBeNull();
  });

  it('routes contest.tasks to applyTasksUpdate once results exist', () => {
    useContestResultsStore.setState({
      results: { task_set: [], contestsummary_set: [], contest_teams: [], name: 'C', permission_change_contest: false, summary_score_sorting_direction: 'ascending' },
    });
    useContestResultsStore.getState().applyRealtimeMessage({ type: 'contest.tasks', tasks: [{ id: 1, index: 0 }] });
    expect(useContestResultsStore.getState().results?.task_set.map((t) => t.id)).toEqual([1]);
  });

  it('routes score.update to applyScoreUpdate once results exist', () => {
    useContestResultsStore.setState({
      results: {
        task_set: [],
        contestsummary_set: [{ id: 1, team_name: 'A', total_score: 0, rank: 1 }],
        contest_teams: [],
        name: 'C',
        permission_change_contest: false,
        summary_score_sorting_direction: 'ascending',
      },
    });
    useContestResultsStore.getState().applyRealtimeMessage({
      type: 'score.update',
      contest_summary: { id: 1, team_name: 'A', total_score: 55, rank: 1 },
      test_score: null,
      task_summary: null,
    });
    expect(useContestResultsStore.getState().results?.contestsummary_set[0].total_score).toBe(55);
  });
});
