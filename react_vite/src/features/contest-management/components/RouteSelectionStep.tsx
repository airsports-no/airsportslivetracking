import React, { useEffect, useState } from 'react';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchEditableRoutes } from '../../route-editor/api';
import { Route } from '../../../types';

interface RouteSelectionStepProps {
    subtypeKey: string;
    value: number | null;
    onChange: (routeId: number) => void;
}

// Client-side compatibility filtering, matching the wizards' `compatible_task_types__contains`
// queryset filter - a UX affordance only. The server (NavigationTaskEditableRoutReferenceSerialiser
// via assert_route_compatible_with_task_type) re-checks this regardless of what's offered here.
const RouteSelectionStep: React.FC<RouteSelectionStepProps> = ({ subtypeKey, value, onChange }) => {
    const [routes, setRoutes] = useState<Route[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setLoading(true);
        fetchEditableRoutes()
            .then(setRoutes)
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <span className="loading loading-spinner"></span>;
    if (error) return <div className="alert alert-error">{error}</div>;

    const compatibleRoutes = routes.filter(route => route.compatible_task_types.includes(subtypeKey));

    return (
        <div>
            <label className="form-control w-full">
                <div className="label"><span className="label-text">Route</span></div>
                <Select
                    options={compatibleRoutes.map(route => ({ value: route.id, label: route.name }))}
                    value={value ? { value, label: compatibleRoutes.find(route => route.id === value)?.name ?? '' } : null}
                    onChange={selected => selected && onChange(selected.value)}
                    placeholder="Choose a route"
                    classNamePrefix="my-react-select"
                    styles={selectStyles}
                />
            </label>
            {compatibleRoutes.length === 0 && (
                <p className="text-sm text-warning mt-2">
                    None of your routes support this task type yet. Edit a route to add what's missing, or create a new one.
                </p>
            )}
        </div>
    );
};

export default RouteSelectionStep;
