import React from 'react';
import { Link } from 'react-router-dom';
import { generatePath } from '../../urls';
import { Standings, StandingsCell } from './api';

const formatNumber = (value: number) => (Number.isInteger(value) ? String(value) : value.toFixed(2));

/** One leg of one entrant: the place, or why there is none, with the points it gave */
const LegCell: React.FC<{ cell: StandingsCell | undefined; pointsTable: boolean }> = ({ cell, pointsTable }) => {
    if (!cell) return <td />;
    const label = cell.status === 'ranked' ? String(cell.placement) : cell.status === 'no_result' ? 'no result' : 'not in it';
    return (
        <td className={`text-center ${cell.counted ? '' : 'opacity-40 line-through'}`} title={cell.counted ? undefined : 'Not counted: only the best legs add to the total'}>
            <div className={cell.status === 'ranked' ? 'font-semibold' : 'text-xs opacity-70'}>{label}</div>
            <div className="text-xs opacity-60">{pointsTable || cell.status !== 'ranked' ? `${formatNumber(cell.points)} p` : ''}</div>
        </td>
    );
};

/**
 * The ranking of a series: each entrant's place in every leg and the total. Lowest total wins when the series adds up
 * placements, highest when it scores with a points table.
 */
const StandingsTable: React.FC<{ standings: Standings }> = ({ standings }) => {
    const pointsTable = standings.scoring_method === 'points_table';
    if (standings.rows.length === 0) {
        return <p className="opacity-70">There are no results yet.</p>;
    }
    return (
        <div className="overflow-x-auto">
            <table className="table table-sm">
                <thead>
                    <tr>
                        <th className="w-10">#</th>
                        <th>{standings.entrant_identity === 'crew' ? 'Crew' : 'Pilot'}</th>
                        {standings.legs.map(leg => (
                            <th key={leg.contest_id} className="text-center">
                                <Link className="link" to={generatePath('MISSION_DASHBOARD_DETAIL', { contestId: leg.contest_id })}>{leg.name}</Link>
                                {leg.weight !== 1 && <div className="text-xs opacity-60 font-normal">× {leg.weight}</div>}
                            </th>
                        ))}
                        <th className="text-right">Total</th>
                    </tr>
                </thead>
                <tbody>
                    {standings.rows.map(row => (
                        <tr key={row.entrant.key}>
                            <td className="font-bold">{row.rank}</td>
                            <td>
                                <div className="font-semibold">{row.entrant.name}</div>
                                {row.entrant.club && <div className="text-xs opacity-60">{row.entrant.club}</div>}
                            </td>
                            {standings.legs.map(leg => (
                                <LegCell key={leg.contest_id} cell={row.legs.find(cell => cell.contest_id === leg.contest_id)} pointsTable={pointsTable} />
                            ))}
                            <td className="text-right font-bold">{formatNumber(row.total)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default StandingsTable;
