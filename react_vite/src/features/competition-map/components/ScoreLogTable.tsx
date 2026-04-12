import React from 'react';
import { ScoreLogEntry } from '../types';
import { X } from 'lucide-react';

interface Props {
    scoreLog: ScoreLogEntry[];
    contestantName: string;
    onClose: () => void;
}

export default function ScoreLogTable({ scoreLog, contestantName, onClose }: Props) {
  if (!scoreLog) {
    return null;
  }
  return (
    <div className="overflow-y-auto max-h-[40vh] sm:max-h-96">
      <table className="table table-zebra table-xs w-full">
        <thead className="sticky top-0 bg-base-200 z-10">
          <tr>
            <th className="px-1 w-12">Time</th>
            <th className="px-1 w-12">Gate</th>
            <th className="px-1">Msg</th>
            <th className="px-1 w-10 text-right">Pts</th>
          </tr>
        </thead>
        <tbody>
          {scoreLog.map((entry) => (
            <tr key={entry.id}>
              <td className="px-1 whitespace-nowrap tabular-nums">{new Date(entry.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
              <td className="px-1 truncate max-w-[50px]" title={entry.gate}>{entry.gate}</td>
              <td className="px-1 text-xs leading-tight break-words">{entry.message}</td>
              <td className="px-1 text-right tabular-nums">{(entry.points ?? 0).toFixed(0)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
