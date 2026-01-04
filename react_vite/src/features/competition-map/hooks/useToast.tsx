import React, { useState, useCallback, useRef } from 'react';
import { createPortal } from 'react-dom';

export interface ToastMessage {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

interface ToastContainerProps {
  toasts: ToastMessage[];
  removeToast: (id: string) => void;
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, removeToast }) => {
  return createPortal(
    <div className="toast toast-top toast-end z-[9999]">
      {toasts.map(toast => (
        <div key={toast.id} className={`alert alert-${toast.type} shadow-lg`}>
          <div>
            <span>{toast.message}</span>
          </div>
          <div className="flex-none">
            <button className="btn btn-sm btn-ghost" onClick={() => removeToast(toast.id)}>✕</button>
          </div>
        </div>
      ))}
    </div>,
    document.body
  );
};

export function useToast() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const toastId = useRef(0);

  const showToast = useCallback((message: string, type: ToastMessage['type'] = 'info', duration: number = 5000) => {
    const id = String(toastId.current++);
    const newToast: ToastMessage = { id, message, type };
    setToasts(prev => [...prev, newToast]);

    setTimeout(() => {
      removeToast(id);
    }, duration);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  }, []);

  return { toasts, showToast, removeToast, ToastContainer };
}
