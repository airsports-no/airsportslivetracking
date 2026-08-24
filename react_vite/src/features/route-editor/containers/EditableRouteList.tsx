import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/basicComponents";
import { Route } from "../../../types";
import { MoreVertical, Plus, Copy, Shield, Trash2 } from "lucide-react";
import { fetchEditableRoutes, fetchTaskSubtypeCatalog, TaskCompatibilitySubtype } from "../api";
import { isTaskSubtypeVisible } from "../taskTemplates";
import { reverse } from "../../../urls";
import routes from "../../../routes.json";

const formatRouteLength = (meters: number) => `${(meters / 1852).toFixed(2)} NM`;

const getEditorSummary = (route: Route) => {
    if (route.editors.length === 0) return "No named editors";
    return route.editors
        .slice(0, 2)
        .map((editor) => `${editor.first_name} ${editor.last_name}`.trim() || editor.email)
        .join(", ");
};

// Caps the number of task-type badges shown per tile before collapsing the rest into a "+N" badge,
// so a route compatible with many legacy families doesn't dominate the card.
const MAX_TASK_TYPE_BADGES = 3;

const EditableRouteTile: React.FC<{ route: Route; subtypeLabels: Record<string, string>; visibleSubtypeKeys: Set<string> }> = ({ route, subtypeLabels, visibleSubtypeKeys }) => {
    const hasThumbnail = Boolean(route.thumbnail);
    const managePermissionsLabel = route.editors.length > 1 ? `${route.editors.length} editors` : route.is_editor ? "You can edit" : "Shared route";
    const titleClassName = "card-title text-base sm:text-lg leading-tight line-clamp-2 hover:underline break-words";
    const badgeClassName = "badge badge-outline";

    // Prefer the route creator's declared intent; an undeclared route (empty intended_task_types)
    // falls back to showing everything the route's content actually supports. Never show a CIMA
    // type the viewer doesn't have access to, even if the route happens to support it.
    const taskTypeKeys = ((route.intended_task_types?.length ? route.intended_task_types : route.compatible_task_types) ?? [])
        .filter((key) => visibleSubtypeKeys.has(key));
    const taskTypeLabels = taskTypeKeys.map((key) => subtypeLabels[key] ?? key);
    const shownTaskTypeLabels = taskTypeLabels.slice(0, MAX_TASK_TYPE_BADGES);
    const hiddenTaskTypeCount = taskTypeLabels.length - shownTaskTypeLabels.length;

    return (
        <div className={`card shadow-xl border border-base-300 overflow-hidden h-[300px] ${hasThumbnail ? "image-full bg-base-300" : "bg-base-200"}`}>
            {hasThumbnail && (
                <figure>
                    <img
                        src={route.thumbnail}
                        alt={`${route.name} thumbnail`}
                        className="w-full h-full object-cover"
                        loading="lazy"
                        decoding="async"
                    />
                </figure>
            )}
            <div className="card-body p-4 flex flex-col h-full">
                <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                        <Link
                            to={`edit/${route.id}`}
                            className={titleClassName}
                        >
                            {route.name}
                        </Link>
                        <div className="text-xs mt-2 text-base-content/70">
                            {managePermissionsLabel}
                        </div>
                    </div>
                    <div className="dropdown dropdown-bottom dropdown-end shrink-0">
                        <label tabIndex={0} className="btn btn-circle btn-xs btn-ghost">
                            <MoreVertical size={16} />
                        </label>
                        <ul tabIndex={0} className="dropdown-content z-[100] menu p-2 shadow-2xl bg-base-100 rounded-box w-56 border border-base-300">
                            <li>
                                <a href={reverse("editableroute_createnavigationtask", route.id)} className="flex items-center gap-3 py-3">
                                    <Plus size={16} className="text-primary" />
                                    <span className="font-medium">Create Navigation Task</span>
                                </a>
                            </li>
                            <li>
                                <a href={reverse("editableroute_copy", route.id)} className="flex items-center gap-3 py-3">
                                    <Copy size={16} />
                                    <span>Duplicate Route</span>
                                </a>
                            </li>
                            <li>
                                <a href={reverse("editableroute_permissions_list", route.id)} className="flex items-center gap-3 py-3">
                                    <Shield size={16} />
                                    <span>Manage Permissions</span>
                                </a>
                            </li>
                            <div className="divider my-0 opacity-50"></div>
                            <li>
                                <a href={reverse("editableroute_delete", route.id)} className="flex items-center gap-3 py-3 text-error hover:bg-error/10">
                                    <Trash2 size={16} />
                                    <span className="font-medium">Delete Route</span>
                                </a>
                            </li>
                        </ul>
                    </div>
                </div>

                <div className="mt-auto space-y-3">
                    <div className="flex flex-wrap gap-2">
                        <div className={badgeClassName}>{route.number_of_waypoints} waypoints</div>
                        <div className={badgeClassName}>{formatRouteLength(route.route_length)}</div>
                        {route.is_editor && <div className={badgeClassName}>Editor</div>}
                    </div>

                    {taskTypeLabels.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                            {shownTaskTypeLabels.map((label) => (
                                <div key={label} className="badge badge-sm badge-primary badge-outline">{label}</div>
                            ))}
                            {hiddenTaskTypeCount > 0 && (
                                <div className="badge badge-sm badge-ghost" title={taskTypeLabels.slice(MAX_TASK_TYPE_BADGES).join(', ')}>
                                    +{hiddenTaskTypeCount}
                                </div>
                            )}
                        </div>
                    )}

                    <div className="rounded-lg p-3 backdrop-blur-sm bg-base-100 text-base-content border border-base-300">
                        <div className="text-xs font-semibold uppercase tracking-wide opacity-80 mb-1">Editors</div>
                        <div className="text-sm line-clamp-2">{getEditorSummary(route)}</div>
                    </div>

                    <div className="flex gap-2">
                        <Link to={`edit/${route.id}`} className="btn btn-primary btn-sm flex-1">
                            Edit route
                        </Link>
                        <a href={reverse("editableroute_createnavigationtask", route.id)} className="btn btn-secondary btn-sm">
                            Task
                        </a>
                    </div>
                </div>
            </div>
        </div>
    );
};

