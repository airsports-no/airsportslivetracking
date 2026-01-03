import React from 'react';

interface Row {
  id: number;
  name: string;
  score: number;
  state?: string;
  color?: string;
}

interface Props {
    rows: Row[];
    onRowClick?: (id: number) => void;
    dividerIndex?: number;
}

export default function ResultsTable({ rows, onRowClick, dividerIndex = -1 }: Props) {
  return (
    <div className="overflow-y-auto max-h-96">
      <table className="table table-zebra table-sm w-full">
        <thead className="sticky top-0 bg-base-200 z-10">
          <tr>
            <th>Rank</th>
            <th>Contestant</th>
            <th>Score</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, idx) => (
            <React.Fragment key={r.id}>
              {idx === dividerIndex && (
                <tr className="bg-base-300 pointer-events-none">
                    <td colSpan={3} className="h-1 p-0">
                        <div className="w-full h-px bg-base-content/20"></div>
                    </td>
                </tr>
              )}
              <tr onClick={() => onRowClick?.(r.id)} className={onRowClick ? 'cursor-pointer hover:bg-base-300' : ''}>
                <td style={{borderLeft: `4px solid ${r.color ?? 'transparent'}`}}>{idx + 1}</td>
                <td>{r.name}</td>
                <td>{r.score.toFixed(0)}</td>
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
