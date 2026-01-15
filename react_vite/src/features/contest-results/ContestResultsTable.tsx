import React, { useEffect, useMemo, useState } from 'react';
import { ColumnDef, createColumnHelper } from '@tanstack/react-table';
import { DataTable } from '../../components/common/DataTable/DataTable';
import { useContestResultsWebSocket } from '../../hooks/useContestResultsWebSocket';
import { ContestSummary, Task } from '../../store/contestResultsStore';
import { useContestResultsStore } from '../../store/contestResultsStore';
import { EditableCell } from '../../components/common/DataTable/EditableCell';
import { useScoreUpdates } from '../../hooks/useScoreUpdates';
import { TaskModal } from './TaskModal';
import { PencilIcon, Trash2Icon, ChevronLeftIcon, ChevronRightIcon } from 'lucide-react';
import { useParams } from 'react-router-dom';

// Helper function from original reactjs
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
  navigationTaskId?: number; // Used for highlighting tasks
}

const columnHelper = createColumnHelper<ContestSummary & { [key: string]: any }>(); // Extend ContestSummary for dynamic task scores

export const ContestResultsTable: React.FC<ContestResultsTableProps> = ({ navigationTaskId }) => {
  const params = useParams<{ contestId: string }>();
  const contestId = params.contestId ? parseInt(params.contestId, 10) : undefined;

  const results = useContestResultsStore((state) => state.results);
  const loading = useContestResultsStore((state) => state.loading);
  const error = useContestResultsStore((state) => state.error);
  const fetchResults = useContestResultsStore((state) => state.fetchResults);
  const createOrUpdateTask = useContestResultsStore((state) => state.createOrUpdateTask);
  const deleteTask = useContestResultsStore((state) => state.deleteTask);
  const deleteTeamResults = useContestResultsStore((state) => state.deleteTeamResults);

  const [isTaskModalOpen, setTaskModalOpen] = useState(false);
  const [editingTask, setEditingTask] = useState<Task | null>(null);
  const [expandedTasks, setExpandedTasks] = useState<Record<number, boolean>>({});

  useEffect(() => {
    if (contestId) {
      fetchResults(contestId);
    }
  }, [contestId, fetchResults]);

  useContestResultsWebSocket(contestId); // Listen for real-time updates
  const { updateContestSummary, updateTaskSummary } = useScoreUpdates(); // Use the new hook

  const handleNewTask = () => {
    setEditingTask(null);
    setTaskModalOpen(true);
  };

  const handleEditTask = (task: Task) => {
    setEditingTask(task);
    setTaskModalOpen(true);
  };

  const handleDeleteTask = async (taskId: number) => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      await deleteTask(contestId, taskId);
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

  const handleToggleTask = (taskId: number) => {
    setExpandedTasks((prev) => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  const handleTaskSubmit = async (task: Task) => {
    await createOrUpdateTask(contestId, task);
    setTaskModalOpen(false);
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
    }
    fetchResults(contestId);
  };

  const columns = useMemo<ColumnDef<ContestSummary & { [key: string]: any }>[]>(() => {
    if (!results) return [];

    const baseColumns: ColumnDef<ContestSummary & { [key: string]: any }>[] = [
      columnHelper.accessor('rank', {
        header: '#',
        cell: (info) => <span className="align-middle">{info.getValue()}</span>,
        enableSorting: true,
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
              >
                <Trash2Icon size={12} />
              </button>
            )}
          </div>
        ),
        enableSorting: false,
      }),
      columnHelper.accessor('contestSummary', {
        header: 'Σ',
        enableSorting: true,
        cell: results.permission_change_contest ? EditableCell : (info) => info.getValue(),
      }),
    ];

    const tasks = (results.task_set || []).sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));
    tasks.forEach((task, index) => {
      // Add columns for tests within the task if expanded
      if (expandedTasks[task.id]) {
        const tests = (task.tasktest_set || []).sort((a, b) => ((a.index || 0) > (b.index || 0) ? 1 : -1));
        tests.forEach((test) => {
          const testDataField = `test_${test.id.toFixed(0)}`;
          baseColumns.push(
            columnHelper.accessor(testDataField, {
              header: () => <span>{test.heading}</span>,
              id: `test-${test.id}`,
              cell: results.permission_change_contest ? EditableCell : (info) => info.getValue(),
              meta: {
                columnType: 'test',
                testId: test.id,
              },
            }),
          );
        });
      }

      const dataField = `task_${task.id.toFixed(0)}`;
      baseColumns.push(
        columnHelper.accessor(dataField, {
          header: () => (
            <div className="flex items-center gap-2 cursor-pointer" onClick={() => handleToggleTask(task.id)}>
              <span>
                {task.heading} {expandedTasks[task.id] ? '(Σ)' : ''}
              </span>
              {results.permission_change_contest && (
                <>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMoveTask(task, 'left');
                    }}
                    className="btn btn-xs btn-ghost"
                    disabled={index === 0}
                  >
                    <ChevronLeftIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleMoveTask(task, 'right');
                    }}
                    className="btn btn-xs btn-ghost"
                    disabled={index === tasks.length - 1}
                  >
                    <ChevronRightIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleEditTask(task);
                    }}
                    className="btn btn-xs btn-ghost"
                  >
                    <PencilIcon size={12} />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteTask(task.id);
                    }}
                    className="btn btn-xs btn-ghost"
                  >
                    <Trash2Icon size={12} />
                  </button>
                </>
              )}
            </div>
          ),
          id: `task-${task.id}`,
          enableSorting: true,
          cell: results.permission_change_contest && !task.autosum_scores ? EditableCell : (info) => info.getValue(),
          meta: {
            columnType: 'task',
            taskId: task.id,
            sortDirection: task.summary_score_sorting_direction,
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
        const teamId = taskSummary.team?.id;
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
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold">{results.name}</h2>
        {results.permission_change_contest && (
          <button onClick={handleNewTask} className="btn btn-primary">
            New Task
          </button>
        )}
      </div>
      <DataTable
        columns={columns}
        data={data}
        className="table table-striped table-hover table-condensed table-dark"
        updateMyData={updateMyData}
      />
      <TaskModal
        show={isTaskModalOpen}
        onClose={() => setTaskModalOpen(false)}
        onSubmit={handleTaskSubmit}
        task={editingTask}
      />
    </div>
  );
};
