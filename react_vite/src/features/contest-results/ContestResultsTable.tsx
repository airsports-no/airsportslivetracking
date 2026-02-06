import React, { useEffect, useMemo, useState } from 'react';
import { ColumnDef, createColumnHelper } from '@tanstack/react-table';
import { DataTable } from '../../components/common/DataTable/DataTable';
import { useContestResultsWebSocket } from '../../hooks/useContestResultsWebSocket';
import { ContestSummary, Task } from '../../store/contestResultsStore';
import { useContestResultsStore } from '../../store/contestResultsStore';
import { EditableCell } from '../../components/common/DataTable/EditableCell';
import { useScoreUpdates } from '../../hooks/useScoreUpdates';
import { TaskModal } from './TaskModal';
import { TestModal } from './TestModal';
import { PencilIcon, Trash2Icon, ChevronLeftIcon, ChevronRightIcon, ChevronDownIcon, PlusCircleIcon, DownloadIcon } from 'lucide-react';
import { useParams } from 'react-router-dom';
import { reverse } from '../../urls';
import { Test } from '../../store/contestResultsStore';
import { fetchContest } from '../mission-dashboard/api';
import { Contest } from '../mission-dashboard/types';

const teamRankingTable = (team: any) => {
  if (!team) return 'N/A';
  let crewNames = '';
  if (team.crew && team.crew.member1) {
    crewNames += team.crew.member1.first_name + ' ' + team.crew.member1.last_name;
  }
  if (team.crew && team.crew.member2) {
    crewNames += ' / ' + team.crew.member2.first_name + ' ' + team.crew.member2.last_name;
  }
  return crewNames;
};

interface ContestResultsTableProps {
}

const columnHelper = createColumnHelper<ContestSummary & { [key: string]: any }>(); // Extend ContestSummary for dynamic task scores

