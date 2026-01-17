import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ASTable } from "../components/filteredSearchableTable";
import { Loading } from "../components/basicComponents";
import { Route } from "../../../types";
import { ColumnDef } from "@tanstack/react-table";
import { fetchEditableRoutes } from "../api"; // New import
import { reverse } from "../../../urls";

export const EditableRouteList = () => {
    const [data, setData] = useState<Route[]>([]);
    const [loading, setLoading] = useState(true);
    const [showAll, setShowAll] = useState(false);

    useEffect(() => {
        fetchEditableRoutes()
            .then((data: Route[]) => {
                setData(data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const columns = useMemo((): ColumnDef<Route>[] => [
        {
            header: "",
            accessorKey: "thumbnail",
            cell: ({ getValue }) => {
                const value = getValue() as string;
                return value ? (
                    <img
                        className="zoom w-[50px] -my-5 -mr-5 max-w-none object-cover transition-transform duration-300 ease-in-out hover:scale-[3] hover:shadow-2xl hover:z-10"
                        src={value}
                        alt="Thumbnail"
                        loading="lazy"
                        decoding="async"
                    />
                ) : null;
            },
            enableSorting: false,
            enableColumnFilter: false,
        },
        {
            header: "Route",
            accessorKey: "name",
            id: "Route",
            enableSorting: false,
            cell: ({ row, getValue }) => (
                <div className="whitespace-normal break-words max-w-[16rem]">
                    <Link
                        to={`edit/${row.original.id}`}
                        className="link link-primary"
                    >
                        {getValue() as string}
                    </Link>
                </div>
            )
        },
        {
            header: "Wpts",
            accessorKey: "number_of_waypoints",
            enableColumnFilter: false,
        },
        {
            header: "Length",
            accessorKey: "route_length",
            enableColumnFilter: false,
            cell: ({ getValue }) => `${(getValue<number>() / 1852).toFixed(2)} NM`
        },
        {
            header: "Editors",
            accessorKey: "editors",
            cell: ({ getValue }) => (
                <div className="whitespace-normal max-w-[16rem]">
                    <ul className="list-disc list-inside text-xs">
                        {getValue<any[]>().map((editor) => (
                            <li key={editor.email}>
                                {editor.first_name} {editor.last_name}
                            </li>
                        ))}
                    </ul>
                </div>
            ),
            enableColumnFilter: false,
            enableSorting: false,
        },
        {
            header: "Actions",
            id: "actions",
            cell: ({ row }) => (
                <div className="grid grid-cols-2 gap-x-3 gap-y-1">
                    <a href={reverse("editableroute_createnavigationtask",row.original.id)} className="link link-primary text-xs">Create task</a>
                    <a href={reverse("editableroute_copy",row.original.id)} className="link link-primary text-xs">Copy</a>
                    <a href={reverse("editableroute_permissions_list",row.original.id)} className="link link-primary text-xs">Perms</a>
                    <a href={reverse("editableroute_delete",row.original.id)} className="link link-error text-xs">Del</a>
                </div>
            ),
            enableSorting: false,
            enableColumnFilter: false,
        }

    ], []);

    const filteredData = useMemo(() => {
        if (!data) return [];
        return data.filter((item) => showAll || item.is_editor);
    }, [data, showAll]);

    return (
        <div className="w-full flex flex-col items-center mt-10 px-4">
            <div className="w-full max-w-5xl flex justify-between items-center mb-4">
                <div>
                    {document.configuration.is_superuser && (
                        <div className="flex items-center">
                            <input
                                id="show-all-routes"
                                type="checkbox"
                                checked={showAll}
                                onChange={(e) => setShowAll(e.target.checked)}
                                className="checkbox checkbox-sm checkbox-primary"
                            />
                            <label htmlFor="show-all-routes" className="ml-2 text-sm font-medium text-gray-900">
                                Show all
                            </label>
                        </div>
                    )}
                </div>
                <div className="flex gap-2">
                    <a href={reverse('editableroute_create')} className="btn btn-primary btn-sm">
                        Create new route
                    </a>
                    <a href={reverse('editableroute_import')} className="btn btn-secondary btn-sm">
                        Import route
                    </a>
                </div>
            </div>
            <div className="relative w-full max-w-5xl shadow-xl rounded-box border border-base-300 bg-base-100 min-h-[200px]">
                <div className="overflow-x-auto rounded-box">
                    <ASTable
                        columns={columns}
                        data={filteredData}
                        className=""
                        initialState={{
                            sorting: [{ id: "Route", desc: false }]
                        }}
                    />
                </div>
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-base-100/50 z-50 text-primary">
                        <Loading />
                    </div>
                )}
            </div>
        </div>
    );
};