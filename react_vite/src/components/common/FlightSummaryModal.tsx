import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { Sparkles } from 'lucide-react';
import { FlightAnalysis, fetchFlightSummary, FlightSummaryState, requestFlightSummary } from './flightSummaryApi';

const POLL_INTERVAL_MS = 3000;

const signedSeconds = (seconds: number | null) => (seconds === null ? '-' : `${seconds > 0 ? '+' : ''}${seconds} s`);

const minutesAndSeconds = (seconds: number | null) =>
  seconds === null ? '-' : `${Math.floor(seconds / 60)}:${String(Math.abs(seconds % 60)).padStart(2, '0')}`;

const headwind = (knots: number | null) =>
  knots === null ? '-' : knots >= 0 ? `${knots.toFixed(0)} kt head` : `${(-knots).toFixed(0)} kt tail`;

/** The legs behind the summary: planned and flown times, and what the wind did. */
const LegTable: React.FC<{ analysis: FlightAnalysis }> = ({ analysis }) => (
  <details className="collapse collapse-arrow bg-base-200">
    <summary className="collapse-title text-sm font-semibold">🧭 Leg by leg</summary>
    <div className="collapse-content overflow-x-auto">
      <p className="text-xs opacity-70 mb-2">
        Planned wind {analysis.planned_wind.direction}° / {analysis.planned_wind.speed_kt} kt. The actual wind is the weather
        model's at {analysis.wind_height_ft_above_ground} ft above the ground; "wind effect" is how much later (+) or earlier
        that wind alone would have made you at the planned airspeed.
      </p>
      <table className="table table-xs">
        <thead>
          <tr>
            <th>Leg</th>
            <th>Planned</th>
            <th>Flown</th>
            <th>At gate</th>
            <th>Wind</th>
            <th>Head/tail</th>
            <th>Wind effect</th>
          </tr>
        </thead>
        <tbody>
          {analysis.legs.map((leg) => (
            <tr key={`${leg.from}-${leg.to}`}>
              <td className="whitespace-nowrap">
                {leg.from} → {leg.to}
              </td>
              <td>{minutesAndSeconds(leg.planned_seconds)}</td>
              <td>{minutesAndSeconds(leg.actual_seconds)}</td>
              <td>{signedSeconds(leg.offset_at_end_seconds)}</td>
              <td className="whitespace-nowrap">
                {leg.actual_wind ? `${leg.actual_wind.direction}° / ${leg.actual_wind.speed_kt.toFixed(0)} kt` : '-'}
              </td>
              <td className="whitespace-nowrap">{headwind(leg.actual_headwind_kt)}</td>
              <td>{signedSeconds(leg.wind_effect_seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </details>
);

export interface FlightSummaryModalHandle {
  open: () => void;
}

interface FlightSummaryModalProps {
  contestantId: number;
  /** Shown under the heading, e.g. the task or the contestant number. */
  subtitle?: string;
}

/**
 * Shows the AI summary of a flight, and lets the crew (or a superuser) ask for it. It is written in the background, so
 * the modal polls while it is pending.
 */
const FlightSummaryModal = forwardRef<FlightSummaryModalHandle, FlightSummaryModalProps>(({ contestantId, subtitle }, ref) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [state, setState] = useState<FlightSummaryState | null>(null);
  const [loading, setLoading] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setState(await fetchFlightSummary(contestantId));
    } catch (err: any) {
      setError(err.message || 'Could not load the summary');
    } finally {
      setLoading(false);
    }
  };

  useImperativeHandle(ref, () => ({
    open: () => {
      dialogRef.current?.showModal();
      setIsOpen(true);
      load();
    },
  }));

  useEffect(() => {
    if (!isOpen || state?.status !== 'pending') return;
    const timer = window.setTimeout(async () => {
      try {
        setState(await fetchFlightSummary(contestantId));
      } catch (err: any) {
        setError(err.message || 'Could not load the summary');
      }
    }, POLL_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [isOpen, state, contestantId]);

  const request = async (regenerate: boolean) => {
    setRequesting(true);
    setError(null);
    try {
      setState(await requestFlightSummary(contestantId, regenerate));
    } catch (err: any) {
      setError(err.message || 'Could not ask for the summary');
    } finally {
      setRequesting(false);
    }
  };

  const pending = state?.status === 'pending';

  return (
    <dialog ref={dialogRef} className="modal" onClose={() => setIsOpen(false)}>
      <div className="modal-box max-w-2xl">
        <form method="dialog">
          <button type="submit" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" aria-label="Close">
            ✕
          </button>
        </form>
        <h3 className="font-bold text-lg flex items-center gap-2">
          <Sparkles size={18} /> AI flight summary
        </h3>
        {subtitle && <p className="text-sm opacity-70">{subtitle}</p>}

        {loading && !state && <p className="py-4 text-sm opacity-70">Loading...</p>}
        {error && <p className="py-2 text-error text-sm">{error}</p>}

        {state && (
          <div className="py-3 space-y-3">
            {state.status === 'done' && (
              <>
                {state.sections?.length > 0 ? (
                  <>
                    <p className="text-lg font-semibold">{state.headline}</p>
                    {state.sections.map((section) => (
                      <div key={section.title} className="rounded-box bg-base-200 p-3">
                        <h4 className="font-semibold mb-1">
                          <span className="mr-2" aria-hidden="true">
                            {section.emoji}
                          </span>
                          {section.title}
                        </h4>
                        <p className="whitespace-pre-line leading-relaxed text-sm">{section.text}</p>
                      </div>
                    ))}
                  </>
                ) : (
                  <div className="whitespace-pre-line leading-relaxed">{state.text}</div>
                )}
                {state.analysis?.legs?.length ? <LegTable analysis={state.analysis} /> : null}
                <p className="text-xs opacity-60">
                  Written by AI from the official score log. The scores and the results list are what count.
                  {state.analysis?.weather_source && (
                    <>
                      {' '}
                      Weather data by{' '}
                      <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" className="link">
                        Open-Meteo.com
                      </a>
                      .
                    </>
                  )}
                </p>
              </>
            )}
            {pending && (
              <p className="flex items-center gap-2 text-sm">
                <span className="loading loading-spinner loading-sm" /> Writing the summary...
              </p>
            )}
            {state.status === 'failed' && <p className="text-sm text-warning">The summary could not be written this time.</p>}
            {state.status === null && state.can_generate && (
              <p className="text-sm">
                Get a short written debrief of this flight: where you lost points and what went well, from the score log.
              </p>
            )}
            {state.reason && !pending && state.status !== 'done' && <p className="text-sm opacity-70">{state.reason}</p>}
            {state.model !== undefined && state.status !== null && (
              <p className="text-xs opacity-60">
                {state.model} · ${state.cost_usd}
                {state.error && ` · ${state.error}`}
              </p>
            )}
          </div>
        )}

        <div className="modal-action">
          {state?.can_generate && (
            <button type="button" className="btn btn-primary btn-sm" disabled={requesting} onClick={() => request(false)}>
              {state.status === 'failed' ? 'Try again' : 'Write summary'}
            </button>
          )}
          {state?.can_regenerate && (
            <button type="button" className="btn btn-outline btn-sm" disabled={requesting} onClick={() => request(true)}>
              Regenerate
            </button>
          )}
          {state?.remaining_today !== null && state?.remaining_today !== undefined && state.can_generate && (
            <span className="text-xs opacity-60 self-center">{state.remaining_today} left today</span>
          )}
        </div>
      </div>
      <form method="dialog" className="modal-backdrop">
        <button>close</button>
      </form>
    </dialog>
  );
});

FlightSummaryModal.displayName = 'FlightSummaryModal';

/** A link-styled button that opens the flight's AI summary. */
export const FlightSummaryButton: React.FC<FlightSummaryModalProps> = (props) => {
  const modalRef = useRef<FlightSummaryModalHandle>(null);
  return (
    <>
      <button type="button" className="link inline-flex items-center gap-1" onClick={() => modalRef.current?.open()}>
        <Sparkles size={14} /> AI summary
      </button>
      <FlightSummaryModal ref={modalRef} {...props} />
    </>
  );
};

export default FlightSummaryModal;
