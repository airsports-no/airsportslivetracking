import React, { useState, useEffect } from 'react';
import { Task } from '../../store/contestResultsStore';

interface TaskModalProps {
  show: boolean;
  onClose: () => void;
  onSubmit: (task: Task) => void;
  task?: Task | null;
}

export const TaskModal: React.FC<TaskModalProps> = ({ show, onClose, onSubmit, task }) => {
  const [name, setName] = useState('');
  const [heading, setHeading] = useState('');
  const [weight, setWeight] = useState(1.0);
  const [autosumScores, setAutosumScores] = useState(true);
  const [sortingDirection, setSortingDirection] = useState('asc');

  useEffect(() => {
    if (task) {
      setName(task.name);
      setHeading(task.heading);
      setWeight(task.weight || 1.0);
      setAutosumScores(task.autosum_scores !== undefined ? task.autosum_scores : true);
      setSortingDirection(task.summary_score_sorting_direction || 'asc');
    } else {
      // Reset for new task
      setName('');
      setHeading('');
      setWeight(1.0);
      setAutosumScores(true);
      setSortingDirection('asc');
    }
  }, [task, show]);

  const handleSubmit = () => {
    const editedTask: Task = {
      ...task,
      id: task?.id || 0,
      name,
      heading,
      weight,
      autosum_scores: autosumScores,
      summary_score_sorting_direction: sortingDirection,
      index: task?.index || 0,
      tasksummary_set: task?.tasksummary_set || [],
      tasktest_set: task?.tasktest_set || [],
      contest: task?.contest || 0,
    };
    onSubmit(editedTask);
  };

  if (!show) {
    return null;
  }

  return (
    <dialog open className="modal">
      <div className="modal-box">
        <h3 className="font-bold text-lg">{task ? 'Edit Task' : 'Add New Task'}</h3>

        <div className="form-control">
          <label className="label">
            <span className="label-text">Task Name</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              if (!heading) setHeading(e.target.value);
            }}
            className="input input-bordered"
          />
        </div>

        <div className="form-control">
          <label className="label cursor-pointer">
            <span className="label-text">Autosum test scores</span>
            <input
              type="checkbox"
              checked={autosumScores}
              onChange={(e) => setAutosumScores(e.target.checked)}
              className="checkbox"
            />
          </label>
        </div>

        <div className="form-control">
          <label className="label">
            <span className="label-text">Task Weight</span>
          </label>
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(parseFloat(e.target.value))}
            step="0.1"
            className="input input-bordered"
          />
        </div>

        <div className="form-control">
          <label className="label">
            <span className="label-text">Score Sorting Direction</span>
          </label>
          <select
            value={sortingDirection}
            onChange={(e) => setSortingDirection(e.target.value)}
            className="select select-bordered"
          >
            <option value="asc">Ascending</option>
            <option value="desc">Descending</option>
          </select>
        </div>

        <div className="modal-action">
          <button onClick={handleSubmit} className="btn btn-primary">
            Submit
          </button>
          <button onClick={onClose} className="btn">
            Close
          </button>
        </div>
      </div>
    </dialog>
  );
};
