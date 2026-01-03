import React from 'react';

interface Row {
  id: number;
  name: string;
  score: number;
}

export default function ResultsTable({ rows }: { rows: Row[] }) {
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
            <tr key={r.id}>
              <td>{idx + 1}</td>
              <td>{r.name}</td>
              <td>{r.score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
