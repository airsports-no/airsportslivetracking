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
    const overlay = overlayRef.current;
    const made: HTMLElement[] = [];
    const makeInert = (element: Element) => {
      if (element === overlay || !(element instanceof HTMLElement) || element.inert) return;
      if (['SCRIPT', 'STYLE', 'LINK'].includes(element.tagName)) return;
      element.inert = true;
      made.push(element);
    };
    for (const element of Array.from(document.body.children)) {
      // The portal root holds this overlay and other portals (a toast's dismiss button): its other children go inert
      // one by one, not the whole root.
      if (element === portalRoot) Array.from(portalRoot.children).forEach(makeInert);
      else makeInert(element);
    }
    // The control that had the focus (the one that started the deletion) gets it back when the overlay goes, if it is
    // still there: after a failed deletion the keyboard user is where they were.
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    overlay?.focus();
    return () => {
      made.forEach(element => { element.inert = false; });
      if (previous && previous.isConnected && previous !== document.body) previous.focus();
    };
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
