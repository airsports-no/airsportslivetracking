import React, { useState, useEffect } from 'react';
import { Test, Task } from '../../store/contestResultsStore';

interface TestModalProps {
  show: boolean;
  onClose: () => void;
  onSubmit: (test: Test) => void;
  test?: Test | null;
  task?: Task | null;
}

export const TestModal: React.FC<TestModalProps> = ({ show, onClose, onSubmit, test, task }) => {
  const [name, setName] = useState('');
  const [heading, setHeading] = useState('');
  const [weight, setWeight] = useState(1.0);
  const [sorting, setSorting] = useState('asc');

  useEffect(() => {
    if (test) {
      setName(test.name);
      setHeading(test.heading);
      setWeight(test.weight || 1.0);
      setSorting(test.sorting || 'asc');
    } else {
      // Reset for new test
      setName('');
      setHeading('');
      setWeight(1.0);
      setSorting('asc');
    }
  }, [test, show]);

  const handleSubmit = () => {
    const isNavigationTask = test?.navigation_task !== null && test?.navigation_task !== undefined;
    const editedTest: Test = {
      ...test,
      id: test?.id || 0,
      name,
      heading: name, // Ensure heading is always the same as name
      weight,
      sorting: isNavigationTask ? test.sorting : sorting,
      index: test?.index || 0,
      task: task?.id || 0,
      navigation_task: test?.navigation_task || null,
      navigation_task_link: test?.navigation_task_link || null,
      teamtestscore_set: test?.teamtestscore_set || [],
    };
    onSubmit(editedTest);
  };

  if (!show) {
    return null;
  }

  const isNavigationTask = test?.navigation_task !== null && test?.navigation_task !== undefined;

  return (
    <dialog open className="modal">
      <div className="modal-box">
        <h3 className="font-bold text-lg">{test ? 'Edit Test' : 'Add New Test'}</h3>

        <div className="form-control">
          <label className="label">
            <span className="label-text">Test Name</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input input-bordered"
            disabled={isNavigationTask}
          />
        </div>

        <div className="form-control">
          <label className="label">
            <span className="label-text">Test Weight</span>
          </label>
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(parseFloat(e.target.value))}
            step="0.1"
            className="input input-bordered"
          />
        </div>

        {!isNavigationTask && (
          <div className="form-control">
            <label className="label">
              <span className="label-text">Score Sorting Direction</span>
            </label>
            <select
              value={sorting}
              onChange={(e) => setSorting(e.target.value)}
              className="select select-bordered"
            >
              <option value="asc">Ascending</option>
              <option value="desc">Descending</option>
            </select>
          </div>
        )}

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
