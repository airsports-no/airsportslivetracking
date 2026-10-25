import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getPortalRoot } from '../../utils/portalRoot';

/**
 * Covers the page with a spinner and a message while something slow runs (deleting a task with many contestants
 * takes half a minute), so it is clear that the click did something and that the page should be left alone.
 */
const BusyOverlay: React.FC<{ message: string; detail?: string }> = ({
  message,
  detail = 'This can take a while for a task with many contestants.',
}) => {
  const overlayRef = useRef<HTMLDivElement>(null);

  // Everything else on the page is made inert while this is up (no clicks, no keys, no focus), and the focus is moved
  // here, so nothing can be started underneath a deletion.
  useEffect(() => {
    const portalRoot = getPortalRoot();
    const made: HTMLElement[] = [];
    for (const element of Array.from(document.body.children)) {
      if (element === portalRoot || !(element instanceof HTMLElement) || element.inert) continue;
      if (['SCRIPT', 'STYLE', 'LINK'].includes(element.tagName)) continue;
      element.inert = true;
      made.push(element);
    }
    overlayRef.current?.focus();
    return () => made.forEach(element => { element.inert = false; });
  }, []);

  return createPortal(
    <div
      ref={overlayRef}
      tabIndex={-1}
      className="fixed inset-0 z-[10000] flex flex-col items-center justify-center gap-4 bg-base-100 outline-none"
      role="alertdialog"
      aria-modal="true"
      aria-live="assertive"
      aria-busy="true"
      aria-label={message}
    >
      <span className="loading loading-spinner loading-lg text-primary" aria-hidden="true" />
      <p className="text-lg font-semibold">{message}</p>
      <p className="text-sm opacity-70">{detail}</p>
    </div>,
    getPortalRoot(),
  );
};

export default BusyOverlay;
