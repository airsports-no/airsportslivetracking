import React from 'react';

interface Row {
  id: number;
  name: string;
  score: number;
  state?: string;
  color?: string;
  countdown?: number | null;
}

interface Props {
    rows: Row[];
    onRowClick?: (id: number) => void;
    dividerIndex?: number;
}

function formatCountdown(totalSeconds: number): string {
    const negative = totalSeconds < 0;
    const seconds = Math.abs(totalSeconds);
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    const pad = (num: number) => String(num).padStart(2, '0');
    let timeString = `${pad(m)}:${pad(s)}`;
    if (h > 0) {
        timeString = `${pad(h)}:${timeString}`;
    }
    return negative ? `+${timeString}` : `-${timeString}`;
}

export default function ResultsTable({ rows, onRowClick, dividerIndex = -1 }: Props) {
  return (
    <div className="overflow-y-auto max-h-[40vh] sm:max-h-96">
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
                <td className="max-w-[100px] sm:max-w-[150px] md:max-w-none truncate">{r.name}</td>
                <td>
                    {r.countdown && r.countdown > 0 ? (
                        formatCountdown(r.countdown)
                    ) : (
                        r.score.toFixed(0)
                    )}
                </td>
              </tr>
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
