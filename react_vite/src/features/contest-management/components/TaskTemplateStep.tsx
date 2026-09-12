import React, { useEffect, useState } from 'react';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchTaskTemplates } from '../api';
import { TaskTemplateChoice, TaskTemplateGroup } from '../types';

interface TaskTemplateStepProps {
    editableRouteId?: number;
    value: TaskTemplateChoice | null;
    onChange: (template: TaskTemplateChoice) => void;
}

interface GroupedOption {
    label: string;
    options: { value: string; label: string; template: TaskTemplateChoice }[];
}

const TaskTemplateStep: React.FC<TaskTemplateStepProps> = ({ editableRouteId, value, onChange }) => {
    const [groups, setGroups] = useState<TaskTemplateGroup[]>([]);
    const [message, setMessage] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        fetchTaskTemplates(editableRouteId)
            .then(response => {
                setGroups(response.groups);
                setMessage(response.no_compatible_task_types_message);
            })
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, [editableRouteId]);

    if (loading) return <span className="loading loading-spinner"></span>;
    if (error) return <div className="alert alert-error">{error}</div>;

    const options: GroupedOption[] = groups.map(group => ({
        label: group.group,
        options: group.templates.map(template => ({ value: template.value, label: template.label, template })),
    }));

    return (
        <div>
            <label className="form-control w-full">
                <div className="label"><span className="label-text">Task type</span></div>
                <Select
                    options={options}
                    value={value ? { value: value.value, label: value.label, template: value } : null}
                    onChange={selected => selected && onChange(selected.template)}
                    placeholder="Choose a task type"
                    classNamePrefix="my-react-select"
                    styles={selectStyles}
                />
            </label>
            {message && <p className="text-sm text-warning mt-2">{message}</p>}
        </div>
    );
};

export default TaskTemplateStep;
