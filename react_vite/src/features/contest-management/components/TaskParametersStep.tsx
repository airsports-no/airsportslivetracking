import React from 'react';
import { requiredParameters } from '../navigationTaskFlow';

export interface TaskParameters {
    corridor_width?: number;
    rounded_corners?: boolean;
}

interface TaskParametersStepProps {
    taskType: string;
    value: TaskParameters;
    onChange: (value: TaskParameters) => void;
}

const TaskParametersStep: React.FC<TaskParametersStepProps> = ({ taskType, value, onChange }) => {
    const fields = requiredParameters(taskType);

    return (
        <div className="space-y-4">
            {fields.includes('rounded_corners') && (
                <label className="label cursor-pointer justify-start gap-3">
                    <input
                        type="checkbox"
                        className="checkbox"
                        checked={value.rounded_corners ?? false}
                        onChange={e => onChange({ ...value, rounded_corners: e.target.checked })}
                    />
                    <span className="label-text">Rounded corners</span>
                </label>
            )}
            {fields.includes('rounded_corners') && value.rounded_corners && (
                <p className="text-sm text-warning">
                    Using rounded corners will not look good with sharp corners or short legs. Each leg should be at
                    least three or four times as long as the corridor width, and turns should not be much more than
                    90 degrees, especially for a wide corridor.
                </p>
            )}
            {fields.includes('corridor_width') && (
                <label className="form-control w-full">
                    <div className="label"><span className="label-text">Corridor width (NM)</span></div>
                    <input
                        type="number"
                        step="0.1"
                        className="input input-bordered w-full"
                        value={value.corridor_width ?? ''}
                        onChange={e => onChange({ ...value, corridor_width: parseFloat(e.target.value) })}
                    />
                </label>
            )}
        </div>
    );
};

export default TaskParametersStep;
