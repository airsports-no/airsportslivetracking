import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import type { UndoableStep } from '../useRouteHistory';

export interface RouteNotice {
  id: number;
  text: string;
  // The undoable step of the change that removed something
  step: UndoableStep;
}

// How long the notice stays when it is not dismissed.
export const NOTICE_DURATION_MS = 10000;

interface RouteChangeNoticeProps {
  notice: RouteNotice;
  onDismiss: () => void;
}

// What a change of the route removed, over the map: not a dialog, the editor stays usable. Undo puts the route back as it
// was before the change; it is hidden once something else has been done since (undoing then would take that too).
const RouteChangeNotice: React.FC<RouteChangeNoticeProps> = ({ notice, onDismiss }) => {
  useEffect(() => {
    const timer = setTimeout(onDismiss, NOTICE_DURATION_MS);
    return () => clearTimeout(timer);
  }, [notice.id, onDismiss]);

  return (
    <div
      className="absolute bottom-6 left-1/2 z-[1000] w-max max-w-[min(40rem,calc(100%-2rem))] -translate-x-1/2"
      role="status"
      data-testid="route-change-notice"
    >
      <div className="alert alert-warning shadow-lg py-2">
        <span className="text-sm">{notice.text}</span>
        {notice.step.isLatest() && (
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => {
              notice.step.undo();
              onDismiss();
            }}
          >
            Undo
          </button>
        )}
        <button type="button" className="btn btn-sm btn-ghost btn-square" onClick={onDismiss} aria-label="Dismiss">
          <X size={16} />
        </button>
      </div>
    </div>
  );
};

export default RouteChangeNotice;
