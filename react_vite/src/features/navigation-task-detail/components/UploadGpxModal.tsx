import React, { forwardRef, useState } from 'react';
import { uploadGpxTrack } from '../api';

interface UploadGpxModalProps {
  contestId: number;
  navigationTaskId: number;
  contestantId: number;
  onUploaded: () => void;
}

const readFileAsBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      // readAsDataURL prefixes with "data:<mime>;base64," - the API wants just the base64 body.
      const commaIndex = result.indexOf(',');
      resolve(commaIndex >= 0 ? result.slice(commaIndex + 1) : result);
    };
    reader.onerror = () => reject(reader.error || new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });

const UploadGpxModal = forwardRef<HTMLDialogElement, UploadGpxModalProps>(
  ({ contestId, navigationTaskId, contestantId, onUploaded }, ref) => {
    const [file, setFile] = useState<File | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (event: React.FormEvent) => {
      event.preventDefault();
      if (!file) return;
      setBusy(true);
      setError(null);
      try {
        const base64 = await readFileAsBase64(file);
        await uploadGpxTrack(contestId, navigationTaskId, contestantId, base64);
        setFile(null);
        (ref as React.RefObject<HTMLDialogElement>).current?.close();
        onUploaded();
      } catch (err: any) {
        setError(err.message || 'Failed to upload GPX track');
      } finally {
        setBusy(false);
      }
    };

    return (
      <dialog ref={ref} className="modal">
        <div className="modal-box">
          <form method="dialog">
            <button type="button" className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2" onClick={() => (ref as React.RefObject<HTMLDialogElement>).current?.close()}>
              ✕
            </button>
          </form>
          <h3 className="font-bold text-lg">Upload GPX track</h3>
          <p className="py-2 text-sm text-gray-500">
            Resets this contestant's existing track/score and replaces it with the uploaded FlightContest GPX file.
          </p>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <input
              type="file"
              accept=".gpx"
              className="file-input file-input-bordered file-input-sm w-full"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            {error && <p className="text-error text-sm">{error}</p>}
            <div className="modal-action">
              <button type="submit" className="btn btn-primary btn-sm" disabled={!file || busy}>
                {busy ? 'Uploading...' : 'Upload'}
              </button>
            </div>
          </form>
        </div>
        <form method="dialog" className="modal-backdrop">
          <button>close</button>
        </form>
      </dialog>
    );
  }
);

UploadGpxModal.displayName = 'UploadGpxModal';

export default UploadGpxModal;
