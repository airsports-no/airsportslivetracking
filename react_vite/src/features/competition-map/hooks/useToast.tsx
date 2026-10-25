import React, { useState, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';
import { getPortalRoot } from '../../../utils/portalRoot';

export interface ToastMessage {
  id: string;
  message: string;
  html?: boolean;
  type: 'success' | 'error' | 'info' | 'warning';
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  removeToast: (id: string) => void;
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, removeToast }) => {
  // On a phone the top is the docked panel: the notices go along the bottom, above the bar, and stay small.
  return createPortal(
    <div className="toast toast-end toast-bottom sm:toast-top z-[9999] max-sm:bottom-24 max-sm:left-2 max-sm:w-auto">
      {toasts.map(toast => (
        <div key={toast.id} className={`alert alert-${toast.type} shadow-lg max-sm:py-2 max-sm:text-sm`}>
          <div>
            {toast.html ? <span dangerouslySetInnerHTML={{ __html: toast.message }} /> : <span>{toast.message}</span>}
          </div>
          <div className="flex-none">
            <button className="btn btn-sm btn-ghost" onClick={() => removeToast(toast.id)}>✕</button>
          </div>
        </div>
      ))}
    </div>,
    getPortalRoot()
  );
};

export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const toastId = useRef(0);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastMessage['type'] = 'info', duration: number = 15000, html: boolean = false) => {
    const id = String(toastId.current++);
    const newToast: ToastMessage = { id, message, type, html };
    setToasts(prev => [...prev, newToast]);

    setTimeout(() => {
      removeToast(id);
    }, duration);
  }, [removeToast]);

  return { toasts, showToast, removeToast, ToastContainer };
}
