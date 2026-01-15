import React, { useMemo } from 'react';
import { ColumnDef, createColumnHelper } from '@tanstack/react-table';
import { DataTable, getTableUpdateMyData } from '../../components/common/DataTable/DataTable';
import { useContestResults } from '../../hooks/useContestResults';
import { useContestResultsWebSocket } from '../../hooks/useContestResultsWebSocket';
import { ContestSummary, ContestResultsState, Task } from '../../store/contestResultsStore'; // Assuming these interfaces
import { useContestResultsStore } from '../../store/contestResultsStore';
import { EditableCell } from '../../components/common/DataTable/EditableCell';
import { mdiChevronDown, mdiChevronUp } from '@mdi/js';
import Icon from '@mdi/react';

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
  contestId: number;
  navigationTaskId?: number; // Used for highlighting tasks
}

export const ContestResultsTable: React.FC<ContestResultsTableProps> = ({ contestId, navigationTaskId }) => {
  const { results, loading, error, fetchResults } = useContestResults(contestId);
  useContestResultsWebSocket(contestId); // Listen for real-time updates

  const columnHelper = createColumnHelper<ContestSummary & { [key: string]: any }>(); // Extend ContestSummary for dynamic task scores

  // Function to simulate updating data - this will be replaced by actual API calls in Subtask 7
  const updateMyData = (rowIndex: number, columnId: string, value: any) => {
    // This is a placeholder for updating the data
    console.log(`Updating row ${rowIndex}, column ${columnId} with value ${value}`);
    // In a real scenario, you'd dispatch an action to update the backend
    // and then potentially update the local state after a successful response.
  };

  const columns = useMemo<ColumnDef<ContestSummary & { [key: string]: any }>[]>(() => {
    if (!results) return [];

    const baseColumns: ColumnDef<ContestSummary & { [key: string]: any }>[] = [
      columnHelper.accessor('rank', {
        header: '#',
        cell: info => <span className="align-middle">{info.getValue()}</span>,
        enableSorting: true,
      }),
      columnHelper.accessor('team', {
        header: 'CREW',
        cell: info => <div className="align-middle crew-name">{teamRankingTable(info.getValue())}</div>,
        enableSorting: false,
      }),
      columnHelper.accessor('contestSummary', {
        header: 'Σ',
        cell: info => info.getValue(),
        enableSorting: true,
        // The original component had 'sortDirection' on the columnDef, but tanstack/react-table handles this via table state
      }),
    ];

    // Dynamically add task columns
    const tasks = (results.task_set || []).sort((a, b) => (a.index || 0) > (b.index || 0) ? 1 : -1); // Assuming 'index' on Task
    tasks.forEach((task) => {
      const dataField = `task_${task.id.toFixed(0)}`;
      baseColumns.push(
        columnHelper.accessor(dataField, {
          header: () => (
            <span className={navigationTaskId && navigationTaskId === task.id ? 'taskTitleName' : ''}>
              {task.heading} {/* Assuming 'heading' property on Task */}
            </span>
          ),
          id: `task-${task.id}`, // Unique ID for the column
          cell: info => info.getValue(), // Render score directly
          enableSorting: true,
          // Custom properties can be added to columnDef and accessed via cell.column.columnDef as any
          meta: {
            columnType: 'task',
            taskId: task.id,
            sortDirection: task.summary_score_sorting_direction, // Assuming this is present on Task
          },
        })
      );
    });

    return baseColumns;
  }, [results, navigationTaskId, columnHelper]);

  const data = useMemo(() => {
    if (!results) return [];

    const transformedData: (ContestSummary & { [key: string]: any })[] = [];
    const ranks = new Map<number, number>(); // Map team ID to rank

    // Calculate ranks (simplified from original for now)
    const sortedSummaries = [...(results.contestsummary_set || [])].sort((a, b) => {
        // Assuming 'points' property for sorting, similar to the original compareOverall
        return (a.points || 0) - (b.points || 0);
    });
    sortedSummaries.forEach((summary, index) => {
        if (summary.team?.id) { // Assuming team has an id
            ranks.set(summary.team.id, index + 1);
        }
    });


    // Initialize data for each team
    (results.contest_teams || []).forEach(team => {
        const teamId = team.id;
        transformedData.push({
            id: teamId,
            team: team, // Keep full team object
            rank: ranks.get(teamId) || '-',
            contestSummary: '-',
            // Initialize task scores
            ...results.task_set.reduce((acc, task) => {
                acc[`task_${task.id.toFixed(0)}`] = '-';
                return acc;
            }, {}),
        });
    });

    // Populate contest summary and task scores
    (results.contestsummary_set || []).forEach(summary => {
      const teamId = summary.team?.id;
      if (teamId) {
        const existingEntry = transformedData.find(d => d.id === teamId);
        if (existingEntry) {
          existingEntry.contestSummary = summary.points; // Assuming 'points' property
        }
      }
    });

    (results.task_set || []).forEach(task => {
        (task.tasksummary_set || []).forEach((taskSummary: any) => { // Assuming taskSummary has team.id and points
            const teamId = taskSummary.team?.id;
            if (teamId) {
                const existingEntry = transformedData.find(d => d.id === teamId);
                if (existingEntry) {
                    existingEntry[`task_${task.id.toFixed(0)}`] = taskSummary.points;
                }
            }
        });
    });

    return transformedData;
  }, [results]);

  if (loading) return <div>Loading Contest Results...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!results) return <div>No Contest Results available.</div>;

  return (
    <DataTable
      columns={columns}
      data={data}
      className="table table-striped table-hover table-condensed table-dark" // Example styling
      initialState={{
        // The original component used sortBy, but tanstack/react-table handles this through sorting state
        // For initial sort, you would set the `sorting` state of useReactTable.
        // The original also had 'id: "contestSummary"', I need to map it correctly.
      }}
      updateMyData={updateMyData}
    />
  );
};
