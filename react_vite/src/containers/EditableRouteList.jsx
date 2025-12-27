import React, { useEffect, useMemo, useState } from "react";
import {ASTable} from "../components/filteredSearchableTable";
import {Loading} from "../components/basicComponents";

export const EditableRouteList = () => {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [showAll, setShowAll] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch(document.configuration.EDITABLE_ROUTES_URL);
                const result = await response.json();
                setData(result);
            } catch (error) {
                console.error("Error fetching routes:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    const columns = useMemo(() => [
        {
            Header: "Thumbnail",
            accessor: "thumbnail",
            Cell: ({ value }) => value ? (
                <img
                    className="zoom w-[50px] -my-5 -mr-5 max-w-none object-cover"
                    src={value}
                    alt="Thumbnail"
                />
            ) : null,
            disableSortBy: true,
            disableFilters: true,
        },
        {
            Header: "Route",
            accessor: "name",
            id: "Route",
            disableSortBy: true,
            Cell: ({ row, value }) => (
                <a
                    href={document.configuration.editRouteViewUrl(row.original.id)}
                    className="text-blue-600 hover:text-blue-800 hover:underline"
                >
                    {value}
                </a>
            )
        },
        {
            Header: "Waypoints",
            accessor: "number_of_waypoints",
            disableFilters: true,
        },
        {
            Header: "Total length",
            accessor: "route_length",
            disableFilters: true,
            Cell: ({ value }) => `${(value / 1852).toFixed(2)} NM`
        },
        {
            Header: "Editors",
            accessor: "editors",
            Cell: ({ value }) => (
                <ul className="list-disc list-inside">
                    {value.map((editor) => (
                        <li key={editor.email}>
                            {editor.first_name} {editor.last_name}
                        </li>
                    ))}
                </ul>
            ),
            disableFilters: true,
            disableSortBy: true,
        },
        {
            Header: "Actions",
            accessor: (row) => (
                <div className="flex items-center space-x-2 text-sm">
                    <a href={document.configuration.createTaskViewUrl(row.id)} className="text-blue-600 hover:underline">Create task</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.copyRouteViewUrl(row.id)} className="text-blue-600 hover:underline">Copy</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.permissionListViewUrl(row.id)} className="text-blue-600 hover:underline">Permissions</a>
                    <span className="text-gray-300">|</span>
                    <a href={document.configuration.deleteRouteViewUrl(row.id)} className="text-red-600 hover:underline">Delete</a>
                </div>
            ),
            id: "actions",
            disableSortBy: true,
            disableFilters: true,
        }

    ], []);

    const filteredData = useMemo(() => {
        if (!data) return [];
        return data.filter((item) => showAll || item.is_editor);
    }, [data, showAll]);

    if (loading) return <Loading />;

    return (
        <div className="p-4">
            {document.configuration.is_superuser && (
                <div className="flex items-center mb-4">
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
            <div className="overflow-x-auto shadow ring-1 ring-black ring-opacity-5 sm:rounded-lg">
                <ASTable
                    columns={columns}
                    data={filteredData}
                    className="min-w-full divide-y divide-gray-300 [&_tr:nth-of-type(odd)]:bg-white [&_tr:nth-of-type(even)]:bg-gray-50 [&_tr:hover]:bg-gray-100"
                    initialState={{
                        sortBy: [{ id: "Route", desc: false }]
                    }}
                />
            </div>
        </div>
    );
};