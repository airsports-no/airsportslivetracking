import React from 'react';
import { Wand2 } from 'lucide-react';
import type { DummyBranchPhase } from '../unknownLegWizard';

interface WizardActionBannerProps {
  // The step's full description: shown on hover only, the wizard panel has it too
  currentWizardActionLabel: string;
  // A short title worth showing (which trigger the extension waypoints belong to), or nothing
  title?: string | null;
  instruction: string;
  stopWizardAction: () => void;
  dummyBranchPhase?: DummyBranchPhase;
  awaitingNonTriggerSelection?: boolean;
}

// A slim bar over the map while a wizard step is active: what to click, and Done. Kept small so the map stays usable.
const WizardActionBanner: React.FC<WizardActionBannerProps> = ({
  currentWizardActionLabel,
  title,
  instruction,
  stopWizardAction,
  dummyBranchPhase = 'idle',
  awaitingNonTriggerSelection = false,
}) => {
  return (
    <div
      className="absolute top-28 left-1/2 z-[999] w-max max-w-[min(34rem,calc(100%-2rem))] -translate-x-1/2 pointer-events-auto"
      title={currentWizardActionLabel}
    >
      <div className="flex items-center gap-2 rounded-full border border-warning/40 bg-base-100/95 py-1 pl-3 pr-1 shadow-lg backdrop-blur">
        <Wand2 size={14} className="shrink-0 text-warning" />
        <p className="min-w-0 text-xs leading-snug text-base-content line-clamp-2">
          {title && <span className="font-semibold">{title}: </span>}
          {instruction}
        </p>
        <button type="button" onClick={stopWizardAction} className="btn btn-xs btn-warning shrink-0 rounded-full" title="Stop active step">
          Done
        </button>
      </div>
      {dummyBranchPhase === 'awaiting_trigger' && awaitingNonTriggerSelection && (
        <div className="mt-1 rounded-full border border-warning/30 bg-base-100/95 px-3 py-1 text-xs text-base-content/80 shadow">
          That waypoint isn't an unknown-leg point: pick an amber one, or change a waypoint's type to Unknown Leg.
        </div>
      )}
    </div>
  );
};

export default WizardActionBanner;
