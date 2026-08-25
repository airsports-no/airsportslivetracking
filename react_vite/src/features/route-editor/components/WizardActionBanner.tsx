import React from 'react';
import { Wand2, X } from 'lucide-react';
import type { DummyBranchPhase } from '../unknownLegWizard';

interface WizardActionBannerProps {
  currentWizardActionLabel: string;
  title: string;
  instruction: string;
  stopWizardAction: () => void;
  dummyBranchPhase?: DummyBranchPhase;
  awaitingNonTriggerSelection?: boolean;
}

const WizardActionBanner: React.FC<WizardActionBannerProps> = ({
  currentWizardActionLabel,
  title,
  instruction,
  stopWizardAction,
  dummyBranchPhase = 'idle',
  awaitingNonTriggerSelection = false,
}) => {
  return (
    <div className="absolute top-28 left-1/2 z-[999] w-[min(36rem,calc(100%-2rem))] -translate-x-1/2 pointer-events-auto">
      <div className="card border border-warning/30 bg-base-100/95 shadow-xl backdrop-blur">
        <div className="card-body gap-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-warning">
                <Wand2 size={14} />
                Active step
              </div>
              <h3 className="text-sm font-semibold text-base-content">{currentWizardActionLabel}</h3>
              <p className="mt-1 text-sm font-medium text-base-content">{title}</p>
              <p className="mt-1 text-sm text-base-content/80">{instruction}</p>
            </div>
            <button type="button" onClick={stopWizardAction} className="btn btn-ghost btn-sm btn-square" title="Stop active step">
              <X size={16} />
            </button>
          </div>

          {dummyBranchPhase === 'awaiting_trigger' && awaitingNonTriggerSelection && (
            <div className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-sm text-base-content/80">
              That waypoint isn't an unknown-leg trigger — pick an amber one, or change a waypoint's type to Unknown Leg.
            </div>
          )}

          <div className="flex justify-end">
            <button type="button" onClick={stopWizardAction} className="btn btn-outline btn-sm">
              Stop active step
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WizardActionBanner;
