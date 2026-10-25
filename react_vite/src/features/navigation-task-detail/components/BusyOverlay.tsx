import React from 'react';
import { createPortal } from 'react-dom';
import { getPortalRoot } from '../../../utils/portalRoot';

/**
 * Covers the page with a spinner and a message while something slow runs (deleting a task with many contestants
 * takes half a minute), so it is clear that the click did something and that the page should be left alone.
 */
const BusyOverlay: React.FC<{ message: string }> = ({ message }) =>
  createPortal(
    <div
      className="fixed inset-0 z-[10000] flex flex-col items-center justify-center gap-4 bg-base-100/80 backdrop-blur-sm"
      role="alert"
      aria-live="assertive"
      aria-busy="true"
    >
      <span className="loading loading-spinner loading-lg text-primary" aria-hidden="true" />
      <p className="text-lg font-semibold">{message}</p>
      <p className="text-sm opacity-70">This can take a while for a task with many contestants.</p>
    </div>,
    getPortalRoot(),
  );

export default BusyOverlay;
