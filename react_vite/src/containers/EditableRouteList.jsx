import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {ASTable} from "../components/filteredSearchableTable";
import {Loading} from "../components/basicComponents";

export const EditableRouteList = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [showAll, setShowAll] = useState(false);

    useEffect(() => {
        fetch(document.configuration.EDITABLE_ROUTES_URL)
            .then((res) => res.json())
            .then((data) => {
                setData(data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    }, []);

    const columns = useMemo(() => [
        {
            header: "Thumbnail",
            accessorKey: "thumbnail",
            cell: ({ getValue }) => {
                const value = getValue();
                return value ? (
                    <img
                        className="zoom w-[50px] -my-5 -mr-5 max-w-none object-cover"
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
                <Link
                    to={`/edit/${row.original.id}`}
                    className="text-blue-600 hover:text-blue-800 hover:underline"
                >
                    {getValue()}
                </Link>
            )
        },
        {
            header: "Waypoints",
            accessorKey: "number_of_waypoints",
            enableColumnFilter: false,
        },
        {
            header: "Total length",
            accessorKey: "route_length",
            enableColumnFilter: false,
            cell: ({ getValue }) => `${(getValue() / 1852).toFixed(2)} NM`
        },
        {
            header: "Editors",
            accessorKey: "editors",
            cell: ({ getValue }) => (
                <ul className="list-disc list-inside">
                    {getValue().map((editor) => (
                        <li key={editor.email}>
                            {editor.first_name} {editor.last_name}
                        </li>
                    ))}
                </ul>
            ),
            enableColumnFilter: false,
            enableSorting: false,
        },
        {
            header: "Actions",
            id: "actions",
            cell: ({ row }) => (
                <div className="flex items-center space-x-2 text-sm">
                    <a href={document.configuration.createTaskViewUrl(row.original.id)} className="text-blue-600 hover:underline">Create task</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.copyRouteViewUrl(row.original.id)} className="text-blue-600 hover:underline">Copy</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.permissionListViewUrl(row.original.id)} className="text-blue-600 hover:underline">Permissions</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.deleteRouteViewUrl(row.original.id)} className="text-red-600 hover:underline">Delete</a>
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
        <div className="p-4">
            <div className="flex justify-between items-center mb-4">
                <div>
                    {document.configuration.is_superuser && (
                        <div className="flex items-center">
                            <input
                                id="show-all-routes"
                                type="checkbox"
                                checked={showAll}
                                onChange={(e) => setShowAll(e.target.checked)}
                                className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus:ring-2"
                            />
                            <label htmlFor="show-all-routes" className="ml-2 text-sm font-medium text-gray-900">
                                Show all
                            </label>
                        </div>
                    )}
                </div>
                <a href={document.configuration.createRouteUrl} className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
                    Create new route
                </a>
            </div>
            <div className="relative overflow-hidden shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg min-h-[200px]">
                <div className="overflow-x-auto">
                    <ASTable
                        columns={columns}
                        data={filteredData}
                        className="min-w-full divide-y divide-gray-300 [&_tr:nth-of-type(odd)]:bg-white [&_tr:nth-of-type(even)]:bg-gray-50 [&_tr:hover]:bg-gray-100"
                        initialState={{
                            sorting: [{ id: "Route", desc: false }]
                        }}
                    />
                </div>
                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-white bg-opacity-50 z-50">
                        <Loading />
                    </div>
                )}
            </div>
        </div>
    );
};