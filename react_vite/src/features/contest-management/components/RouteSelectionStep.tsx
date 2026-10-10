import React, { useEffect, useState } from 'react';
import Select from 'react-select';
import { selectStyles } from '../../../utils/selectStyles';
import { fetchEditableRoutes } from '../../route-editor/api';
import { Route } from '../../../types';
import appRoutes from '../../../routes.json';

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

    const loadRoutes = () => {
        setLoading(true);
        setError(null);
        fetchEditableRoutes()
            .then(setRoutes)
            .catch(err => setError((err as Error).message))
            .finally(() => setLoading(false));
    };

    useEffect(loadRoutes, []);

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
                <div className="alert alert-warning mt-3 text-sm items-start">
                    <div className="flex-1">
                        <p>
                            {routes.length === 0
                                ? 'You have no routes yet. A route is the flight path of a task: draw one in the route editor or import a file.'
                                : "None of your routes support this task type yet. Edit a route to add what's missing, or create a new one."}
                        </p>
                        <p className="mt-1 opacity-80">
                            The route editor opens in a new tab so you keep your place here. Come back and press <em>Refresh routes</em> when you have saved it.
                        </p>
                        <div className="flex flex-wrap gap-2 mt-2">
                            <a className="btn btn-xs btn-primary" href={`/${appRoutes.ROUTE_EDITOR_CREATE}`} target="_blank" rel="noreferrer">Create a route</a>
                            <a className="btn btn-xs btn-outline" href={`/${appRoutes.ROUTE_EDITOR_LIST}`} target="_blank" rel="noreferrer">My routes / import</a>
                            <button type="button" className="btn btn-xs btn-outline" onClick={loadRoutes}>Refresh routes</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default RouteSelectionStep;
