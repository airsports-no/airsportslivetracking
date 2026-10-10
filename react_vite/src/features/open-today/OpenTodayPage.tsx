import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Navigation, UserPlus } from 'lucide-react';
import { reverse } from '../../urls';
import { Loading } from '../route-editor/components/basicComponents';
import {
    browserTimeZone,
    ContestGroup,
    directionsUrl,
    formatWindow,
    groupByContest,
    hasLocation,
    mapUrl,
    OpenRegistrationTask,
    registerPath,
} from './openToday';

/**
 * Tasks happening today that a pilot can register a flight for, grouped by contest with the venue's location, so the
 * pilot can find the place to register before flying. Used by the standalone page and the mission dashboard tab.
 */
export const OpenTodayList = () => {
    const [groups, setGroups] = useState<ContestGroup[] | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const load = async () => {
            try {
                const url = new URL(reverse('contests-open-registration-today'), window.location.origin);
                const zone = browserTimeZone();
                if (zone) url.searchParams.set('timezone', zone);
                const response = await fetch(url.toString());
                if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
                const tasks: OpenRegistrationTask[] = await response.json();
                setGroups(groupByContest(tasks));
            } catch (e: any) {
                setError(e?.message ?? 'Could not load the list');
            }
        };
        load();
    }, []);

    if (error) {
        return <div role="alert" className="alert alert-error">Could not load today's registrations: {error}</div>;
    }
    if (!groups) {
        return <div className="w-full flex items-center justify-center p-8"><Loading /></div>;
    }

    return (
        <>
            {groups.length === 0 && (
                <div className="card bg-base-200 border border-base-300">
                    <div className="card-body">
                        <p>No tasks are open for registration today.</p>
                        <div className="card-actions">
                            <Link to="/" className="btn btn-primary btn-sm">Browse contests</Link>
                        </div>
                    </div>
                </div>
            )}

            <div className="flex flex-col gap-4">
                {groups.map((group) => (
                    <div key={group.contestId} className="card bg-base-100 border border-base-300 shadow-sm">
                        <div className="card-body p-4 gap-3">
                            <div>
                                <h2 className="card-title">{group.contestName}</h2>
                                {group.country && <div className="text-sm opacity-70">{group.country}</div>}
                            </div>

                            {hasLocation(group) ? (
                                <div className="flex flex-wrap gap-2">
                                    <a className="btn btn-outline btn-sm gap-1" href={directionsUrl(group.latitude!, group.longitude!)} target="_blank" rel="noopener noreferrer">
                                        <Navigation size={16} /> Directions
                                    </a>
                                    <a className="btn btn-ghost btn-sm gap-1" href={mapUrl(group.latitude!, group.longitude!)} target="_blank" rel="noopener noreferrer">
                                        <MapPin size={16} /> Show on map
                                    </a>
                                </div>
                            ) : (
                                <div className="text-sm opacity-70">The organizer has not published a location.</div>
                            )}

                            <div className="flex flex-col divide-y divide-base-300">
                                {group.tasks.map((task) => (
                                    <div key={task.navigation_task_id} className="py-3 flex flex-wrap items-center justify-between gap-2">
                                        <div>
                                            <div className="font-semibold">{task.navigation_task_name}</div>
                                            <div className="text-sm opacity-70">
                                                {formatWindow(task, group.timeZone)} <span className="opacity-70">(local time at the venue)</span>
                                            </div>
                                            {task.is_open_now && <span className="badge badge-success badge-sm mt-1">Open now</span>}
                                        </div>
                                        <Link className="btn btn-primary btn-sm gap-1" to={registerPath(task.contest_id, task.navigation_task_id)}>
                                            <UserPlus size={16} /> Register a flight
                                        </Link>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </>
    );
};

/**
 * Standalone page. Also opened inside the mobile app (embedded, without the site's navigation bar).
 */
const OpenTodayPage = () => (
    <div className="container mx-auto p-4 max-w-3xl">
        <h1 className="text-3xl font-bold mb-1">Open for registration today</h1>
        <p className="mb-4 opacity-70">
            Tasks you can register a flight for yourself. Find the venue, then register before you fly.
        </p>
        <OpenTodayList />
    </div>
);

export default OpenTodayPage;
