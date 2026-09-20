import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { assignPlayingCard, fetchPlayingCards, PlayingCardsResponse, removePlayingCard } from '../api';
import { ContestantRow } from '../types';

export interface PlayingCardsModalHandle {
  open: () => void;
}

interface PlayingCardsModalProps {
  contestId: number;
  navigationTaskId: number;
  contestant: ContestantRow;
  canManage: boolean;
  onChanged: () => void;
}

// Mirrors display/poker/poker_cards.py's PLAYING_CARDS exactly (suit/rank ordering included) -
// the REST payload only carries the raw two-character code (e.g. "Ah"), not a display label.
const PLAYING_CARD_OPTIONS: [string, string][] = [
  ['Ah', 'Ace of hearts'], ['Kh', 'King of hearts'], ['Qh', 'Queen of hearts'], ['Jh', 'Jack of hearts'],
  ['Th', '10 of hearts'], ['9h', '9 of hearts'], ['8h', '8 of hearts'], ['7h', '7 of hearts'],
  ['6h', '6 of hearts'], ['5h', '5 of hearts'], ['4h', '4 of hearts'], ['3h', '3 of hearts'], ['2h', '2 of hearts'],
  ['Ad', 'Ace of diamonds'], ['Kd', 'King of diamonds'], ['Qd', 'Queen of diamonds'], ['Jd', 'Jack of diamonds'],
  ['Td', '10 of diamonds'], ['9d', '9 of diamonds'], ['8d', '8 of diamonds'], ['7d', '7 of diamonds'],
  ['6d', '6 of diamonds'], ['5d', '5 of diamonds'], ['4d', '4 of diamonds'], ['3d', '3 of diamonds'], ['2d', '2 of diamonds'],
  ['Ac', 'Ace of clubs'], ['Kc', 'King of clubs'], ['Qc', 'Queen of clubs'], ['Jc', 'Jack of clubs'],
  ['Tc', '10 of clubs'], ['9c', '9 of clubs'], ['8c', '8 of clubs'], ['7c', '7 of clubs'],
  ['6c', '6 of clubs'], ['5c', '5 of clubs'], ['4c', '4 of clubs'], ['3c', '3 of clubs'], ['2c', '2 of clubs'],
  ['As', 'Ace of spades'], ['Ks', 'King of spades'], ['Qs', 'Queen of spades'], ['Js', 'Jack of spades'],
  ['Ts', '10 of spades'], ['9s', '9 of spades'], ['8s', '8 of spades'], ['7s', '7 of spades'],
  ['6s', '6 of spades'], ['5s', '5 of spades'], ['4s', '4 of spades'], ['3s', '3 of spades'], ['2s', '2 of spades'],
];

const CARD_LABELS: Record<string, string> = Object.fromEntries(PLAYING_CARD_OPTIONS);

const PlayingCardsModal = forwardRef<PlayingCardsModalHandle, PlayingCardsModalProps>(
  ({ contestId, navigationTaskId, contestant, canManage, onChanged }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const [data, setData] = useState<PlayingCardsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [busyCardPk, setBusyCardPk] = useState<number | null>(null);

    const waypointNames = contestant.compiled_effective_route_payload?.waypoint_names || [];
    const [waypointIndex, setWaypointIndex] = useState('0');
    const [card, setCard] = useState('random');
    const [assigning, setAssigning] = useState(false);

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetchPlayingCards(contestId, navigationTaskId, contestant.pk);
        setData(response);
        const latestWaypointIndex = response.cards.reduce((max, c) => Math.max(max, c.waypoint_index), -1);
        const nextIndex = Math.min(latestWaypointIndex + 1, Math.max(waypointNames.length - 1, 0));
        setWaypointIndex(String(nextIndex));
      } catch (err: any) {
        setError(err.message || 'Failed to load playing cards');
      } finally {
        setLoading(false);
      }
    };

    useImperativeHandle(ref, () => ({
      open: () => {
        dialogRef.current?.showModal();
        load();
      },
    }));

    const handleRemove = async (cardPk: number) => {
      if (busyCardPk !== null || !window.confirm('Remove this card?')) return;
      setBusyCardPk(cardPk);
      try {
        await removePlayingCard(contestId, navigationTaskId, contestant.pk, cardPk);
        await load();
        onChanged();
      } catch (err: any) {
        window.alert(err.message || 'Failed to remove card');
      } finally {
        setBusyCardPk(null);
      }
    };

    const handleAssign = async (event: React.FormEvent) => {
      event.preventDefault();
      setAssigning(true);
      try {
        await assignPlayingCard(contestId, navigationTaskId, contestant.pk, {
          waypoint_index: Number(waypointIndex),
          card,
        });
        await load();
        onChanged();
      } catch (err: any) {
        window.alert(err.message || 'Failed to assign card');
      } finally {
        setAssigning(false);
      }
    };

    return (
      <dialog ref={dialogRef} className="modal">
        <div className="modal-box max-w-lg">
          <form method="dialog">
            <button
              type="button"
              className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
              onClick={() => dialogRef.current?.close()}
            >
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg">Playing cards - contestant #{contestant.contestant_number}</h3>

          {loading && <p className="py-4 text-sm text-gray-500">Loading...</p>}
          {error && <p className="py-4 text-error text-sm">{error}</p>}

          {data && !loading && (
            <div className="py-2">
              <p className="text-sm text-gray-500 mb-3">
                Current hand: {data.current_hand}, relative score {data.current_relative_score}%
              </p>
              <div className="overflow-x-auto">
                <table className="table table-sm w-full">
                  <thead>
                    <tr>
                      <th>Card</th>
                      <th>Waypoint</th>
                      {canManage && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {data.cards.map((entry) => (
                      <tr key={entry.id}>
                        <td>{CARD_LABELS[entry.card] || entry.card}</td>
                        <td>{entry.waypoint_name}</td>
                        {canManage && (
                          <td>
                            <button
                              type="button"
                              disabled={busyCardPk === entry.id}
                              onClick={() => handleRemove(entry.id)}
                              className="btn btn-ghost btn-xs text-error px-1"
                            >
                              Remove
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                    {data.cards.length === 0 && (
                      <tr>
                        <td colSpan={canManage ? 3 : 2} className="text-center text-sm text-gray-500">
                          No cards dealt yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {canManage && waypointNames.length > 0 && (
                <form onSubmit={handleAssign} className="mt-4 border-t border-base-200 pt-4 flex flex-wrap items-end gap-2">
                  <div className="form-control">
                    <label className="label label-text text-xs">Waypoint</label>
                    <select
                      className="select select-bordered select-sm"
                      value={waypointIndex}
                      onChange={(e) => setWaypointIndex(e.target.value)}
                    >
                      {waypointNames.map((name, index) => (
                        <option key={name} value={index}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="form-control">
                    <label className="label label-text text-xs">Card</label>
                    <select className="select select-bordered select-sm" value={card} onChange={(e) => setCard(e.target.value)}>
                      <option value="random">Random</option>
                      {PLAYING_CARD_OPTIONS.map(([code, label]) => (
                        <option key={code} value={code}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={assigning}>
                    {assigning ? 'Assigning...' : 'Assign'}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

PlayingCardsModal.displayName = 'PlayingCardsModal';

export default PlayingCardsModal;