export const ContestResultsTable: React.FC<ContestResultsTableProps> = () => {
  const params = useParams<{ contestId: string }>();
  const contestId = params.contestId ? parseInt(params.contestId, 10) : undefined;

  const results = useContestResultsStore((state) => state.results);
  const loading = useContestResultsStore((state) => state.loading);
  const error = useContestResultsStore((state) => state.error);
  const fetchResults = useContestResultsStore((state) => state.fetchResults);
  const createOrUpdateTask = useContestResultsStore((state) => state.createOrUpdateTask);
  const createOrUpdateTest = useContestResultsStore((state) => state.createOrUpdateTest);
  const deleteTask = useContestResultsStore((state) => state.deleteTask);
  const deleteTest = useContestResultsStore((state) => state.deleteTest);
  const deleteTeamResults = useContestResultsStore((state) => state.deleteTeamResults);

  const [isTaskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [isTestModalOpen, setTestModalOpen] = useState(false);
  const [editingTest, setEditingTest] = useState<Test | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Record<number, boolean>>({});
  const [contest, setContest] = useState<Contest | null>(null);

  useEffect(() => {
    if (contestId) {
      fetchResults(contestId);
      fetchContest(contestId).then(setContest);
    }
  }, [contestId, fetchResults]);

  useContestResultsWebSocket(contestId); // Listen for real-time updates
  const { updateContestSummary, updateTaskSummary, updateTestResult } = useScoreUpdates(); // Use the new hook

  const initialSorting = useMemo(() => {
    if (!results) return [];
    return [{ id: 'contestSummary', desc: results.summary_score_sorting_direction?.toUpperCase() === 'DESC' }];
  }, [results]);

  const handleNewTask = () => {
    setEditingTask(null);
    setTaskModalOpen(true);
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    setTaskModalOpen(true);
  };

  const handleNewTest = (task: Task) => {
    setEditingTest(null);
    setEditingTask(task); // We need to know which task to add the test to
    setTestModalOpen(true);
  };

  const handleEditTest = (test: Test, task: Task) => {
    setEditingTest(test);
    setEditingTask(task);
    setTestModalOpen(true);
  };

  const handleDeleteTask = async (taskId: number) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      await deleteTask(contestId, taskId);
    }
  };

  const handleDeleteTest = async (testId: number) => {
    if (window.confirm('Are you sure you want to delete this test?')) {
      await deleteTest(contestId, testId);
    }
  };

  const handleDeleteTeamResults = async (teamId: number) => {
    if (window.confirm('Are you sure you want to delete this team results?')) {
      await deleteTeamResults(contestId, teamId);
    }
  };

  const handleMoveTask = async (task: Task, direction: 'left' | 'right') => {
    if (!results) return;
    const tasks = (results.task_set || []).sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));
    const currentIndex = tasks.findIndex((t) => t.id === task.id);

    if (direction === 'left' && currentIndex > 0) {
      const otherTask = tasks[currentIndex - 1];
      const taskA = { ...task, index: task.index - 1 };
      const taskB = { ...otherTask, index: otherTask.index + 1 };
      await Promise.all([createOrUpdateTask(contestId, taskA), createOrUpdateTask(contestId, taskB)]);
    } else if (direction === 'right' && currentIndex < tasks.length - 1) {
      const otherTask = tasks[currentIndex + 1];
      const taskA = { ...task, index: task.index + 1 };
      const taskB = { ...otherTask, index: otherTask.index - 1 };
      await Promise.all([createOrUpdateTask(contestId, taskA), createOrUpdateTask(contestId, taskB)]);
    }
  };

  const handleMoveTest = async (test: Test, task: Task, direction: 'left' | 'right') => {
    if (!task.tasktest_set) return;
    const tests = [...task.tasktest_set].sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));
    const currentIndex = tests.findIndex((t) => t.id === test.id);

    if (direction === 'left' && currentIndex > 0) {
      const otherTest = tests[currentIndex - 1];
      const testA = { ...test, index: test.index - 1 };
      const testB = { ...otherTest, index: otherTest.index + 1 };
      await Promise.all([
        createOrUpdateTest(contestId, task.id, testA),
        createOrUpdateTest(contestId, task.id, testB)
      ]);
    } else if (direction === 'right' && currentIndex < tests.length - 1) {
      const otherTest = tests[currentIndex + 1];
      const testA = { ...test, index: test.index + 1 };
      const testB = { ...otherTest, index: otherTest.index - 1 };
      await Promise.all([
        createOrUpdateTest(contestId, task.id, testA),
        createOrUpdateTest(contestId, task.id, testB)
      ]);
    }
  };

  const handleToggleTask = (taskId: number) => {
    setExpandedTasks((prev) => {
      const isCurrentlyExpanded = prev[taskId];
      return isCurrentlyExpanded ? {} : { [taskId]: true };
    });
  };

  const handleTaskSubmit = async (task: Task) => {
    await createOrUpdateTask(contestId, task);
    setTaskModalOpen(false);
  };

  const handleTestSubmit = async (test: Test) => {
    await createOrUpdateTest(contestId, editingTask.id, test);
    setTestModalOpen(false);
  };

  const updateMyData = async (rowIndex: number, columnId: string, value: any) => {
    if (!results || !results.permission_change_contest) return;

    const row = data[rowIndex];
    const teamId = row.team.id;

    if (columnId === 'contestSummary') {
      await updateContestSummary(contestId, teamId, value);
    } else if (columnId.startsWith('task_')) {
      const taskId = parseInt(columnId.replace('task_', ''));
      await updateTaskSummary(contestId, teamId, taskId, value);
    } else if (columnId.startsWith('test-')) {
      const testId = parseInt(columnId.replace('test-', ''));
      await updateTestResult(contestId, teamId, testId, value);
    }
    fetchResults(contestId);
  };

  const columns = useMemo<ColumnDef<ContestSummary & { [key: string]: any }>[]>(() => {
    if (!results) return [];

    const baseColumns: ColumnDef<ContestSummary & { [key: string]: any }>[] = [
      columnHelper.accessor('rank', {
        header: '#',
        cell: (info) => <span className="align-middle">{info.getValue()}</span>,
        enableSorting: false,
      }),
      columnHelper.accessor('team', {
        header: 'CREW',
        cell: (info) => (
          <div className="flex items-center gap-2">
            <span className="align-middle crew-name">{teamRankingTable(info.getValue())}</span>
            {results.permission_change_contest && info.row.original.team?.id && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteTeamResults(info.row.original.team.id);
                }}
                className="btn btn-xs btn-ghost"
                title="Delete team results"
              >
                <Trash2Icon size={12} />
              </button>
            )}
          </div>
        ),
        enableSorting: false,
      }),
      columnHelper.accessor('contestSummary', {
        header: () => (
          <div className="flex items-center gap-2">
            <span>Σ</span>
            {results.permission_change_contest && (
              <button
                onClick={handleNewTask}
                className="btn btn-xs btn-ghost"
                title="Add new task"
              >
                <PlusCircleIcon size={12} />
              </button>
            )}
          </div>
        ),
        enableSorting: true,
        sortDescFirst: results.summary_score_sorting_direction?.toUpperCase() === 'DESC',
        cell: results.permission_change_contest && !results.autosum_scores ? EditableCell : (info) => info.getValue(),
        meta: {
          fixedSortDirection: results.summary_score_sorting_direction,
        },
      }),
    ];

    const expandedTaskId = Object.keys(expandedTasks).find((id) => expandedTasks[id]);
    const tasksToRender = expandedTaskId
        ? (results.task_set || []).filter((task) => task.id === parseInt(expandedTaskId))
        : (results.task_set || []).sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));

    tasksToRender.forEach((task, index) => {
      // Add columns for tests within the task if expanded
      if (expandedTasks[task.id]) {
        const tests = (task.tasktest_set || []).sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));
        tests.forEach((test, testIndex) => {
          const testDataField = `test_${test.id.toFixed(0)}`;
          baseColumns.push(
            columnHelper.accessor(testDataField, {
              header: () => (
                <div className="flex flex-col items-center gap-1">
                  <span className="px-2 py-1 text-sm bg-base-200 text-base-content font-normal rounded-md">{test.heading}</span>
                  {results.permission_change_contest && (
                    <div className="flex items-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMoveTest(test, task, 'left');
                        }}
                        className="btn btn-xs btn-ghost"
                        disabled={testIndex === 0}
                        title="Move test left"
                      >
                        <ChevronLeftIcon size={12} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMoveTest(test, task, 'right');
                        }}
                        className="btn btn-xs btn-ghost"
                        disabled={testIndex === tests.length - 1}
                        title="Move test right"
                      >
                        <ChevronRightIcon size={12} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleEditTest(test, task);
                        }}
                        className="btn btn-xs btn-ghost"
                        title="Edit test"
                      >
                        <PencilIcon size={12} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteTest(test.id);
                        }}
                        className="btn btn-xs btn-ghost"
                        title="Delete test"
                      >
                        <Trash2Icon size={12} />
                      </button>
                    </div>
                  )}
                </div>
              ),
              id: `test-${test.id}`,
              enableSorting: true,
              sortDescFirst: test.sorting?.toUpperCase() === 'DESC',
              cell: results.permission_change_contest && test.navigation_task === null ? EditableCell : (info) => info.getValue(),
              meta: {
                columnType: 'test',
                testId: test.id,
                fixedSortDirection: test.sorting,
              },
            }),
          );
        });
      }

      const dataField = `task_${task.id.toFixed(0)}`;
      baseColumns.push(
        columnHelper.accessor(dataField, {
          header: () => (
            <div className="flex flex-col items-center gap-1">
              <div
                className="flex items-center gap-2 cursor-pointer bg-primary text-primary-content hover:bg-primary-focus px-2 py-1 rounded-md font-semibold"
                onClick={(e) => {
                  e.stopPropagation();
                  handleToggleTask(task.id);
                }}
              >
                <ChevronDownIcon
                  size={16}
                  className={`transition-transform duration-200 ${expandedTasks[task.id] ? 'rotate-180' : ''}`}
                />
                <span>
                  {task.heading} {expandedTasks[task.id] ? '(Σ)' : ''}
                </span>
              </div>
              {results.permission_change_contest && (
                <div className="flex items-center gap-1">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMoveTask(task, 'left');
                    }}
                    className="btn btn-xs btn-ghost"
                    disabled={index === 0}
                    title="Move task left"
                  >
                    <ChevronLeftIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMoveTask(task, 'right');
                    }}
                    className="btn btn-xs btn-ghost"
                    disabled={index === tasksToRender.length - 1}
                    title="Move task right"
                  >
                    <ChevronRightIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditTask(task);
                    }}
                    className="btn btn-xs btn-ghost"
                    title="Edit task"
                  >
                    <PencilIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteTask(task.id);
                    }}
                    className="btn btn-xs btn-ghost"
                    title="Delete task"
                  >
                    <Trash2Icon size={12} />
                  </button>
                  {expandedTasks[task.id] && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleNewTest(task);
                    }}
                    className="btn btn-xs btn-ghost"
                    title="Add new test"
                  >
                    <PlusCircleIcon size={12} />
                  </button>
                  )}
                </div>
              )}
            </div>
          ),
          id: `task-${task.id}`,
          enableSorting: true,
          sortDescFirst: task.summary_score_sorting_direction?.toUpperCase() === 'DESC',
          cell: results.permission_change_contest && !task.autosum_scores ? EditableCell : (info) => info.getValue(),
          meta: {
            columnType: 'task',
            taskId: task.id,
            sortDirection: task.summary_score_sorting_direction,
            fixedSortDirection: task.summary_score_sorting_direction,
          },
        }),
      );
    });

    return baseColumns;
  }, [results, contestId, expandedTasks]);

  const data = useMemo(() => {
    if (!results) return [];

    const transformedData: (ContestSummary & { [key: string]: any })[] = [];
    const ranks = new Map<number, number>();

    const sortedSummaries = [...(results.contestsummary_set || [])].sort((a, b) => {
      return (a.points || 0) - (b.points || 0);
    });
    sortedSummaries.forEach((summary, index) => {
      if (summary.team?.id) {
        ranks.set(summary.team.id, index + 1);
      }
    });

    // Build initial transformedData based on contestsummary_set
    (results.contestsummary_set || []).forEach((summary) => {
      const teamId = summary.team?.id;
      if (teamId) {
        const initialData: any = {
          id: teamId,
          team: summary.team, // Use the team object from contest summary
          rank: ranks.get(teamId) || '-',
          contestSummary: summary.points,
        };

        // Initialize task and test columns to '-' for this team
        (results.task_set || []).forEach((task) => {
          initialData[`task_${task.id.toFixed(0)}`] = '-';
          (task.tasktest_set || []).forEach((test) => {
            initialData[`test_${test.id.toFixed(0)}`] = '-';
          });
        });
        transformedData.push(initialData);
      }
    });

    (results.contestsummary_set || []).forEach((summary) => {
      const teamId = summary.team?.id;
      if (teamId) {
        const existingEntry = transformedData.find((d) => d.id === teamId);
        if (existingEntry) {
          existingEntry.contestSummary = summary.points;
        }
      }
    });

    (results.task_set || []).forEach((task) => {
      (task.tasksummary_set || []).forEach((taskSummary: any) => {
        const teamId = taskSummary.team;
        if (teamId) {
          const existingEntry = transformedData.find((d) => d.id === teamId);
          if (existingEntry) {
            existingEntry[`task_${task.id.toFixed(0)}`] = taskSummary.points;
          }
        }
      });
      (task.tasktest_set || []).forEach((test) => {
        (test.teamtestscore_set || []).forEach((score: any) => {
          const teamId = score.team;
          if (teamId) {
            const existingEntry = transformedData.find((d) => d.id === teamId);
            if (existingEntry) {
              existingEntry[`test_${test.id.toFixed(0)}`] = score.points;
            }
          }
        });
      });
    });

    return transformedData;
  }, [results]);

  if (loading) return <div>Loading Contest Results...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!results) return <div>No Contest Results available.</div>;

  return (
    <div>
      <div className="mb-8">
        {(contest?.header_image || contest?.logo) && (
          <img
            src={contest.header_image || contest.logo}
            alt={`${results.name} Header`}
            className="w-full h-64 object-cover rounded-lg mb-4"
          />
        )}
        <div className="flex items-center justify-between mb-4">
          <div className="flex-1" />
          <h2 className="text-2xl font-bold text-center">{results.name}</h2>
          <div className="flex-1 flex justify-end">
            <a
              href={reverse('contests-results-csv', contestId)}
              className="btn btn-sm btn-outline gap-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              <DownloadIcon size={16} />
              Export CSV
            </a>
          </div>
        </div>
      </div>
      <DataTable
        columns={columns}
        data={data}
        className="table table-zebra table-pin-rows table-pin-cols"
        updateMyData={updateMyData}
        initialSorting={initialSorting}
      />
      <TaskModal
        show={isTaskModalOpen}
        onClose={() => setTaskModalOpen(false)}
        onSubmit={handleTaskSubmit}
        task={editingTask}
      />
      <TestModal
        show={isTestModalOpen}
        onClose={() => setTestModalOpen(false)}
        onSubmit={handleTestSubmit}
        test={editingTest}
        task={editingTask}
      />
    </div>
  );
};
