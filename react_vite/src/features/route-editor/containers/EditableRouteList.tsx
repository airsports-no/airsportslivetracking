import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loading } from "../components/basicComponents";
import { Route } from "../../../types";
import { MoreVertical, Plus, Copy, Shield, Trash2 } from "lucide-react";
import { fetchEditableRoutes } from "../api";
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

const EditableRouteTile: React.FC<{ route: Route }> = ({ route }) => {
    const hasThumbnail = Boolean(route.thumbnail);
    const managePermissionsLabel = route.editors.length > 1 ? `${route.editors.length} editors` : route.is_editor ? "You can edit" : "Shared route";
    const titleClassName = "card-title text-base sm:text-lg leading-tight line-clamp-2 hover:underline break-words";
    const badgeClassName = "badge badge-outline";

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

    useEffect(() => {
        fetchEditableRoutes()
            .then((routes: Route[]) => {
                setData(routes);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const filteredData = useMemo(() => {
        return data
            .filter((item) => showAll || item.is_editor)
            .slice()
            .sort((left, right) => left.name.localeCompare(right.name));
    }, [data, showAll]);

    return (
        <div className="w-full flex flex-col items-center mt-10 px-4">
            <div className="w-full max-w-6xl flex flex-col gap-4 mb-6 md:flex-row md:justify-between md:items-center">
                <div className="space-y-2">
                    <div>
                        <h1 className="text-2xl font-bold">Editable routes</h1>
                        <p className="text-sm text-base-content/70">Large route tiles with quick actions and overlay details.</p>
                    </div>
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
                            <EditableRouteTile key={route.id} route={route} />
                        ))}
                    </div>
                )}

                {!loading && filteredData.length === 0 && (
                    <div className="card bg-base-100 border border-base-300 shadow-xl">
                        <div className="card-body items-center text-center py-12">
                            <h2 className="card-title">No routes to show</h2>
                            <p className="text-base-content/70 max-w-md">
                                {showAll ? "No editable routes are available yet." : "You do not currently have any editable routes. Create or import one to get started."}
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