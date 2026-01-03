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
    <div className="overflow-y-auto max-h-96">
        <div className="flex justify-between items-center p-2 bg-base-200 sticky top-0 z-20">
            <h3 className="font-bold">Score Log for {contestantName}</h3>
            <button onClick={onClose} className="btn btn-sm btn-ghost">
                <X size={20} />
            </button>
        </div>
      <table className="table table-zebra table-sm w-full">
        <thead className="sticky top-[48px] bg-base-200 z-10">
          <tr>
            <th>Time</th>
            <th>Gate</th>
            <th>Message</th>
            <th>Points</th>
          </tr>
        </thead>
        <tbody>
          {scoreLog.map((entry) => (
            <tr key={entry.id}>
              <td>{new Date(entry.time).toLocaleTimeString()}</td>
              <td>{entry.gate}</td>
              <td>{entry.message}</td>
              <td>{entry.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