export const EditableRouteList = () => {
    const [data, setData] = useState<Route[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAll, setShowAll] = useState(false);
    const [subtypeCatalog, setSubtypeCatalog] = useState<TaskCompatibilitySubtype[]>([]);
    const [taskTypeFilter, setTaskTypeFilter] = useState('');

    useEffect(() => {
        fetchEditableRoutes()
            .then((routes: Route[]) => {
                setData(routes);
                setLoading(false);
            })
            .catch(() => setLoading(false));
        // The subtype catalog (key -> display_name/group) is fixed regardless of any specific
        // route's content, so it's fetched once for the whole list rather than per tile.
        fetchTaskSubtypeCatalog()
            .then(setSubtypeCatalog)
            .catch((err) => console.error('Failed to load task type catalog', err));
    }, []);

    const subtypeLabels = useMemo(
        () => Object.fromEntries(subtypeCatalog.map((subtype) => [subtype.key, subtype.display_name])),
        [subtypeCatalog],
    );

    const visibleTaskTypeGroups = useMemo(() => {
        const groups = document.configuration.visibleTaskTypeGroups;
        if (Array.isArray(groups) && groups.length > 0) {
            return groups;
        }
        return document.configuration.showCimaTaskTypes ? ['legacy', 'cima'] : ['legacy'];
    }, []);

    // Never show or offer filtering by a CIMA task type the viewer doesn't have access to, even
    // if a route happens to support it.
    const visibleSubtypeKeys = useMemo(
        () => new Set(subtypeCatalog.filter((subtype) => isTaskSubtypeVisible(subtype.group, subtype.key, visibleTaskTypeGroups)).map((subtype) => subtype.key)),
        [subtypeCatalog, visibleTaskTypeGroups],
    );

    // Only offer filtering by task types that at least one currently-visible route actually
    // supports - this is meant to help once there are many routes, not to advertise every task
    // type CIMA defines regardless of relevance to this account's routes.
    const taskTypeFilterOptions = useMemo(() => {
        const keysInUse = new Set(data.flatMap((route) => route.compatible_task_types ?? []));
        return subtypeCatalog
            .filter((subtype) => keysInUse.has(subtype.key) && visibleSubtypeKeys.has(subtype.key))
            .sort((left, right) => (left.group === right.group ? left.display_name.localeCompare(right.display_name) : left.group.localeCompare(right.group)));
    }, [data, subtypeCatalog, visibleSubtypeKeys]);

    const filteredData = useMemo(() => {
        return data
            .filter((item) => showAll || item.is_editor)
            .filter((item) => !taskTypeFilter || (item.compatible_task_types ?? []).includes(taskTypeFilter))
            .slice()
            .sort((left, right) => left.name.localeCompare(right.name));
    }, [data, showAll, taskTypeFilter]);

    return (
        <div className="w-full flex flex-col items-center mt-10 px-4">
            <div className="w-full max-w-6xl flex flex-col gap-4 mb-6 md:flex-row md:justify-between md:items-center">
                <div className="space-y-2">
                    <div>
                        <h1 className="text-2xl font-bold">Editable routes</h1>
                        <p className="text-sm text-base-content/70">Large route tiles with quick actions and overlay details.</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-4">
                        {document.configuration.is_superuser && (
                            <div className="flex items-center">
                                <input
                                    id="show-all-routes"
                                    type="checkbox"
                                    checked={showAll}
                                    onChange={(e) => setShowAll(e.target.checked)}
                                    className="checkbox checkbox-sm checkbox-primary"
                                />
                                <label htmlFor="show-all-routes" className="ml-2 text-sm font-medium text-base-content">
                                    Show all
                                </label>
                            </div>
                        )}
                        {taskTypeFilterOptions.length > 1 && (
                            <div className="flex items-center gap-2">
                                <label htmlFor="task-type-filter" className="text-sm font-medium text-base-content">
                                    Task type
                                </label>
                                <select
                                    id="task-type-filter"
                                    value={taskTypeFilter}
                                    onChange={(e) => setTaskTypeFilter(e.target.value)}
                                    className="select select-bordered select-sm"
                                >
                                    <option value="">All</option>
                                    {taskTypeFilterOptions.map((subtype) => (
                                        <option key={subtype.key} value={subtype.key}>
                                            {subtype.group === 'CIMA' ? 'CIMA: ' : ''}{subtype.display_name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                        )}
                    </div>
                </div>
                <div className="flex flex-wrap gap-2">
                    <Link to={`/${routes.ROUTE_EDITOR_CREATE}`} className="btn btn-primary btn-sm">
                        Create new route
                    </Link>
                    <a href={reverse("editableroute_import")} className="btn btn-secondary btn-sm">
                        Import route
                    </a>
                </div>
            </div>

            <div className="relative w-full max-w-6xl min-h-[260px]">
                {filteredData.length > 0 && (
                    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
                        {filteredData.map((route) => (
                            <EditableRouteTile key={route.id} route={route} subtypeLabels={subtypeLabels} visibleSubtypeKeys={visibleSubtypeKeys} />
                        ))}
                    </div>
                )}

                {!loading && filteredData.length === 0 && (
                    <div className="card bg-base-100 border border-base-300 shadow-xl">
                        <div className="card-body items-center text-center py-12">
                            <h2 className="card-title">No routes to show</h2>
                            <p className="text-base-content/70 max-w-md">
                                {taskTypeFilter
                                    ? "No routes match this task type filter."
                                    : showAll
                                        ? "No editable routes are available yet."
                                        : "You do not currently have any editable routes. Create or import one to get started."}
                            </p>
                        </div>
                    </div>
                )}

                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-base-100/60 z-50 rounded-box text-primary">
                        <Loading />
                    </div>
                )}
            </div>
        </div>
    );
};