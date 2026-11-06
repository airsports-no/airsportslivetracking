import React, { forwardRef, useImperativeHandle, useRef, useState } from 'react';
import { generateSpeedMaps, waitForGeneratedPdf } from '../api';
import { addSpeeds, MAX_SPEEDS, speedMapsProblem, speedsInRange } from '../preparedMaps';

export interface GenerateSpeedMapsModalHandle {
  open: () => void;
}

interface GenerateSpeedMapsModalProps {
  contestId: number;
  navigationTaskId: number;
  /** The speeds to start from, such as those the task's contestants fly at */
  defaultSpeeds: number[];
  defaultWindSpeed: number;
  defaultWindDirection: number;
}

type State = 'idle' | 'pending' | 'complete' | 'error';

/**
 * Makes the flight order's map for a range of air speeds in one wind as a single PDF, to print when no printer is at hand
 * on the day. The maps are made as the flight order configuration says (page, scale, map source, minute marks).
 */
const GenerateSpeedMapsModal = forwardRef<GenerateSpeedMapsModalHandle, GenerateSpeedMapsModalProps>(
  ({ contestId, navigationTaskId, defaultSpeeds, defaultWindSpeed, defaultWindDirection }, ref) => {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const cancelled = useRef(false);
    const [speeds, setSpeeds] = useState<number[]>([]);
    const [single, setSingle] = useState('');
    const [rangeFrom, setRangeFrom] = useState('70');
    const [rangeTo, setRangeTo] = useState('110');
    const [rangeStep, setRangeStep] = useState('5');
    const [windSpeed, setWindSpeed] = useState('0');
    const [windDirection, setWindDirection] = useState('0');
    const [state, setState] = useState<State>('idle');
    const [error, setError] = useState<string | null>(null);
    const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
    const [warning, setWarning] = useState<string | null>(null);

    useImperativeHandle(ref, () => ({
      open: () => {
        cancelled.current = false;
        setSpeeds(addSpeeds([], defaultSpeeds));
        setWindSpeed(String(defaultWindSpeed));
        setWindDirection(String(defaultWindDirection));
        setState('idle');
        setError(null);
        setDownloadUrl(null);
        setWarning(null);
        dialogRef.current?.showModal();
      },
    }));

    const problem = speedMapsProblem(speeds, parseFloat(windSpeed), parseFloat(windDirection));

    const handleClose = () => {
      // The maps are still made, but nobody waits for them
      cancelled.current = true;
      dialogRef.current?.close();
    };

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (problem) return;
      setState('pending');
      setError(null);
      try {
        const { status_check_url } = await generateSpeedMaps(contestId, navigationTaskId, {
          speeds,
          wind_speed: parseFloat(windSpeed),
          wind_direction: parseFloat(windDirection),
        });
        const result = await waitForGeneratedPdf(status_check_url, () => cancelled.current);
        if (!result) return;
        setState('complete');
        setWarning(result.warning || null);
        setDownloadUrl(result.url || null);
        // The download starts by itself; the link is for a browser that blocks it
        if (result.url) window.location.href = result.url;
      } catch (err: any) {
        if (cancelled.current) return;
        setState('error');
        setError(err.message || 'Failed to make the maps');
      }
    };

    return (
      <dialog ref={dialogRef} className="modal" onClose={() => { cancelled.current = true; }}>
        <div className="modal-box max-w-xl">
          <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={handleClose} aria-label="Close">
            ✕
          </button>
          <h3 className="font-bold text-lg mb-1">Maps for several speeds</h3>
          <p className="text-sm opacity-70 mb-3">
            One PDF with the flight order&apos;s map for each speed in the same wind, one map to a page, for printing in advance.
            The maps are made as the flight order configuration says.
          </p>

          {state === 'idle' && (
            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
              <div>
                <span className="label-text text-xs">Speeds (knots), {speeds.length} of at most {MAX_SPEEDS}</span>
                <div className="flex flex-wrap gap-1 mt-1 min-h-8" aria-label="Chosen speeds">
                  {speeds.map((speed) => (
                    <span key={speed} className="badge badge-lg gap-1">
                      {speed} kt
                      <button
                        type="button"
                        className="btn btn-ghost btn-xs btn-circle"
                        onClick={() => setSpeeds((previous) => previous.filter((item) => item !== speed))}
                        aria-label={`Remove ${speed} knots`}
                      >
                        ✕
                      </button>
                    </span>
                  ))}
                  {speeds.length === 0 && <span className="text-sm opacity-60">No speeds yet: add some below.</span>}
                </div>
              </div>

              <div className="flex items-end gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">One speed</span>
                  <input type="number" min={20} max={400} className="input input-bordered input-sm w-full" value={single} onChange={(e) => setSingle(e.target.value)} />
                </label>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={!Number.isFinite(parseFloat(single))}
                  onClick={() => {
                    setSpeeds((previous) => addSpeeds(previous, [parseFloat(single)]));
                    setSingle('');
                  }}
                >
                  Add
                </button>
              </div>

              <div className="flex items-end gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">From</span>
                  <input type="number" className="input input-bordered input-sm w-full" value={rangeFrom} onChange={(e) => setRangeFrom(e.target.value)} />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">To</span>
                  <input type="number" className="input input-bordered input-sm w-full" value={rangeTo} onChange={(e) => setRangeTo(e.target.value)} />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Step</span>
                  <input type="number" min={0.1} step="any" className="input input-bordered input-sm w-full" value={rangeStep} onChange={(e) => setRangeStep(e.target.value)} />
                </label>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={speedsInRange(parseFloat(rangeFrom), parseFloat(rangeTo), parseFloat(rangeStep)).length === 0}
                  onClick={() =>
                    setSpeeds((previous) =>
                      addSpeeds(previous, speedsInRange(parseFloat(rangeFrom), parseFloat(rangeTo), parseFloat(rangeStep)))
                    )
                  }
                >
                  Add range
                </button>
              </div>

              <div className="divider my-0 text-xs">Wind</div>
              <div className="flex gap-2">
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Direction it blows from (°)</span>
                  <input type="number" min={0} max={360} className="input input-bordered input-sm w-full" value={windDirection} onChange={(e) => setWindDirection(e.target.value)} />
                </label>
                <label className="form-control flex-1">
                  <span className="label-text text-xs">Speed (knots)</span>
                  <input type="number" min={0} max={100} className="input input-bordered input-sm w-full" value={windSpeed} onChange={(e) => setWindSpeed(e.target.value)} />
                </label>
              </div>

              {problem && speeds.length > 0 && <p className="text-sm text-warning">{problem}</p>}
              <div className="modal-action mt-1">
                <button type="submit" className="btn btn-primary btn-sm" disabled={problem !== null}>
                  Make {speeds.length} {speeds.length === 1 ? 'map' : 'maps'}
                </button>
              </div>
            </form>
          )}

          {state === 'pending' && (
            <div className="py-4 flex flex-col gap-2" role="status">
              <p className="flex items-center gap-2">
                <span className="loading loading-spinner loading-sm" /> Making {speeds.length} {speeds.length === 1 ? 'map' : 'maps'}…
              </p>
              <p className="text-sm opacity-70">
                This takes about ten to twenty seconds a map. The document is downloaded when it is ready; you can close this and
                it will be made anyway, but it will not be downloaded.
              </p>
            </div>
          )}

          {state === 'complete' && (
            <div className="py-4 flex flex-col gap-2" role="status">
              <p className="text-success">The maps are ready{downloadUrl ? ' and are being downloaded.' : '.'}</p>
              {warning && <p className="text-sm text-warning">{warning}</p>}
              {downloadUrl && (
                <a className="link" href={downloadUrl}>
                  Download again
                </a>
              )}
            </div>
          )}

          {state === 'error' && (
            <div className="py-4 flex flex-col gap-2">
              <p className="text-error">{error}</p>
              <button type="button" className="btn btn-sm self-start" onClick={() => setState('idle')}>
                Back
              </button>
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

GenerateSpeedMapsModal.displayName = 'GenerateSpeedMapsModal';

export default GenerateSpeedMapsModal;
