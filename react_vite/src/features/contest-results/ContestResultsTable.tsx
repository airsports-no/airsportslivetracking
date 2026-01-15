interface ContestResultsTableProps {
  navigationTaskId?: number; // Used for highlighting tasks
}

const columnHelper = createColumnHelper<ContestSummary & { [key: string]: any }>(); // Extend ContestSummary for dynamic task scores

export const ContestResultsTable: React.FC<ContestResultsTableProps> = ({ navigationTaskId }) => {