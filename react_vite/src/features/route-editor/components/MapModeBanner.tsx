import React from 'react';
import { Activity, Anchor, Camera, Hexagon, MousePointerClick, PlusCircle, Tag, Wand2, X } from 'lucide-react';
import type { DummyBranchPhase } from '../unknownLegWizard';
import { bannerSentence, type BannerIcon, type BannerTone, type ModeBanner } from '../modeBanner';

const ICONS: Record<BannerIcon, React.ComponentType<{ size?: number; className?: string }>> = {
  plus: PlusCircle,
  tag: Tag,
  camera: Camera,
  hexagon: Hexagon,
  anchor: Anchor,
  activity: Activity,
  wand: Wand2,
  pointer: MousePointerClick,
};

// Whole class names, so Tailwind finds them.
const TONES: Record<BannerTone, { border: string; icon: string; button: string }> = {
  success: { border: 'border-success/50', icon: 'text-success', button: 'btn-success' },
  secondary: { border: 'border-secondary/50', icon: 'text-secondary', button: 'btn-secondary' },
  warning: { border: 'border-warning/50', icon: 'text-warning', button: 'btn-warning' },
  primary: { border: 'border-primary/50', icon: 'text-primary', button: 'btn-primary' },
  info: { border: 'border-info/50', icon: 'text-info', button: 'btn-info' },
};

interface MapModeBannerProps {
  banner: ModeBanner;
  // Replaces the banner's title (the unknown-leg step names the trigger it belongs to).
  title?: string | null;
  // Stops the tool, and the guide step if there is one; the same as Esc.
  onStop: () => void;
  // A guide step is active: its button, "Done, next step" or "Stop".
  guideAction?: { label: string; onDone: () => void; description?: string } | null;
  dummyBranchPhase?: DummyBranchPhase;
  awaitingNonTriggerSelection?: boolean;
}

// The one banner over the map for every placing state, started from the toolbar or from the guide: what a click does
// now, how to stop, and (with a guide step) the guide's own button. Select mode has none. Small, so the map stays usable.
const MapModeBanner: React.FC<MapModeBannerProps> = ({
  banner,
  title,
  onStop,
  guideAction = null,
  dummyBranchPhase = 'idle',
  awaitingNonTriggerSelection = false,
}) => {
  const Icon = ICONS[banner.icon];
  const tone = TONES[banner.tone];
  const sentence = bannerSentence({ title: title ?? banner.title, instruction: banner.instruction });
  // A guide button labelled Stop is the stop button: no second one beside it.
  const doneIsStop = guideAction?.label === 'Stop';

  return (
    <div
      className="absolute top-20 left-1/2 z-[999] w-max max-w-[min(38rem,calc(100%-2rem))] -translate-x-1/2 pointer-events-auto"
      role="status"
      data-testid="map-mode-banner"
      data-mode-kind={banner.kind}
      title={guideAction?.description}
    >
      <div className={`flex items-center gap-2 rounded-full border ${tone.border} bg-base-100/95 py-1 pl-3 pr-1 shadow-lg backdrop-blur`}>
        <Icon size={16} className={`shrink-0 ${tone.icon}`} />
        <p className="min-w-0 text-xs leading-snug text-base-content line-clamp-2">
          {sentence}
          <span className="ml-1 whitespace-nowrap text-base-content/60">Esc to stop.</span>
        </p>
        {guideAction && (
          <button type="button" onClick={guideAction.onDone} className={`btn btn-xs ${tone.button} shrink-0 rounded-full`} title={guideAction.label}>
            {guideAction.label}
          </button>
        )}
        {!doneIsStop && (
          <button type="button" onClick={onStop} className="btn btn-xs btn-circle btn-ghost shrink-0" title="Stop (Esc)" aria-label="Stop">
            <X size={14} />
          </button>
        )}
      </div>
      {dummyBranchPhase === 'awaiting_trigger' && awaitingNonTriggerSelection && (
        <div className="mt-1 rounded-full border border-warning/30 bg-base-100/95 px-3 py-1 text-xs text-base-content/80 shadow">
          That waypoint isn't an unknown-leg point: pick an amber one, or change a waypoint's type to Unknown Leg.
        </div>
      )}
    </div>
  );
};

export default MapModeBanner;
