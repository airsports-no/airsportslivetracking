import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loading } from "../components/basicComponents";
import { Route } from "../../../types";
import { MoreVertical, Plus, Copy, Shield, Trash2, TriangleAlert } from "lucide-react";
import { fetchEditableRoutes, fetchTaskSubtypeCatalog, TaskCompatibilitySubtype } from "../api";
import { COARSE_FAMILY_BADGE_CLASS, COARSE_FAMILY_LABELS, COARSE_FAMILY_ORDER, isTaskSubtypeVisible } from "../taskTemplates";
import { buildRouteTags, routeMatchesTaskFilter, RouteTagGroup, TaskFilterMode, taskTypeKeysInUse, unmetRequirementsTooltip } from "../routeTags";
import { reverse, generatePath } from "../../../urls";
import routes from "../../../routes.json";
import NavigationTaskCreationFlow from "../../contest-management/components/NavigationTaskCreationFlow";

const formatRouteLength = (meters: number) => `${(meters / 1852).toFixed(2)} NM`;

const EditableRouteTile: React.FC<{
    route: Route;
    subtypeByKey: Record<string, TaskCompatibilitySubtype>;
    visibleSubtypeKeys: Set<string>;
    onCreateNavigationTask: (routeId: number) => void;
}> = ({ route, subtypeByKey, visibleSubtypeKeys, onCreateNavigationTask }) => {
    const hasThumbnail = Boolean(route.thumbnail);
    const managePermissionsLabel = route.editors.length > 1 ? `${route.editors.length} editors` : route.is_editor ? "You can edit" : "Shared route";
    const titleClassName = "card-title text-base sm:text-lg leading-tight line-clamp-2 hover:underline break-words";
    const badgeClassName = "badge badge-sm badge-outline";

    // Never show a CIMA type the viewer doesn't have access to, even if the route happens to support it. Collapsed to
    // coarse families (at most 6) so the card shows a handful of short chips; the specific task types are in each
    // chip's tooltip.
    const tags = buildRouteTags(route, subtypeByKey, visibleSubtypeKeys, COARSE_FAMILY_ORDER);
    const chipLabel = (group: RouteTagGroup) => COARSE_FAMILY_LABELS[group.family] ?? group.family;
    const renderChip = (group: RouteTagGroup, quiet: boolean) => {
        const unmet = group.unmetNames.length > 0;
        const tooltip = unmet
            ? [group.subtypeNames.join(', '), ...group.unmetNames.map(unmetRequirementsTooltip)].join('. ')
            : group.subtypeNames.join(', ');
        return (
            <div
                key={`${quiet ? "also" : "made"}-${group.family}`}
                className={quiet ? "badge badge-xs badge-outline badge-ghost" : `badge badge-sm gap-1 ${COARSE_FAMILY_BADGE_CLASS[group.family] ?? 'badge-ghost'}`}
                title={tooltip}
            >
                {unmet && <TriangleAlert size={12} aria-label="Not yet compatible" />}
                {chipLabel(group)}
            </div>
        );
    };
    const renderRow = (label: string, groups: RouteTagGroup[], quiet: boolean) =>
        groups.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5" data-testid={`tags-${label}`}>
                <span className={quiet ? "text-[10px] text-base-content/60" : "text-xs text-base-content/70"}>{label}</span>
                {groups.map((group) => renderChip(group, quiet))}
            </div>
        );

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
                                <button type="button" onClick={() => onCreateNavigationTask(route.id)} className="flex items-center gap-3 py-3 w-full text-left">
                                    <Plus size={16} className="text-primary" />
                                    <span className="font-medium">Create Navigation Task</span>
                                </button>
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

                    <div className="space-y-1">
                        {renderRow("Made for", tags.madeFor, false)}
                        {renderRow("Also suitable for", tags.alsoSuitable, true)}
                        {renderRow("Suitable for", tags.suitable, false)}
                    </div>

                    <div className="flex gap-2">
                        <Link to={`edit/${route.id}`} className="btn btn-primary btn-sm flex-1">
                            Edit route
                        </Link>
                        <button type="button" onClick={() => onCreateNavigationTask(route.id)} className="btn btn-secondary btn-sm">
                            Create task
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export const EditableRouteList = () => {
    const navigate = useNavigate();
    const [data, setData] = useState<Route[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAll, setShowAll] = useState(false);
    const [subtypeCatalog, setSubtypeCatalog] = useState<TaskCompatibilitySubtype[]>([]);
    const [taskTypeFilter, setTaskTypeFilter] = useState('');
    const [taskFilterMode, setTaskFilterMode] = useState<TaskFilterMode>('suitable');
    const [searchQuery, setSearchQuery] = useState('');
    const [searchParams, setSearchParams] = useSearchParams();
    // ?createTask=<routeId> (set by the route editor after saving) opens the task flow straight away
    const [creatingTaskForRouteId, setCreatingTaskForRouteId] = useState<number | null>(() => {
        const requested = parseInt(searchParams.get('createTask') ?? '', 10);
        return Number.isNaN(requested) ? null : requested;
    });
    useEffect(() => {
        if (searchParams.has('createTask')) {
            const next = new URLSearchParams(searchParams);
            next.delete('createTask');
            setSearchParams(next, { replace: true });
        }
    }, []);

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

    const subtypeByKey = useMemo(
        () => Object.fromEntries(subtypeCatalog.map((subtype) => [subtype.key, subtype])),
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
        const keysInUse = taskTypeKeysInUse(data, taskFilterMode);
        return subtypeCatalog
            .filter((subtype) => keysInUse.has(subtype.key) && visibleSubtypeKeys.has(subtype.key))
            .sort((left, right) => (left.group === right.group ? left.display_name.localeCompare(right.display_name) : left.group.localeCompare(right.group)));
    }, [data, subtypeCatalog, visibleSubtypeKeys, taskFilterMode]);

    // A type that the other mode offered may not be in use in this one.
    const activeTaskTypeFilter = taskTypeFilterOptions.some((subtype) => subtype.key === taskTypeFilter) ? taskTypeFilter : '';

    const trimmedSearchQuery = searchQuery.trim().toLowerCase();

    const filteredData = useMemo(() => {
        return data
            .filter((item) => showAll || item.is_editor)
            .filter((item) => routeMatchesTaskFilter(item, activeTaskTypeFilter, taskFilterMode))
            .filter((item) => !trimmedSearchQuery || item.name.toLowerCase().includes(trimmedSearchQuery))
            .slice()
            .sort((left, right) => left.name.localeCompare(right.name));
    }, [data, showAll, activeTaskTypeFilter, taskFilterMode, trimmedSearchQuery]);

    return (
        <div className="w-full flex flex-col items-center mt-10 px-4">
            {creatingTaskForRouteId !== null && (
                <div className="fixed inset-0 bg-black/50 z-[1000] flex justify-center items-start overflow-y-auto px-4 pb-4 pt-12">
                    <NavigationTaskCreationFlow
                        entry={{ kind: 'route', editableRouteId: creatingTaskForRouteId }}
                        onCancel={() => setCreatingTaskForRouteId(null)}
                        onCreated={(contestId, navigationTaskId) => {
                            setCreatingTaskForRouteId(null);
                            navigate(generatePath('NAVIGATION_TASK_DETAIL', { contestId, navigationTaskId }));
                        }}
                    />
                </div>
            )}
            <div className="w-full max-w-6xl flex flex-col gap-4 mb-6 md:flex-row md:justify-between md:items-center">
                <div className="space-y-2">
                    <div>
                        <h1 className="text-2xl font-bold">Editable routes</h1>
                        <p className="text-sm text-base-content/70">Large route tiles with quick actions and overlay details.</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-4">
                        <input
                            type="search"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Search by name..."
                            aria-label="Search routes by name"
                            className="input input-bordered input-sm w-56"
                        />
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
                                <select
                                    id="task-filter-mode"
                                    aria-label="Match routes by"
                                    value={taskFilterMode}
                                    onChange={(e) => setTaskFilterMode(e.target.value as TaskFilterMode)}
                                    className="select select-bordered select-sm"
                                >
                                    <option value="suitable">Suitable for</option>
                                    <option value="made_for">Made for</option>
                                </select>
                                <select
                                    id="task-type-filter"
                                    aria-label="Task type"
                                    value={activeTaskTypeFilter}
                                    onChange={(e) => setTaskTypeFilter(e.target.value)}
                                    className="select select-bordered select-sm"
                                >
                                    <option value="">All task types</option>
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
                            <EditableRouteTile
                                key={route.id}
                                route={route}
                                subtypeByKey={subtypeByKey}
                                visibleSubtypeKeys={visibleSubtypeKeys}
                                onCreateNavigationTask={setCreatingTaskForRouteId}
                            />
                        ))}
                    </div>
                )}

                {!loading && filteredData.length === 0 && (
                    <div className="card bg-base-100 border border-base-300 shadow-xl">
                        <div className="card-body items-center text-center py-12">
                            <h2 className="card-title">No routes to show</h2>
                            <p className="text-base-content/70 max-w-md">
                                {trimmedSearchQuery
                                    ? `No routes match "${searchQuery.trim()}".`
                                    : activeTaskTypeFilter
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