import React, { useEffect } from 'react';
import { Wand2, X } from 'lucide-react';
import { getVisibleTaskTemplates, groupTemplates } from '../taskTemplates';

interface TaskChoiceModalProps {
  visibleTaskTypeGroups: string[];
  // The user chose a task: the guide starts on it.
  onChoose: (templateId: string) => void;
  // "Build without a guide", the close button and Esc.
  onClose: () => void;
}

// What a new route opens with: the task to build the route for, over the map. Closing it leaves the editor as it is
// without a guide.
const TaskChoiceModal: React.FC<TaskChoiceModalProps> = ({ visibleTaskTypeGroups, onChoose, onClose }) => {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [onClose]);

  const grouped = groupTemplates(getVisibleTaskTemplates(visibleTaskTypeGroups));

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="task-choice-title"
        className="relative flex max-h-full w-full max-w-2xl flex-col rounded-box bg-base-100 p-5 shadow-xl"
      >
        <button
          type="button"
          onClick={onClose}
          className="btn btn-sm btn-circle btn-ghost absolute right-2 top-2"
          aria-label="Close"
          title="Close"
        >
          <X size={16} />
        </button>
        <h2 id="task-choice-title" className="flex items-center gap-2 text-lg font-bold">
          <Wand2 size={18} /> What is this route for?
        </h2>
        <p className="text-sm opacity-70">The guide then takes you through the steps that task needs.</p>

        <div className="mt-3 space-y-4 overflow-y-auto pr-1">
          {grouped.map(([group, templates]) => (
            <div key={group} className="space-y-2">
              <h3 className="text-xs font-bold uppercase text-gray-500">{group}</h3>
              <div className="grid gap-2 sm:grid-cols-2">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    type="button"
                    onClick={() => onChoose(template.id)}
                    className="rounded-lg border border-base-300 p-3 text-left transition hover:border-primary hover:bg-base-200"
                  >
                    <div className="text-sm font-semibold">{template.label}</div>
                    <div className="mt-1 text-xs text-gray-500">{template.description}</div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 flex justify-end border-t border-base-200 pt-3">
          <button type="button" onClick={onClose} className="btn btn-outline btn-sm">
            Build without a guide
          </button>
        </div>
      </div>
    </div>
  );
};

export default TaskChoiceModal;
