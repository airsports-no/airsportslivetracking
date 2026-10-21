import React, { useEffect, useState } from 'react';
import { Loading } from '../../route-editor/components/basicComponents';
import { useToast } from '../../competition-map/hooks/useToast';
import { fetchAdminMobileApps, MobileAppsResponse } from '../api';

const WINDOWS: { minutes: number; label: string }[] = [
    { minutes: 15, label: 'Last 15 min' },
    { minutes: 60, label: 'Last hour' },
    { minutes: 24 * 60, label: 'Last 24 h' },
    { minutes: 7 * 24 * 60, label: 'Last 7 days' },
];

const PLATFORM_LABEL = { android: 'Android', ios: 'iOS', msfs: 'MSFS client' } as const;

/** "12 s ago", "5 min ago" or "2 h ago". */
const ageLabel = (iso: string) => {
    const seconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
    if (seconds < 90) return `${seconds} s ago`;
    if (seconds < 90 * 60) return `${Math.round(seconds / 60)} min ago`;
    return `${Math.round(seconds / 3600)} h ago`;
};

const versionLabel = (version: string, build: string) => (version ? `${version} (${build || '?'})` : build ? `build ${build}` : 'unknown');

/**
 * The mobile apps that have recently talked to the server, per user, with the app version. An app counts as connected
 * when its signed-in user made a request in the chosen time window (the app asks the server at start-up and every few
 * seconds while tracking).
 */
export default function MobileAppsPanel() {
    const { showToast } = useToast();
    const [minutes, setMinutes] = useState(15);
    const [data, setData] = useState<MobileAppsResponse | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        let cancelled = false;
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setLoading(true);
        fetchAdminMobileApps(minutes)
            .then((response) => {
                if (!cancelled) setData(response);
            })
            .catch((err: Error) => {
                if (!cancelled) showToast(err.message ?? 'Failed to load the mobile apps.', 'error');
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [minutes, showToast]);

    return (
        <div className="card bg-base-100 shadow">
            <div className="card-body gap-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 className="card-title">Mobile apps</h2>
                    <div role="tablist" className="tabs tabs-box">
                        {WINDOWS.map((option) => (
                            <a
                                key={option.minutes}
                                role="tab"
                                className={`tab ${minutes === option.minutes ? 'tab-active' : ''}`}
                                onClick={() => setMinutes(option.minutes)}
                            >
                                {option.label}
                            </a>
                        ))}
                    </div>
                </div>

                {loading && <Loading />}

                {!loading && data && (
                    <>
                        <div className="text-sm opacity-75">
                            {data.total} {data.total === 1 ? 'user' : 'users'} with the app in the chosen period. A user counts when
                            their app made a request: at start-up, and every few seconds while tracking. The position is the last one
                            the tracking stream delivered, if any (for the MSFS client: the simulator aircraft).
                        </div>

                        <div>
                            <h3 className="font-semibold mb-2">Versions</h3>
                            {data.by_version.length === 0 ? (
                                <div className="opacity-60 text-sm">No apps seen in this period.</div>
                            ) : (
                                <div className="overflow-x-auto">
                                    <table className="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>Platform</th>
                                                <th>Version</th>
                                                <th className="text-right">Users</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.by_version.map((row) => (
                                                <tr key={`${row.platform}-${row.app_version}-${row.app_build}`}>
                                                    <td>{PLATFORM_LABEL[row.platform] ?? row.platform}</td>
                                                    <td>{versionLabel(row.app_version, row.app_build)}</td>
                                                    <td className="text-right">{row.users}</td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>

                        {data.users.length > 0 && (
                            <div>
                                <h3 className="font-semibold mb-2">Users</h3>
                                <div className="overflow-x-auto">
                                    <table className="table table-sm">
                                        <thead>
                                            <tr>
                                                <th>User</th>
                                                <th>Platform</th>
                                                <th>Version</th>
                                                <th>Last seen</th>
                                                <th>Position</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {data.users.map((row) => (
                                                <tr key={`${row.email}-${row.platform}`}>
                                                    <td>
                                                        <div className="font-medium">{row.name || row.email}</div>
                                                        {row.name && <div className="text-xs opacity-60">{row.email}</div>}
                                                    </td>
                                                    <td>{PLATFORM_LABEL[row.platform] ?? row.platform}</td>
                                                    <td>{versionLabel(row.app_version, row.app_build)}</td>
                                                    <td>{new Date(row.last_seen).toLocaleString()}</td>
                                                    <td>
                                                        {row.position ? (
                                                            <a
                                                                className="link link-primary"
                                                                href={`https://www.openstreetmap.org/?mlat=${row.position.latitude}&mlon=${row.position.longitude}#map=12/${row.position.latitude}/${row.position.longitude}`}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                            >
                                                                {row.position.latitude.toFixed(4)}, {row.position.longitude.toFixed(4)}
                                                                <span className="opacity-60"> ({ageLabel(row.position.time)})</span>
                                                            </a>
                                                        ) : (
                                                            <span className="opacity-50">not tracking</span>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}
