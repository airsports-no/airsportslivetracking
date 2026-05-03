import React from 'react';

interface Row {
  id: number;
  name: string;
  score: number | string;
  state?: string;
  color?: string;
  countdown?: number | null;
  expectedBy?: string | null;
}

interface Props {
    rows: Row[];
    selectedId?: number | null;
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

export default function ResultsTable({ rows, selectedId, onRowClick, dividerIndex = -1 }: Props) {
  return (
    <div className="results-table-scroll-area overflow-y-auto max-h-[40vh] sm:max-h-96">
      <table className="table table-zebra table-xs sm:table-sm w-full">
        <thead className="sticky top-0 bg-base-200 z-10">
          <tr>
            <th className="w-8 px-1 text-center">#</th>
            <th className="px-2">Contestant</th>
            <th className="px-1 text-right">Score</th>
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
              <tr 
                onClick={() => onRowClick?.(r.id)} 
                className={`
                    ${onRowClick ? 'cursor-pointer hover:bg-base-300' : ''} 
                    ${selectedId === r.id ? 'bg-primary/20 font-bold' : ''}
                `}
              >
                <td className="w-8 px-1 text-center" style={{borderLeft: `4px solid ${r.color ?? 'transparent'}`}}>{idx + 1}</td>
                <td className="max-w-[80px] sm:max-w-[150px] md:max-w-none truncate px-2">
                    <div className="flex flex-col">
                        <span>{r.name}</span>
                        {r.expectedBy && (
                            <span className="text-[10px] opacity-60 font-normal">
                                Exp by: {r.expectedBy}
                            </span>
                        )}
                    </div>
                </td>
                <td className="px-1 text-right tabular-nums">
                    {r.countdown && r.countdown > 0 ? (
                        formatCountdown(r.countdown)
                    ) : (
                        typeof r.score === 'number' ? r.score.toFixed(0) : r.score
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
